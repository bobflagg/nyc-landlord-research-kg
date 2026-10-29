"""The dossier: built from the ledger, rendered with the inference -> source table, written to data/dossiers/ (gitignored), and replayable (design note 0030, I2 and I4)."""
import json
from pathlib import Path

from agent.investigator.ledger import Ledger, result_hash
from etl.config import ROOT

DOSSIERS = ROOT / "data" / "dossiers"
LABEL_TEXT = {"recorded_assertion": "recorded assertion (Type I)", "derived_lead": "derived lead (Type II)", "reported_claim": "reported claim"}


def build(ledger: Ledger, run: dict) -> dict:
    """The whole dossier as plain data. `run` carries the snapshot, the as-of dates and the BOR run (see meta())."""
    return {"subject": ledger.subject, "run": run, "started_at": ledger.started, "finished": ledger.finished, "budget": ledger.budget_report(),
            "claims": [c.model_dump(exclude_none=True) for c in ledger.claims], "leads": [l.model_dump(exclude_none=True) for l in ledger.leads],
            "retrieval_log": [{k: v for k, v in r.model_dump().items() if k != "text"} | {"text": r.text} for r in ledger.records]}


def meta(runner) -> dict:
    from agent.tools.layers import active_run
    from agent.tools.records import _plain, snapshot
    s = snapshot(runner)
    r = runner.run("MATCH (s:Snapshot {snapshot_id: $id}) RETURN s.hpd_violations_as_of AS v, s.hpd_complaints_as_of AS c, s.hpd_litigation_as_of AS l", id=s.get("snapshot_id")).single()
    bor = active_run(runner)
    return {**s, "as_of": {"hpd_violations": _plain(r["v"]), "hpd_complaints": _plain(r["c"]), "hpd_litigation": _plain(r["l"])} if r else {}, "bor_run": bor.get("run_id") if bor else None}


def render(d: dict) -> str:
    out = [f"# Dossier: {d['subject']}", ""]
    run = d["run"]
    out += ["## Run", f"- Snapshot {run.get('snapshot_id')} (snapshot date {run.get('snapshot_date')}); BOR run {run.get('bor_run')}; source as-of dates {run.get('as_of')}.",
            f"- Started {d['started_at']}; budget used: {d['budget']}.", "- Recorded assertions are kept apart from derived leads (a method links or classifies) and reported claims (a third party published them, unreviewed). A group is a lead, not ownership.", ""]
    stop = d.get("finished") or {}
    out += ["## Stop reason", f"**{stop.get('stop_reason', 'not finished')}**" + (f" — {stop['note']}" if stop.get("note") else ""), ""]
    out += ["## Claims: inference to source", "", "| Claim | Label | Review | Sources (result, tool, retrieved, category) |", "| --- | --- | --- | --- |"]
    for c in d["claims"]:
        srcs = "; ".join(f"{s['result_id']} {s['tool']} {s['retrieved_at']} {s['source_category']}" for s in c["sources"])
        q = f' Quote: "{c["quote"]}"' if c.get("quote") else ""
        out.append(f"| {c['claim_id']}: {c['statement']}{q} | {LABEL_TEXT[c['label']]} | {c.get('review_status') or 'recorded'} | {srcs} |")
    leads = d["leads"]
    out += ["", "## Leads", "", "| Lead | Kind | Value | Disposition | Reason | Found in |", "| --- | --- | --- | --- | --- | --- |"]
    for l in leads:
        out.append(f"| {l['lead_id']} | {l['kind']} | {l['value']} | {l['disposition']} | {l.get('reason', '')}{(': ' + l['note']) if l.get('note') else ''} | {l['found_in']} |")
    out += ["", "## Unresolved or not followed", ""]
    rest = [l for l in leads if l["disposition"] in ("unresolved", "set_aside")]
    out += [f"- {l['lead_id']} {l['value']}: {l['disposition']}, {l.get('reason')}" for l in rest] or ["- none"]
    out += ["", "## Retrieval log", "", "| Result | Tool | Arguments | Called | Label | Hash |", "| --- | --- | --- | --- | --- | --- |"]
    out += [f"| {r['result_id']} | {r['tool']} | {json.dumps(r['args'])} | {r['called_at']} | {r['label']} | {r['result_hash']} |" for r in d["retrieval_log"]]
    return "\n".join(out) + "\n"


def save(d: dict, name: str, root: Path = DOSSIERS) -> Path:
    folder = root / name
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "dossier.json").write_text(json.dumps(d, indent=1, default=str))
    (folder / "dossier.md").write_text(render(d))
    return folder


def replay(d: dict, tools: dict) -> list[dict]:
    """Re-run every logged call (`tools`: tool name -> callable taking the logged args) against the graph and the retrieval cache, and compare result hashes.
    The model is not re-run: this checks that the evidence is reproducible. Returns the differences (empty means the dossier replays)."""
    diffs = []
    for r in d["retrieval_log"]:
        fn = tools.get(r["tool"])
        if fn is None:
            diffs.append({"result_id": r["result_id"], "tool": r["tool"], "problem": "tool not available for replay"})
            continue
        try:
            got = fn(**r["args"])
        except Exception as e:      # a replay that cannot run is reported, not hidden
            diffs.append({"result_id": r["result_id"], "tool": r["tool"], "problem": f"{type(e).__name__}: {e}"})
            continue
        if result_hash(got if isinstance(got, dict) else {"result": got}) != r["result_hash"]:
            diffs.append({"result_id": r["result_id"], "tool": r["tool"], "problem": "result differs from the one logged"})
    return diffs
