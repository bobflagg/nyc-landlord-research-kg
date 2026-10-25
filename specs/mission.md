# Mission

Status: draft for review, 2026-10-18.

## Purpose

Build public accountability infrastructure for New York City housing. Journalists, tenant advocates, watchdog agencies and the public should be able to investigate housing conditions and ownership using evidence from the city's public record, and to see exactly where each piece of evidence came from.

The core of the product is a **knowledge graph** of NYC properties, the entities that own and manage them, and what the public record says about them. Applications, starting with an investigator agent, are built on the graph.

The product grows in **stages**. Each stage serves a user group through a set of competency questions, and each follows the same pattern: extend the questions, the controlled vocabulary, the ontology, the ingestion pipeline, then the agent.

## Users

| Stage | Users | What they need |
| --- | --- | --- |
| 1 (current) | **Tenant organizers and advocates** | From one address: who controls the building, how big the portfolio is, conditions across it, and who to pressure |
| Later | Journalists | Claims they can verify and cite, with history over time |
| Later | Watchdog agencies | Patterns across many buildings and owners |
| Later | The public | Plain answers about a building or owner, with their limits stated |

## Outcomes

1. **Traceable evidence.** Every claim names its source record, the data snapshot it comes from, and how it was obtained.
2. **Recorded facts kept apart from derived ones.** What a public record states (Type I) is never presented the same way as what a method inferred or a third party reported (Type II, reported claims). A derived ownership group is a lead, never a finding.
3. **Honest absence.** "Not found" always says why: no linkage, excluded by policy, below an eligibility rule, outside the source's coverage, or outside the method's input.
4. **Stage 1 is done when its 28 competency questions pass:**
   - every Type I question returns the correct answer;
   - every Type II and mixed question returns the correct answer with its required caveats and reason codes;
   - Q20, the integration scenario, passes as a whole against the end-to-end acceptance requirement.

The questions and their contracts are in `docs/competency-questions.md`.

## Boundaries that hold in every stage

- **Names are shown with their source.** A name appears wherever the data has it, with its role (if any), source, reliability and snapshot. A name never asserts a role: a person named only in a report is an attributed, unreviewed reported claim, not an owner. A name match between records is a lead, not a finding (design note 0009).
- **No personal information.** No following links to individuals' home addresses or other non-business information.
- **Only a person marks a fact as checked.** The system can mark a fact `unreviewed` or `contested`, never `confirmed` (design note 0003).
- **Answers state their limits.** Snapshot date, counting unit (lot, building or unit) and which ownership layer was used.

## Non-goals

These apply to every stage:

- **Legal determinations** of ownership or liability.
- **Anything about tenants or individual apartments.** Complaint data is used only as building-level counts.
- **Non-public or paid sources.**
- **Building our own entity resolution.** Owner Portfolio and Operational Network come from BOR/NLR (design note 0001).
- **Regulator mapping** (which agencies oversee an owner).

Not yet in scope, and sequenced in `specs/roadmap.md`: a hosted application, user interfaces for specific audiences, and the review process that lets a checked web finding enter the graph.
