"""Run the Slice 1 build: justfixwow PLUTO and HPD into nyclr, then validate. A violation fails the build.

  uv run python -m etl.run_build --community-district 307     # one district first
  uv run python -m etl.run_build                              # citywide
  uv run python -m etl.run_build --modules acris              # ACRIS deeds on lots already in the graph (note 0015)

Re-runnable: a second run creates nothing new. The snapshot id is the one BOR's release names (note 0008).
"""
import argparse
import sys
from datetime import date

from etl import source
from etl.build import build, build_acris
from etl.config import connect
from etl.schema import load_schema
from etl.vocab import deed_family_codes
from etl.validate import validate

SNAPSHOT_ID, SNAPSHOT_DATE = "justfixwow-2026-05-29", date(2026, 5, 29)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--community-district", type=int, help="load one PLUTO community district, such as 307")
    ap.add_argument("--modules", default="hpd", help="comma list of hpd (PLUTO and HPD) and acris; acris needs hpd loaded first")
    ap.add_argument("--snapshot-id", default=SNAPSHOT_ID)
    ap.add_argument("--snapshot-date", type=date.fromisoformat, default=SNAPSHOT_DATE)
    args = ap.parse_args()
    cd, schema = args.community_district, load_schema()
    src = source.connect()
    driver, database = connect()
    with src, driver, driver.session(database=database) as session:
        mods = set(args.modules.split(","))
        if not mods <= {"hpd", "acris"}:
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
        violations = validate(session)
        print(f"violations: {len(violations)}")
        for v in violations[:50]:
            print("  ", v.rule, v.detail[:200])
    sys.exit(1 if violations else 0)


if __name__ == "__main__":
    main()
