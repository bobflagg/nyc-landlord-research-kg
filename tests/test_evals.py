"""The Slice 1 evaluation dataset and its evaluators. The dataset is derived from the expected answers; the deterministic
evaluators are checked on canned answers; one test runs the real harness on two examples, kept local."""
import os

import pytest
from langsmith import evaluate

from evals.dataset import NOT_EXIST, NO_RECORD, as_examples, build_examples
from evals.evaluators import DETERMINISTIC, caveats_stated, cites_snapshot, facts_present, no_overreach, tool_trajectory

EX = build_examples()
REF = {"expected_tools": [{"name": "get_hpd_registrations", "args": {"bbl": "3008260002"}}], "must_include": ["316103", "2026-09-01"],
       "must_include_any": [["no registration", "exact"]], "caveat_groups": [["title"]], "must_not_include": [" owns the ", "same party was"]}


def out(answer, calls=(("get_hpd_registrations", {"bbl": "3008260002"}),)):
    return {"answer": answer, "tool_calls": [{"name": n, "args": a} for n, a in calls], "tool_results": []}


# ---- the dataset ---------------------------------------------------------------------------------------------

def test_dataset_covers_each_question_and_anchor():
    by_q = {}
    for e in EX:
        by_q.setdefault(e["metadata"]["question_id"], []).append(e["metadata"]["anchor"])
    assert {q: len(v) for q, v in by_q.items()} == {"Q2": 7, "Q3": 7, "Q4": 7, "Q5": 10, "Q24": 4, "Q15": 7, "Q17": 7, "Q27": 7, "Q28": 7, "Q12": 7, "Q13": 7, "Q14": 7}
    assert set(by_q["Q2"]) == set("ABCDEFG")


def test_every_example_names_a_tool_and_what_a_correct_answer_needs():
    for e in EX:
        r = e["outputs"]
        assert e["inputs"]["question"] and r["expected_tools"] and (r["must_include"] or r["must_include_any"])
        assert all(isinstance(t["args"], dict) for t in r["expected_tools"])
        assert any(" owns the " in p for p in r["must_not_include"])   # no example may allow an ownership claim


def test_references_come_from_the_expected_answers():
    q3a = next(e for e in EX if e["metadata"] == {"question_id": "Q3", "anchor": "A"})["outputs"]
    assert "2025032100031001" in q3a["must_include"] and "5413 PLAZA LLC" in q3a["must_include"]
    q5c = [e for e in EX if e["metadata"]["question_id"] == "Q5" and e["metadata"]["anchor"] == "C"]
    assert any("2733264" in e["outputs"]["must_include"] for e in q5c)            # the deed spelling has a record
    assert any(e["outputs"]["must_include_any"] == [NO_RECORD] for e in q5c)      # the HPD spelling does not
    g = next(e for e in EX if e["inputs"]["question"].startswith("What do the records show for KS Turnpike"))
    assert "305188" in g["outputs"]["must_include"] and ["spelling", "different name", "variant"] in g["outputs"]["caveat_groups"]


# ---- evaluators ----------------------------------------------------------------------------------------------

def test_tool_trajectory():
    assert tool_trajectory({}, out("x"), REF)["score"] == 1.0
    assert tool_trajectory({}, out("x", [("get_hpd_registrations", {"bbl": "9999999999"})]), REF)["score"] == 0.0
    assert tool_trajectory({}, out("x", []), REF)["score"] == 0.0


def test_facts_present_scores_the_share_found_and_needs_each_group():
    full = facts_present({}, out("Registration **316103** ends `2026-09-01`; the names agree exactly."), REF)
    assert full["score"] == 1.0
    part = facts_present({}, out("Registration 316103, names agree exactly."), REF)
    assert part["score"] == pytest.approx(2 / 3) and "2026-09-01" in part["comment"]
    assert facts_present({}, out("nothing"), REF)["score"] == 0.0


def test_dates_written_in_words_match_the_iso_reference():
    ref = {**REF, "must_include": ["2020-10-15", "2026-09-01"], "must_include_any": []}
    assert facts_present({}, out("Filed October 15, 2020; the period ends 1 September 2026."), ref)["score"] == 1.0


def test_caveats_need_one_phrase_per_group():
    assert caveats_stated({}, out("A registration is not proof of title."), REF)["score"] == 1.0
    assert caveats_stated({}, out("The owner is X."), REF)["score"] == 0.0


def test_no_overreach_flags_ownership_claims_and_forbidden_strings():
    assert no_overreach({}, out("The registered owner is 5413 PLAZA LLC. This is a lead."), REF)["score"] == 1.0
    assert no_overreach({}, out("5413 Plaza LLC owns the building."), REF)["score"] == 0.0
    assert no_overreach({}, out("The process name does not say who runs or owns the entity."), REF)["score"] == 1.0
    assert no_overreach({}, out("A same party was found."), REF)["score"] == 0.0


def test_snapshot_cited():
    assert cites_snapshot({}, out("As of snapshot 2026-05-29"), REF)["score"] == 1.0
    assert cites_snapshot({}, out("as of last year"), REF)["score"] == 0.0


def test_the_phrase_groups_accept_how_the_agent_actually_words_them():
    assert caveats_stated({}, out("No DOS record does not mean the entity does not exist."), {**REF, "caveat_groups": [NOT_EXIST]})["score"] == 1.0
    assert facts_present({}, out("I did not find a record."), {**REF, "must_include": [], "must_include_any": [NO_RECORD]})["score"] == 1.0


# ---- the harness, kept local ---------------------------------------------------------------------------------

@pytest.mark.agent
@pytest.mark.skipif(not os.environ.get("ANTHROPIC_API_KEY"), reason="no model key")
def test_two_examples_run_end_to_end_without_uploading():
    from evals.run import target
    pick = [next(e for e in EX if e["metadata"] == {"question_id": "Q2", "anchor": "A"}),
            next(e for e in EX if e["metadata"] == {"question_id": "Q5", "anchor": "G"} and "Is there" in e["inputs"]["question"])]
    res = evaluate(target, data=as_examples(pick), evaluators=DETERMINISTIC, upload_results=False, max_concurrency=1)
    rows = list(res)
    assert len(rows) == 2
    for row in rows:
        got = {r.key: r.score for r in row["evaluation_results"]["results"]}
        assert set(got) == {f.__name__ for f in DETERMINISTIC}
        assert got["tool_trajectory"] == 1.0 and got["no_overreach"] == 1.0
