# 0031: Slice 7 exit check (the investigator)

Date: 2026-10-29

Status: **not yet accepted: Q20 scores 4 of 6 cases.** Credit was added and the cost controls below were made before the rerun. Plan: note 0030.

## What is built and checked without a model

- The ledger, the wrapped tools, the dossier (build, render, save, replay), the validator for the seven parts of the acceptance requirement and the Q20 components, the case runner: `agent/investigator/` and `evals/q20.py`.
- **Tests:** 648 pass and 2 are skipped (live web). The nine that fail all call the model and failed with the credit error (`test_q1_agent`, `test_q3_q24_agent`, `test_evals::test_two_examples_run_end_to_end`); they passed in the last full run before this. New and passing: 24 for the ledger (rules for claims, leads, budget, the stop reason, parallel calls, the required report search and the foreign-registry step), 7 for the wrapped tools and the dossier on the real graph (a scripted investigation of anchor A builds a dossier that replays with matching hashes, and a changed hash is caught), 5 for the validator (each way a dossier can break the requirement is caught).

## What the live runs showed (before the credit ran out)

Two full investigations of anchor A (`5413 7 Avenue, Brooklyn 11220`) and one run of each other case:

- **The agent works end to end.** From an address it identified the lot, the HPD registration and contacts, the deeds, the DOS record, the layers (the lot is in no group), followed the leads (702 PLAZA LLC, 5413 7TH AVENUE LLC, the 5 Cromwell Circle process address, the shared HPD address), ran report searches, and produced a dossier of 12 to 21 claims with the inference to source table, 1 to 5 leads and a computed stop reason. The shared-evidence claims, the mortgage with 702 PLAZA LLC, the different managing agent on a 2024 city statement and the court-order report about 702 Plaza LLC all appeared with their labels and quotes.
- **Failures the runs found, each now fixed in code:** a race in result and lead ids under parallel tool calls; a call budget that parallel calls overran (43 against 40); a crash when the agent passed a vocabulary value as a lead outcome; a replay that differed because the reader's classification of a web quote was not cached; unstable list order in `get_affiliations`; a dossier that skipped the report search (now required before finishing); a foreign-registered owner without a registry step (now required before finishing).
- **Not yet shown to pass:** replay after the reader fix (the cached readings only exist from the last runs), the judge on the full cases (its first findings were claims that generalized beyond a cited result, which the orchestrator's prompt now forbids, and a judge that truncated long search results, now widened), and the six cases as a set. The first full set of six scored 0 of 6, for reasons now fixed or caused by the credit running out: replay differences (reader), the crash (D), a phrase check (F), the missing registry step and the unoffered mail-drop address (MD), and the credit error for the last four.

## To finish the exit check

1. Add API credit.
2. `uv run python -m evals.q20` (six cases, about 10 minutes each at most; live web, model judge). A case passes when every deterministic check does and the judge finds no unsupported claim and no overstated label.
3. Rerun the full evaluation (132 examples) and the test suite, then record the results here and change the status.
4. Tune the prompts from what step 2 shows; the contract (sources, labels, reasons, one stop reason, replay) is checked by code, so the prompts are only for quality.

## Limits, stated

- A run follows different leads on different days; the score checks the contract and the claims every good run must contain (the owner entity, its DOS id, the mortgage, a registry step for a foreign entity, the mail-drop address as a set-aside lead), not the same trail.
- The investigator's claims are written by the model from tool results; the ledger checks that each cites results, that the label is no stronger than the sources, that a quote is verbatim, and that no ownership is stated on a derived or reported source. It cannot check that a sentence is a fair summary: that is the judge's job.
- Web text reaches only the web researcher; a claim from the web needs a verbatim quote that exists in the retrieved result.

## Cost controls and the Q20 rerun (2026-10-29)

**Cost controls made** (the earlier runs cost far more than they needed to: a 9,500-token prompt and tool block re-sent on every call at full price, a Sonnet judge reading every result, whole regression runs after each wording fix):
- **Prompt caching** on the evaluation agent (`AnthropicPromptCachingMiddleware`); Deep Agents already applies it to the investigator and its subagents. In the cases below 60 to 80 percent of input tokens were read from cache at a tenth of the price.
- **Cheaper models for mechanical steps:** the judge, the web-quote reader and the web subagent use Haiku 5.5 (`JUDGE_MODEL`, `READER_MODEL`, `WEB_MODEL` override); the agents stay on Sonnet 5.5. Haiku was under 4 percent of the cost of a case.
- **The judge skips an answer that already fails a deterministic check** (reported apart as "not judged") **and caches a verdict** by model, prompt, question, answer and results.
- **A sample by default:** `evals.run` with no flag runs one example per question id; `--full` runs all, `--only Q3,Q9` runs families.
- **Shorter context for the investigator:** the model sees each result without boilerplate keys (caveats, how-to-read), with long text cut and long lists capped with a count; the log keeps the full result for quotes and replay.
- **Cost reporting:** every model is built through `agent/costs.py`, which tracks tokens; `evals.run` and `evals.q20` print tokens and an estimated dollar cost (list prices: Sonnet 5.5 $2 in / $10 out, Haiku 5.5 $0.10 / $0.50, cache reads at a tenth). An estimate from token counts, not an invoice.
- **Not done:** per-tool rules loaded on demand instead of in the system prompt. With caching the prompt costs a tenth, and moving rules out risks the behavior 132 evaluation examples check.

**Q20, second run (after the controls and a claim-check fix): 4 of 6 cases pass, $2.29 in all ($0.38 a case).**

| Case | Result | Tool calls | Model cost |
| --- | --- | --- | --- |
| A, 5413 7 Avenue | fail (judge) | 30 | $0.36 |
| C, 438 52 Street | fail (judge) | 27 | $0.32 |
| D, 224 54 Street | pass | 29 | $0.54 |
| F, 259 22 Street | pass | 27 | $0.27 |
| DE, Delaware-owned lot | pass | 24 | $0.43 |
| MD, mail-drop lot | pass | 27 | $0.37 |

Sonnet is 97 to 98 percent of each case; Haiku (judge, reader, web subagent) about $0.01. The first run, before a ledger check on values, scored 1 of 6 at $2.23. All deterministic checks (the seven parts and the components) passed in every case in both runs; every failure is the model judge finding a claim that goes beyond or leaves out something in the result it cites: a characterization of web results as only aggregator pages when two were city documents, "no BOR masking" without the result's qualification, and a similar-name web hit presented as a listing for the lot. The fix between runs: a claim may only use ids and dates that appear in the results it cites, which removed the mis-cited-result failures.

**Open:** A and C. They need the claim discipline in the orchestrator prompt tightened (state a result's qualification with the claim; never describe a set of results more broadly than the results show), or the judge's strictness reviewed. Replay of every dossier matched. The 132-example evaluation has not been rerun since the cost controls; the full test suite passes (663, 2 skipped).
