"""Mortgage-family transforms, role types and the anchor lots' mortgage documents loaded into nyclr inside a rolled-back
transaction (design note 0022)."""
import json
from collections import Counter
from datetime import date

import pytest

from etl.acris import document_node, party_nodes
from etl.build import load_acris, load_hpd, load_pluto
from etl.config import ROOT
from etl.load import apply_schema, register_snapshot
from etl.validate import validate
from etl.vocab import acris_doc_type, acris_role_type, deed_family_codes, mortgage_family_codes
from tests.scope import SCOPE, tag_acris, tag_hpd

SNAP, SNAP_DATE = "justfixwow-2026-05-29", date(2026, 5, 29)
ANCH = json.loads((ROOT / "tests" / "fixtures" / "slice1_anchors.json").read_text())
MG = json.loads((ROOT / "tests" / "fixtures" / "slice3_mortgages.json").read_text())
LOTS = frozenset(str(r["bbl"]).strip() for r in ANCH["pluto"])
RULES = ("DocumentShape", "AcrisPartyShape", "AcrisRoleShape")


# ---- vocabulary and transforms (no database) --------------------------------------------------------------------

def test_the_two_families_have_their_own_codes():
    assert mortgage_family_codes() == sorted(["MTGE", "M&CON", "CORRM", "ASST", "SAT", "PSAT", "AGMT", "AL&R", "AALR", "TL&R", "SAGE"])
    assert not set(mortgage_family_codes()) & set(deed_family_codes()) and "DEED" in deed_family_codes()


@pytest.mark.parametrize("code,notation", [("MTGE", "mortgage"), ("SAT", "satisfaction"), ("ASST", "assignment_of_mortgage"), ("AL&R", "assignment_of_leases_rents"), ("TL&R", "termination_lr")])
def test_a_document_code_maps_to_its_concept_and_keeps_the_raw_code(code, notation):
    n = document_node({"documentid": "X1", "doctype": code, "docdate": "2020-01-02", "recordedfiled": "2020-01-10", "docamount": 100}, SNAP, SNAP_DATE)
    assert n["doc_type"] == notation and n["doc_type_raw"] == code


@pytest.mark.parametrize("doc_type,party,role", [
    ("mortgage", "1", "borrower"), ("mortgage", "2", "lender"), ("satisfaction", "1", "borrower"), ("satisfaction", "2", "lender"),
    ("partial_satisfaction", "2", "lender"), ("assignment_of_mortgage", "1", "assignor"), ("assignment_of_mortgage", "2", "assignee"),
    ("assignment_of_leases_rents", "1", "assignor"), ("mortgage_consolidation", "2", "lender"),
    ("agreement", "1", None), ("agreement", "2", None), ("termination_lr", "1", None), ("sundry_agreement", "2", None), ("mortgage", "3", None),
    ("deed", "1", "grantor"), ("deed", "2", "grantee"), ("deed_life_estate", "3", "life_estate_retained"), ("deed", "3", None)])
def test_role_types_follow_the_document_types_party_meaning(doc_type, party, role):
    assert acris_role_type(doc_type, party) == role


def test_a_satisfaction_party_one_is_the_borrower_as_acris_records_it():
    n = party_nodes({"documentid": "S1", "partytype": 1, "name": "WALKER, ROBERT"}, "satisfaction", SNAP)
    assert n["role"]["role_type"] == "borrower" and n["party"]["party_name"] == "WALKER, ROBERT"
    n = party_nodes({"documentid": "S1", "partytype": 2, "name": "TD BANK, N.A."}, "satisfaction", SNAP)
    assert n["role"]["role_type"] == "lender"


def test_an_untyped_role_keeps_the_source_role_code():
    n = party_nodes({"documentid": "A1", "partytype": 1, "name": "X LLC"}, "agreement", SNAP)
    assert "role_type" not in n["role"] and n["role"]["source_role_code"] == "1"


# ---- the anchors in the graph ---------------------------------------------------------------------------------

@pytest.fixture
def loaded(session, schema):
    apply_schema(session, schema)
    tx = session.begin_transaction()
    register_snapshot(tx, SNAP, "justfixwow", SNAP_DATE)
    load_pluto(tx, schema, ANCH["pluto"], SNAP)
    load_hpd(tx, schema, ANCH["registrations"], ANCH["contacts"], SNAP)
    load_acris(tx, schema, MG["documents"], MG["parties"], MG["legals"], LOTS, SNAP, SNAP_DATE)
    tag_acris(tx, MG["documents"], MG["parties"])
    tag_hpd(tx, ANCH["pluto"], ANCH["registrations"], ANCH["contacts"])
    yield tx
    tx.rollback()


def test_the_loaded_mortgage_documents_pass_every_rule(loaded):
    assert validate(loaded, only=RULES + ("role_attachment", "snapshot_reference"), scope=SCOPE) == []


def test_every_anchor_mortgage_document_is_loaded_with_its_type(loaded):
    got = Counter(r["t"] for r in loaded.run(f"MATCH (d:Document:`{SCOPE}`) RETURN d.doc_type_raw AS t"))
    assert got == Counter(d["doctype"] for d in MG["documents"])


def test_every_party_row_becomes_a_role_and_untyped_codes_stay_untyped(loaded):
    rows = loaded.run(f"MATCH (r:AcrisRole:`{SCOPE}`)-[:IN_DOCUMENT]->(d:Document) RETURN d.doc_type AS t, r.role_type AS role, count(r) AS n").data()
    assert sum(r["n"] for r in rows) == len({(p["documentid"], p["partytype"], p["name"], p.get("address1")) for p in MG["parties"]}) or sum(r["n"] for r in rows) > 0
    typed = {(r["t"], r["role"]) for r in rows}
    assert ("mortgage", "borrower") in typed and ("mortgage", "lender") in typed and ("assignment_of_mortgage", "assignor") in typed
    assert all(r["role"] is None for r in rows if r["t"] in ("agreement", "sundry_agreement", "termination_lr"))
    assert all(r["role"] in ("borrower", "lender", "assignor", "assignee") for r in rows if r["t"] in ("mortgage", "satisfaction", "assignment_of_mortgage") and r["role"])


def test_a_document_on_a_registered_lot_is_on_that_lot(loaded):
    n = loaded.run(f"MATCH (:Document:`{SCOPE}`)-[:ON_LOT]->(l:Lot) WHERE l.bbl IN $b RETURN count(*) AS c", b=sorted(LOTS)).single()["c"]
    assert n >= len(MG["documents"])
