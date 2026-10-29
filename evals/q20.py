"""Score Q20, the integration scenario, as a whole (design note 0030, I6).

  uv run python -m evals.q20                       # all cases, live web, model judge
  uv run python -m evals.q20 --only A,F --no-judge
  uv run python -m evals.q20 --web-replay          # web calls read the local cache only (record first with a live run)

For each case: run the investigator, check the dossier against the seven parts of the acceptance requirement and the Q20 components (agent/investigator/validate.py),
replay its retrieval log against the graph and the cache and compare hashes, check the case's expected claims and stop reasons, and ask a model judge whether every claim
is supported by the results it cites. Nothing is uploaded to LangSmith. Dossiers go to data/dossiers/q20-<case>/ (gitignored)."""
import argparse
import json
import os
import re
import sys

from dotenv import load_dotenv
from pydantic import BaseModel, Field

from agent import costs
from agent.investigator import dossier as D
from agent.investigator.agent import Investigation, replay_tools
from agent.investigator.validate import check, passed
from etl.config import ROOT

ANY_STOP = {"reached_registered_agent_mail_drop_or_masked_address", "no_further_recorded_link", "needs_payment_or_inaccessible", "budget_reached", "conflicting_records_unresolved"}
CASES = {
    "A": {"subject": "5413 7 Avenue, Brooklyn 11220", "mention": ["5413 PLAZA LLC", "5857246", "2021031601183001"], "stops": ANY_STOP},
    "C": {"subject": "438 52 Street, Brooklyn 11220", "mention": ["438 52 ST OWNERS CORP", "2733264"], "stops": ANY_STOP},
    "D": {"subject": "224 54 Street, Brooklyn 11220", "mention": ["HP SUNSET PARK I HDFC"], "stops": ANY_STOP},
    "F": {"subject": "259 22 Street, Brooklyn 11232", "any": [["no hpd registration", "not registered", "no registration", "no_registration"]], "stops": {"no_further_recorded_link", "needs_payment_or_inaccessible", "budget_reached"}},
    "DE": {"subject": "1000070038", "bbl": True, "mention": ["Sixty Pearl LLC"], "must_call": "lookup_registry", "stops": ANY_STOP},
    "MD": {"subject": "1017460027", "bbl": True, "mention": ["Betna67 LLC"], "mail_drop_lead": True, "stops": ANY_STOP},
}


class Verdict(BaseModel):
    unsupported_claims: list[str] = Field(description="Claims in the dossier that the cited tool results do not support. Empty if none.")
    overstated_labels: list[str] = Field(description="Claims that present a derived lead or a published claim as a fact or as ownership. Empty if none.")
    reason: str


JUDGE = """You check a dossier about a New York City property against the tool results it cites.

Claims, each with the results it cites (the only evidence):
{claims}

Report: claims not supported by the cited results (names, ids, dates, counts must match), and claims that present a derived lead (a group placement, a name or address match) or a published claim as a fact or as ownership. Be strict about what the results say, not about style."""


def judge(d: dict, model: str | None = None) -> Verdict:
    from agent.costs import chat_model, model_for
    llm = chat_model(model or model_for("judge")).with_structured_output(Verdict, method="json_schema")
    log = {r["result_id"]: r for r in d["retrieval_log"]}
    blocks = []
    for c in d["claims"]:
        src = "\n".join(f"[{s['result_id']} {s['tool']}]\n{log[s['result_id']]['text'][:30000]}" for s in c["sources"] if s["result_id"] in log)
        blocks.append(f"{c['claim_id']} ({c['label']}): {c['statement']}\n{src}")
    return llm.invoke(JUDGE.format(claims="\n\n".join(blocks)[:300000]))


def run_case(name: str, case: dict, use_judge: bool, web_replay: bool) -> dict:
    before = costs.snapshot()
    if web_replay:
        os.environ["WEB_MODE"] = "replay"
    inv = Investigation(case["subject"])
    d = inv.run()
    D.save(d, f"q20-{name.lower()}")
    saved = os.environ.get("WEB_MODE")
    os.environ["WEB_MODE"] = "replay"                      # the replay reads the cache the run filled
    try:
        diffs = D.replay(d, replay_tools())
    finally:
        os.environ["WEB_MODE"] = saved or "live"
        if saved is None:
            os.environ.pop("WEB_MODE", None)
    results = check(d, bbl_given=case.get("bbl", False), replay_diffs=diffs)
    text = " ".join(c["statement"] + " " + (c.get("quote") or "") for c in d["claims"]).lower()
    for m in case.get("mention", []):
        results.append((f"case: dossier mentions {m!r}", m.lower() in text, ""))
    for group in case.get("any", []):
        results.append((f"case: dossier says one of {group}", any(p in text for p in group), ""))
    stop = (d.get("finished") or {}).get("stop_reason")
    results.append(("case: stop reason is one this case allows", stop in case["stops"], f"stop {stop}"))
    if case.get("must_call"):
        results.append((f"case: {case['must_call']} was called", any(r["tool"] == case["must_call"] for r in d["retrieval_log"]) or any(l.get("reason") in ("needs_payment", "inaccessible") for l in d["leads"]), ""))
    if case.get("mail_drop_lead"):
        results.append(("case: the mail-drop address is a set-aside lead", any(l["disposition"] == "set_aside" and l.get("reason") == "mail_drop_address" for l in d["leads"]), ""))
    v = judge(d) if use_judge else None
    if v is not None:
        results.append(("judge: every claim supported by its sources", not v.unsupported_claims, "; ".join(v.unsupported_claims)[:600]))
        results.append(("judge: no label overstated", not v.overstated_labels, "; ".join(v.overstated_labels)[:600]))
    cost = costs.report(costs.delta(before, costs.snapshot()))
    (D.DOSSIERS / f"q20-{name.lower()}" / "cost.json").write_text(json.dumps(cost, indent=1))
    return {"case": name, "stop": stop, "claims": len(d["claims"]), "leads": len(d["leads"]), "budget": d["budget"], "results": results, "passed": passed(results), "cost": cost}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only")
    ap.add_argument("--no-judge", action="store_true")
    ap.add_argument("--web-replay", action="store_true")
    args = ap.parse_args()
    load_dotenv(ROOT / ".env")
    names = [n for n in CASES if not args.only or n in args.only.split(",")]
    rows = []
    for n in names:
        try:
            r = run_case(n, CASES[n], not args.no_judge, args.web_replay)
        except Exception as e:                              # a crash is a failed case, not a hidden one
            r = {"case": n, "stop": None, "claims": 0, "leads": 0, "budget": {}, "results": [("run completed", False, f"{type(e).__name__}: {e}"[:400])], "passed": False}
        rows.append(r)
        c = r.get("cost", {})
        print(f"{n}: {'PASS' if r['passed'] else 'FAIL'} stop={r['stop']} claims={r['claims']} leads={r['leads']} calls={r['budget'].get('tool_calls_used')} "
              f"cost=${c.get('total_dollars', 0):.2f} (in {c.get('total_input_tokens', 0):,} tok, {c.get('cache_read_tokens', 0):,} cached; out {c.get('total_output_tokens', 0):,})", flush=True)
        for m, u in c.get("models", {}).items():
            print(f"     {m}: in {u['input_tokens']:,} (cache read {u['cache_read']:,}, written {u['cache_creation']:,}) out {u['output_tokens']:,} = ${u['dollars']:.3f}", flush=True)
        for name, ok, detail in r["results"]:
            if not ok:
                print(f"   FAIL {name} {detail}", flush=True)
    total = sum(r.get("cost", {}).get("total_dollars", 0) for r in rows)
    print(f"\nQ20: {sum(r['passed'] for r in rows)}/{len(rows)} cases pass; estimated model cost ${total:.2f} (${total / max(1, len(rows)):.2f} per case)")
    sys.exit(0 if all(r["passed"] for r in rows) else 1)


if __name__ == "__main__":
    main()
