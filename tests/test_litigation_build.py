"""Litigation transforms, and the anchor cases loaded into nyclr inside a rolled-back transaction, with the Q28 tool
checked against them (design note 0020)."""
import json
from datetime import date

import pytest

from agent.tools.conditions import litigation
from etl.build import load_litigation, set_as_of
from etl.conditions import litigation_node
from etl.config import ROOT
from etl.load import apply_schema, register_snapshot
from etl.validate import validate
from tests.scope import SCOPE, tag_hpd, tag_litigation

SNAP, SNAP_DATE, AS_OF = "justfixwow-2026-05-29", date(2026, 5, 29), date(2026, 7, 7)
ROWS = json.loads((ROOT / "tests" / "fixtures" / "slice2_litigation.json").read_text())["rows"]
BBLS = ("3008070024", "3008080025", "3008260002", "3008260005")


def _row(**kw):
    return {"litigationid": 1, "casetype": "Tenant Action", "caseopendate": "2023-05-15", "casestatus": "CLOSED", "respondent": "A LLC,B C", "bbl": "3000000001", **kw}


# ---- transforms (no database) --------------------------------------------------------------------------------

def test_case_has_vocabulary_type_provenance_and_split_respondents():
    n = litigation_node(_row(respondent="438 52 STREET OWNERS CORPORATION,SAHIT HADZOVIC"), SNAP, AS_OF)
    assert n["case_type"] == "tenant_action" and n["case_type_raw"] == "Tenant Action" and n["case_open_date"] == date(2023, 5, 15)
    assert n["respondent_names"] == ["438 52 STREET OWNERS CORPORATION", "SAHIT HADZOVIC"] and n["respondent_names_n1"] == ["438 52 STREET OWNERS CORPORATION", "SAHIT HADZOVIC"]
    assert (n["source"], n["reliability"], n["source_record_id"]) == ("hpd_litigations", "I", "1")


@pytest.mark.parametrize("opened,prop", [("0204-03-28", "case_open_date_raw"), ("2030-10-05", "case_open_date_raw"), ("2026-03-24", "case_open_date")])
def test_open_dates_outside_1900_to_as_of_are_kept_as_text(opened, prop):
    n = litigation_node(_row(caseopendate=opened), SNAP, AS_OF)
    assert prop in n and ("case_open_date" in n) == (prop == "case_open_date")


def test_status_with_a_date_is_split_and_the_raw_text_kept():
    n = litigation_node(_row(casestatus="GRANTED - 03/05/2020"), SNAP, AS_OF)
    assert n["case_status"] == "GRANTED" and n["case_status_raw"] == "GRANTED - 03/05/2020"


def test_unknown_case_type_keeps_the_raw_value_only():
    n = litigation_node(_row(casetype="Brand New Type"), SNAP, AS_OF)
    assert "case_type" not in n and n["case_type_raw"] == "Brand New Type"


# ---- the anchors in the graph ---------------------------------------------------------------------------------

@pytest.fixture
def cases(tx, schema):
    """The sample load plus the anchor cases; their lots and registrations come from the anchor fixture."""
    anchors = json.loads((ROOT / "tests" / "fixtures" / "slice1_anchors.json").read_text())
    from etl.build import load_hpd, load_pluto
    load_pluto(tx, schema, anchors["pluto"], SNAP)
    load_hpd(tx, schema, anchors["registrations"], anchors["contacts"], SNAP)
    register_snapshot(tx, SNAP, "justfixwow", SNAP_DATE)
    set_as_of(tx, SNAP, "hpd_litigation_as_of", AS_OF)
    counts = load_litigation(tx, schema, ROWS, frozenset(r["bbl"] for r in anchors["pluto"]), SNAP, AS_OF)
    tag_hpd(tx, anchors["pluto"], anchors["registrations"], anchors["contacts"])
    tag_litigation(tx, ROWS)
    return tx, counts


def test_every_anchor_case_is_loaded_on_its_lot_and_building(cases):
    tx, counts = cases
    assert counts["Litigation"] == 11 and counts["skipped (lot not in graph)"] == 0
    assert tx.run(f"MATCH (:Litigation:`{SCOPE}`)-[:ON_LOT]->(:Lot) RETURN count(*) AS c").single()["c"] == 11
    assert tx.run(f"MATCH (:Litigation:`{SCOPE}`)-[:ON_BUILDING]->(:Building) RETURN count(*) AS c").single()["c"] == 11


def test_the_loaded_cases_validate(cases):
    tx, _ = cases
    bad = validate(tx, scope=SCOPE)
    assert bad == [], [(v.rule, v.detail[:120]) for v in bad[:3]]


def test_q28_anchor_c_one_closed_tenant_action_with_the_owners_corporation_matching(cases):
    tx, _ = cases
    r = litigation(tx, "3008070024")
    assert r["status"] == "found" and r["case_count"] == 1 and r["litigation_data_as_of"] == "2026-07-07"
    c = r["cases"][0]
    assert (c["case_type"], c["case_open_date"], c["case_status"]) == ("tenant_action", "2023-05-15", "CLOSED") and c["finding_of_harassment"] == "none recorded in the data"
    assert c["building_bins"] == ["3013901"]
    first, second = c["respondents"]
    assert first["name_as_recorded"] == "438 52 STREET OWNERS CORPORATION" and second["name_as_recorded"] == "SAHIT HADZOVIC"
    assert first["role"].startswith("respondent") and first["source"] == "hpd_litigations"


def test_q28_a_lot_with_no_case_says_so_without_claiming_none_was_brought(cases):
    tx, _ = cases
    r = litigation(tx, "3008210012")
    assert r["status"] == "no_case" and "does not mean" in r["note"]


def test_q28_counts_by_status_and_a_missing_open_date(cases):
    tx, _ = cases
    r = litigation(tx, "3008260005")
    assert r["case_count"] == 3 and r["cases_by_status"] == {"PENDING": 3}
    assert any("case_open_date" not in c and "case_open_date_raw" not in c for c in r["cases"])


def test_q28_an_unknown_lot_is_lot_absent(cases):
    tx, _ = cases
    assert litigation(tx, "9999999999")["status"] == "lot_absent"


def test_q28_a_respondent_equal_to_the_registered_owner_by_exact_name_is_a_lead(cases):
    tx, _ = cases
    r = litigation(tx, "3008260005")
    by = {c["litigation_id"]: c for c in r["cases"]}
    plaza = by["405072"]["respondents"][0]
    assert plaza["name_as_recorded"] == "702 PLAZA LLC" and plaza["name_agreement_with_registered_owner"] == "exact_normalized"
    assert [m["registration_id"] for m in plaza["matches"]] == ["300258"]
    person = by["405072"]["respondents"][1]
    assert person["name_agreement_with_registered_owner"] == "none_found" and person["matches"] == []
    assert "lead" in " ".join(r["caveats"])
