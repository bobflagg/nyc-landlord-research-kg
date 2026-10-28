"""HPD violations, complaint summaries and litigation to nodes (design note 0020). Pure; no database.

A date before 1900 or after the source's as-of date is not stored as a date; the recorded value is kept as text in a
`_raw` property, as ACRIS does (note 0015). Apartment, story, unit and complainant fields are never read."""
import re
from datetime import date, datetime

from etl.names import n1
from etl.pluto import provenance
from etl.vocab import complaint_type, litigation_case_type, violation_class, violation_status_group

VIOLATIONS, COMPLAINTS, LITIGATION = "hpd_violations", "hpd_complaints", "hpd_litigations"
EARLIEST = date(1900, 1, 1)
DATE_IN_STATUS = re.compile(r"\s*,?\s*-?\s*\d{1,2}/\d{1,2}/\d{2,4}.*$")


def _s(v) -> str | None:
    v = re.sub(r"\s+", " ", str(v)).strip() if v is not None else ""
    return v or None


def _day(v) -> date | None:
    if v is None:
        return None
    return v.date() if isinstance(v, datetime) else v if isinstance(v, date) else date.fromisoformat(str(v)[:10])


def _dated(node: dict, prop: str, value, as_of: date) -> None:
    """The date, or its text under `<prop>_raw` when it is outside 1900..as_of."""
    d = _day(value)
    if d is None:
        return
    if EARLIEST <= d <= as_of:
        node[prop] = d
    else:
        node[f"{prop}_raw"] = d.isoformat()


def violation_node(row: dict, snapshot_id: str, as_of: date) -> dict | None:
    """One violation row, or None when it has no class HPD uses (the loader counts those)."""
    vid = str(row["violationid"]).strip()
    cls, group = violation_class(row.get("class")), violation_status_group(row.get("violationstatus"))
    if cls is None or group is None:
        return None
    node = {"violation_id": vid, **provenance(VIOLATIONS, snapshot_id, vid), "violation_class": cls,
            "status_group": group, "current_status": _s(row.get("currentstatus")), "nov_issued_date": _day(row.get("novissueddate")),
            "rent_impairing": row.get("rentimpairing"),
            "registration_id": str(row["registrationid"]).strip() if row.get("registrationid") is not None else None}
    _dated(node, "inspection_date", row.get("inspectiondate"), as_of)
    _dated(node, "current_status_date", row.get("currentstatusdate"), as_of)
    return {k: v for k, v in node.items() if v is not None}


def litigation_node(row: dict, snapshot_id: str, as_of: date) -> dict:
    lid, raw_type = str(row["litigationid"]).strip(), _s(row.get("casetype"))
    status_raw = _s(row.get("casestatus"))
    respondent = _s(row.get("respondent"))
    names = [x for x in (_s(p) for p in respondent.split(",")) if x and n1(x)] if respondent else []
    node = {"litigation_id": lid, **provenance(LITIGATION, snapshot_id, lid), "case_type": litigation_case_type(raw_type), "case_type_raw": raw_type,
            "case_status_raw": status_raw, "case_status": _s(DATE_IN_STATUS.sub("", status_raw)) if status_raw else None,
            "open_judgement": _s(row.get("openjudgement")), "finding_of_harassment": _s(row.get("findingofharassment")),
            "finding_date": _day(row.get("findingdate")), "penalty": _s(row.get("penalty")), "respondent_raw": respondent,
            "respondent_names": names or None, "respondent_names_n1": [n1(x) for x in names] or None}
    _dated(node, "case_open_date", row.get("caseopendate"), as_of)
    return {k: v for k, v in node.items() if v is not None}


def complaint_summary_node(row: dict, grouping: str, snapshot_id: str) -> dict:
    """One aggregated source group (building, year, type or major category, problem status) to a ComplaintSummary.

    `row` comes from the SQL grouping in etl.source: counts of problem rows (duplicates apart), distinct complaints for a
    type group, and the latest received date. No apartment, unit, complainant or anonymity column is ever selected."""
    if grouping not in ("type", "category"):
        raise ValueError(grouping)
    raw = _s(row["group_value"])
    value = (complaint_type(raw) or raw) if grouping == "type" else raw
    bbl, bin_, year, status = str(row["bbl"]).strip(), str(row["bin"]).strip(), int(row["year"]), _s(row["problemstatus"])
    sid = "|".join((bbl, bin_, grouping, value, str(year), status))
    node = {"summary_id": sid, **provenance(COMPLAINTS, snapshot_id, sid), "grouping": grouping, "group_value": value, "year": year,
            "problem_status": status, "problem_count": int(row["problems"]), "duplicate_problem_count": int(row["duplicates"]),
            "latest_received": _day(row.get("latest_received"))}
    if grouping == "type":
        node["group_value_raw"] = raw
        node["complaint_count"] = int(row["complaints"])
    return {k: v for k, v in node.items() if v is not None}
