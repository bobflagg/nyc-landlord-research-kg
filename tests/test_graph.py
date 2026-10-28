"""Schema, sample load and checks against nyclr, inside a rolled-back transaction."""
import json

import pytest

from etl.config import ROOT

from etl.sample import BAD
from etl.validate import compiled_rules, handwritten_checks, validate
from tests.scope import SCOPE


CORE_RULES = ("LotShape", "BuildingShape", "PartyShape", "RoleShape", "SnapshotShape", "ProvenanceShape", "role_attachment", "snapshot_reference")


def test_sample_is_clean(tx):
    assert validate(tx, only=CORE_RULES, scope=SCOPE) == []


@pytest.mark.parametrize("rule, cypher", BAD, ids=[r for r, _ in BAD])
def test_bad_row_trips_rule(tx, rule, cypher):
    tx.run(cypher.replace("CREATE (:", f"CREATE (:{SCOPE}:", 1)).consume()   # the bad row carries the scope label
    assert rule in {v.rule for v in validate(tx, only=(rule,), scope=SCOPE)}  # that rule alone, on the bad row alone


def test_every_manifest_rule_is_run():
    total = sum(len(json.loads(p.read_text())["rules"]) for p in (ROOT / "ontology" / "generated").glob("*.manifest.json"))
    assert len(compiled_rules()) == total
    assert {n for n, _ in handwritten_checks()} == {"role_attachment", "snapshot_reference"}
