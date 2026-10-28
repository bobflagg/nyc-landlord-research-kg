"""Evaluators for the Slice 1 dataset. Signature (inputs, outputs, reference_outputs) -> {"key", "score", "comment"}.

Deterministic: tool trajectory, facts present, caveats stated, no overreach, snapshot cited. Model judge: every claim is
supported by what the tools returned, and no name or address match is presented as a finding (design notes 0009, 0017).
`outputs` is what agent.harness.ask returns: answer, tool_calls, tool_results."""
import os
import re

from dotenv import load_dotenv
from pydantic import BaseModel, Field

from etl.config import ROOT

load_dotenv(ROOT / ".env")
DEFAULT_JUDGE = "anthropic:claude-sonnet-5-5"


MONTHS = {m: i for i, m in enumerate(["january", "february", "march", "april", "may", "june", "july", "august", "september", "october",
                                      "november", "december"], 1)}
LONG_DATE = re.compile(r"\b(%s)\s+(\d{1,2}),?\s+(\d{4})\b|\b(\d{1,2})\s+(%s),?\s+(\d{4})\b" % ("|".join(MONTHS), "|".join(MONTHS)))


def _iso(m: re.Match) -> str:
    month, day, year = (m.group(1), m.group(2), m.group(3)) if m.group(1) else (m.group(5), m.group(4), m.group(6))
    return f"{year}-{MONTHS[month]:02d}-{int(day):02d}"


def _text(outputs: dict) -> str:
    """The answer as plain lowercase text: markdown bold and backticks removed, whitespace collapsed, and dates written
    out in words (October 15, 2020) turned into ISO form so they can be matched."""
    text = re.sub(r"\s+", " ", re.sub(r"[*`]", "", outputs.get("answer", ""))).lower()
    return LONG_DATE.sub(_iso, text)


def _result(key: str, score: float, comment: str = "") -> dict:
    return {"key": key, "score": score, "comment": comment}


def tool_trajectory(inputs: dict, outputs: dict, reference_outputs: dict) -> dict:
    """Every expected tool was called, with the expected arguments (string arguments compared case-insensitively)."""
    calls, missing = outputs.get("tool_calls", []), []
    for want in reference_outputs["expected_tools"]:
        ok = any(c["name"] == want["name"] and all(str(c["args"].get(k, "")).casefold() == str(v).casefold() for k, v in want["args"].items())
                 for c in calls)
        if not ok:
            missing.append(want["name"])
    return _result("tool_trajectory", 0.0 if missing else 1.0, f"missing: {missing}; called: {[c['name'] for c in calls]}" if missing else "")


def facts_present(inputs: dict, outputs: dict, reference_outputs: dict) -> dict:
    """The share of required strings in the answer, and every any-of group satisfied."""
    text = _text(outputs)
    need = [f.casefold() for f in reference_outputs["must_include"]]
    groups = reference_outputs["must_include_any"]
    absent = [f for f in need if f not in text]
    groups_missing = [g for g in groups if not any(p.casefold() in text for p in g)]
    total = len(need) + len(groups)
    score = 1.0 if total == 0 else (total - len(absent) - len(groups_missing)) / total
    return _result("facts_present", score, f"absent: {absent}; groups missing: {groups_missing}" if score < 1 else "")


def caveats_stated(inputs: dict, outputs: dict, reference_outputs: dict) -> dict:
    """Each caveat group has at least one of its phrases in the answer."""
    text = _text(outputs)
    missing = [g for g in reference_outputs["caveat_groups"] if not any(p.casefold() in text for p in g)]
    total = len(reference_outputs["caveat_groups"])
    return _result("caveats_stated", 1.0 if not total else (total - len(missing)) / total, f"missing: {missing}" if missing else "")


NEGATION = re.compile(r"\b(not|no|nor|never|without|neither|cannot)\b|n't")


def _asserted(text: str) -> str:
    """The sentences that assert something: a sentence with a negation ("does not say who runs or owns the entity")
    is a denial, not a claim, and is left out."""
    return " ".join(s for s in re.split(r"(?<=[.!?;])\s+|\n", text) if not NEGATION.search(s))


def no_overreach(inputs: dict, outputs: dict, reference_outputs: dict) -> dict:
    """None of the forbidden claims or strings appears in an asserting sentence: no ownership claim, no joining of
    records the tool did not match."""
    text = _asserted(_text(outputs))
    hit = [p for p in reference_outputs["must_not_include"] if p.casefold() in text]
    return _result("no_overreach", 0.0 if hit else 1.0, f"found: {hit}" if hit else "")


def cites_snapshot(inputs: dict, outputs: dict, reference_outputs: dict) -> dict:
    return _result("cites_snapshot", 1.0 if "2026-05-29" in _text(outputs) else 0.0)


DETERMINISTIC = [tool_trajectory, facts_present, caveats_stated, no_overreach, cites_snapshot]


class Verdict(BaseModel):
    """The judge's reading of one answer against the tool results."""
    unsupported_claims: list[str] = Field(description="Claims in the answer that the tool results do not support. Empty if none.")
    presents_match_as_finding: bool = Field(description="True if a name or address match is stated as proof that two records are the same party, or as ownership.")
    reason: str


JUDGE_PROMPT = """You check an answer about New York City property records against what the tools returned.

Question: {question}

Tool results (the only evidence):
{results}

Answer:
{answer}

The tool results include their own notes, rules and caveats; those are evidence too. Judge only what the answer actually says.

List a claim only if it is a material one that the tool results do not support: a name, id, date, count, role, address, or a conclusion
about identity, ownership, control, cause or someone's circumstances (for example that a person is deceased, or that a record is out of date).
Also list a gendered pronoun used for a person named in a record, since the records give no gender.
Do not list: a plain restatement or plain-English gloss of a field or label the tool returned, an offer of a next step, a summary or
rounding of a count, or a null field read as "none listed".
Say whether the answer presents a name match or address match as proof that two records are the same party or the same person, or as ownership.
Saying the same name appears in several records is fine; saying it is the same person is not. A statement that a match is a lead, or
that something is not proven, is fine. Details left out are not claims."""


def make_judge(model: str | None = None):
    """An evaluator that asks the judge model (JUDGE_MODEL in .env, a LangChain model string) to check grounding."""
    from langchain.chat_models import init_chat_model
    llm = init_chat_model(model or os.environ.get("JUDGE_MODEL", DEFAULT_JUDGE)).with_structured_output(Verdict, method="json_schema")

    def grounded(inputs: dict, outputs: dict, reference_outputs: dict) -> dict:
        results = "\n\n".join(f"[{r['name']}]\n{r['content'][:40000]}" for r in outputs.get("tool_results", [])) or "(no tool was called)"
        v = llm.invoke(JUDGE_PROMPT.format(question=inputs["question"], results=results, answer=outputs.get("answer", "")))
        ok = not v.unsupported_claims and not v.presents_match_as_finding
        return _result("grounded", 1.0 if ok else 0.0, v.reason + (f" | unsupported: {v.unsupported_claims}" if v.unsupported_claims else "")
                       + (" | presents a match as a finding" if v.presents_match_as_finding else ""))
    return grounded
