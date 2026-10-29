"""Q7 and Q22: evidence shared between two entities, and whether two names are one entity (design note 0026, P2 and P3). Read-only, parameterized.

An entity here is a name: the records that carry its normalized name (HPD parties, ACRIS parties, DOS entities). Every item of evidence is a lead with its source,
and is marked used or set aside with the reason (a mail-drop or hub address, a common person name, a commercial agent). Items are never added into a score, and
no stored link is made. A name match is not a finding that two records are one party."""
from langchain.tools import tool

from agent.db import read_session
from agent.tools.linkrules import COMMERCIAL_AGENT_LOTS, COMMON_NAME, HUB_DEGREE, address_status, dos_process_key, mail_drop, name_relation
from agent.tools.records import PROV, _clean, _plain, snapshot
from etl.names import n1, n2

PRINCIPAL = ["registered_owner", "head_officer", "officer", "shareholder", "lessee"]
CAVEATS = [
    "Each item is a lead with its source, not a finding. A name match is exact after normalization (rule N1; rule N2 also ignores spaces) and nothing fuzzy is tried. "
    "Items are not added into a score, and none of them says that two parties are one owner or are under common control.",
    "An item set aside is shown with its reason: an address on the project's mail-drop list (unreviewed) or shared by many parties, a person name shared by many parties, or a commercial managing agent links nothing on its own.",
    "People appear only in the HPD or ACRIS role the record gives them, with a business address as filed. DOS carries no officers for LLCs, so their absence is not evidence.",
]
HPD_BY_ORG = """
MATCH (p:HpdParty {name_n1: $n})
OPTIONAL MATCH (p)<-[:HELD_BY]-(o:HpdRole)
RETURN p {.party_id, .organization_name, .person_name, .business_address_key} AS p, collect(DISTINCT o.role_type) AS roles
"""
HPD_BY_PERSON = HPD_BY_ORG.replace("{name_n1: $n}", "{person_name_n1: $n}")
OTHERS = """
MATCH (p:HpdParty {%s: $n})<-[:HELD_BY]-(own:HpdRole)-[:IN_REGISTRATION]->(reg:Registration)
OPTIONAL MATCH (reg)-[:ON_LOT]->(l:Lot)
WITH reg, collect(DISTINCT l.bbl) AS lots
MATCH (reg)<-[:IN_REGISTRATION]-(o:HpdRole)-[:HELD_BY]->(q:HpdParty)
RETURN reg.registration_id AS reg, lots, o.role_type AS role, q {.party_id, .organization_name, .person_name, .name_n1, .person_name_n1, .business_address_key} AS q
LIMIT 3000
"""
DOS = "MATCH (e:DosEntity {name_n1: $n}) RETURN e {.dos_id, .entity_name, .entity_type, .initial_filing_date, .process_name, .process_address_line1, .process_zip, .registered_agent_name, .snapshot_id} AS e"
JOINT_DOCS = f"""
MATCH (p1:AcrisParty {{name_n1: $a}})<-[:HELD_BY]-(r1:AcrisRole)-[:IN_DOCUMENT]->(d:Document)<-[:IN_DOCUMENT]-(r2:AcrisRole)-[:HELD_BY]->(p2:AcrisParty {{name_n1: $b}})
RETURN d {{.document_id, .doc_type, .recorded, .amount, {PROV}}} AS d, collect(DISTINCT r1.role_type) AS roles_a, collect(DISTINCT r2.role_type) AS roles_b
ORDER BY d.recorded, d.document_id LIMIT 25
"""
DOS_DEGREE = "MATCH (e:DosEntity {process_address_line1: $l}) WHERE e.process_zip = $z RETURN count(e) AS c"
NAME_COUNT = "MATCH (p:HpdParty {person_name_n1: $n}) RETURN count(p) AS c"
AGENT_LOTS = "MATCH (p:HpdParty {%s: $n})<-[:HELD_BY]-(:HpdRole {role_type: 'managing_agent'})-[:IN_REGISTRATION]->(:Registration)-[:ON_LOT]->(l:Lot) RETURN count(DISTINCT l) AS lots"
GROUPS = """
UNWIND $lots AS b MATCH (:Lot {bbl: b})-[:MEMBER_OF]->(g:BorGroup)
RETURN g.group_id AS group_id, g.layer AS layer, g.lot_count AS lot_count, collect(DISTINCT b) AS lots
"""


def profile(runner, name: str) -> dict:
    """What the graph holds under a name: HPD parties (org or person), the people and agents on their registrations, DOS entities, lots."""
    key = n1(name)
    parties = [{**dict(r["p"]), "roles": r["roles"]} for r in runner.run(HPD_BY_ORG, n=key).data()] + \
              [{**dict(r["p"]), "roles": r["roles"]} for r in runner.run(HPD_BY_PERSON, n=key).data()]
    others, lots = [], set()
    for field in ("name_n1", "person_name_n1"):
        for r in runner.run(OTHERS % field, n=key).data():
            others.append(r)
            lots |= set(r["lots"])
    acris = runner.run("MATCH (p:AcrisParty {name_n1: $n}) RETURN count(p) AS c", n=key).single()["c"]
    return {"name": name, "n1": key, "n2": n2(name), "acris_parties": acris, "hpd_parties": parties, "others": others, "lots": sorted(lots),
            "dos": [dict(r["e"]) for r in runner.run(DOS, n=key).data()]}


def _item(kind: str, used: bool, why: str, source: str, reliability: str, **detail) -> dict:
    return {"type": kind, "status": "used" if used else "set_aside", "reason": why, **_clean(detail), "source": source, "reliability": reliability}


def pair_evidence(runner, pa: dict, pb: dict) -> tuple[list[dict], list[str]]:
    """Evidence items between two profiles, and the kinds searched that found nothing."""
    items, searched = [], []
    # 1. the same HPD business address among the parties of either name
    addrs: dict[str, dict] = {}
    for tag, pr in (("a", pa), ("b", pb)):
        for p in pr["hpd_parties"]:
            if p.get("business_address_key"):
                addrs.setdefault(p["business_address_key"], {"a": set(), "b": set()})[tag].add(p.get("organization_name") or p.get("person_name"))
    searched.append("shared HPD business address")
    for k, v in addrs.items():
        if v["a"] and v["b"]:
            st = address_status(runner, k)
            items.append(_item("shared_hpd_business_address", not st["set_aside"], st["reason"] or f"shared by {st['degree']['hpd_parties']} HPD parties in all", "hpd_contacts", "I",
                               address_key=k, parties_a=sorted(v["a"]), parties_b=sorted(v["b"]), degree=st["degree"]))
    # 2. the same person in a principal role on the registrations of either name, and 3. the same person spelled with different spacing
    searched += ["same person name in a principal role", "person name differing by spacing"]
    def people(pr):
        out = {}
        for r in pr["others"]:
            q = r["q"]
            if r["role"] in PRINCIPAL and q.get("person_name_n1"):
                out.setdefault(q["person_name_n1"], {"name": q["person_name"], "roles": set(), "regs": set()})
                out[q["person_name_n1"]]["roles"].add(r["role"]); out[q["person_name_n1"]]["regs"].add(r["reg"])
        return out
    ppa, ppb = people(pa), people(pb)
    for k in sorted(set(ppa) & set(ppb)):
        c = runner.run(NAME_COUNT, n=k).single()["c"]
        items.append(_item("same_person_name_in_a_principal_role", c < COMMON_NAME, None if c < COMMON_NAME else f"the name is carried by {c} HPD parties (at least {COMMON_NAME}), so it does not tie them",
                           "hpd_contacts", "I", person_name=ppa[k]["name"], roles_a=sorted(ppa[k]["roles"]), roles_b=sorted(ppb[k]["roles"]), hpd_parties_with_this_name=c))
    by2a, by2b = {n2(k): k for k in ppa}, {n2(k): k for k in ppb}
    for k2 in sorted(set(by2a) & set(by2b)):
        ka, kb = by2a[k2], by2b[k2]
        if ka != kb:
            items.append(_item("person_name_differing_by_spacing", True, None, "hpd_contacts", "I", name_a=ppa[ka]["name"], name_b=ppb[kb]["name"],
                               roles_a=sorted(ppa[ka]["roles"]), roles_b=sorted(ppb[kb]["roles"]), rule="N2: equal once spaces are removed; a lead, not the same person"))
    # 4. the same managing agent
    searched.append("shared managing agent")
    def agents(pr):
        return {(r["q"].get("name_n1") or r["q"].get("person_name_n1")): r["q"] for r in pr["others"] if r["role"] == "managing_agent"}
    aa, ab = agents(pa), agents(pb)
    for k in sorted(set(aa) & set(ab)):
        q = aa[k]
        lots = runner.run(AGENT_LOTS % ("name_n1" if q.get("name_n1") else "person_name_n1"), n=k).single()["lots"]
        md = mail_drop(runner, q.get("business_address_key"))
        commercial = lots >= COMMERCIAL_AGENT_LOTS or md is not None
        items.append(_item("shared_managing_agent", not commercial, f"a commercial agent: registered on {lots} lots" + (" and at a mail-drop-list address" if md else "") if commercial else None,
                           "hpd_contacts", "I", agent=q.get("organization_name") or q.get("person_name"), lots_registered=lots, relationship="management, not ownership"))
    # 5. a document that names both
    searched.append("an ACRIS document naming both")
    if pa["n1"] != pb["n1"]:
        for r in runner.run(JOINT_DOCS, a=pa["n1"], b=pb["n1"]).data():
            items.append(_item("shared_acris_document", True, None, "acris_master, acris_parties", "I", document=_clean(r["d"]), role_of_a=r["roles_a"], role_of_b=r["roles_b"],
                               note="joint borrowers, or grantor and grantee, are records on one document, not common control"))
    # 6. DOS process address and registered agent
    searched.append("same DOS process address or registered agent")
    for ea in pa["dos"]:
        for eb in pb["dos"]:
            if ea["dos_id"] == eb["dos_id"]:
                continue
            ka, kb = dos_process_key(ea), dos_process_key(eb)
            if ka and ka == kb:
                md = mail_drop(runner, ka)
                shared = runner.run(DOS_DEGREE, l=ea["process_address_line1"], z=ea["process_zip"]).single()["c"]
                why = f"on the project's mail-drop list ({md['kind']})" if md else (f"the process address of {shared} DOS entities (at least {HUB_DEGREE})" if shared >= HUB_DEGREE else None)
                items.append(_item("same_dos_process_address", why is None, why, "nys_corporations", "I",
                                   dos_entities_at_this_address=shared, address_key=ka, dos_id_a=ea["dos_id"], dos_id_b=eb["dos_id"], filed_a=ea.get("initial_filing_date"), filed_b=eb.get("initial_filing_date"),
                                   note="the state forwards papers to this address; many unrelated entities can share one"))
            if ea.get("registered_agent_name") and ea.get("registered_agent_name") == eb.get("registered_agent_name"):
                items.append(_item("same_dos_registered_agent", False, "a registered agent is a service for many entities", "nys_corporations", "I", agent=ea["registered_agent_name"]))
    # 7. a lot where either name holds a registration
    searched.append("a lot where both are registered")
    both = sorted(set(pa["lots"]) & set(pb["lots"]))
    if both and pa["n1"] != pb["n1"]:
        items.append(_item("registered_on_the_same_lot", True, None, "hpd_registrations", "I", lots=both[:20], lot_count=len(both),
                           note="two registrations (or two roles) on one lot; the records do not say the parties are related"))
    # 8. the same Owner Portfolio or Operational Network
    searched.append("the same BOR group")
    ga = {(g["layer"], g["group_id"]) for g in runner.run(GROUPS, lots=pa["lots"][:300]).data()} if pa["lots"] else set()
    gb = {(g["layer"], g["group_id"]) for g in runner.run(GROUPS, lots=pb["lots"][:300]).data()} if pb["lots"] else set()
    for layer, gid in sorted(ga & gb):
        items.append(_item("same_bor_group", True, None, "bor", "II", layer=layer, group_id=gid, note="a derived lead from BOR's method (note 0024), not legal ownership"))
    found = {i["type"] for i in items}
    names = {"shared HPD business address": "shared_hpd_business_address", "same person name in a principal role": "same_person_name_in_a_principal_role",
             "person name differing by spacing": "person_name_differing_by_spacing", "shared managing agent": "shared_managing_agent", "an ACRIS document naming both": "shared_acris_document",
             "same DOS process address or registered agent": "same_dos_process_address", "a lot where both are registered": "registered_on_the_same_lot", "the same BOR group": "same_bor_group"}
    return items, [s for s in searched if names[s] not in found and not (s == "same DOS process address or registered agent" and "same_dos_registered_agent" in found)]


def _holdings(p: dict) -> dict:
    return {"hpd_parties": len(p["hpd_parties"]), "acris_parties": p["acris_parties"], "hpd_registered_lots": len(p["lots"]), "dos_entities": [{"dos_id": e["dos_id"], "entity_name": e["entity_name"], "filed": _plain(e.get("initial_filing_date"))} for e in p["dos"]]}


def shared_evidence(runner, a: str, b: str) -> dict:
    """Evidence between two names, or between the registered owners of two lots when both arguments are 10-digit BBLs."""
    base = {"a": a, "b": b, **snapshot(runner), "caveats": CAVEATS}
    def names_for(x: str) -> list[str]:
        if x.isdigit() and len(x) == 10:
            r = runner.run("MATCH (l:Lot {bbl: $b})<-[:ON_LOT]-(:Registration)<-[:IN_REGISTRATION]-(:HpdRole {role_type: 'registered_owner'})-[:HELD_BY]->(p:HpdParty) "
                           "RETURN DISTINCT coalesce(p.organization_name, p.person_name) AS n", b=x).data()
            return sorted({v["n"] for v in r})
        return [x]
    na, nb = names_for(a), names_for(b)
    if not na or not nb:
        return {**base, "status": "no_name", "note": "A lot given has no registered owner in the graph, so there is no name to compare; give the names directly."}
    items, searched, rel = [], None, []
    for x in na:
        for y in nb:
            pa, pb = profile(runner, x), profile(runner, y)
            it, nf = pair_evidence(runner, pa, pb)
            items += [{**i, "between": [x, y]} for i in it]
            searched = nf if searched is None else [s for s in searched if s in nf]
            rel.append(name_relation(x, y))
    return {**base, "status": "found", "names_compared": {"a": na, "b": nb}, "name_relations": rel, "evidence": items,
            "used": sum(1 for i in items if i["status"] == "used"), "set_aside": sum(1 for i in items if i["status"] == "set_aside"),
            "searched_and_not_found": searched or [], "how_to_read": "Used items are leads that may tie the two; set-aside items are shown with why they do not. Neither group is a finding of common control."}


def compare_entity_names(runner, name_a: str, name_b: str) -> dict:
    """Q22: are two names one entity? The relation under N1 and N2, the records under each name, and evidence for and against."""
    base = {"name_a": name_a, "name_b": name_b, **snapshot(runner), "caveats": CAVEATS + [
        "Rule N1 removes case and punctuation and collapses whitespace; rule N2 also removes spaces. A normalization or spacing match is a lead, derived by the rule stated, not a link. "
        "Names that differ by a numeral or a word are different names unless a record other than the name connects them."]}
    rel = name_relation(name_a, name_b)
    pa, pb = profile(runner, name_a), profile(runner, name_b)
    if rel["relation"] == "unusable":
        return {**base, "status": "unusable", "relation": rel}
    items, searched = pair_evidence(runner, pa, pb)
    used = [i for i in items if i["status"] == "used"]
    against = []
    if pa["dos"] and pb["dos"] and {e["dos_id"] for e in pa["dos"]}.isdisjoint({e["dos_id"] for e in pb["dos"]}):
        against.append({"type": "distinct_dos_records", "detail": f"each name has its own DOS entity (ids {[e['dos_id'] for e in pa['dos']]} and {[e['dos_id'] for e in pb['dos']]}), filed "
                                                                 f"{[e.get('initial_filing_date') for e in pa['dos']]} and {[e.get('initial_filing_date') for e in pb['dos']]}", "source": "nys_corporations"})
    if rel["relation"] in ("differs_by_one_token", "different"):
        against.append({"type": "names_differ", "detail": rel["reading"]})
    if rel["relation"] in ("normalization_match", "spacing_match"):
        verdict = f"{rel['relation']}: " + rel["reading"] + ". A lead. " + ("The records also connect them (see evidence_for)." if used else "No record other than the names connects them in the loaded sources.")
    elif used:
        verdict = "The names differ, and records other than the names connect them (see evidence_for). That is a lead for a relationship, not a finding that they are one entity."
    else:
        verdict = "The names differ and no record other than the names connects them in the loaded sources: nothing here supports treating them as one entity."
    return {**base, "status": "found", "relation": rel, "judgment": verdict, "holdings": {"a": _holdings(pa), "b": _holdings(pb)}, "evidence_for": used,
            "set_aside": [i for i in items if i["status"] == "set_aside"], "evidence_against": against, "searched_and_not_found": searched,
            "rule": "N1: uppercase, punctuation deleted, whitespace collapsed. N2: N1 with spaces removed. Nothing fuzzy.",
            "sources_searched": "HPD contacts, ACRIS parties (deed family on all lots, mortgage family on registered lots) and DOS active entities (DOS holds active entities only, so no DOS entity does not mean none ever existed)"}


@tool
def get_shared_evidence(a: str, b: str) -> dict:
    """List the evidence shared between two entities or two buildings: give two names exactly as the records spell them, or two tax lots (10-digit BBL strings;
    their registered owners are compared). Each item says what it is (a shared HPD business address, the same person in a principal role, a person name that
    differs by spacing, a shared managing agent, an ACRIS document naming both, the same DOS process address or registered agent, a lot where both are registered,
    the same BOR group), its source, and whether it is used or set aside (a mail-drop or hub address, a common person name, a commercial agent) with the reason.
    Every item is a lead; none is a finding of common ownership or control, and items are not scored."""
    with read_session() as session:
        return shared_evidence(session, a, b)


@tool
def compare_entities(name_a: str, name_b: str) -> dict:
    """Judge whether two names are the same entity, with the rule: a normalization match (rule N1: case, punctuation, whitespace), a spacing match (rule N2:
    spaces also ignored), names that differ by one token such as a numeral or a word, or different names. Gives the records under each name (HPD, DOS), the
    evidence for (records other than the names that connect them) and against (for example two distinct DOS entities), and what was searched and not found.
    A match is a lead, never a link, and names that differ by a numeral or word are not the same entity on the names alone."""
    with read_session() as session:
        return compare_entity_names(session, name_a, name_b)
