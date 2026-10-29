"""Q14: the title holder and the registered owner of a lot on a past date, usually a violation date (design note 0022, T5 and T6).
Read-only, parameterized.

Records are today's version of the past. Title is dated by the recorded date (the document date is shown); the date used for a violation
is its inspection date unless the notice-issue date is asked for. HPD gives no registration start date, so a registration is taken to be
in force from its last registration date to the end of its period, and only the latest period of each registration is in the data."""
from datetime import date

from langchain.tools import tool

from agent.db import read_session
from agent.tools.records import OWNERS, PARTIES, PROV, _clean, _plain, snapshot
from etl.names import n1
from etl.vocab import deed_family_types

CAVEATS_Q14 = [
    "These are today's records of the past. A deed shows who the document names as grantee, dated by when it was recorded; it is not a finding of who was responsible for the building on that date, and a title holder is not shown to be the party "
    "responsible for a violation.",
    "HPD's data holds each registration's last registration date and the end of its period, with no start date and no earlier periods. A registration is taken to cover the dates from its last registration date to its period end. "
    "A date before the registrations in the data, or after their periods, has no registrant here, which does not mean there was none.",
    "The violations in the data are about a fifth of all HPD violations and closed history is partial, so a violation not in the data cannot be asked about.",
    "A past title holder missing from the DOS active-entity record is reported as no record in that snapshot, which says nothing about whether the entity existed on the date.",
    "Names are compared only by exact normalized name (rule N1). Agreement is a lead, and a difference is not shown to mean two different parties.",
]
DEED_ROWS = f"""
MATCH (l:Lot {{bbl: $bbl}})<-[:ON_LOT]-(d:Document) WHERE d.doc_type IN $deed_types AND d.doc_type <> 'deed_correction' AND d.recorded IS NOT NULL
RETURN d {{.document_id, .doc_type, .doc_type_raw, .doc_date, .doc_date_raw, .recorded, .amount, {PROV}}} AS d
ORDER BY d.recorded, d.doc_date, d.document_id
"""
VIOLATION = "MATCH (v:Violation {violation_id: $id})-[:ON_LOT]->(l:Lot) RETURN l.bbl AS bbl, v.inspection_date AS inspection, v.nov_issued_date AS nov, v.violation_class AS cls, v.status_group AS grp"
DOS = "MATCH (e:DosEntity {name_n1: $n}) RETURN count(e) AS c"


def _d(v):
    return v.to_native() if hasattr(v, "to_native") else v


def _title(runner, rows: list[dict], on: date) -> dict:
    """The deeds recorded on or before `on`, the latest recorded date being the title holder(s), and the deeds that cross the date."""
    upto = [r["d"] for r in rows if _d(r["d"]["recorded"]) <= on]
    later = [r["d"] for r in rows if _d(r["d"]["recorded"]) > on]
    crossing = [d for d in later if d.get("doc_date") is not None and _d(d["doc_date"]) <= on]
    out = {"deeds_recorded_on_or_before": len(upto), "deeds_recorded_after": len(later)}
    if crossing:
        out["deeds_dated_on_or_before_but_recorded_after"] = [_clean({k: d.get(k) for k in ("document_id", "doc_date", "recorded", "amount")}) for d in crossing]
    if not upto:
        return out | {"title_holders": [], "title_status": "no_deed_recorded_by_then"}
    last = upto[-1]["recorded"]
    holders = []
    for d in [x for x in upto if x["recorded"] == last]:
        grantees = [_clean(x["p"]) | {"role": x["role_type"]} for x in runner.run(PARTIES, id=d["document_id"]).data() if x["role_type"] == "grantee"]
        for g in grantees:
            g["dos_active_record"] = "found" if g.get("name_n1") and runner.run(DOS, n=g["name_n1"]).single()["c"] else "no record in the active-entity snapshot"
        holders.append(_clean({k: d.get(k) for k in ("document_id", "doc_type_raw", "doc_date", "recorded", "amount", "source", "snapshot_id")}) |
                       {"for_value": bool(d.get("amount")), "grantees": [{k: v for k, v in g.items() if k not in ("address_line2",)} for g in grantees]})
    return out | {"title_status": "supported_by_deed", "latest_recorded_before_the_date": _plain(last), "title_holders": holders}


def _registrants(runner, bbl: str, on: date) -> dict:
    owners = runner.run(OWNERS, bbl=bbl).data()
    if not owners:
        return {"registration_status": "no_registration_on_lot", "registered_owners": []}
    periods = {}
    for o in owners:
        r = o["reg"]
        periods[r["registration_id"]] = {"registration_id": r["registration_id"], "last_registration_date": _plain(r.get("last_registration_date")), "registration_end_date": _plain(r.get("registration_end_date"))}
    inforce = [o for o in owners if o["reg"].get("last_registration_date") is not None and o["reg"].get("registration_end_date") is not None
               and _d(o["reg"]["last_registration_date"]) <= on <= _d(o["reg"]["registration_end_date"])]
    out = {"registration_periods_in_data": sorted(periods.values(), key=lambda p: p["registration_id"])}
    if not inforce:
        first = min((_d(o["reg"]["last_registration_date"]) for o in owners if o["reg"].get("last_registration_date")), default=None)
        last = max((_d(o["reg"]["registration_end_date"]) for o in owners if o["reg"].get("registration_end_date")), default=None)
        why = ("the date is before the earliest registration in the data" if first and on < first else "the date is after the latest registration period in the data ended" if last and on > last
               else "the date falls between the registration periods in the data")
        return out | {"registration_status": "none_in_force_in_data", "reason": why, "registered_owners": []}
    return out | {"registration_status": "in_force", "registered_owners": [
        {"name": o["p"].get("organization_name") or o["p"].get("person_name"), "name_n1": o["p"].get("name_n1"), "registration_id": o["reg"]["registration_id"],
         "contact_id": o["role"]["source_record_id"], "contact_type": o["role"]["source_role_code"], "source": o["role"]["source"], "snapshot_id": o["role"]["snapshot_id"]} for o in inforce]}


def title_and_registrant(runner, bbl: str | None = None, on: str | None = None, violation_id: str | None = None, date_kind: str = "inspection") -> dict:
    """Title holder(s) from deeds and registered owner(s) from HPD registrations on a date, whether they coincide, and each gap or conflict.
    Give a BBL and an ISO date, or a violation id (its lot and its inspection or notice date are used)."""
    base = {**snapshot(runner), "caveats": CAVEATS_Q14}
    violation = None
    if violation_id:
        v = runner.run(VIOLATION, id=str(violation_id)).single()
        if v is None:
            return {**base, "status": "violation_not_found", "note": "No such violation in the data. The data holds about a fifth of all HPD violations."}
        if date_kind not in ("inspection", "notice"):
            return {**base, "status": "bad_date_kind", "note": "date_kind is inspection or notice."}
        chosen = _d(v["inspection"] if date_kind == "inspection" else v["nov"])
        if chosen is None:
            return {**base, "status": "violation_has_no_" + date_kind + "_date", "bbl": v["bbl"]}
        bbl, on = v["bbl"], chosen.isoformat()
        violation = {"violation_id": str(violation_id), "class": v["cls"], "status_group": v["grp"], "date_used": on, "date_kind": date_kind}
    try:
        when = date.fromisoformat(on or "")
    except ValueError:
        return {**base, "status": "bad_date", "note": "Give the date as YYYY-MM-DD."}
    if not bbl or runner.run("MATCH (l:Lot {bbl: $bbl}) RETURN l.bbl", bbl=bbl).single() is None:
        return {**base, "status": "lot_absent", "bbl": bbl, "note": "The graph holds no such lot."}
    title = _title(runner, runner.run(DEED_ROWS, bbl=bbl, deed_types=deed_family_types()).data(), when)
    reg = _registrants(runner, bbl, when)
    gaps = []
    if title["title_status"] == "no_deed_recorded_by_then":
        gaps.append("No deed-family document recorded on or before the date is in the graph for this lot, so no title holder is supported for it.")
    if title.get("deeds_dated_on_or_before_but_recorded_after"):
        gaps.append("A deed dated on or before the date was recorded after it: the title holder on the date is uncertain between the deed's date and its recording.")
    if reg["registration_status"] != "in_force":
        gaps.append("No registered owner is in force on the date in the registration data (" + reg.get("reason", "the lot has no registration in the data") + ").")
    if title["title_holders"] and any(h["for_value"] is False for h in title["title_holders"]):
        gaps.append("The latest deed before the date is for $0, which is not a sale: it names a grantee but does not show a sale.")
    comparisons = []
    for h in title["title_holders"]:
        for g in h["grantees"]:
            for o in reg["registered_owners"]:
                comparisons.append({"deed_grantee": g.get("party_name"), "registered_owner": o["name"], "registration_id": o["registration_id"],
                                    "name_agreement": "exact_normalized" if g.get("name_n1") and g["name_n1"] == o.get("name_n1") else "different"})
    if comparisons and not any(c["name_agreement"] == "exact_normalized" for c in comparisons):
        gaps.append("No title holder's normalized name equals a registered owner's name: the two records name different parties by name, which is not shown to mean they are unrelated.")
    coincide = ("not_comparable" if not comparisons else "exact_name_agreement" if any(c["name_agreement"] == "exact_normalized" for c in comparisons) else "names_differ")
    return {**base, "status": "found", "bbl": bbl, "date": when.isoformat(), "date_given_as": ("the " + violation["date_kind"] + " date of the violation" if violation else "a date supplied in the question"), "date_basis": "title by recorded date; registration by last registration date to period end",
            **({"violation": violation} if violation else {}), "title": title, "registration": reg, "do_they_coincide": coincide, "comparisons": comparisons, "gaps_and_conflicts": gaps}


@tool
def get_title_and_registrant_on_date(bbl: str = "", date: str = "", violation_id: str = "", date_kind: str = "inspection") -> dict:
    """Who the deeds name as title holder, and who HPD registration data names as registered owner, on a past date. Give either a tax lot
    (BBL, 10 digits) and a date (YYYY-MM-DD), or a violation_id (its lot and its inspection date are used; date_kind 'notice' uses the notice
    date). Title is dated by the recorded date. Returns the title holders and their deeds, the registered owners in force with their registration
    dates, whether the names agree, and each gap or conflict. These are today's records of the past, not a finding of who was responsible."""
    with read_session() as session:
        return title_and_registrant(session, bbl or None, date or None, violation_id or None, date_kind)
