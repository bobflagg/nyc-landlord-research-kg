"""Run the Slice 1 build: justfixwow PLUTO and HPD into nyclr, then validate. A violation fails the build.

  uv run python -m etl.run_build --community-district 307     # one district first
  uv run python -m etl.run_build                              # citywide

Re-runnable: a second run creates nothing new. The snapshot id is the one BOR's release names (note 0008).
"""
import argparse
import sys
from datetime import date

from etl import source
from etl.build import build
from etl.config import connect
from etl.schema import load_schema
from etl.validate import validate

SNAPSHOT_ID, SNAPSHOT_DATE = "justfixwow-2026-05-29", date(2026, 5, 29)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--community-district", type=int, help="load one PLUTO community district, such as 307")
    ap.add_argument("--snapshot-id", default=SNAPSHOT_ID)
    ap.add_argument("--snapshot-date", type=date.fromisoformat, default=SNAPSHOT_DATE)
    args = ap.parse_args()
    cd, schema = args.community_district, load_schema()
    src = source.connect()
    driver, database = connect()
    with src, driver, driver.session(database=database) as session:
        totals = build(session, schema, args.snapshot_id, args.snapshot_date,
                       source.pluto(src, cd), source.registrations(src, cd), source.contacts(src, cd))
        print("loaded:", totals)
        violations = validate(session)
        print(f"violations: {len(violations)}")
        for v in violations[:50]:
            print("  ", v.rule, v.detail[:200])
    sys.exit(1 if violations else 0)


if __name__ == "__main__":
    main()
