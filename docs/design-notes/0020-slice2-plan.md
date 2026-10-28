# 0020: Slice 2 plan (conditions)

Date: 2026-10-28

Status: **accepted 2026-10-28 and built; the exit check is note 0021.** The user chose the recommended option for C1 to C6.

## What Slice 2 delivers

Roadmap: open violations, complaints and HPD litigation at a building; missing or lapsed registration. Questions Q15, Q17, Q27, Q28, all Type I (recorded facts), on the snapshot `justfixwow-2026-05-29`. Slice 1 and Slice 0 must still pass.

| Q | Contract | New data | Answer shape |
| --- | --- | --- | --- |
| Q15 | Open violations of a building | `hpd_violations` | counts by class (A, B, C, I) and status, the oldest open inspection date, open per residential unit (PLUTO) |
| Q17 | Missing, lapsed or stale registration | none: `hpd_registrations`, PLUTO, ACRIS deeds already loaded | yes/no per condition with dates, units and the 3+ unit threshold stated; no ruling on legal applicability |
| Q27 | Complaints at a building | `hpd_complaints_and_problems` | counts by type, category and status since a date, problems or complaints said which, a rate; no apartment or complainant detail |
| Q28 | Housing Court actions by HPD | `hpd_litigations` | cases with type, open date, status, harassment finding; respondents with the recorded role and source; a respondent matches the registered owner only by exact normalized name |

## What the source holds (checked 2026-10-28 in the justfixwow database)

- **Violations:** 1,970,575 rows (the roadmap's known limit: about 2M of about 11M violations; open ones are present, closed history is partial). Classes A, B, C and I; open 510,150 and closed 1,460,420 by `violationstatus`; 21 distinct `currentstatus` texts. 156,866 distinct BINs and 150,663 distinct BBLs; 5 rows have no BBL or BIN. Largest building: 2,329 violations.
- **Complaints:** 16,167,204 problem rows in 8,827,077 complaints on 261,758 BINs, from 2001-12-16. 2,621,726 problem rows carry the duplicate flag. Types: EMERGENCY, NON EMERGENCY, IMMEDIATE EMERGENCY, HAZARDOUS, REFERRAL. The rows carry apartment, unit type and an anonymous flag, which are never loaded (mission, out of scope).
- **Litigation:** 239,434 cases, 14 case types. `casestatus` mixes a status and a date ("DENIED , 03/..."); `caseopendate` runs from 0204-03-28 to 2030-10-05; `respondent` is a free-text list of names.
- **The tables are newer than the snapshot date.** The snapshot date 2026-05-29 is the latest registration date, but violations have 12,423 inspections and an NOV issued as late as 2026-07-06, complaints have 69,433 problems received after 2026-05-29 (latest 2026-07-07), and `currentstatusdate` holds the sentinel 9999-12-11. Deeds run to 2026-06-01. The Q15 and Q27 examples in the detail document are from an older snapshot (2026-10-17) and do not apply.
- **Joins:** violations, complaints and litigation each carry `bin` and `bbl`. The graph's 200,172 buildings are those HPD registered; the lots are all 859,636 PLUTO lots. How many violation, complaint and litigation BINs fall outside the registered buildings is not yet measured (the source tables have no BIN index, so the check needs a staged load); it is the first task of steps 2 to 4 and is reported in the note's update.

## Decisions for the user

**C1. How violations are stored.**
- **(a) One `Violation` node per row (1.97M), recommended.** Each can be cited by id, carries its class, status, dates and provenance, and later questions need it: Q14 (state on a violation date) and Q21 (violations across a layer) both walk to individual violations. The volume is below ACRIS roles (9.96M). Linked to its building by BIN, to the lot by BBL when the building is not in the graph.
- (b) Per-building counts only. Smaller, but nothing to cite and Q14 and Q21 would need a rebuild.

**C2. How complaints are stored.**
- **(a) Aggregate nodes, recommended.** One `ComplaintSummary` per building, year, type and problem status, holding `problem_count`, `complaint_count` (distinct complaint ids) and the latest received date, plus a second kind by major category holding problem counts only (a complaint spans categories, so complaint counts exist only at the type level). No apartment, unit, complainant or anonymity field is ever read into the graph, so the privacy boundary is built in, not enforced by the tool. Problem rows with the duplicate flag are counted in a separate `duplicate_problem_count` and left out of the main count; the answer says which it reports.
- (b) A node per problem row without the private fields (16M nodes): heavy, and a detail the questions never ask for.
- (c) One total per building: cannot answer "since 2022".

**C3. How litigation respondents are stored.**
- **(a) Respondent names as properties on the `Litigation` node, recommended:** the raw text, the split list `respondent_names` and their N1 forms `respondent_names_n1`. A respondent name does not assert ownership (note 0009); Q28 compares a respondent with the registered owner by exact N1 at query time, as Q3 does. No `Role` nodes yet.
- (b) `Party` and `Role` nodes for each respondent (role `respondent`). Right once Q22 and Q23 need respondents as entities, which is Slice 5, so it can wait.

**C4. Dates after the snapshot date and bad dates.**
- **(a) Keep every source row; give each source its own as-of date, recommended.** The Snapshot node gets `hpd_violations_as_of`, `hpd_complaints_as_of` and `hpd_litigation_as_of` (the latest date the table holds, excluding sentinels), and every Slice 2 answer states its source's as-of date beside the snapshot id. "Open" means the source's own `violationstatus` at that date. Implausible dates (before 1900 or after the as-of date) are kept as text in a `_raw` property and flagged, as in notes 0014 and 0015, never repaired. The sentinel year 9999 is treated the same way.
- (b) Drop rows dated after 2026-05-29: loses real current violations and still leaves the status of older ones as of July.
- (c) Re-date everything to 2026-05-29: hides what the data is.

**C5. Vocabularies.** New SKOS schemes: `violation-class` (A, B, C, I), `violation-status-group` (open, closed, derived from `violationstatus`; the 21 `currentstatus` texts are kept as the source writes them), `complaint-type` (5 values) and `litigation-case-type` (14 values), each with the source's spelling as a hidden label. **Recommended** as stated; the alternative is leaving the source texts as plain strings with no scheme, which the earlier modules did not do.

**C6. Q17 is derived at query time, no new nodes, recommended.** The tool reads the building's or lot's registrations (period end), PLUTO units and year built, and the latest deed date (ACRIS), and reports each condition with its dates: no registration in the dataset; the latest period ended before the as-of date; the latest registration older than the latest deed. It states units and the 3+ threshold and says it does not decide applicability; new construction is named as a legitimate reason for no registration. The as-of date for registration is 2026-05-29. The alternative is a stored `RegistrationStatus` node, which would freeze a judgment in the graph for no benefit.

## Build order

1. Decisions C1 to C6 and the schema (vocabularies, ontology module `hpd_conditions` or additions to `hpd`, shapes, indexes), with the matching spec lines.
2. Litigation and Q28 (smallest source, tests the respondent and date rules).
3. Violations and Q15 (the largest load: batch it as ACRIS was, with scoped validation in tests).
4. Complaints and Q27 (aggregated in SQL so 16M rows never reach Python as nodes).
5. Q17 (no load).
6. Expected answers re-derived from the snapshot for anchors A to G (SQL kept beside them), evaluation examples for the four questions, then the Slice 2 exit check (note 0021) including Slice 1 regression.

Each step ends with tests on the anchors against the expected answers, a validated citywide load where there is one, and no commit until asked.

## Risks

- Violation and complaint BINs outside the registered buildings attach to the lot only, so a building's count can differ from the lot's. The answer states which it reports.
- Violations are about a fifth of all violations (known limit). Q15 therefore counts what the snapshot holds and says closed history is partial.
- Load time: violations about the size of the ACRIS parties; complaints are aggregated first; the full citywide validation stays the build gate and the tests stay scoped.
- Class names and source-named subclasses stay NYC-specific (memory: NYC-only scope).

## Schema as built (step 1)

Module `ontology/conditions.ttl` and `conditions.shapes.ttl` (prefix `cond:`): `Violation` (key `violation_id`), `ComplaintSummary` (key `summary_id`, grouping `type` or `category`) and `Litigation` (key `litigation_id`), each with the flat provenance shape, on a lot (required) through `ON_LOT` and on a building (when in the graph) through `ON_BUILDING`. Source as-of dates are three properties on the `Snapshot` node. Vocabularies: `violation-class` (A, B, C, I), `violation-status-group` (open, closed), `complaint-type` (5) and `litigation-case-type` (14), each with the source's spelling as `x-hpd` hidden labels; the raw case type is always kept. Violations with no BBL (5 rows) and rows whose lot is not in the graph are not loaded and are counted. The shapes compile with the rest in one pass.

## Step 2 built: litigation and Q28 (2026-10-28)

`etl/conditions.py` (`litigation_node`), `build_litigation` and `--modules litigation`; `agent/tools/conditions.py` `get_hpd_litigation` (Q28), registered in the harness with a prompt rule. Citywide load: 239,060 cases on lots (374 skipped because their lot is not in the graph), 210,428 also on a building; validation 0 violations. The litigation as-of date is **2026-07-09**, the latest case open date not after the build date; it is stored on the Snapshot node and returned with every Q28 answer. The as-of rule for all three sources is that date: the latest event date the table holds that is not after the build date, because a later date is a typing error or sentinel. The respondent text is split at commas; a respondent matches a registered owner only by exact N1 on the owner's organization or person name, and a match is a lead. Tests: 13 in `tests/test_litigation_build.py` (transforms, the anchors loaded and validated, Q28 against the anchor cases); the suite is 254 passing.

## Step 3 built: violations and Q15 (2026-10-28)

`violation_node`, `build_violations`, `--modules violations`; `get_hpd_violations` (Q15) in `agent/tools/conditions.py`, registered in the harness with a prompt rule. Citywide load: 1,965,893 violations, all on a lot; 1,903,380 also on a registered building. The other 62,513 (3.2%) carry a BIN that is not a building in the graph (not HPD-registered, or one of the BINs on several lots), so they are counted on the lot and shown in the answer under "not tied to a building in the graph". 5 rows without a class and 4,677 on a lot not in the graph were skipped. Validation 0 violations. The violations as-of date is **2026-07-02**; the tool reports it beside the snapshot and counts violations inspected after the snapshot date (anchor A has 3, inspected 2026-06-24). The answer gives counts by class (I kept apart from A, B, C) and by open or closed, the oldest open inspection date with the five oldest open ids, and open class A, B and C per PLUTO residential unit (lot-level). The detail document's Q15 example (20 open, snapshot 2026-10-17) is from another snapshot and is superseded by the anchors' expected answers, to be derived in step 6. Tests: 14 in `tests/test_violation_build.py` (transforms, the 132 anchor violations loaded and validated, counts checked against the fixture rows and the source); the suite is 268 passing.

## Step 4 built: complaints and Q27 (2026-10-28)

`complaint_summary_node`, `build_complaints`, `--modules complaints`; `get_hpd_complaints(bbl, since_year)` (Q27) in `agent/tools/conditions.py`, with a prompt rule. The source rows are aggregated in the database (`source.complaint_groups`), so the 16M problem rows never reach Python and no apartment, unit, complainant or anonymity column is selected. Citywide load: 5,876,670 summaries (type and major-category groups by building, year and problem status), all on a lot, 5,031,881 also on a registered building; 9,335 groups on a lot not in the graph were skipped; validation 0 violations. The complaints as-of date is **2026-07-07** (latest problem received, not after the build date). The answer counts problem rows with duplicates left out (6 of 45 for anchor C since 2022 are flagged duplicate), gives distinct complaints per type with the note that they do not add to a total, the problems per PLUTO residential unit, and the as-of date. Anchor C since 2022: 39 problems, all closed, latest 2026-04-20, 1.22 per unit. Tests: 21 in `tests/test_complaint_build.py` (transforms, no private field can reach a summary, the anchor groups loaded and validated, counts checked against the fixture groups); the suite is 289 passing.

## Step 5 built: Q17 (2026-10-28)

`get_registration_status(bbl)` in `agent/tools/conditions.py`, with a prompt rule; no new data and no new nodes (C6). It reports, each with dates: no registration in the dataset; the latest registration period on the lot ended before the snapshot date (`lapsed`); the latest registration date is earlier than the latest recorded non-correction deed (`registration_older_than_latest_deed`). It adds the lot's PLUTO residential and total units against the dataset's 3+ threshold, the year built, a "built recently, may be legitimately unregistered" flag when the year built is within two years of the snapshot year, and a note when the latest deed is for $0. It never says the owner failed to register. Live: anchor E is registered, lapsed (ended 2021-09-01) and older than the 2026-04-21 deed; anchor F (40 units, built 2025) has no registration and is flagged recently built; anchor A's period ends 2026-09-01 (not lapsed). Tests: 11 in `tests/test_registration_status.py`. Steps 1 to 5 are built; step 6 (expected answers for the anchors, evaluation examples, exit check 0021) remains.
