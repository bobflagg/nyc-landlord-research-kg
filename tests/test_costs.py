"""Cost controls (design note 0030): result compaction for the model, usage pricing, the judge's skip and cache."""
import json

from agent import costs
from agent.investigator.tools import compact


def test_compact_drops_boilerplate_caps_lists_and_text_and_keeps_facts():
    r = {"status": "found", "caveats": ["long boilerplate"], "how_to_read": "x", "rows": list(range(100)), "note": "n" * 5000, "deep": {"caveats": ["c"], "keep": 1}}
    c = compact(r)
    assert "caveats" not in c and "how_to_read" not in c and "caveats" not in c["deep"] and c["deep"]["keep"] == 1 and c["status"] == "found"
    assert len(c["rows"]) == 41 and c["rows"][-1] == {"_more_not_shown": 60} and c["note"].endswith("more characters not shown]") and len(c["note"]) < 1600


def test_usage_is_priced_with_cache_reads_at_a_tenth_and_writes_at_one_and_a_quarter():
    usage = {"claude-sonnet-5-5": {"input_tokens": 1_000_000, "output_tokens": 100_000, "cache_read": 600_000, "cache_creation": 100_000},
             "claude-haiku-5-5": {"input_tokens": 1_000_000, "output_tokens": 0, "cache_read": 0, "cache_creation": 0}}
    r = costs.report(usage)
    # sonnet: 300k fresh x $2 + 600k cached x $0.2 + 100k written x $2.5 + 100k out x $10 = 0.6 + 0.12 + 0.25 + 1.0 = $1.97; haiku: 1M x $0.10
    assert r["models"]["claude-sonnet-5-5"]["dollars"] == 1.97 and r["models"]["claude-haiku-5-5"]["dollars"] == 0.10 and r["total_dollars"] == 2.07
    assert r["models"]["claude-sonnet-5-5"]["uncached_input"] == 300_000


def test_delta_subtracts_what_was_used_before():
    a = {"m": {"input_tokens": 10, "output_tokens": 5, "input_token_details": {"cache_read": 4}}}
    b = {"m": {"input_tokens": 30, "output_tokens": 9, "input_token_details": {"cache_read": 14, "cache_creation": 2}}}
    assert costs.delta(a, b) == {"m": {"input_tokens": 20, "output_tokens": 4, "cache_read": 10, "cache_creation": 2}}


def test_roles_default_to_the_cheap_model_and_the_agent_to_the_main_one(monkeypatch):
    for k in ("JUDGE_MODEL", "READER_MODEL", "WEB_MODEL", "AGENT_MODEL", "MODEL"):
        monkeypatch.delenv(k, raising=False)
    assert costs.model_for("judge") == costs.model_for("reader") == costs.model_for("web") == costs.CHEAP and costs.model_for("agent") == costs.MAIN
    monkeypatch.setenv("JUDGE_MODEL", "anthropic:claude-sonnet-5-5")
    assert costs.model_for("judge") == "anthropic:claude-sonnet-5-5"


def test_the_judge_skips_a_failing_answer_and_caches_a_verdict(tmp_path, monkeypatch):
    from evals import evaluators as E
    monkeypatch.setattr(E, "_VERDICTS", tmp_path / "judge.json")
    calls = []
    class Fake:
        def with_structured_output(self, *a, **k):
            return self
        def invoke(self, prompt):
            calls.append(prompt)
            return E.Verdict(unsupported_claims=[], presents_match_as_finding=False, reason="ok")
    monkeypatch.setattr(costs, "chat_model", lambda name, **k: Fake())
    judge = E.make_judge()
    ref = {"expected_tools": [{"name": "t", "args": {}}], "must_include": [], "must_include_any": [["alpha"]], "caveat_groups": [], "must_not_include": []}
    good = {"answer": "alpha 2026-05-29", "tool_calls": [{"name": "t", "args": {}}], "tool_results": [{"name": "t", "content": "{}"}]}
    bad = {**good, "answer": "beta 2026-05-29"}
    assert judge({"question": "q"}, bad, ref)["comment"].startswith("skipped:") and calls == []
    assert judge({"question": "q"}, good, ref)["score"] == 1.0 and len(calls) == 1
    judge({"question": "q"}, good, ref)
    assert len(calls) == 1
