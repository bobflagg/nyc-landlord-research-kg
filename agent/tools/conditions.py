"""Q15, Q17, Q27 and Q28: conditions at a lot or building (design note 0020). Read-only, parameterized.

An HPD action is not an eviction and not a finding of liability. A respondent name is a name in a role the record gives
(respondent), never a statement of ownership; a respondent equals a registered owner only by exact normalized name (rule N1),
and that is a lead."""
from datetime import date

from langchain.tools import tool

from agent.db import read_session
from agent.tools.records import N1_RULE, PROV, _clean, _plain, snapshot

CAVEATS_Q28 = [
    "An HPD action is a case HPD brought in Housing Court. It is not an eviction and not a finding of liability; the case type, status and any harassment finding are as HPD records them.",
    "Respondents are the names HPD lists, split at commas, each shown in the role the record gives (respondent) with its source. A name that itself contains a comma "
    "can be split, so respondent_raw is given too. A respondent name does not say who owns or runs the building.",
    "A respondent is compared with the HPD registered owner only by exact normalized name (rule N1): a match is a lead, and a respondent that does not match is not shown to be someone else.",
]
CAVEATS_Q15 = [
    "A violation is what an HPD inspector cited, not a finding by a court. Open means HPD's own status is Open at the data's as-of date.",
    "Class I is reported apart from A, B and C and is not added to them. The dataset holds only part of all HPD violations (about a fifth citywide): open violations "
    "are present, closed history is partial, so a lot with no violation here is not shown to have had none.",
    "The rate divides open violations by PLUTO's residential units for the lot (lot-level, not per building). Violations are counted on the lot; the building "
    "breakdown covers those HPD tied to a building the graph holds.",
]
VIOLATION_COUNTS = """
MATCH (l:Lot {bbl: $bbl})<-[:ON_LOT]-(v:Violation)
RETURN v.violation_class AS cls, v.status_group AS grp, count(v) AS n, min(v.inspection_date) AS oldest, max(v.inspection_date) AS latest,
       sum(CASE WHEN v.inspection_date > date($snap) THEN 1 ELSE 0 END) AS after_snapshot,
       sum(CASE WHEN v.inspection_date IS NULL THEN 1 ELSE 0 END) AS undated
ORDER BY cls, grp
"""
VIOLATION_BUILDINGS = """
MATCH (l:Lot {bbl: $bbl})<-[:ON_LOT]-(v:Violation)
OPTIONAL MATCH (v)-[:ON_BUILDING]->(b:Building)
RETURN b.bin AS bin, v.status_group AS grp, count(v) AS n ORDER BY bin, grp
"""
OLDEST_OPEN = f"""
MATCH (l:Lot {{bbl: $bbl}})<-[:ON_LOT]-(v:Violation {{status_group: 'open'}}) WHERE v.inspection_date IS NOT NULL
RETURN v {{.violation_id, .violation_class, .inspection_date, .current_status, {PROV}}} AS v ORDER BY v.inspection_date, v.violation_id LIMIT 5
"""
LOT_UNITS = "MATCH (l:Lot {bbl: $bbl}) RETURN l.units_residential AS res, l.units_total AS total, l.source AS source"
VIOLATIONS_AS_OF = "MATCH (s:Snapshot {source: 'justfixwow'}) RETURN s.hpd_violations_as_of AS d, s.snapshot_date AS snap ORDER BY s.snapshot_date DESC LIMIT 1"
CAVEATS_Q27 = [
    "A complaint is a report to HPD, not a finding. These are counts of problem rows (a complaint can have several problems) with problems HPD flags as duplicates left out; "
    "complaint_count is the distinct complaints per type, and a complaint with problems of several types appears under each, so those figures do not add up to a total of complaints.",
    "Counts are by calendar year received: a since-year includes that whole year. No apartment, unit or complainant detail is loaded or returned.",
    "The rate divides non-duplicate problems by PLUTO's residential units for the lot (lot-level, not per building).",
]
COMPLAINT_TYPES = """
MATCH (l:Lot {bbl: $bbl})<-[:ON_LOT]-(s:ComplaintSummary {grouping: 'type'}) WHERE s.year >= $since
RETURN s.group_value AS type, s.group_value_raw AS type_raw, s.problem_status AS status, sum(s.problem_count) AS problems, sum(s.duplicate_problem_count) AS duplicates,
       sum(s.complaint_count) AS complaints, max(s.latest_received) AS latest, collect(DISTINCT s.year) AS years
"""
COMPLAINT_CATEGORIES = """
MATCH (l:Lot {bbl: $bbl})<-[:ON_LOT]-(s:ComplaintSummary {grouping: 'category'}) WHERE s.year >= $since
RETURN s.group_value AS category, sum(s.problem_count) AS problems ORDER BY problems DESC, category
"""
COMPLAINTS_AS_OF = "MATCH (s:Snapshot {source: 'justfixwow'}) RETURN s.hpd_complaints_as_of AS d ORDER BY s.snapshot_date DESC LIMIT 1"
CAVEATS_Q17 = [
    "HPD's registration dataset covers buildings with three or more units. This tool reports the lot's units against that threshold and does not decide whether registration was legally required.",
    "A registration period that has ended is a lapse only as far as the registration data goes: a newer registration may exist outside the snapshot. The dates are those of the snapshot, not today.",
    "A recent deed does not show who should have registered. The deed comparison with the HPD owner is a separate question (Q3).",
]
REG_ROWS = """
MATCH (l:Lot {bbl: $bbl})<-[:ON_LOT]-(reg:Registration)
RETURN reg.registration_id AS registration_id, reg.last_registration_date AS last_registered, reg.registration_end_date AS ends
ORDER BY reg.registration_id
"""
LOT_FACTS = "MATCH (l:Lot {bbl: $bbl}) RETURN l.units_residential AS res, l.units_total AS total, l.year_built AS year_built, l.year_built_raw AS year_built_raw, l.building_class AS cls, l.source AS source"
LATEST_DEEDS = f"""
MATCH (l:Lot {{bbl: $bbl}})<-[:ON_LOT]-(d:Document) WHERE d.doc_type IS NOT NULL AND d.doc_type <> 'deed_correction' AND d.recorded IS NOT NULL
WITH d ORDER BY d.recorded DESC, d.document_id LIMIT 3
RETURN d {{.document_id, .doc_type, .recorded, .doc_date, .amount, {PROV}}} AS d
"""
CASES = f"""
MATCH (l:Lot {{bbl: $bbl}})<-[:ON_LOT]-(c:Litigation)
OPTIONAL MATCH (c)-[:ON_BUILDING]->(b:Building)
WITH c, collect(b.bin) AS bins
RETURN c {{.litigation_id, .case_type, .case_type_raw, .case_open_date, .case_open_date_raw, .case_status, .case_status_raw, .open_judgement,
          .finding_of_harassment, .finding_date, .penalty, .respondent_raw, .respondent_names, .respondent_names_n1, {PROV}}} AS c, bins
ORDER BY c.case_open_date DESC, c.litigation_id
"""
OWNER_NAMES = """
MATCH (l:Lot {bbl: $bbl})<-[:ON_LOT]-(reg:Registration)<-[:IN_REGISTRATION]-(:HpdRole {role_type: 'registered_owner'})-[:HELD_BY]->(p:HpdParty)
RETURN reg.registration_id AS registration_id, coalesce(p.organization_name, p.person_name) AS name,
       [x IN [p.name_n1, p.person_name_n1] WHERE x IS NOT NULL] AS keys
"""
AS_OF = "MATCH (s:Snapshot {source: 'justfixwow'}) RETURN s.hpd_litigation_as_of AS d ORDER BY s.snapshot_date DESC LIMIT 1"


def litigation(runner, bbl: str) -> dict:
    """Every HPD Housing Court case on a lot, with respondents and their exact-name agreement with the registered owners."""
    base = {"bbl": bbl, **snapshot(runner)}
    if runner.run("MATCH (l:Lot {bbl: $bbl}) RETURN l.bbl", bbl=bbl).single() is None:
        return {**base, "status": "lot_absent", "note": "The graph holds no such lot."}
    rec = runner.run(AS_OF).single()
    as_of = _plain(rec["d"]) if rec and rec["d"] is not None else None
    base |= {"litigation_data_as_of": as_of, "rule": N1_RULE, "caveats": CAVEATS_Q28}
    rows = runner.run(CASES, bbl=bbl).data()
    if not rows:
        return {**base, "status": "no_case", "note": "No HPD Housing Court case on this lot in the snapshot. That does not mean none was ever brought: this is HPD's litigation dataset only."}
    owners = runner.run(OWNER_NAMES, bbl=bbl).data()
    cases = []
    for r in rows:
        c, by_status = r["c"], None
        names, keys = c.get("respondent_names") or [], c.get("respondent_names_n1") or []
        respondents = []
        for name, key in zip(names, keys):
            matches = [{"registration_id": o["registration_id"], "registered_owner_name": o["name"]} for o in owners if key in o["keys"]]
            respondents.append({"name_as_recorded": name, "role": "respondent (as HPD records it)", "source": c["source"], "snapshot_id": c["snapshot_id"],
                                "name_agreement_with_registered_owner": "exact_normalized" if matches else "none_found", "matches": matches})
        cases.append({"finding_of_harassment": "none recorded in the data"} | _clean({k: v for k, v in c.items() if k not in ("respondent_names", "respondent_names_n1")}) | {"building_bins": sorted(r["bins"]), "respondents": respondents})
    counts: dict = {}
    for c in cases:
        counts[c.get("case_status") or "unknown"] = counts.get(c.get("case_status") or "unknown", 0) + 1
    return {**base, "status": "found", "case_count": len(cases), "cases_by_status": counts, "cases": cases}


def violations(runner, bbl: str) -> dict:
    """Counts of HPD violations on a lot by class and open or closed, the oldest open inspection date and a rate per residential unit."""
    base = {"bbl": bbl, **snapshot(runner)}
    lot = runner.run(LOT_UNITS, bbl=bbl).single()
    if lot is None:
        return {**base, "status": "lot_absent", "note": "The graph holds no such lot."}
    meta = runner.run(VIOLATIONS_AS_OF).single()
    as_of = _plain(meta["d"]) if meta and meta["d"] is not None else None
    snap_date = _plain(meta["snap"]) if meta else base.get("snapshot_date")
    base |= {"violation_data_as_of": as_of, "caveats": CAVEATS_Q15}
    rows = runner.run(VIOLATION_COUNTS, bbl=bbl, snap=snap_date).data()
    if not rows:
        return {**base, "status": "no_violation", "note": "No HPD violation on this lot in the data. The data holds only part of all violations, so this does not show the lot never had one."}
    by_class: dict = {}
    for r in rows:
        c = by_class.setdefault(r["cls"], {"open": 0, "closed": 0})
        c[r["grp"]] += r["n"]
    open_total = sum(c["open"] for c in by_class.values())
    open_abc = sum(c["open"] for k, c in by_class.items() if k != "I")
    opens = [r["oldest"] for r in rows if r["grp"] == "open" and r["oldest"] is not None]
    units = lot["res"]
    buildings: dict = {}
    for r in runner.run(VIOLATION_BUILDINGS, bbl=bbl).data():
        b = buildings.setdefault(r["bin"], {"bin": r["bin"], "open": 0, "closed": 0})
        b[r["grp"]] += r["n"]
    return {**base, "status": "found", "by_class": {k: by_class[k] for k in sorted(by_class)},
            "open_total": open_total, "open_classes_a_b_c": open_abc, "open_class_i": by_class.get("I", {}).get("open", 0),
            "closed_total": sum(c["closed"] for c in by_class.values()),
            "oldest_open_inspection_date": _plain(min(opens)) if opens else None,
            "oldest_open": [_clean(r["v"]) for r in runner.run(OLDEST_OPEN, bbl=bbl).data()],
            "latest_inspection_date": _plain(max(r["latest"] for r in rows if r["latest"] is not None)) if any(r["latest"] for r in rows) else None,
            "inspected_after_snapshot_date": sum(r["after_snapshot"] for r in rows),
            "without_inspection_date": sum(r["undated"] for r in rows),
            "by_building": list(buildings.values()), "by_building_note": "Each entry is a BIN HPD tied the violations to; an entry with bin null counts violations on the lot not tied to a building in the graph.",
            "residential_units": units, "units_source": lot["source"],
            "open_a_b_c_per_residential_unit": round(open_abc / units, 2) if units else None,
            "rate_note": "Open class A, B and C violations divided by PLUTO's residential units for the lot; null when PLUTO has no residential units."}


def complaints(runner, bbl: str, since_year: int | None = None) -> dict:
    """Counts of HPD complaint problems on a lot from `since_year` (calendar years, whole year included) by type, status and major category."""
    base = {"bbl": bbl, **snapshot(runner)}
    lot = runner.run(LOT_UNITS, bbl=bbl).single()
    if lot is None:
        return {**base, "status": "lot_absent", "note": "The graph holds no such lot."}
    meta = runner.run(COMPLAINTS_AS_OF).single()
    base |= {"complaint_data_as_of": _plain(meta["d"]) if meta and meta["d"] is not None else None, "since_year": since_year, "caveats": CAVEATS_Q27,
             "counted": "problem rows, duplicates left out"}
    since = since_year if since_year is not None else 0
    rows = runner.run(COMPLAINT_TYPES, bbl=bbl, since=since).data()
    if not rows:
        return {**base, "status": "no_complaint", "note": "No HPD complaint problem on this lot in the data" + (f" from {since_year}" if since_year else "") + "."}
    by_type: dict = {}
    by_status = {"OPEN": 0, "CLOSE": 0}
    for r in rows:
        t = by_type.setdefault(r["type"], {"problems": 0, "complaints": 0, "open": 0, "closed": 0})
        t["problems"] += r["problems"]
        t["complaints"] += r["complaints"]
        t["open" if r["status"] == "OPEN" else "closed"] += r["problems"]
        by_status[r["status"]] += r["problems"]
    problems = sum(t["problems"] for t in by_type.values())
    units = lot["res"]
    latest = max(r["latest"] for r in rows if r["latest"] is not None) if any(r["latest"] for r in rows) else None
    return {**base, "status": "found", "problems": problems, "duplicate_problems_left_out": sum(r["duplicates"] for r in rows),
            "by_type": {k: by_type[k] for k in sorted(by_type)}, "open_problems": by_status["OPEN"], "closed_problems": by_status["CLOSE"],
            "by_major_category": {r["category"]: r["problems"] for r in runner.run(COMPLAINT_CATEGORIES, bbl=bbl, since=since).data()},
            "years_with_problems": sorted({y for r in rows for y in r["years"]}), "latest_received": _plain(latest) if latest else None,
            "residential_units": units, "units_source": lot["source"],
            "problems_per_residential_unit": round(problems / units, 2) if units else None}


def registration_status(runner, bbl: str) -> dict:
    """Whether a lot has an HPD registration, whether the latest registration period has ended, and whether the latest registration is older
    than the latest recorded deed, each with its dates, plus the lot's units against the dataset's three-unit threshold."""
    base = {"bbl": bbl, **snapshot(runner)}
    lot = runner.run(LOT_FACTS, bbl=bbl).single()
    if lot is None:
        return {**base, "status": "lot_absent", "note": "The graph holds no such lot."}
    snap = date.fromisoformat(base["snapshot_date"]) if base.get("snapshot_date") else None
    units = lot["res"]
    out = {**base, "status": "found", "registration_data_as_of": base.get("snapshot_date"), "caveats": CAVEATS_Q17,
           "units": {"residential": units, "total": lot["total"], "source": lot["source"], "threshold_in_dataset": "3 or more units",
                     "at_or_above_threshold": None if units is None else units >= 3},
           "year_built": lot["year_built"] if lot["year_built"] is not None else lot["year_built_raw"], "building_class": lot["cls"]}
    if lot["year_built"] is not None and snap is not None and lot["year_built"] >= snap.year - 2:
        out["recently_built"] = ("Built in the last few years before the snapshot: a new building can be unregistered for a legitimate reason. "
                                 "This tool does not know whether it was required to register yet.")
    regs = runner.run(REG_ROWS, bbl=bbl).data()
    deeds = [r["d"] for r in runner.run(LATEST_DEEDS, bbl=bbl).data()]
    latest_deed = _clean(deeds[0]) if deeds else None
    out["latest_deed"] = latest_deed
    if latest_deed and latest_deed.get("amount") == 0:
        out["latest_deed_note"] = "The latest deed is for $0, which is not a sale."
    if not regs:
        return {**out, "registration": "none_in_dataset", "no_registration": True, "lapsed": None, "registration_older_than_latest_deed": None,
                "note": "No HPD registration on this lot in the snapshot. That is not 'the owner failed to register': the answer is only what the dataset holds."}
    ends = [r["ends"].to_native() for r in regs if r["ends"] is not None]
    regd = [r["last_registered"].to_native() for r in regs if r["last_registered"] is not None]
    latest_end, latest_reg = (max(ends) if ends else None), (max(regd) if regd else None)
    lapsed = None if latest_end is None or snap is None else latest_end < snap
    older = None
    if latest_reg is not None and latest_deed and latest_deed.get("recorded"):
        older = latest_reg < date.fromisoformat(latest_deed["recorded"])
    return {**out, "registration": "present", "no_registration": False, "registrations": [
        {"registration_id": r["registration_id"], "last_registration_date": _plain(r["last_registered"]), "registration_end_date": _plain(r["ends"])} for r in regs],
        "latest_registration_date": latest_reg.isoformat() if latest_reg else None, "latest_registration_end_date": latest_end.isoformat() if latest_end else None,
        "lapsed": lapsed, "lapsed_meaning": "the latest registration period on the lot ended before the snapshot date",
        "registration_older_than_latest_deed": older, "older_meaning": "the latest registration date is earlier than the latest recorded deed date"}


@tool
def get_registration_status(bbl: str) -> dict:
    """Report whether a tax lot (BBL, a 10-digit string) has an HPD registration, whether the latest registration period has ended by the
    snapshot date, and whether the latest registration is older than the latest recorded deed, each with its dates; also the lot's units
    against the registration dataset's three-unit threshold and the year built. It does not decide whether registration was legally required."""
    with read_session() as session:
        return registration_status(session, bbl)


@tool
def get_hpd_complaints(bbl: str, since_year: int = 0) -> dict:
    """Summarize the HPD complaint problems on a tax lot (BBL, a 10-digit string) from a calendar year on (since_year, for example 2022 for
    'since January 1, 2022'; 0 means all years): problem counts by type (emergency, non-emergency, immediate emergency, hazardous, referral),
    by open or closed and by major category, distinct complaints per type, the latest received date and problems per residential unit.
    A complaint is a report, not a finding. No apartment or complainant detail is available."""
    with read_session() as session:
        return complaints(session, bbl, since_year or None)


@tool
def get_hpd_violations(bbl: str) -> dict:
    """Summarize the HPD violations on a tax lot (BBL, a 10-digit string): counts by class (A, B, C and I, kept apart) and by open or closed,
    the oldest open inspection date with the five oldest open violations (ids), the latest inspection date, a count by building, and open
    violations per residential unit. A violation is what an inspector cited, not a court finding; the data holds part of all violations."""
    with read_session() as session:
        return violations(session, bbl)


@tool
def get_hpd_litigation(bbl: str) -> dict:
    """List the Housing Court cases HPD brought that name a tax lot (BBL, a 10-digit string): case type, open date, status, any harassment
    finding, and the respondents HPD lists, each with whether its exact normalized name equals an HPD registered owner of the lot.
    An HPD action is not an eviction and not a finding of liability, and a respondent name is a lead, not proof of ownership."""
    with read_session() as session:
        return litigation(session, bbl)
