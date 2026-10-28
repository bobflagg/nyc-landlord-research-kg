# 0018: The Slice 1 evaluation

Date: 2026-10-28

Status: **proposed**; the first baseline is recorded below. Builds on notes 0003, 0009, 0012 and 0017.

## What was built

- `evals/dataset.py`: 34 examples derived from `evals/expected/slice1.json`, so the expected answers stay in one place. Each reference says what a correct answer must contain (expected tool calls, facts, caveat phrases, any-of groups) and must not (ownership claims, and a record joined across spellings).
- `evals/evaluators.py`: five deterministic evaluators and one model judge (`JUDGE_MODEL`, structured output by JSON schema, because forced tool calling is unreliable on `claude-sonnet-5-5`).
- `evals/run.py`: runs the agent on each example. By default the results stay local (`upload_results=False`). `--upload` creates the `nyclr-slice1` dataset and logs the experiment in LangSmith; it sends names from public records and the agent's answers to an outside service, so it is an explicit choice and has not been used.
- `agent.harness.ask` now returns the tool results as well as the answer and tool calls, so the judge can check an answer against the evidence.

## Choices

1. **Deterministic evaluators gate; the judge informs.** A phrase check cannot read nuance, and a model judge varies between runs, so the five code evaluators are the regression gate (target 1.00) and the judge's comments are read by a person.
2. **No-overreach looks at asserting sentences.** A sentence with a negation ("does not say who runs or owns the entity") is a denial, not a claim, and is skipped.
3. **Dates in words match ISO references.** "October 15, 2020" counts as 2020-10-15.
4. **Absence cases are examples too:** the HPD spelling with no DOS record, a name with no record, a lot with no registration.

## Baseline (2026-10-28, `claude-sonnet-5-5` for agent and judge)

First runs of 34 examples, kept local, then after the fixes below:

| Evaluator | First runs | After the fixes (3 runs) |
| --- | --- | --- |
| tool trajectory | 34 of 34 | 34 of 34 |
| cites snapshot | 28 of 34 | 34 of 34 |
| facts present, caveats stated, no overreach | 33 or 34 of 34 | 34 of 34 in the last seven runs |
| grounded (judge) | 0.62 to 0.94 | 0.94 to 1.00 over the last ten runs |

What the runs found and what was done about it:

- **Tools did not state the snapshot when they found nothing** (six answers about absence did not cite it). Every tool result now carries the snapshot id and date.
- **An agent answer said "the same person"** for one name in three HPD roles. The prompt now says the same name is "the same name", never the same person, and forbids inferences the tool did not return and gendered pronouns for people in records.
- **The agent altered a spelling** (KOURASH to Kourosh; ALROSE with an accent), **tied a DOS record to a lot**, and **gave a wrong example of how N1 treats `L.L.C.`**. The prompt now says to copy names exactly, that DOS records are not tied to a lot, and to use only the examples in the tool's rule field, which now carries correct ones.
- **Agent answers added a limit from another tool** (DOS holds active entities only, on an HPD answer). The prompt now says to state a limit only when it applies to a tool the agent used. The Q24 caveats gained the $0-deed and CEO-fields lines so the agent has them as evidence, and the Q4 tool says which of the managing agent, head officer and site manager HPD does not list.
- **Tool outputs were ambiguous:** a null mail-drop flag, a same-name count that included the record itself, and the label `other_name`. Each now has an explicit note.
- **Later slips found and fixed:** the agent called differently spelled owner names "the same owner"; it read `not_comparable` as "no match found" and gave its own reason (the tool now returns `not_comparable_reason`); it read a same-name count that includes the record itself as "other" records (the key is now `records_with_same_normalized_name_including_this_one`); and its no-record answers sometimes left out the "no record is not 'does not exist'" sentence, partly because the evaluator's phrase list was narrower than natural wording (it now accepts more phrasings, and the prompt is imperative).
- **The judge was misled by its own prompt.** A DOS example in the judge prompt made it report a DOS remark in answers that never mentioned DOS; the example is removed. The judge still varies between runs, so its comments are read, not only its score.

## What is left

Each run still has zero to two judge failures, and they rotate: a gloss on a label, a reading of a field (such as the cause of `not_comparable` or a count) that the tool does not state, or a claim that an entity is not an LLC. They are single-sentence interpretations, not name matches presented as findings or ownership claims, and none has failed in more than two runs in a row. Tightening further is a prompt-and-tool-output exercise with diminishing returns; the deterministic evaluators are the gate.

## Not done

- No `--upload` to LangSmith, and no hosted evaluator.
- Q1 and the integration scenario Q20 are not in this dataset.
- The judge and agent use the same model; a different judge model would be a stricter test.
