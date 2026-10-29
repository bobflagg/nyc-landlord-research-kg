"""Run the Slice 1 evaluation: each example goes to the agent, then the evaluators score it.

  uv run python -m evals.run                      # all examples, kept local (nothing is sent to LangSmith)
  uv run python -m evals.run --only Q3 --no-judge # one question, deterministic evaluators only
  uv run python -m evals.run --upload             # also create the dataset and log the experiment in LangSmith

Without --upload the results stay on this machine (upload_results=False). --upload sends the questions, the expected
facts and the agent's answers to LangSmith, so it needs LANGSMITH_API_KEY and is a choice, not a default."""
import argparse
import sys
from collections import defaultdict

from dotenv import load_dotenv
from langsmith import Client, evaluate

from agent.harness import ask
from etl.config import ROOT
from evals.dataset import as_examples, build_examples
from evals.evaluators import DETERMINISTIC, make_judge

DATASET = "nyclr-slice1"


def target(inputs: dict) -> dict:
    return ask(inputs["question"])


def upload_dataset(client: Client, examples: list[dict]):
    """Create the dataset and its examples if it does not exist; return it. Existing datasets are left as they are."""
    if client.has_dataset(dataset_name=DATASET):
        return client.read_dataset(dataset_name=DATASET)
    ds = client.create_dataset(dataset_name=DATASET, description="Slice 1 questions Q2 to Q5 and Q24 on anchor lots A to G; references derived from evals/expected/slice1.json (snapshot justfixwow-2026-05-29).")
    client.create_examples(dataset_id=ds.id, examples=examples)
    return ds


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="a question id such as Q3, or several separated by commas")
    ap.add_argument("--no-judge", action="store_true")
    ap.add_argument("--upload", action="store_true", help="send the dataset and results to LangSmith")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--full", action="store_true", help="run every example (default: one example per question id, a regression sample)")
    ap.add_argument("--concurrency", type=int, default=2)
    ap.add_argument("--web-live", action="store_true", help="use the live search provider and registries for Q16 and Q25 instead of the recorded fixtures")
    args = ap.parse_args()
    load_dotenv(ROOT / ".env")
    if not args.web_live:                       # deterministic: Q16 and Q25 replay recorded responses and never touch the network (design note 0028, W6)
        import os, tempfile
        from agent.web.cache import Cache
        path = os.path.join(tempfile.mkdtemp(), "web.sqlite")
        Cache(path).load_fixtures(ROOT / "tests" / "fixtures" / "web" / "replay.json")
        os.environ["WEB_MODE"], os.environ["WEB_CACHE_PATH"] = "replay", path
    examples = [e for e in build_examples() if not args.only or e["metadata"]["question_id"] in args.only.split(",")]
    if not args.full and not args.only:        # cost control: a full run is ~10M tokens; the default is one example per question id
        seen, sample = set(), []
        for e in examples:
            if e["metadata"]["question_id"] not in seen:
                seen.add(e["metadata"]["question_id"])
                sample.append(e)
        examples = sample
        print(f"sample run: {len(examples)} of {len(build_examples())} examples (one per question id); --full runs all, --only Q3,Q9 runs those families")
    examples = examples[: args.limit]
    from agent import costs
    before = costs.snapshot()
    evaluators = [*DETERMINISTIC, *([] if args.no_judge else [make_judge()])]
    data = as_examples(examples)
    if args.upload:
        client = Client()
        data = upload_dataset(client, build_examples()).name
    results = evaluate(target, data=data, evaluators=evaluators, experiment_prefix="slice1", max_concurrency=args.concurrency,
                       upload_results=args.upload, metadata={"snapshot_id": "justfixwow-2026-05-29"})
    scores, failed, skipped = defaultdict(list), [], []
    for row in results:
        meta = row["example"].metadata if hasattr(row["example"], "metadata") else {}
        for r in row["evaluation_results"]["results"]:
            if (r.comment or "").startswith("skipped:"):          # not judged because a deterministic check failed: counted apart, not as a judge result
                skipped.append((meta.get("question_id"), meta.get("anchor")))
                continue
            if r.score is None:                      # an evaluator that raised: counted as a failure, not hidden
                failed.append((meta.get("question_id"), meta.get("anchor"), r.key, None, (r.comment or "evaluator error")[:300]))
                continue
            scores[r.key].append(r.score)
            if r.score < 1:
                failed.append((meta.get("question_id"), meta.get("anchor"), r.key, r.score, (r.comment or "")[:700]))
    print(f"\n{len(examples)} examples")
    for key, vals in scores.items():
        print(f"  {key:16} {sum(vals)/len(vals):.2f}  ({sum(1 for v in vals if v == 1)}/{len(vals)} full marks)")
    for f in failed:
        print("  FAIL", *f)
    if skipped:
        print(f"  grounded not judged for {len(skipped)} example(s) whose deterministic checks failed: {skipped}")
    c = costs.report(costs.delta(before, costs.snapshot()))
    print(f"  cost (estimate from token counts): ${c['total_dollars']:.2f}; input {c['total_input_tokens']:,} tokens ({c['cache_read_tokens']:,} read from cache), output {c['total_output_tokens']:,}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
