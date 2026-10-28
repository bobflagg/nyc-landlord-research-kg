# 0021: Slice 2 exit check

Date: 2026-10-28

Status: **accepted: Slice 2 is done (2026-10-28).** Roadmap rule: a slice is done when its questions pass (Type I questions return the correct answer) and every earlier slice still passes.

## What was checked

Slice 2 delivers Q15, Q17, Q27 and Q28, all Type I, on snapshot `justfixwow-2026-05-29` (design note 0020). Evidence:

- **Graph:** the violations, complaint summaries and litigation are loaded citywide and validated with 0 violations after each load. 1,965,893 violations (1,903,380 also on a registered building), 5,876,670 complaint summaries (5,031,881 also on a building), 239,060 litigation cases (210,428 also on a building). Source as-of dates: violations 2026-07-02, complaints 2026-07-07, litigation 2026-07-09, all later than the snapshot date and stated in every answer.
- **Expected answers** for the seven anchors, derived from the source database without the graph (`evals/expected/derive_slice2.py`): 36 tests in `tests/test_expected_slice2.py` compare the tools running on the citywide graph with them, and all pass. The graph and the source agree on every count, date and id checked.
- **Tests:** 337 pass in about 64 seconds (transforms, the anchors loaded and validated, the tools against the fixture rows and the expected answers, privacy: no apartment, unit or complainant field can reach a summary).
- **Evaluation:** 63 examples (35 from Slice 1, 28 new), local, nothing uploaded. Final run: all five deterministic evaluators 63 of 63; the judge 62 of 63 (the miss was a "none listed" gloss on an absent DOS field in a Slice 1 Q24 answer).
- **Earlier slices:** Slice 1's 35 examples and its tests pass in the same run; the Slice 0 sample validates and Q1 runs end to end.

## By question

| Q | Contract | Result |
| --- | --- | --- |
| Q15 | Open violations of a building: counts by class, the oldest open inspection date, a rate | Met: counts by class and open or closed with class I kept apart, oldest open date and ids, the five oldest, open A, B and C per PLUTO residential unit, the as-of date, violations inspected after the snapshot date, and "part of all violations" stated; a lot with none says so without claiming it never had one |
| Q17 | Missing, lapsed or stale registration | Met: no registration, lapsed, and older than the latest deed, each with its dates; units against the 3+ threshold; new construction named as a legitimate reason; never says the owner failed to register |
| Q27 | Complaints at a building | Met: problem rows with duplicates left out, by type, status and major category, distinct complaints per type with the non-additivity stated, since-year, latest received, rate, the years that have problems; no apartment or complainant detail exists |
| Q28 | Housing Court actions by HPD | Met: cases with type, open date (or none), status, harassment finding (or "none recorded"), respondents in the role respondent, exact-name agreement with the registered owner as a lead; "not an eviction and not a finding of liability"; no case is not "none was ever brought" |

## Findings along the way

- The tables for violations, complaints and litigation are newer than the registrations the snapshot date comes from. Each answer therefore carries its own as-of date (C4), and anchor A has three violations inspected after the snapshot date.
- The detail document's Q15 and Q27 examples (20 open violations; 45 problems in 30 complaints) are from the older snapshot 2026-10-17 and do not apply; `slice2.json` supersedes them.
- Evaluation caught five tool-output slips, all fixed in the output fields: a first/last year pair read as the only years, a building key labeled "BIN", an absent harassment finding read as "no finding", a DOS remark appearing in a deed answer, and no-case answers dropping the "not none ever" caveat.
- 3.2% of violations and 14% of complaint summaries carry a BIN that is not a registered building; they count on the lot and are shown as not tied to a building.

## Open and not blocking

- Complaint summaries are per calendar year, so "since 2022-01-01" is exact only at a year boundary.
- Litigation respondents are a comma-split list; a company name that contains a comma can be split (the raw text is returned).
- The violations table holds about a fifth of all HPD violations (known limit); Q14 (Slice 3) must report or backfill the gap.
- The LangSmith upload stays off. Slice 3 plan is next.
