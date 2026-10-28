"""Violation transforms, and the anchor violations loaded into nyclr inside a rolled-back transaction, with the Q15 tool
checked against counts taken from the fixture rows and from the source (design note 0020)."""
import json
from collections import Counter
from datetime import date

import pytest

from agent.tools.conditions import violations
from etl.build import load_hpd, load_pluto, load_violations, set_as_of
from etl.conditions import violation_node
from etl.config import ROOT
from etl.load import register_snapshot
from etl.validate import validate
from tests.scope import SCOPE, tag, tag_hpd

SNAP, SNAP_DATE, AS_OF = "justfixwow-2026-05-29", date(2026, 5, 29), date(2026, 7, 9)
ROWS = json.loads((ROOT / "tests" / "fixtures" / "slice2_violations.json").read_text())["rows"]
ANCHORS = json.loads((ROOT / "tests" / "fixtures" / "slice1_anchors.json").read_text())
A, B, C, D, E, F, G = "3008260002", "3008260005", "3008070024", "3008210012", "3008210019", "3008970014", "3008080025"   # F has no violation in the data


def _row(**kw):
    return {"violationid": 7, "registrationid": 9, "class": "B", "inspectiondate": "2023-03-25", "novissueddate": "2023-04-01", "currentstatus": "NOV SENT OUT",
            "currentstatusdate": "2023-04-02", "violationstatus": "Open", "rentimpairing": False, "bbl": "3000000001", "bin": "3000001", **kw}


# ---- transforms (no database) --------------------------------------------------------------------------------

def test_violation_has_vocabulary_class_status_group_and_provenance():
    n = violation_node(_row(), SNAP, AS_OF)
    assert (n["violation_class"], n["status_group"], n["inspection_date"]) == ("B", "open", date(2023, 3, 25))
    assert (n["source"], n["reliability"], n["source_record_id"], n["registration_id"]) == ("hpd_violations", "I", "7", "9")
    assert "apartment" not in n and "story" not in n


@pytest.mark.parametrize("status,group", [("Open", "open"), ("Close", "closed")])
def test_status_group_follows_the_source_status(status, group):
    assert violation_node(_row(violationstatus=status), SNAP, AS_OF)["status_group"] == group


def test_a_sentinel_status_date_and_a_future_inspection_are_kept_as_text():
    n = violation_node(_row(currentstatusdate="9999-12-11", inspectiondate="2026-08-01"), SNAP, AS_OF)
    assert "current_status_date" not in n and n["current_status_date_raw"] == "9999-12-11"
    assert "inspection_date" not in n and n["inspection_date_raw"] == "2026-08-01"


def test_a_row_without_a_class_is_not_a_violation_node():
    assert violation_node(_row(**{"class": None}), SNAP, AS_OF) is None


# ---- the anchors in the graph ---------------------------------------------------------------------------------

@pytest.fixture
def loaded(tx, schema):
    load_pluto(tx, schema, ANCHORS["pluto"], SNAP)
    load_hpd(tx, schema, ANCHORS["registrations"], ANCHORS["contacts"], SNAP)
    register_snapshot(tx, SNAP, "justfixwow", SNAP_DATE)
    set_as_of(tx, SNAP, "hpd_violations_as_of", AS_OF)
    counts = load_violations(tx, schema, ROWS, frozenset(r["bbl"] for r in ANCHORS["pluto"]), SNAP, AS_OF)
    tag_hpd(tx, ANCHORS["pluto"], ANCHORS["registrations"], ANCHORS["contacts"])
    tag(tx, "Violation", "violation_id", [r["violationid"] for r in ROWS])
    return tx, counts


def test_every_anchor_violation_is_loaded_on_its_lot(loaded):
    tx, counts = loaded
    assert counts["Violation"] == len(ROWS) and counts["skipped (lot not in graph)"] == 0
    assert tx.run(f"MATCH (:Violation:`{SCOPE}`)-[:ON_LOT]->(:Lot) RETURN count(*) AS c").single()["c"] == len(ROWS)


def test_the_loaded_violations_validate(loaded):
    tx, _ = loaded
    bad = validate(tx, scope=SCOPE)
    assert bad == [], [(v.rule, v.detail[:120]) for v in bad[:3]]


def test_q15_counts_agree_with_the_fixture_rows_for_every_anchor(loaded):
    tx, _ = loaded
    for bbl in (A, B, C, D, E, G):
        rows = [r for r in ROWS if r["bbl"] == bbl]
        want = Counter((r["class"], "open" if r["violationstatus"] == "Open" else "closed") for r in rows)
        got = violations(tx, bbl)
        for cls, c in got["by_class"].items():
            assert (c["open"], c["closed"]) == (want[(cls, "open")], want[(cls, "closed")]), (bbl, cls)
        assert sum(sum(c.values()) for c in got["by_class"].values()) == len(rows)


def test_q15_anchor_c_two_open_class_b_and_two_open_class_c(loaded):
    tx, _ = loaded
    r = violations(tx, C)
    assert r["status"] == "found" and r["by_class"]["B"] == {"open": 2, "closed": 3} and r["by_class"]["C"] == {"open": 2, "closed": 2}
    assert r["open_total"] == 4 and r["open_class_i"] == 0 and r["oldest_open_inspection_date"] == "2023-03-25"
    assert r["violation_data_as_of"] == "2026-07-09" and r["inspected_after_snapshot_date"] == 0
    assert r["by_building"] == [{"bin": "3013901", "open": 4, "closed": 6}] and "BIN" in r["by_building_note"]


def test_q15_class_i_is_kept_apart_from_a_b_and_c(loaded):
    tx, _ = loaded
    r = violations(tx, E)
    assert r["by_class"]["I"] == {"open": 2, "closed": 0} and r["open_class_i"] == 2
    assert r["open_classes_a_b_c"] == 8 + 19 + 5 and r["open_total"] == r["open_classes_a_b_c"] + 2
    assert r["oldest_open_inspection_date"] == "2023-11-21" and r["oldest_open"][0]["violation_class"] == "I"


def test_q15_violations_inspected_after_the_snapshot_date_are_counted(loaded):
    tx, _ = loaded
    r = violations(tx, A)
    assert r["inspected_after_snapshot_date"] == sum(1 for x in ROWS if x["bbl"] == A and x["inspectiondate"] > "2026-05-29") >= 3
    assert r["latest_inspection_date"] == "2026-06-24"


def test_q15_the_rate_uses_open_a_b_c_and_pluto_residential_units(loaded):
    tx, _ = loaded
    r = violations(tx, C)
    units = tx.run("MATCH (l:Lot {bbl: $b}) RETURN l.units_residential AS u", b=C).single()["u"]
    assert r["residential_units"] == units and r["open_a_b_c_per_residential_unit"] == round(4 / units, 2)


def test_q15_a_lot_with_no_violation_does_not_claim_none_ever_existed(loaded):
    tx, _ = loaded
    r = violations(tx, F)
    assert r["status"] == "no_violation" and "does not show" in r["note"]


def test_q15_an_unknown_lot_is_lot_absent(loaded):
    tx, _ = loaded
    assert violations(tx, "9999999999")["status"] == "lot_absent"
