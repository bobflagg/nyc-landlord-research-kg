"""Q26: what each absence means for one lot (design notes 0007, 0024). Read-only, parameterized.

For a lot, which sources hold no record (HPD registration, HPD owner contact, DOS entity, either BOR layer, violations, complaints, Housing Court
actions, deeds) and what each absence means in terms of the five reasons of note 0007. An absence says what a source or the method held or used. It is
never evidence that nothing exists or that the owners differ."""
from langchain.tools import tool

from agent.db import read_session
from agent.tools.layers import CAVEATS, LAYERS, active_run, lot_absence
from agent.tools.records import _clean, snapshot
from etl.names import n1
from etl.vocab import bor_meaning, deed_family_types

COUNTS = """
MATCH (l:Lot {bbl: $bbl})
RETURN l {.bbl, .address_text, .building_class, .units_residential} AS l,
       COUNT { (l)<-[:ON_LOT]-(:Registration) } AS registrations,
       COUNT { (l)<-[:ON_LOT]-(:Violation) } AS violations,
       COUNT { (l)<-[:ON_LOT]-(:ComplaintSummary) } AS complaints,
       COUNT { (l)<-[:ON_LOT]-(:Litigation) } AS litigation,
       COUNT { (l)<-[:ON_LOT]-(d:Document) WHERE d.doc_type IN $deed_types } AS deeds
"""
OWNERS = """
MATCH (l:Lot {bbl: $bbl})<-[:ON_LOT]-(reg:Registration)<-[:IN_REGISTRATION]-(o:HpdRole)-[:HELD_BY]->(p:HpdParty)
WHERE o.role_type = 'registered_owner'
RETURN DISTINCT p.organization_name AS org, p.person_name AS person
"""
ANY_CONTACT = "MATCH (:Lot {bbl: $bbl})<-[:ON_LOT]-(:Registration)<-[:IN_REGISTRATION]-(o:HpdRole) RETURN count(o) AS n"
DOS = "MATCH (e:DosEntity {name_n1: $n}) RETURN count(e) AS n"


def _absent(reason: str, top: str, **extra) -> dict:
    return {"status": "absent", "reason": bor_meaning("absence-reason", reason), "top_level_reason": bor_meaning("absence-reason", top), **extra}


def explain_absences(runner, bbl: str, run_id: str | None = None) -> dict:
    """One entry per source: present with a count, or absent with a reason and what it does not mean."""
    base = {"bbl": bbl, **snapshot(runner), "caveats": CAVEATS[-1:] + [
        "An absence is described by one of five reasons: outside source coverage (the source holds no record), outside method input (the source holds it but the method did not use it), "
        "excluded by policy, below an eligibility rule, or no qualifying linkage. None of them is evidence that no relationship exists or that the owners differ."]}
    r = runner.run(COUNTS, bbl=bbl, deed_types=deed_family_types()).single()
    if r is None:
        return {**base, "status": "lot_absent", "note": "The graph holds no such lot, so no source can be said to hold or lack a record for it."}
    out = {**base, "status": "found", "lot": _clean(r["l"]) | {"units_source": "PLUTO residential units (lot-level)"}}
    sources = []
    if r["registrations"]:
        sources.append({"source": "HPD registration", "status": "present", "count": r["registrations"]})
    else:
        sources.append({"source": "HPD registration", **_absent("no_registration", "outside_source_coverage", meaning_here="No HPD registration on this lot in the snapshot. "
                        "Whether the building had to register is not decided here: buildings with fewer than three units and others need not register.")})
    contacts = runner.run(ANY_CONTACT, bbl=bbl).single()["n"]
    if r["registrations"] and not contacts:
        sources.append({"source": "HPD registration contacts", **_absent("no_owner_contact", "outside_method_input", meaning_here="The lot is registered but the registration has no contact row in the snapshot.")})
    elif contacts:
        sources.append({"source": "HPD registration contacts", "status": "present", "count": contacts})
    owners = runner.run(OWNERS, bbl=bbl).data()
    orgs = sorted({o["org"] for o in owners if o["org"]})
    for name in orgs:
        key = n1(name)
        n = runner.run(DOS, n=key).single()["n"] if key else 0
        entry = {"source": "NY Department of State entity", "searched_name": name, "normalized_name": key}
        if n:
            sources.append(entry | {"status": "present", "count": n})
        else:
            sources.append(entry | _absent("outside_source_coverage", "outside_source_coverage",
                                           meaning_here="No active DOS entity has this normalized name (rule N1). DOS holds active entities only, so a dissolved entity, a foreign entity or a different spelling is not found; "
                                                        "a different spelling is a different name. It is not 'the entity does not exist'."))
    if r["registrations"] and not orgs:
        sources.append({"source": "NY Department of State entity", "status": "not_searched", "note": "No registered owner on this lot is an organization, so there is no entity name to look up."})
    run = active_run(runner, run_id)
    if run is None:
        sources.append({"source": "Owner Portfolio and Operational Network", "status": "no_run_loaded"})
    else:
        out["bor_run"] = run
        for layer in LAYERS:
            m = runner.run("MATCH (:Lot {bbl: $bbl})-[:MEMBER_OF]->(g:BorGroup {run_id: $run, layer: $layer}) RETURN g.group_id AS id, g.lot_count AS lots", bbl=bbl, run=run["run_id"], layer=layer).single()
            if m:
                sources.append({"source": LAYERS[layer], "status": "present", "group_id": m["id"], "lots": m["lots"]})
            else:
                for a in lot_absence(runner, bbl, run["run_id"], layer) or [{"reason": None}]:
                    sources.append({"source": LAYERS[layer], "status": "absent", **{k: v for k, v in a.items() if k != "layer"},
                                    **({"note": "BOR wrote no row for this lot, and a missing row means nothing."} if a["reason"] is None else {})})
    for key, label, note in (("violations", "HPD violations", "The violations table holds about a fifth of all HPD violations (open ones are present, closed history is partial), so no row is not 'never cited'."),
                             ("complaints", "HPD complaint summaries", "A complaint is a report, not a finding; no summary row means none was received in the loaded years."),
                             ("litigation", "HPD Housing Court actions", "No case here means none in the loaded HPD litigation table; it does not cover cases HPD did not bring."),
                             ("deeds", "ACRIS deed documents", "Only the deed family recorded on this lot is loaded; no deed here does not mean the lot was never conveyed (a condo or older conveyance may be recorded elsewhere).")):
        if r[key]:
            sources.append({"source": label, "status": "present", "count": r[key]})
        else:
            sources.append({"source": label, **_absent("outside_source_coverage", "outside_source_coverage", meaning_here=note)})
    out["sources"] = sources
    out["absences"] = sum(1 for s in sources if s["status"] == "absent")
    return out


@tool
def explain_what_is_missing(bbl: str) -> dict:
    """For a tax lot (BBL, a 10-digit string), list which sources hold no record and what each absence means: HPD registration and contacts, NY DOS entity for
    each registered organization owner, the BOR Owner Portfolio and Operational Network (with BOR's reason code and top-level reason, and the masked address
    where one applies), HPD violations, complaint summaries, Housing Court actions and ACRIS deeds. Each absence is described by one of five reasons (outside
    source coverage, outside method input, excluded by policy, below an eligibility rule, no qualifying linkage). An absence is not evidence that nothing exists
    or that the owners differ."""
    with read_session() as session:
        return explain_absences(session, bbl)
