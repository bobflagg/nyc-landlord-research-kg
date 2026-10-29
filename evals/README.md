# evals/

Evaluation of the investigator (design notes 0012 and 0018).

| Path | What |
| --- | --- |
| `expected/` | Expected answers from the build snapshot (`slice1.json`, `slice2.json`), the SQL that derives them, and how to read them |
| `dataset.py` | The evaluation dataset, derived from `expected/slice1.json`, `slice2.json` and `slice3.json`: 84 examples (Q2 to Q5, Q24, Q15, Q17, Q27, Q28, Q12, Q13 and Q14 on anchor lots A to G, plus absence and spelling cases). Each has the question and a reference: expected tool calls, required facts, caveat phrases, forbidden claims |
| `evaluators.py` | Five deterministic evaluators (tool trajectory, facts present, caveats stated, no overreach, snapshot cited) and a model judge (`grounded`) |
| `run.py` | Runs the agent on every example and scores it |

```
uv run python -m evals.run                       # all 84, results kept on this machine
uv run python -m evals.run --only Q3 --no-judge  # one question, deterministic evaluators only
uv run python -m evals.run --upload              # also create the dataset in LangSmith and log the experiment
```

Without `--upload` nothing leaves the machine (`upload_results=False`); the agent and judge models still run, so it uses the
model key. `--upload` sends the questions, the expected facts and the answers to LangSmith and needs `LANGSMITH_API_KEY`.
Q1 (address to lot) is covered by `tests/test_q1_agent.py` and `tests/test_geosupport_live.py`, which need the Geosupport sidecar.

The deterministic evaluators are the regression gate: they should stay at 1.00. The judge reads each answer against what the tools
returned, for unsupported claims and for a name or address match presented as a finding; it varies from run to run, so read its
comments rather than only its score. Add a question by adding examples to `dataset.py`, and keep its expected answer in
`expected/slice1.json`.
