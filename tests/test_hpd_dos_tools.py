"""Q2, Q4 and Q5 tools against the anchor lots, loaded into nyclr inside a rolled-back transaction and checked against
the expected answers (evals/expected/slice1.json). Design notes 0014, 0016, 0017."""
import json
from datetime import date

import pytest

from agent.tools.dos import CAVEATS_Q5, dos_record
from agent.tools.hpd import contacts, registrations
from etl.build import load_hpd, load_nodes, load_pluto
from etl.config import ROOT
from etl.dos import dos_entity_node
from etl.load import apply_schema, register_snapshot

SNAP, SNAP_DATE = "justfixwow-2026-05-29", date(2026, 5, 29)
FX = ROOT / "tests" / "fixtures"
ANCH, DOS = (json.loads((FX / f).read_text()) for f in ("slice1_anchors.json", "slice1_dos.json"))
EXPECTED = json.loads((ROOT / "evals" / "expected" / "slice1.json").read_text())
Q2, Q4, Q5 = (EXPECTED["questions"][q] for q in ("Q2", "Q4", "Q5"))
BBL = {k: v["bbl"] for k, v in EXPECTED["anchors"].items()}


@pytest.fixture
def graph(session, schema):
    apply_schema(session, schema)
    tx = session.begin_transaction()
    register_snapshot(tx, SNAP, "justfixwow", SNAP_DATE)
    load_pluto(tx, schema, ANCH["pluto"], SNAP)
    load_hpd(tx, schema, ANCH["registrations"], ANCH["contacts"], SNAP)
    load_nodes(tx, schema, "Party", (dos_entity_node(r, SNAP) for r in DOS), also=("DosEntity",))
    yield tx
    tx.rollback()


# ---- Q2 -----------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("anchor", [a for a, v in Q2.items() if not isinstance(v, str)])
def test_q2_registrations_match(graph, anchor):
    got = {r["registration_id"]: r for r in registrations(graph, BBL[anchor])["registrations"]}
    assert set(got) == {e["registration_id"] for e in Q2[anchor]}
    for e in Q2[anchor]:
        r = got[e["registration_id"]]
        assert (r["last_registration_date"], r["registration_end_date"], r["hpd_building_id"]) == (e["last_registration_date"], e["registration_end_date"], e["hpd_building_id"])
        assert [(b["bin"], b["address_text"]) for b in r["buildings"]] == [(e["bin"], f'{e["house_number"]} {e["street_name"]}')] or r["buildings"][0]["bin"] == e["bin"]
        assert [(o["name"], o["contact_type"]) for o in r["registered_owners"]] == [(e["registered_owner"], e["owner_contact_type"])]
        assert (r["source"], r["snapshot_id"], r["snapshot_date"]) == ("hpd_registrations", SNAP, "2026-05-29")


def test_q2_a_period_that_ended_before_the_snapshot_is_marked_and_a_current_one_is_not(graph):
    assert registrations(graph, BBL["E"])["registrations"][0]["registration_end_date_before_snapshot"] is True    # ended 2021-09-01
    assert registrations(graph, BBL["A"])["registrations"][0]["registration_end_date_before_snapshot"] is False   # ends 2026-09-01


def test_q2_no_registration_is_not_exemption_and_caveats_are_stated(graph):
    r = registrations(graph, BBL["F"])
    assert r["status"] == "no_registration" and "not 'the building is exempt'" in r["note"]
    assert any("not who holds title" in c for c in registrations(graph, BBL["A"])["caveats"])
    assert registrations(graph, "3999999999")["status"] == "lot_absent"


# ---- Q4 -----------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("anchor", [a for a, v in Q4.items() if not isinstance(v, str)])
def test_q4_contacts_match(graph, anchor):
    got = {r["registration_id"]: {c["contact_id"]: c for c in r["contacts"]} for r in contacts(graph, BBL[anchor])["registrations"]}
    assert set(got) == set(Q4[anchor])
    for reg_id, expected in Q4[anchor].items():
        assert set(got[reg_id]) == {c["contact_id"] for c in expected}
        for e in expected:
            c = got[reg_id][e["contact_id"]]
            assert (c["hpd_type"], c.get("title"), c.get("organization_name"), c.get("person_name")) == (e["type"], e["title"], e["organization_name"], e["person_name"])
            assert (c["source"], c["reliability"], c["snapshot_id"]) == ("hpd_contacts", "I", SNAP)
            ea = e["business_address"] or {}
            assert (c["business_address"].get("house"), c["business_address"].get("zip")) == (ea.get("house_number"), ea.get("zip5"))


def test_q4_management_is_grouped_apart_from_registered_principals(graph):
    cs = {c["hpd_type"]: c for c in contacts(graph, BBL["A"])["registrations"][0]["contacts"]}
    assert cs["Agent"]["grouping"] == "management" and cs["SiteManager"]["grouping"] == "management"
    assert cs["CorporateOwner"]["grouping"] == "registered principal" and cs["HeadOfficer"]["title"] == "PRESIDENT"
    assert any("not ownership" in c for c in contacts(graph, BBL["A"])["caveats"])


def test_q4_no_registration_says_so(graph):
    assert contacts(graph, BBL["F"])["status"] == "no_registration"


# ---- Q5 -----------------------------------------------------------------------------------------------------

def _expected_records():
    for anchor, e in Q5.items():
        for key in ("record", "other", "deed_grantee_record"):
            if e.get(key):
                yield pytest.param(e[key], id=f"{anchor}-{key}")


@pytest.mark.parametrize("exp", list(_expected_records()))
def test_q5_record_matches(graph, exp):
    r = dos_record(graph, exp["entity_name"])
    rec = next(x for x in r["records"] if x["dos_id"] == exp["dos_id"])
    assert (rec["entity_type"], rec["initial_filing_date"], rec["process_name"]) == (exp["entity_type"], exp["initial_filing_date"], exp["process_name"])
    assert rec["process_address"].replace(",", "") == exp["process_address"].replace(",", "")
    assert rec["registered_agent"] == exp["registered_agent"] and rec["source"] == "dos_active_corporations" and rec["snapshot_id"] == SNAP


@pytest.mark.parametrize("name", ["KS Turnpike LLC", "438 52 ST OWNERS CORP", "HP SUNSET PARK I HDFC INC.", "HP SUNSET PARK I HOUSING DEV FUND COMPANY, INC"])
def test_q5_a_spelling_with_no_match_says_no_record_and_what_was_tried(graph, name):
    r = dos_record(graph, name)
    assert r["status"] == "no_record" and r["variants_tried"] and "not 'does not exist'" in " ".join(r["caveats"])


def test_q5_spelling_decides_the_match_for_anchor_c_and_g(graph):
    assert dos_record(graph, "438 52ND ST OWNERS CORP")["records"][0]["dos_id"] == "2733264"     # deed and PLUTO spelling
    assert dos_record(graph, "K S TURNPIKE LLC")["records"][0]["dos_id"] == "3574572"


def test_q5_process_name_kinds(graph):
    assert dos_record(graph, "5413 PLAZA LLC")["records"][0]["process_name_kind"] == "entitys_own_name"
    assert dos_record(graph, "606 56TH ST LLC")["records"][0]["process_name_kind"] == "statutory_default"
    assert dos_record(graph, "K S TURNPIKE LLC")["records"][0]["process_name_kind"] == "other_name"   # a person, anchor G


def test_q5_caveats_name_the_limits(graph):
    c = " ".join(dos_record(graph, "5413 PLAZA LLC")["caveats"])
    assert "active entities only" in c and "not carried for LLCs" in c and "lead" in c
