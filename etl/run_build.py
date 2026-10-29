"""Run the Slice 1 build: justfixwow PLUTO and HPD into nyclr, then validate. A violation fails the build.

  uv run python -m etl.run_build --community-district 307     # one district first
  uv run python -m etl.run_build                              # citywide
  uv run python -m etl.run_build --modules acris              # ACRIS deeds on lots already in the graph (note 0015)
  uv run python -m etl.run_build --modules dos                # every active DOS entity, statewide (note 0016)
  uv run python -m etl.run_build --modules litigation         # HPD Housing Court cases on lots already in the graph (note 0020)
  uv run python -m etl.run_build --modules violations         # HPD violations on lots already in the graph (note 0020)
  uv run python -m etl.run_build --modules mortgages          # the mortgage family on HPD-registered lots (note 0022)
  uv run python -m etl.run_build --modules references         # recorded references between mortgage-family documents in the graph (note 0022)
  uv run python -m etl.run_build --modules complaints         # HPD complaint counts by building, year, type and category (note 0020)

Re-runnable: a second run creates nothing new. The snapshot id is the one BOR's release names (note 0008).
"""
import argparse
import sys
from datetime import date

from etl import source
from etl.build import build, build_acris, build_dos, build_complaints, build_litigation, build_references, build_violations
from etl.config import connect
from etl.schema import load_schema
from etl.vocab import deed_family_codes, mortgage_family_codes, mortgage_family_types
from etl.validate import validate

SNAPSHOT_ID, SNAPSHOT_DATE = "justfixwow-2026-05-29", date(2026, 5, 29)


def source_doc_ids(session):
    """Ids of the mortgage-family documents in the graph, in pages, so their references can be read from the source."""
    last = ""
    while True:
        ids = [r["id"] for r in session.run("MATCH (d:Document) WHERE d.doc_type IN $types AND d.document_id > $last RETURN d.document_id AS id ORDER BY id LIMIT 50000",
                                             types=mortgage_family_types(), last=last)]
        if not ids:
            return
        yield from ids
        last = ids[-1]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--community-district", type=int, help="load one PLUTO community district, such as 307")
    ap.add_argument("--modules", default="hpd", help="comma list of hpd (PLUTO and HPD), acris litigation, violations, complaints, mortgages and references (all need hpd loaded first) and dos (statewide; ignores --community-district)")
    ap.add_argument("--snapshot-id", default=SNAPSHOT_ID)
    ap.add_argument("--snapshot-date", type=date.fromisoformat, default=SNAPSHOT_DATE)
    args = ap.parse_args()
    cd, schema = args.community_district, load_schema()
    src = source.connect()
    driver, database = connect()
    with src, driver, driver.session(database=database) as session:
        mods = set(args.modules.split(","))
        if not mods <= {"hpd", "acris", "dos", "litigation", "violations", "complaints", "mortgages", "references"}:
            raise SystemExit(f"unknown module in {args.modules!r}")
        if "hpd" in mods:
            totals = build(session, schema, args.snapshot_id, args.snapshot_date,
                           source.pluto(src, cd), source.registrations(src, cd), source.contacts(src, cd),
                           conflicted_bins=source.conflicted_bins(src))
            print("loaded (hpd):", totals)
        if "acris" in mods:
            totals = build_acris(session, schema, args.snapshot_id, args.snapshot_date,
                                 source.acris_documents(src, deed_family_codes(), cd), source.acris_children(src),
                                 source.graph_lots(src, cd))
            print("loaded (acris):", totals)
        if "mortgages" in mods:
            totals = build_acris(session, schema, args.snapshot_id, args.snapshot_date,
                                 source.acris_documents(src, mortgage_family_codes(), cd, registered_only=True), source.acris_children(src),
                                 source.registered_lots(src))
            print("loaded (mortgages):", totals)
        if "references" in mods:
            print("loaded (references):", build_references(session, schema, source_doc_ids(session), source.acris_references(src)))
        if "dos" in mods:
            print("loaded (dos):", build_dos(session, schema, args.snapshot_id, args.snapshot_date, source.dos_entities(src)))
        if "litigation" in mods:
            as_of = source.as_of(src, "hpd_litigations", "caseopendate", date.today())
            print("loaded (litigation):", build_litigation(session, schema, args.snapshot_id, args.snapshot_date, source.litigation(src),
                                                           source.graph_lots(src), as_of), "as of", as_of)
        if "violations" in mods:
            as_of = source.as_of(src, "hpd_violations", "inspectiondate", date.today())
            print("loaded (violations):", build_violations(session, schema, args.snapshot_id, args.snapshot_date, source.violations(src),
                                                           source.graph_lots(src), as_of), "as of", as_of)
        if "complaints" in mods:
            as_of = source.as_of(src, "hpd_complaints_and_problems", "receiveddate", date.today())
            groups = {g: source.complaint_groups(src, g, date.today()) for g in ("type", "category")}
            print("loaded (complaints):", build_complaints(session, schema, args.snapshot_id, args.snapshot_date, groups, source.graph_lots(src), as_of), "as of", as_of)
        violations = validate(session)
        print(f"violations: {len(violations)}")
        for v in violations[:50]:
            print("  ", v.rule, v.detail[:200])
    sys.exit(1 if violations else 0)


if __name__ == "__main__":
    main()
