"""Run one investigation and write its dossier.

  uv run python -m agent.investigator.run "5413 7 Avenue, Brooklyn 11220" [--name a] [--max-calls 40] [--max-leads 6] [--max-seconds 720]
  uv run python -m agent.investigator.run --replay data/dossiers/a      # re-run the logged calls and compare hashes (no model)

Web calls use the live provider unless WEB_MODE=replay (with WEB_CACHE_PATH). The dossier goes to data/dossiers/<name>/ (gitignored)."""
import argparse
import json
import re
import sys

from agent.db import read_session
from agent.investigator import dossier as D
from agent.investigator.agent import Investigation, replay_tools


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("subject", nargs="?")
    ap.add_argument("--name")
    ap.add_argument("--max-calls", type=int, default=40)
    ap.add_argument("--max-leads", type=int, default=6)
    ap.add_argument("--max-seconds", type=float, default=720.0)
    ap.add_argument("--replay", help="a dossier folder: re-run its logged calls and compare")
    args = ap.parse_args()
    if args.replay:
        d = json.loads((D.DOSSIERS.parent.parent / args.replay / "dossier.json").read_text()) if not args.replay.startswith("/") else json.loads(open(args.replay + "/dossier.json").read())
        diffs = D.replay(d, replay_tools())
        print(json.dumps(diffs, indent=1) if diffs else f"replay matches: {len(d['retrieval_log'])} calls")
        sys.exit(1 if diffs else 0)
    if not args.subject:
        ap.error("a subject (an address or a BBL) is required")
    inv = Investigation(args.subject, args.max_calls, args.max_leads, args.max_seconds)
    d = inv.run()
    name = args.name or re.sub(r"[^a-z0-9]+", "-", args.subject.lower()).strip("-")[:40]
    folder = D.save(d, name)
    print(f"dossier: {folder}/dossier.md")
    print("stop reason:", (d.get("finished") or {}).get("stop_reason", "NOT FINISHED"), "| claims:", len(d["claims"]), "| leads:", len(d["leads"]), "| budget:", d["budget"])


if __name__ == "__main__":
    main()
