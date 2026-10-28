# 0019: Slice 1 exit check

Date: 2026-10-28

Status: **accepted: Slice 1 is done (2026-10-28).** Roadmap rule: a slice is done when its questions pass (Type I questions return the correct answer; Type II and mixed ones with their caveats) and every earlier slice still passes.

## What was checked

Slice 1 delivers Q1, Q2, Q3, Q4, Q5 and Q24, all Type I. Evidence, on snapshot `justfixwow-2026-05-29`:

- **Graph:** loaded citywide and validated with 0 violations by the last build run (the DOS load, which checks every rule on every node). Nothing has written to the graph since; every test runs in a rolled-back transaction. 859,636 lots, 200,172 buildings, 193,567 registrations, 733,038 HPD roles (782,024 contact rows; repeated contact ids keep one row, note 0014), 3,016,989 deed documents, 9,964,908 ACRIS roles, 4,242,054 DOS entities, 26.1M relationships, one real snapshot.
- **Tests:** 241 pass in 59 seconds (after the gap fixes) (transforms, schema and rule behavior, loads on the seven anchor lots against the expected answers, the five tools against the expected answers, the live Geosupport tests, and 8 tests that run the agent with the model).
- **Evaluation:** 35 examples, local; the final run scored 35 of 35 on all five deterministic evaluators and 35 of 35 on the judge (note 0018).
- **Live Q1 on the real graph:** the typed address of each anchor resolves through Geosupport to the expected BBL and exactly the expected BINs, 7 of 7.
- **Earlier slice (0):** the invented sample validates and Q1 runs end to end with the model.

## By question

| Q | Contract | Result |
| --- | --- | --- |
| Q1 | Address to lot and buildings, whether the match is unambiguous, and the lot's characteristics (year built, class, residential units, assessed value) | Met after the fix: lot and BINs correct 7 of 7, match kind reported, and PLUTO's class, units, year built and assessed total returned with source and snapshot (live check: 438 52nd Street gives C1, 32 units, built 1931, assessed $1,371,600) |
| Q2 | Registered owner and when the registration was last filed | Met: owner, registration id, buildings, last registration date, period end, snapshot date; no registration is not "exempt" |
| Q3 | Latest deed's grantee against the HPD owner by exact normalized name | Met: ties reported, last deed for value, name and address agreement as separate fields, `not_comparable` with its reason, mail-drop flag, a name match called a lead |
| Q4 | Managing agent, head officer, site manager | Met: every contact with role, title, name and address; a person only in the recorded role; roles HPD does not list are stated |
| Q5 | DOS record: type, filing date, process name and address, registered agent; where absent, what is known and from what source | Met for the graph: the record, the process-name kind, no-record handled as "not the same as does not exist", spelling shown to decide the match. The no-record answer points to `find_records_by_name` for the ACRIS and HPD mentions; retrieved filings are Slice 6 |
| Q24 | From an entity name, or a person in a recorded role: which lots and buildings, in which roles, with what variants | Met after the fix: entity names and persons (including a person recorded beside an organization) are found, with spellings listed as variants |

## Gaps and proposed fixes

1. **Q1 lot characteristics.** Tool change only: return PLUTO's address, building class, residential and total units, year built (or the raw value), assessed total and buildings count with the lot, each with its source and snapshot, and drop the "units not in the graph" note. No schema change. Needs the Q1 tests and the sample to carry attributes.
2. **Q24 person search.** A schema decision for the user (CLAUDE.md): add `person_name_n1`, the N1 form of the person's name, to HPD parties, indexed, and search both keys. Options: **(a)** a second property on `HpdParty`, populated by the next HPD load (about 11 minutes), recommended; **(b)** make `name_n1` a list of both forms, which breaks the exact comparison in Q3 and the index lookup; **(c)** leave the gap and say in the answer that persons beside an organization are not searched.
3. **Q5 pointer (small).** Make the no-record answer say that find_records_by_name lists the name's ACRIS and HPD mentions, and the agent follow it.

## Gap 2 resolved (2026-10-28)

The user chose option (a). `HpdParty.person_name_n1` (rule N1 of the person's name, set whenever `person_name` is, indexed) is added, and `find_records_by_name` matches either key and reports which one matched (`matched_on`) with the organization and the person as recorded. `wl:name_n1` stays the organization's name so owners still compare with deed grantees. The HPD load was rerun: 406,529 parties carry the new key (every party with a person name), the index is online, and the full validation reports 0 violations. A search for DAVID FRIEDMAN went from 15 HPD rows to 93; the 78 added are managing-agent contacts recorded beside a firm, among them anchor D's agent under FAIRSTEAD MANAGEMENT LLC. Tests: one transform test and one tool test on anchor D; one new evaluation example (SAHIT HADZOVIC, the agent and head officer on anchor C).

## Gaps 1 and 3 resolved (2026-10-28)

Gap 1: `find_lot_by_address` returns the lot's PLUTO characteristics (address text, zip, building class, residential and total units, buildings count, year built or `year_built_raw`, assessed total) with the lot's source and snapshot, leaves out fields the source lacks, reports the unit totals in `counts`, and no longer says units are not in the graph. Gap 3: a DOS no-record result carries a `next_step` pointing to `find_records_by_name`, and the prompt tells the agent to offer it. No schema change.

## Gaps 1 and 3 resolved (2026-10-28)

Gap 1: `find_lot_by_address` returns the lot's PLUTO characteristics (address text, zip, building class, residential and total units, buildings count, year built or `year_built_raw`, assessed total) with the lot's source and snapshot, leaves out fields the source lacks, reports the unit totals in `counts`, and no longer says units are not in the graph. Gap 3: a DOS no-record result carries a `next_step` pointing to `find_records_by_name`, and the prompt tells the agent to offer it. No schema change.

## Exit judgment (2026-10-28)

Slice 1 is done. Q1, Q2, Q3, Q4, Q5 and Q24 return the correct answers from the graph on the seven anchor lots, each with source and snapshot, and the Type I questions need no Type II caveat beyond the name-match-is-a-lead rule, which the agent states. Slice 0 still passes (sample validation and the Q1 end-to-end tests). One evaluation run before the final one caught the agent adding a DOS remark to a Q3 answer (the judge flagged it, twice in three runs); the prompt now allows that remark only after a DOS call, and Q3 then scored 1.00 in three runs. Not blocking, carried forward: the items below.

## Open and not blocking

- Corner addresses (Q1 scenario) and caching of Geosupport results; the 29 `unknown` rows of the mail-drop list; whether a person's ACRIS party name format ("LAST, FIRST") needs matching (Q24); a LangSmith upload of the dataset (deferred by the user).
