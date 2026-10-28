"""Derive evals/expected/slice2.json and slice2.sql from the justfixwow database (read-only), independent of the graph.

  uv run python -m evals.expected.derive_slice2

Q15, Q17, Q27 and Q28 on the anchor lots A-G of docs/competency-questions-detail.md (design note 0020). The tables hold data newer
than the snapshot date, so each source's as-of date is derived the way the build derives it: the latest event date not after the
build date (the day this is run), so a run on another day can change the as-of dates and nothing else."""
import json
from datetime import date

from etl import source
from etl.config import ROOT

OUT = ROOT / "evals" / "expected"
SNAPSHOT_ID, SNAPSHOT_DATE = "justfixwow-2026-05-29", date(2026, 5, 29)
ANCHOR_DOC = json.loads((OUT / "slice1.json").read_text())["anchors"]
BBLS = [a["bbl"] for a in ANCHOR_DOC.values()]
DEED_CODES = ["DEED", "DEED, TS", "DEED, LE", "DEEDO", "DEED COR", "DEED, RC", "DEEDP"]

SQL = {
    "Q15 violation counts by class and status": """select bbl, class, violationstatus, count(*) as n, min(inspectiondate) as oldest_inspection, max(inspectiondate) as latest_inspection,
       count(*) filter (where inspectiondate > %(snap)s) as inspected_after_snapshot
from hpd_violations where bbl = any(%(bbls)s) group by bbl, class, violationstatus order by bbl, class, violationstatus""",
    "Q15 five oldest open violations": """select bbl, violationid, class, inspectiondate, currentstatus from (
  select *, row_number() over (partition by bbl order by inspectiondate, violationid) as rn
  from hpd_violations where bbl = any(%(bbls)s) and violationstatus = 'Open' and inspectiondate is not null) x where rn <= 5 order by bbl, rn""",
    "Q15/Q17/Q27 lot facts": """select bbl, unitsres, unitstotal, yearbuilt, bldgclass from pluto_latest where bbl = any(%(bbls)s) order by bbl""",
    "Q17 registrations": """select bbl, registrationid, lastregistrationdate, registrationenddate from hpd_registrations where bbl = any(%(bbls)s) order by bbl, registrationid""",
    "Q17 latest deed (not a correction), latest version of each document": """select distinct on (l.bbl) l.bbl, m.documentid, m.doctype, m.recordedfiled, m.docdate, m.docamount
from real_property_legals l join (select distinct on (documentid) * from real_property_master order by documentid, modifieddate desc) m on m.documentid = l.documentid
where l.bbl = any(%(bbls)s) and m.doctype = any(%(deeds)s) and m.doctype <> 'DEED COR' and m.recordedfiled is not null
order by l.bbl, m.recordedfiled desc, m.documentid""",
    "Q27 problems by type and status (all years)": """select bbl, extract(year from receiveddate)::int as year, type, problemstatus,
       count(*) filter (where not problemduplicateflag) as problems, count(*) filter (where problemduplicateflag) as duplicates,
       count(distinct complaintid) filter (where not problemduplicateflag) as complaints, max(receiveddate) filter (where not problemduplicateflag) as latest
from hpd_complaints_and_problems where bbl = any(%(bbls)s) and receiveddate <= %(today)s group by bbl, year, type, problemstatus order by bbl, year, type, problemstatus""",
    "Q27 problems by major category (all years)": """select bbl, extract(year from receiveddate)::int as year, majorcategory, count(*) filter (where not problemduplicateflag) as problems
from hpd_complaints_and_problems where bbl = any(%(bbls)s) and receiveddate <= %(today)s group by bbl, year, majorcategory order by bbl, year, majorcategory""",
    "Q28 litigation cases": """select bbl, litigationid, casetype, caseopendate, casestatus, findingofharassment, respondent from hpd_litigations where bbl = any(%(bbls)s) order by bbl, litigationid""",
}


def _plain(v):
    return v.isoformat() if hasattr(v, "isoformat") else v


def main() -> None:
    today = date.today()
    params = {"bbls": BBLS, "deeds": DEED_CODES, "snap": SNAPSHOT_DATE, "today": today}
    with source.connect() as conn, conn.cursor() as cur:
        res = {}
        for name, sql in SQL.items():
            cur.execute(sql, params)
            res[name] = [{k: _plain(v) for k, v in r.items()} for r in cur.fetchall()]
        as_of = {"hpd_violations": _plain(source.as_of(conn, "hpd_violations", "inspectiondate", today)),
                 "hpd_complaints": _plain(source.as_of(conn, "hpd_complaints_and_problems", "receiveddate", today)),
                 "hpd_litigation": _plain(source.as_of(conn, "hpd_litigations", "caseopendate", today))}
    lots = {r["bbl"]: r for r in res["Q15/Q17/Q27 lot facts"]}
    letters = {a["bbl"]: letter for letter, a in ANCHOR_DOC.items()}
    q15, q17, q27, q28 = {}, {}, {}, {}
    for bbl, letter in letters.items():
        lot = lots[bbl]
        rows = [r for r in res["Q15 violation counts by class and status"] if r["bbl"] == bbl]
        by_class = {}
        for r in rows:
            by_class.setdefault(r["class"], {"open": 0, "closed": 0})["open" if r["violationstatus"] == "Open" else "closed"] += r["n"]
        opens = [r for r in res["Q15 five oldest open violations"] if r["bbl"] == bbl]
        abc = sum(c["open"] for k, c in by_class.items() if k != "I")
        q15[letter] = ("no violation in the data" if not rows else {
            "by_class": by_class, "open_total": sum(c["open"] for c in by_class.values()), "open_classes_a_b_c": abc, "open_class_i": by_class.get("I", {}).get("open", 0),
            "oldest_open_inspection_date": opens[0]["inspectiondate"] if opens else None, "oldest_open_ids": [str(o["violationid"]) for o in opens],
            "latest_inspection_date": max(r["latest_inspection"] for r in rows), "inspected_after_snapshot_date": sum(r["inspected_after_snapshot"] for r in rows),
            "residential_units": lot["unitsres"], "open_a_b_c_per_residential_unit": round(abc / lot["unitsres"], 2) if lot["unitsres"] else None})
        regs = [r for r in res["Q17 registrations"] if r["bbl"] == bbl]
        deed = next((r for r in res["Q17 latest deed (not a correction), latest version of each document"] if r["bbl"] == bbl), None)
        latest_end = max((r["registrationenddate"] for r in regs if r["registrationenddate"]), default=None)
        latest_reg = max((r["lastregistrationdate"] for r in regs if r["lastregistrationdate"]), default=None)
        q17[letter] = {"registered": bool(regs), "registration_ids": [str(r["registrationid"]) for r in regs], "latest_registration_date": latest_reg,
                       "latest_registration_end_date": latest_end, "lapsed": None if not latest_end else latest_end < SNAPSHOT_DATE.isoformat(),
                       "older_than_latest_deed": None if not (latest_reg and deed) else latest_reg < deed["recordedfiled"],
                       "latest_deed": None if not deed else {"document_id": str(deed["documentid"]), "recorded": deed["recordedfiled"], "amount": deed["docamount"]},
                       "residential_units": lot["unitsres"], "year_built": lot["yearbuilt"]}
        tr = [r for r in res["Q27 problems by type and status (all years)"] if r["bbl"] == bbl]
        cats = [r for r in res["Q27 problems by major category (all years)"] if r["bbl"] == bbl]

        def window(since):
            t = [r for r in tr if r["year"] >= since]
            if not t:
                return "no complaint in the data"
            n = sum(r["problems"] for r in t)
            return {"problems": n, "duplicates_left_out": sum(r["duplicates"] for r in t), "open": sum(r["problems"] for r in t if r["problemstatus"] == "OPEN"),
                    "by_type": {ty: sum(r["problems"] for r in t if r["type"] == ty) for ty in sorted({r["type"] for r in t})},
                    "by_major_category": {c: sum(r["problems"] for r in cats if r["majorcategory"] == c and r["year"] >= since) for c in sorted({r["majorcategory"] for r in cats if r["year"] >= since})},
                    "latest_received": max(r["latest"] for r in t if r["latest"]), "problems_per_residential_unit": round(n / lot["unitsres"], 2) if lot["unitsres"] else None}
        q27[letter] = {"since_2022": window(2022), "all_years": window(0)}
        cases = [r for r in res["Q28 litigation cases"] if r["bbl"] == bbl]
        q28[letter] = ("no case in the data" if not cases else [
            {"litigation_id": str(c["litigationid"]), "case_type": c["casetype"], "case_open_date": c["caseopendate"], "case_status": c["casestatus"],
             "finding_of_harassment": c["findingofharassment"], "respondent_raw": c["respondent"]} for c in cases])
    doc = {"snapshot_id": SNAPSHOT_ID, "derived": today.isoformat(), "as_of": as_of, "source": "justfixwow PostgreSQL (read-only); queries in slice2.sql",
           "how_to_read": ("Expected answers for the Slice 2 questions (Q15, Q17, Q27, Q28) on the anchors A-G, taken from the snapshot the graph is built from. "
                           "The violation, complaint and litigation tables are newer than the snapshot date 2026-05-29, so each answer is as of its source's as-of date (note 0020). "
                           "Complaint figures count problem rows without the duplicate flag. The detail document's Q15 and Q27 examples are from the older snapshot 2026-10-17."),
           "anchors": {l: {"bbl": a["bbl"]} for l, a in ANCHOR_DOC.items()}, "questions": {"Q15": q15, "Q17": q17, "Q27": q27, "Q28": q28}}
    (OUT / "slice2.json").write_text(json.dumps(doc, indent=1) + "\n")
    (OUT / "slice2.sql").write_text("-- Queries behind evals/expected/slice2.json, run read-only on the justfixwow database by derive_slice2.py.\n"
                                     "-- %(bbls)s = the seven anchor BBLs (A-G); %(snap)s = 2026-05-29; %(today)s = the day it was run; %(deeds)s = the deed-family codes.\n\n"
                                     + "\n\n".join(f"-- {n}\n{q};" for n, q in SQL.items()) + "\n")
    print("written; as of", as_of)


if __name__ == "__main__":
    main()
