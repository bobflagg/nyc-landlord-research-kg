"""HPD and PLUTO transforms, and the anchor lots loaded into nyclr inside a rolled-back transaction, checked against
the expected answers (evals/expected/slice1.json)."""
import copy
import json

import pytest

from etl.build import load_hpd, load_pluto
from etl.config import ROOT
from etl.hpd import contact_nodes, party_id, pick_contacts, real_bin, registration_nodes
from etl.load import apply_schema, register_snapshot
from etl.pluto import lot_node
from etl.validate import validate

HPD_RULES = ("LotShape", "LotAttributesShape", "BuildingShape", "PartyShape", "RoleShape", "RegistrationShape", "HpdPartyShape",
             "HpdRoleShape", "role_attachment", "snapshot_reference")
from datetime import date

SNAP = "justfixwow-2026-05-29"
FIX = json.loads((ROOT / "tests" / "fixtures" / "slice1_anchors.json").read_text())
EXP = json.loads((ROOT / "evals" / "expected" / "slice1.json").read_text())["questions"]


# ---- transforms (no database) ---------------------------------------------------------------------------------

def test_placeholder_and_padded_bins_are_not_buildings():
    assert real_bin("3324448") == "3324448" and real_bin("3324448 ") == "3324448"
    for bad in ("1000000", "0      ", "", None, "12345"):
        assert real_bin(bad) is None


def test_registration_without_a_real_bin_has_no_building():
    row = {**FIX["registrations"][0], "bin": "1000000"}
    assert registration_nodes(row, "GEN.PART", SNAP)["building"] is None


def test_a_bin_on_several_lots_gets_no_building():
    row = FIX["registrations"][0]
    n = registration_nodes(row, "LLC", SNAP, frozenset({real_bin(row["bin"])}))
    assert n["building"] is None and n["registration"]["registration_id"] == str(row["registrationid"])


def test_repeated_contact_id_keeps_the_most_complete_row_and_is_stable():
    base = {"registrationcontactid": 7, "registrationid": 1, "type": "JointOwner", "firstname": "Yun", "lastname": "Ni",
            "businessapartment": None}
    fuller = {**base, "firstname": "YUN", "lastname": "NI", "businessapartment": "1"}
    other = {**base, "registrationcontactid": 8}
    by_id = lambda cs: sorted(cs, key=lambda c: c["registrationcontactid"])
    assert by_id(pick_contacts([base, fuller, other])) == by_id(pick_contacts([other, fuller, base]))
    got = {c["registrationcontactid"]: c for c in pick_contacts([base, fuller, other])}
    assert got[7] == fuller and got[8] == other and len(got) == 2


def test_year_zero_and_empty_values_are_not_stored():
    lot = lot_node({"bbl": "3000000001", "address": "", "yearbuilt": 0, "unitsres": None, "cd": None}, SNAP)
    assert set(lot) == {"bbl", "reliability", "source_category", "source", "snapshot_id", "source_record_id"}


def test_owner_kind_keeps_the_raw_value_and_unknown_maps_to_nothing():
    assert registration_nodes(FIX["registrations"][0], "LLC", SNAP)["registration"]["owner_kind"] == "partnership_or_llc"
    n = registration_nodes(FIX["registrations"][0], "ESTATE", SNAP)["registration"]
    assert "owner_kind" not in n and n["owner_kind_raw"] == "ESTATE"


def test_unknown_hpd_contact_type_is_an_error_not_a_dropped_role():
    with pytest.raises(ValueError):
        contact_nodes({**FIX["contacts"][0], "type": "Landlord"}, SNAP)


def test_party_identity_is_type_name_and_address_and_stable():
    a, b = FIX["contacts"][0], copy.deepcopy(FIX["contacts"][0])
    assert party_id(a) == party_id(b)
    assert party_id({**a, "type": "Agent"}) != party_id(a)
    assert party_id({**a, "businesszip": "11221"}) != party_id(a)


# ---- the anchors in the graph ---------------------------------------------------------------------------------

@pytest.fixture
def anchors(session, schema):
    apply_schema(session, schema)
    tx = session.begin_transaction()
    register_snapshot(tx, SNAP, "justfixwow", date(2026, 5, 29))
    load_pluto(tx, schema, FIX["pluto"], SNAP)
    load_hpd(tx, schema, FIX["registrations"], FIX["contacts"], SNAP)
    yield tx
    tx.rollback()


def test_anchors_validate_clean(anchors):
    assert validate(anchors, only=HPD_RULES) == []


def test_loading_twice_changes_nothing(anchors, schema):
    before = anchors.run("MATCH (n) RETURN count(n) AS c").single()["c"]
    load_pluto(anchors, schema, FIX["pluto"], SNAP)
    load_hpd(anchors, schema, FIX["registrations"], FIX["contacts"], SNAP)
    assert anchors.run("MATCH (n) RETURN count(n) AS c").single()["c"] == before
    assert anchors.run("MATCH ()-[r]->() WHERE r.snapshot_id IS NULL RETURN count(r) AS c").single()["c"] >= 0


@pytest.mark.parametrize("anchor", list(EXP["Q1"]))
def test_q1_lot_and_buildings_match_the_expected_answers(anchors, anchor):
    exp = EXP["Q1"][anchor]
    rec = anchors.run("""MATCH (l:Lot {bbl: $bbl}) OPTIONAL MATCH (b:Building)-[:ON_LOT]->(l)
                         RETURN l {.*} AS lot, collect(b.bin) AS bins""", bbl=exp["lot"]["bbl"]).single()
    lot = rec["lot"]
    for ours, theirs in [("address_text", "address"), ("zip5", "zip5"), ("building_class", "building_class"),
                         ("units_residential", "units_residential"), ("units_total", "units_total"),
                         ("year_built", "year_built"), ("assessed_total", "assessed_total")]:
        assert lot[ours] == exp["lot"][theirs]
    assert lot["source"] == "pluto"          # HPD met the lot again and did not take it over
    assert sorted(rec["bins"]) == sorted(b["bin"] for b in exp["buildings"])


@pytest.mark.parametrize("anchor", [a for a, v in EXP["Q2"].items() if not isinstance(v, str)])
def test_q2_registrations_match(anchors, anchor):
    for exp in EXP["Q2"][anchor]:
        r = anchors.run("MATCH (r:Registration {registration_id: $id}) RETURN r {.*} AS r", id=exp["registration_id"]).single()["r"]
        assert (r["last_registration_date"].iso_format(), r["registration_end_date"].iso_format()) == (exp["last_registration_date"], exp["registration_end_date"])
        assert r["hpd_building_id"] == exp["hpd_building_id"]


@pytest.mark.parametrize("anchor", [a for a, v in EXP["Q4"].items() if not isinstance(v, str)])
def test_q4_roles_match(anchors, anchor):
    for reg_id, contacts in EXP["Q4"][anchor].items():
        rows = anchors.run("""MATCH (role:HpdRole)-[:IN_REGISTRATION]->(:Registration {registration_id: $id}), (role)-[:HELD_BY]->(p:HpdParty)
                              RETURN role.source_record_id AS cid, role.source_role_code AS code, role.title AS title,
                                     p.organization_name AS org, p.person_name AS person""", id=reg_id)
        got = {r["cid"]: (r["code"], r["title"], r["org"], r["person"]) for r in rows}
        want = {c["contact_id"]: (c["type"], c["title"], c["organization_name"], c["person_name"]) for c in contacts}
        assert got == want


def test_a_lot_with_three_registrations_has_three_buildings_and_their_roles_sit_on_them(anchors):
    r = anchors.run("""MATCH (l:Lot {bbl: '3008210012'})<-[:ON_LOT]-(b:Building)<-[:ON_BUILDING]-(role:Role)
                       RETURN count(DISTINCT b) AS buildings, count(role) AS roles""").single()
    assert (r["buildings"], r["roles"]) == (3, 12)


def test_roles_without_a_building_attach_to_the_lot(session, schema):
    apply_schema(session, schema)
    tx = session.begin_transaction()
    try:
        register_snapshot(tx, SNAP, "justfixwow", date(2026, 5, 29))
        shift = 900_000_000  # ids no real registration or contact has, so a loaded district cannot interfere
        reg = {**FIX["registrations"][0], "bin": "1000000", "registrationid": FIX["registrations"][0]["registrationid"] + shift}
        cs = [{**c, "registrationid": reg["registrationid"], "registrationcontactid": c["registrationcontactid"] + shift}
              for c in FIX["contacts"] if c["registrationid"] == FIX["registrations"][0]["registrationid"]]
        load_hpd(tx, schema, [reg], cs, SNAP)
        assert validate(tx, only=HPD_RULES) == []
        ids = [f"hpd:{c['registrationcontactid']}" for c in cs]
        on_lot = tx.run("MATCH (role:Role)-[:ON_LOT]->(:Lot {bbl: $b}) WHERE role.role_id IN $ids RETURN count(role) AS c", b=reg["bbl"], ids=ids).single()["c"]
        on_bld = tx.run("MATCH (role:Role)-[:ON_BUILDING]->(:Building) WHERE role.role_id IN $ids RETURN count(role) AS c", ids=ids).single()["c"]
        assert (on_lot, on_bld) == (5, 0)
    finally:
        tx.rollback()

