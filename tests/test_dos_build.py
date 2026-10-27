"""DOS transforms, and the anchor entities loaded into nyclr inside a rolled-back transaction, checked against the
expected Q5 answers (evals/expected/slice1.json). Design note 0016."""
import json
from datetime import date

import pytest

from etl.build import load_nodes
from etl.config import ROOT
from etl.dos import dos_entity_node
from etl.load import apply_schema, register_snapshot
from etl.names import n1
from etl.validate import validate

SNAP, SNAP_DATE = "justfixwow-2026-05-29", date(2026, 5, 29)
ROWS = json.loads((ROOT / "tests" / "fixtures" / "slice1_dos.json").read_text())
EXP = json.loads((ROOT / "evals" / "expected" / "slice1.json").read_text())["questions"]["Q5"]
DOS_RULES = ("DosEntityShape", "PartyShape", "ProvenanceShape", "snapshot_reference")


def _expected_records():
    for anchor, e in EXP.items():
        for key in ("record", "other", "deed_grantee_record"):
            if e.get(key):
                yield pytest.param(anchor, e[key], id=f"{anchor}-{key}")


# ---- transforms (no database) ---------------------------------------------------------------------------------

def test_entity_node_has_identity_provenance_and_the_n1_name():
    n = dos_entity_node(next(r for r in ROWS if r["dosid"] == 3574572), SNAP)
    assert n["party_id"] == "dos:3574572" and n["dos_id"] == "3574572" and n["name_n1"] == "K S TURNPIKE LLC"
    assert (n["source"], n["reliability"], n["source_category"], n["source_record_id"]) == ("dos_active_corporations", "I", "public_record", "3574572")


def test_empty_fields_are_left_off_and_the_filing_date_is_a_date():
    n = dos_entity_node({"dosid": 1, "currententityname": "A  B LLC", "initialdosfilingdate": "2020-10-14", "ceoname": "  ", "dosprocessname": "A B LLC"}, SNAP)
    assert n["entity_name"] == "A B LLC" and n["initial_filing_date"] == date(2020, 10, 14)
    assert "ceo_name" not in n and "registered_agent_name" not in n


# ---- the anchors in the graph ---------------------------------------------------------------------------------

@pytest.fixture
def dos(session, schema):
    apply_schema(session, schema)
    tx = session.begin_transaction()
    register_snapshot(tx, SNAP, "justfixwow", SNAP_DATE)
    load_nodes(tx, schema, "Party", (dos_entity_node(r, SNAP) for r in ROWS), also=("DosEntity",))
    yield tx
    tx.rollback()


def test_loaded_entities_pass_the_dos_rules(dos):
    from etl.validate import compiled_rules
    assert any(n.startswith("DosEntityShape") for n, _ in compiled_rules())
    assert validate(dos, only=DOS_RULES) == []


def test_loading_twice_changes_nothing(dos, schema):
    before = dos.run("MATCH (n:DosEntity) RETURN count(n) AS c").single()["c"]
    load_nodes(dos, schema, "Party", (dos_entity_node(r, SNAP) for r in ROWS), also=("DosEntity",))
    assert dos.run("MATCH (n:DosEntity) RETURN count(n) AS c").single()["c"] == before


@pytest.mark.parametrize("anchor,exp", list(_expected_records()))
def test_q5_record_matches(dos, anchor, exp):
    n = dos.run("MATCH (e:DosEntity {dos_id: $id}) RETURN e {.*} AS e", id=exp["dos_id"]).single()["e"]
    assert (n["entity_name"], n["entity_type"], n["initial_filing_date"].iso_format()) == (exp["entity_name"], exp["entity_type"], exp["initial_filing_date"])
    assert n["process_name"] == exp["process_name"]
    assert f'{n["process_address_line1"]}, {n["process_city"]} {n["process_zip"]}' == exp["process_address"]
    assert n.get("registered_agent_name") == exp["registered_agent"]


def test_a_statutory_default_process_name_is_loaded_as_written(dos):
    n = dos.run("MATCH (e:DosEntity {name_n1: '606 56TH ST LLC'}) RETURN e.process_name AS p").single()
    assert n["p"] == "THE COMPANY"


@pytest.mark.parametrize("name,found", [("5413 PLAZA LLC", True), ("702 Plaza LLC", True), ("K S TURNPIKE LLC", True),
                                        ("KS Turnpike LLC", False),   # the HPD spelling: no match under N1 (anchor G)
                                        ("438 52 ST OWNERS CORP", False),   # anchor C, HPD spelling: no match
                                        ("438 52ND ST OWNERS CORP", True),  # anchor C, deed spelling: DOS has 438 52ND ST. OWNERS' CORP.
                                        ("HP SUNSET PARK I HDFC INC", False), ("HP SUNSET PARK I HOUSING DEV FUND COMPANY, INC", False)])  # anchor D
def test_name_lookup_by_n1_finds_the_exact_normalized_name_only(dos, name, found):
    got = dos.run("MATCH (e:DosEntity {name_n1: $n}) RETURN count(e) AS c", n=n1(name)).single()["c"]
    assert (got == 1) if found else (got == 0)
