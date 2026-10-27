"""Schema, sample load and checks against nyclr, inside a rolled-back transaction."""
import json

import pytest

from etl.config import ROOT

from etl.sample import BAD
from etl.validate import compiled_rules, handwritten_checks, validate


CORE_RULES = ("LotShape", "BuildingShape", "PartyShape", "RoleShape", "SnapshotShape", "ProvenanceShape", "role_attachment", "snapshot_reference")


def test_sample_is_clean(tx):
    assert validate(tx, only=CORE_RULES) == []


@pytest.mark.parametrize("rule, cypher", BAD, ids=[r for r, _ in BAD])
def test_bad_row_trips_rule(tx, rule, cypher):
    tx.run(cypher).consume()
    assert rule in {v.rule for v in validate(tx, only=(rule,))}  # that rule alone: the full set scans every loaded node


def test_every_manifest_rule_is_run():
    total = sum(len(json.loads(p.read_text())["rules"]) for p in (ROOT / "ontology" / "generated").glob("*.manifest.json"))
    assert len(compiled_rules()) == total
    assert {n for n, _ in handwritten_checks()} == {"role_attachment", "snapshot_reference"}
