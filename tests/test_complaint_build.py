"""Complaint-summary transforms, and the anchor groups loaded into nyclr inside a rolled-back transaction, with the Q27 tool
checked against counts taken from the fixture groups and from the source (design note 0020)."""
import json
from collections import defaultdict
from datetime import date

import pytest

from agent.tools.conditions import complaints
from etl.build import load_complaints, load_hpd, load_pluto, set_as_of
from etl.conditions import complaint_summary_node
from etl.config import ROOT
from etl.load import register_snapshot
from etl.validate import validate
from tests.scope import SCOPE, tag, tag_hpd

SNAP, SNAP_DATE, AS_OF = "justfixwow-2026-05-29", date(2026, 5, 29), date(2026, 7, 7)
FIX = json.loads((ROOT / "tests" / "fixtures" / "slice2_complaints.json").read_text())
ANCHORS = json.loads((ROOT / "tests" / "fixtures" / "slice1_anchors.json").read_text())
LOTS = frozenset(r["bbl"] for r in ANCHORS["pluto"])
A, B, C, D, E, F, G = "3008260002", "3008260005", "3008070024", "3008210012", "3008210019", "3008970014", "3008080025"


def _group(**kw):
    return {"bbl": "3000000001", "bin": "3000001", "year": 2024, "group_value": "NON EMERGENCY", "problemstatus": "CLOSE", "problems": 3, "duplicates": 1,
            "complaints": 2, "latest_received": "2024-05-01", **kw}


# ---- transforms (no database) --------------------------------------------------------------------------------

def test_type_summary_has_vocabulary_value_counts_and_provenance():
    n = complaint_summary_node(_group(), "type", SNAP)
    assert (n["group_value"], n["group_value_raw"], n["problem_count"], n["duplicate_problem_count"], n["complaint_count"]) == ("non_emergency", "NON EMERGENCY", 3, 1, 2)
    assert n["summary_id"] == "3000000001|3000001|type|non_emergency|2024|CLOSE" and n["latest_received"] == date(2024, 5, 1)
    assert (n["source"], n["reliability"], n["source_record_id"]) == ("hpd_complaints", "I", n["summary_id"])


def test_category_summary_keeps_the_category_and_has_no_complaint_count():
    n = complaint_summary_node(_group(group_value="HEAT/HOT WATER", complaints=None), "category", SNAP)
    assert n["group_value"] == "HEAT/HOT WATER" and "complaint_count" not in n and "group_value_raw" not in n


def test_no_private_field_can_reach_a_summary():
    n = complaint_summary_node(_group(apartment="3B", complaintanonymousflag=True, unittype="APARTMENT"), "type", SNAP)
    assert not {"apartment", "unit", "unittype", "complaintanonymousflag", "anonymous"} & set(n)


# ---- the anchors in the graph ---------------------------------------------------------------------------------

@pytest.fixture
def loaded(tx, schema):
    load_pluto(tx, schema, ANCHORS["pluto"], SNAP)
    load_hpd(tx, schema, ANCHORS["registrations"], ANCHORS["contacts"], SNAP)
    register_snapshot(tx, SNAP, "justfixwow", SNAP_DATE)
    set_as_of(tx, SNAP, "hpd_complaints_as_of", AS_OF)
    ids = []
    for grouping in ("type", "category"):
        counts = load_complaints(tx, schema, FIX[grouping], grouping, LOTS, SNAP)
        assert counts["skipped (lot not in graph)"] == 0
        ids += [complaint_summary_node(r, grouping, SNAP)["summary_id"] for r in FIX[grouping]]
    tag_hpd(tx, ANCHORS["pluto"], ANCHORS["registrations"], ANCHORS["contacts"])
    tag(tx, "ComplaintSummary", "summary_id", ids)
    return tx


def test_every_anchor_group_is_loaded_on_its_lot(loaded):
    n = loaded.run(f"MATCH (:ComplaintSummary:`{SCOPE}`)-[:ON_LOT]->(:Lot) RETURN count(*) AS c").single()["c"]
    assert n == len(FIX["type"]) + len(FIX["category"])


def test_the_loaded_summaries_validate(loaded):
    bad = validate(loaded, scope=SCOPE)
    assert bad == [], [(v.rule, v.detail[:120]) for v in bad[:3]]


@pytest.mark.parametrize("bbl", [A, B, C, D, E, G])
@pytest.mark.parametrize("since", [None, 2022])
def test_q27_counts_agree_with_the_fixture_groups(loaded, bbl, since):
    rows = [r for r in FIX["type"] if r["bbl"] == bbl and r["year"] >= (since or 0)]
    r = complaints(loaded, bbl, since)
    if not rows:
        assert r["status"] == "no_complaint"
        return
    by_type, by_status = defaultdict(int), defaultdict(int)
    for x in rows:
        by_type[x["group_value"].lower().replace(" ", "_")] += x["problems"]
        by_status[x["problemstatus"]] += x["problems"]
    assert {k: v["problems"] for k, v in r["by_type"].items()} == dict(by_type)
    assert r["problems"] == sum(by_type.values()) and (r["open_problems"], r["closed_problems"]) == (by_status["OPEN"], by_status["CLOSE"])
    cats = sum(x["problems"] for x in FIX["category"] if x["bbl"] == bbl and x["year"] >= (since or 0))
    assert sum(r["by_major_category"].values()) == cats == r["problems"]


def test_q27_anchor_c_since_2022(loaded):
    r = complaints(loaded, C, 2022)
    assert r["status"] == "found" and r["problems"] == 39 and r["latest_received"] == "2026-04-20" and r["duplicate_problems_left_out"] == 6
    assert r["complaint_data_as_of"] == "2026-07-07" and r["counted"] == "problem rows, duplicates left out"
    assert r["problems_per_residential_unit"] == round(39 / r["residential_units"], 2)


def test_q27_lists_the_years_that_have_problems_instead_of_a_range(loaded):
    r = complaints(loaded, C, 2022)
    assert r["years_with_problems"] == sorted({x["year"] for x in FIX["type"] if x["bbl"] == C and x["year"] >= 2022}) and "first_year_with_a_problem" not in r


def test_q27_says_what_is_counted_and_that_no_apartment_detail_exists(loaded):
    r = complaints(loaded, C, 2022)
    text = " ".join(r["caveats"])
    assert "not a finding" in text and "No apartment, unit or complainant detail" in text and "do not add up" in text


def test_q27_a_lot_with_no_complaint_says_so(loaded):
    r = complaints(loaded, F, None)
    assert r["status"] == "no_complaint"


def test_q27_an_unknown_lot_is_lot_absent(loaded):
    assert complaints(loaded, "9999999999", 2022)["status"] == "lot_absent"
