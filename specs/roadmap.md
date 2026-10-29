# Roadmap

Status: draft for review, 2026-10-18. Slices are ordered by what they deliver, not by date.

## How a slice works

Each slice takes a group of competency questions through the stage pattern: **vocabulary → ontology → ingestion → agent tools → evaluation**. A slice is done when its questions pass under the mission's rule:

- Type I questions return the correct answer;
- Type II and mixed questions return the correct answer with their caveats and reason codes;
- every earlier slice still passes.

Expected answers come from the snapshot the graph was built from.

## Stage 1: Tenant organizers and advocates

Goal: from an address, a cited dossier on who controls a building and how it is run, built on the current justfixwow snapshot. Questions are in `docs/competency-questions.md`.

| Slice | Delivers | Questions | Depends on |
| --- | --- | --- | --- |
| **0. Foundations** | Core ontology module and shapes (property, lot, building, entity, role, provenance, reliability); core vocabularies (reliability, source category, review status); the snapshot-tagged load framework; the agent and evaluation harness; competency question examples and expected answers re-derived from the snapshot | none: a sample load validates under SHACL, and the harness runs one question end to end | Test framework, model provider, snapshot identifier |
| **1. Who is my landlord** | Address to lot and buildings; HPD owner, agent and officers; deed grantee compared with the HPD owner; DOS entity record; everything recorded against a name | Q1, Q2, Q3, Q4, Q5, Q24 | Slice 0 |
| **2. Conditions** | Open violations, complaints and HPD litigation at a building; missing or lapsed registration | Q15, Q17, Q27, Q28 | Slice 1 |
| **3. Transactions and history** | Deed transfers, mortgages and satisfactions; title holder and registrant on a past date | Q12, Q13, Q14 | Slice 1. Q14 needs the violation-history gap reported or backfilled |
| **4. Ownership layers** | Owner Portfolio and Operational Network memberships with evidence paths; why buildings are grouped or not; conditions across a layer; what each absence means | Q8, Q9, Q10, Q19, Q21, Q26 | BOR/NLR edge-level evidence export |
| **5. Links and identity** | Aggregator and mail-drop addresses; shared evidence between entities; affiliations; restructuring deeds; same entity or not; a managing agent's footprint | Q6, Q7, Q11, Q18, Q22, Q23 | Slice 4 |
| **6. Beyond the graph** | Reports and filing documents; out-of-state registries, held as session evidence | Q16, Q25 | Web search tool, retrieval cache (decided: design note 0028) |
| **7. The investigator** | The Deep Agents investigator: from an address to a dossier with an inference → source table, unresolved leads and a stop reason | Q20 (integration scenario, scored as a whole) | Slices 1–6 |

**Stage 1 is complete** when slice 7 passes and every earlier slice still passes.

Optional after Stage 1: a public demo of one community district on AuraDB Free (`docs/demo-slice.md`).

## Later horizons (not scheduled)

Each later stage starts by extending the competency questions for its users, then runs the same slices.

| Stage | Users | Likely question themes | New sources it may bring in |
| --- | --- | --- | --- |
| 2 | Journalists | Ownership and conditions over time; financial distress; verifying a claim end to end | Tax lien sale list, DOF sales and exemptions, full violation history |
| 3 | Watchdog agencies | Patterns across portfolios and owners; ranking and change over time | DOB violations and complaints, AEP, speculation watch list |
| 4 | The public | Plain-language answers about a building or owner | None new; a public interface on the existing graph |

## Cross-cutting work

Sequenced when a stage needs it:

- **Production snapshot.** Load a current justfixwow snapshot, produce a new frozen BOR release for it (BOR runs once per snapshot, and the graph loads that release without rerunning it; design note 0007), rebuild the graph, and re-derive the evaluation answers.
- **Live application and hosting** for the graph and agent.
- **Runtime Socrata access** for freshness checks, labeled by retrieval time.
- **Review records and a reviewer interface**, so a person can confirm or refute facts and a checked finding can enter the graph (design note 0003). The `ReviewRecord` class and its shape are defined here, not in Slice 0 (design note 0010).
