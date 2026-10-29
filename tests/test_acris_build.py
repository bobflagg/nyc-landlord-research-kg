"""ACRIS transforms, and the anchor lots' deeds loaded into nyclr inside a rolled-back transaction, checked against
the expected Q3 answers (evals/expected/slice1.json). Design note 0015."""
import json
import re
from datetime import date

import pytest

from etl.acris import document_node, party_id, party_nodes
from etl.build import load_acris, load_hpd, load_pluto
from etl.config import ROOT
from etl.load import apply_schema, register_snapshot
from etl.validate import validate
from tests.scope import SCOPE, tag_acris, tag_hpd
from etl.vocab import acris_doc_type, acris_role_type, deed_family_codes

SNAP, SNAP_DATE = "justfixwow-2026-05-29", date(2026, 5, 29)
ANCH = json.loads((ROOT / "tests" / "fixtures" / "slice1_anchors.json").read_text())
AC = json.loads((ROOT / "tests" / "fixtures" / "slice1_acris.json").read_text())
EXP = json.loads((ROOT / "evals" / "expected" / "slice1.json").read_text())["questions"]["Q3"]
LOTS = frozenset(str(r["bbl"]).strip() for r in ANCH["pluto"])
ACRIS_RULES = ("DocumentShape", "AcrisPartyShape", "AcrisRoleShape")


def _expected_docs():
    for anchor, exp in EXP.items():
        yield from ((anchor, d) for d in exp["deeds"])
        if exp.get("last_deed_for_value"):
            yield anchor, exp["last_deed_for_value"]


# ---- transforms (no database) ---------------------------------------------------------------------------------

def test_deed_family_codes_come_from_the_vocabulary():
    assert deed_family_codes() == sorted(["DEED", "DEED, TS", "DEED, LE", "DEEDO", "DEED COR", "DEED, RC", "DEEDP"])
    assert acris_doc_type("deed, le") == "deed_life_estate" and acris_doc_type("MTGE") == "mortgage" and acris_doc_type("CMTG") is None


def test_party_codes_map_to_roles_and_party_3_means_life_estate_only_on_a_life_estate_deed():
    assert acris_role_type("deed", 1) == "grantor" and acris_role_type("deed", "2") == "grantee"
    assert acris_role_type("deed_life_estate", 3) == "life_estate_retained"
    assert acris_role_type("deed", 3) is None and acris_role_type("deed_other", 3) is None


def test_out_of_range_document_dates_are_kept_as_text_not_dates():
    base = {"documentid": "X1", "doctype": "DEED", "recordedfiled": "2020-01-02", "docamount": 0, "crfn": None}
    ok = document_node({**base, "docdate": "2020-01-01T05:00:00Z"}, SNAP, SNAP_DATE)
    assert ok["doc_date"] == date(2020, 1, 1) and "doc_date_raw" not in ok
    for bad in ("0001-04-05T04:56:02Z", "2028-09-17T04:00:00Z"):
        n = document_node({**base, "docdate": bad}, SNAP, SNAP_DATE)
        assert "doc_date" not in n and n["doc_date_raw"] == bad[:10]


def test_party_identity_is_name_and_address_and_cannot_meet_an_hpd_party():
    a = {"documentid": "D", "partytype": 2, "name": "5413 PLAZA LLC", "address1": "746  61ST STREET", "zip": "11220"}
    assert party_id(a) == party_id({**a, "documentid": "E", "partytype": 1, "address1": "746 61ST STREET"})
    assert party_id(a) != party_id({**a, "zip": "11221"})
    assert re.fullmatch(r"acris:[0-9a-f]{32}", party_id(a))
    n = party_nodes(a, "deed", SNAP)
    assert n["party"]["name_n1"] == "5413 PLAZA LLC" and n["party"]["address_key"] and n["role"]["role_type"] == "grantee"


# ---- the anchors in the graph ---------------------------------------------------------------------------------

@pytest.fixture
def deeds(session, schema):
    apply_schema(session, schema)
    tx = session.begin_transaction()
    register_snapshot(tx, SNAP, "justfixwow", SNAP_DATE)
    load_pluto(tx, schema, ANCH["pluto"], SNAP)
    load_hpd(tx, schema, ANCH["registrations"], ANCH["contacts"], SNAP)
    load_acris(tx, schema, AC["documents"], AC["parties"], AC["legals"], LOTS, SNAP, SNAP_DATE)
    tag_acris(tx, AC["documents"], AC["parties"])
    yield tx
    tx.rollback()


def test_acris_rules_exist_and_the_loaded_deeds_pass_them(deeds):
    from etl.validate import compiled_rules
    names = [n for n, _ in compiled_rules()]
    for shape in ACRIS_RULES:
        assert any(n.startswith(shape) for n in names), shape
    assert validate(deeds, only=ACRIS_RULES + ("role_attachment", "snapshot_reference"), scope=SCOPE) == []


def test_loading_twice_changes_nothing(deeds, schema):
    before = deeds.run("MATCH (n) RETURN count(n) AS c").single()["c"], deeds.run("MATCH ()-[r]->() RETURN count(r) AS c").single()["c"]
    load_acris(deeds, schema, AC["documents"], AC["parties"], AC["legals"], LOTS, SNAP, SNAP_DATE)
    assert (deeds.run("MATCH (n) RETURN count(n) AS c").single()["c"], deeds.run("MATCH ()-[r]->() RETURN count(r) AS c").single()["c"]) == before


def test_a_document_off_the_graph_lots_is_not_loaded(deeds, schema):
    n = deeds.run("MATCH (d:Document) RETURN count(d) AS c").single()["c"]
    load_acris(deeds, schema, AC["documents"], AC["parties"], AC["legals"], frozenset(), SNAP, SNAP_DATE)
    assert deeds.run("MATCH (d:Document) RETURN count(d) AS c").single()["c"] == n


@pytest.mark.parametrize("anchor,exp", list(_expected_docs()))
def test_q3_deeds_match(deeds, anchor, exp):
    d = deeds.run("MATCH (d:Document {document_id: $id}) RETURN d {.*} AS d", id=exp["document_id"]).single()["d"]
    assert (d["doc_date"].iso_format(), d["recorded"].iso_format(), d["amount"]) == (exp["doc_date"], exp["recorded"], exp["amount"])
    assert d["source"] == "acris_master" and d["doc_type"] in {"deed", "deed_other", "deed_timeshare", "deed_life_estate"}


@pytest.mark.parametrize("anchor", list(EXP))
def test_q3_latest_deeds_and_their_grantees(deeds, anchor):
    exp = EXP[anchor]
    rows = deeds.run("""MATCH (l:Lot {bbl: $bbl})<-[:ON_LOT]-(d:Document) WHERE d.doc_type = 'deed' AND d.doc_date IS NOT NULL
                        WITH d ORDER BY d.doc_date DESC, d.recorded DESC
                        WITH collect(d) AS ds WITH [x IN ds WHERE x.doc_date = ds[0].doc_date AND x.recorded = ds[0].recorded] AS latest
                        UNWIND latest AS d RETURN d.document_id AS id""", bbl=_bbl(anchor))
    assert sorted(r["id"] for r in rows) == sorted(d["document_id"] for d in exp["deeds"])
    want = {g["grantee"]: (g["address"], g["zip5"], g["grantee_n1"]) for g in exp["grantees"]}
    got = {}
    for d in exp["deeds"]:
        for r in deeds.run("""MATCH (:Document {document_id: $id})<-[:IN_DOCUMENT]-(r:AcrisRole {role_type: 'grantee'})-[:HELD_BY]->(p:AcrisParty)
                              RETURN p.party_name AS name, p.address_line1 AS a, p.zip AS z, p.name_n1 AS n1""", id=d["document_id"]):
            got[r["name"]] = (r["a"], (r["z"] or "")[:5] or None, r["n1"])
    # Anchor D has two tied deeds; the expected answer's grantees are those of its $45.8M deed (its note), the other
    # deed's grantees are also loaded.
    assert (got == want) if len(exp["deeds"]) == 1 else (want.items() <= got.items())


def _bbl(anchor: str) -> str:
    anchors = json.loads((ROOT / "evals" / "expected" / "slice1.json").read_text())["anchors"]
    return anchors[anchor]["bbl"]
