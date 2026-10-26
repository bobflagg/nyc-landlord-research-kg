"""The Slice 0 sample load: a handful of invented records, enough to exercise every class and the checks.

Source is `sample` and the snapshot is `sample-2026-01-01`, so nothing here can be mistaken for the real record.
Run: uv run python -m etl.sample [--selftest]
"""
import sys
from datetime import date

from etl.config import connect
from etl.load import apply_schema, load_edges, load_nodes, register_snapshot
from etl.schema import load_schema
from etl.validate import validate

SNAPSHOT = "sample-2026-01-01"


def _prov(**extra) -> dict:
    return {"reliability": "I", "source_category": "public_record", "source": "sample", "snapshot_id": SNAPSHOT, **extra}


def load_sample(tx, schema) -> dict[str, int]:
    register_snapshot(tx, SNAPSHOT, "sample", date(2026, 1, 1))
    c = {}
    c["Lot"] = load_nodes(tx, schema, "Lot", [
        _prov(bbl="3000010001", address_key="1 EXAMPLE ST 11201"),
        _prov(bbl="3000010002", address_key="3 EXAMPLE ST 11201"),
        _prov(bbl="3000010003"),
    ])
    c["Building"] = load_nodes(tx, schema, "Building", [
        _prov(bin="3000001", address_key="1 EXAMPLE ST 11201"),
        _prov(bin="3000002", address_key="3 EXAMPLE ST 11201"),
    ])
    c["Party"] = load_nodes(tx, schema, "Party", [_prov(party_id="sample-party-1", name="SAMPLE HOLDINGS LLC")])
    c["Role"] = load_nodes(tx, schema, "Role", [
        _prov(role_id="sample-role-1", role_type="owner", source_record_id="1"),
        _prov(role_id="sample-role-2", role_type="agent", source_record_id="2"),
        _prov(role_id="sample-role-3", role_type="owner", source_record_id="3"),
    ])
    c["ON_LOT"] = (load_edges(tx, schema, "ON_LOT", "Building", "Lot", [("3000001", "3000010001"), ("3000002", "3000010002")])
                   + load_edges(tx, schema, "ON_LOT", "Role", "Lot", [("sample-role-3", "3000010003")]))
    c["ON_BUILDING"] = load_edges(tx, schema, "ON_BUILDING", "Role", "Building", [("sample-role-1", "3000001"), ("sample-role-2", "3000002")])
    c["HELD_BY"] = load_edges(tx, schema, "HELD_BY", "Role", "Party", [(f"sample-role-{i}", "sample-party-1") for i in (1, 2, 3)])
    return c


# Bad rows added inside a rolled-back transaction; each must trigger the named rule.
BAD = [
    ("LotShape.bbl.pattern", "CREATE (:Lot {bbl:'30001', reliability:'I', source_category:'public_record', source:'sample', snapshot_id:'%s'})" % SNAPSHOT),
    ("BuildingShape.bin.not", "CREATE (:Building {bin:'1000000', reliability:'I', source_category:'public_record', source:'sample', snapshot_id:'%s'})" % SNAPSHOT),
    ("BuildingShape.on_lot.minCount", "CREATE (:Building {bin:'3000009', reliability:'I', source_category:'public_record', source:'sample', snapshot_id:'%s'})" % SNAPSHOT),
    ("LotShape.review_status.maxCount", "CREATE (:Lot {bbl:'3000010009', review_status:'unreviewed', reliability:'I', source_category:'public_record', source:'sample', snapshot_id:'%s'})" % SNAPSHOT),
    ("LotShape.node", "CREATE (:Lot {bbl:'3000010008', reliability:'III', source_category:'public_record', source:'sample', snapshot_id:'%s'})" % SNAPSHOT),
    ("snapshot_reference", "CREATE (:Lot {bbl:'3000010007', reliability:'I', source_category:'public_record', source:'sample', snapshot_id:'nosuch-2026-01-01'})"),
    ("role_attachment", "CREATE (:Role {role_id:'bad-role', role_type:'owner', source_record_id:'9', reliability:'I', source_category:'public_record', source:'sample', snapshot_id:'%s'})" % SNAPSHOT),
]


def selftest(session) -> bool:
    """Each bad row must trip its rule, and the good sample must trip none. Nothing is kept."""
    ok = True
    for rule, cypher in BAD:
        tx = session.begin_transaction()
        try:
            tx.run(cypher).consume()
            hit = {v.rule for v in validate(tx)}
        finally:
            tx.rollback()
        status = "ok " if rule in hit else "MISSED"
        ok &= rule in hit
        print(f"  {status} {rule}" + ("" if rule in hit else f"  (got: {sorted(hit)})"))
    return ok


def main() -> None:
    schema = load_schema()
    driver, database = connect()
    with driver, driver.session(database=database) as session:
        apply_schema(session, schema)
        counts = session.execute_write(load_sample, schema)
        print("loaded:", counts)
        violations = validate(session)
        print(f"violations on the sample: {len(violations)}")
        for v in violations:
            print("  ", v.rule, v.detail)
        ok = not violations
        if "--selftest" in sys.argv:
            print("selftest (bad rows, rolled back):")
            ok &= selftest(session)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
