"""The citywide graph agrees with the expected Slice 2 answers, which were derived from the source database without the graph
(evals/expected/derive_slice2.py). Read-only: the tools run against nyclr as it is. Design note 0020."""
import json

import pytest

from agent.db import read_session
from agent.tools.conditions import complaints, litigation, registration_status, violations
from etl.config import ROOT

EXP = json.loads((ROOT / "evals" / "expected" / "slice2.json").read_text())
Q, BBL = EXP["questions"], {k: v["bbl"] for k, v in EXP["anchors"].items()}
LETTERS = list(BBL)


@pytest.fixture(scope="module")
def runner():
    with read_session() as s:
        yield s


def test_the_as_of_dates_in_the_graph_are_the_ones_the_answers_were_derived_with(runner):
    got = runner.run("MATCH (s:Snapshot {snapshot_id: 'justfixwow-2026-05-29'}) RETURN toString(s.hpd_violations_as_of) AS v, toString(s.hpd_complaints_as_of) AS c, toString(s.hpd_litigation_as_of) AS l").single()
    assert {"hpd_violations": got["v"], "hpd_complaints": got["c"], "hpd_litigation": got["l"]} == EXP["as_of"]


@pytest.mark.parametrize("a", LETTERS)
def test_q15(runner, a):
    e, r = Q["Q15"][a], violations(runner, BBL[a])
    if isinstance(e, str):
        assert r["status"] == "no_violation"
        return
    assert r["by_class"] == e["by_class"] and r["open_total"] == e["open_total"] and r["open_class_i"] == e["open_class_i"]
    assert r["open_classes_a_b_c"] == e["open_classes_a_b_c"] and r["oldest_open_inspection_date"] == e["oldest_open_inspection_date"]
    assert [v["violation_id"] for v in r["oldest_open"]] == e["oldest_open_ids"] and r["latest_inspection_date"] == e["latest_inspection_date"]
    assert r["inspected_after_snapshot_date"] == e["inspected_after_snapshot_date"]
    assert (r["residential_units"], r["open_a_b_c_per_residential_unit"]) == (e["residential_units"], e["open_a_b_c_per_residential_unit"])


@pytest.mark.parametrize("a", LETTERS)
def test_q17(runner, a):
    e, r = Q["Q17"][a], registration_status(runner, BBL[a])
    assert r["no_registration"] == (not e["registered"]) and r["lapsed"] == e["lapsed"] and r["registration_older_than_latest_deed"] == e["older_than_latest_deed"]
    assert r.get("latest_registration_date") == e["latest_registration_date"] and r.get("latest_registration_end_date") == e["latest_registration_end_date"]
    assert [x["registration_id"] for x in r.get("registrations", [])] == e["registration_ids"]
    assert (r["latest_deed"]["document_id"], r["latest_deed"]["recorded"]) == (e["latest_deed"]["document_id"], e["latest_deed"]["recorded"])
    assert (r["units"]["residential"], r["year_built"]) == (e["residential_units"], e["year_built"])


@pytest.mark.parametrize("since,key", [(2022, "since_2022"), (None, "all_years")])
@pytest.mark.parametrize("a", LETTERS)
def test_q27(runner, a, since, key):
    e, r = Q["Q27"][a][key], complaints(runner, BBL[a], since)
    if isinstance(e, str):
        assert r["status"] == "no_complaint"
        return
    assert (r["problems"], r["duplicate_problems_left_out"], r["open_problems"], r["latest_received"]) == (e["problems"], e["duplicates_left_out"], e["open"], e["latest_received"])
    assert {k.upper().replace("_", " "): v["problems"] for k, v in r["by_type"].items()} == e["by_type"]
    assert {k: v for k, v in r["by_major_category"].items() if v} == {k: v for k, v in e["by_major_category"].items() if v}
    assert r["problems_per_residential_unit"] == e["problems_per_residential_unit"]


@pytest.mark.parametrize("a", LETTERS)
def test_q28(runner, a):
    e, r = Q["Q28"][a], litigation(runner, BBL[a])
    if isinstance(e, str):
        assert r["status"] == "no_case"
        return
    got = {c["litigation_id"]: c for c in r["cases"]}
    assert set(got) == {c["litigation_id"] for c in e}
    for c in e:
        g = got[c["litigation_id"]]
        assert (g["case_type_raw"], g.get("case_open_date"), g["case_status"], g["respondent_raw"]) == (c["case_type"], c["case_open_date"], c["case_status"], " ".join(c["respondent_raw"].split()))
