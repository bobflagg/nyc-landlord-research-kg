# 0003: Who sets `review_status`

Date: 2026-10-17

Status: **accepted 2026-10-17.** Resolves the "revisit" item in note 0002 and open item 2 in `docs/competency-questions.md`.

## Decision
Only a person decides that a fact has been checked.

- **Pipeline and agent** may write two values: `unreviewed` (the default) and `contested`. `contested` is a factual observation that records or reports disagree. It lists the conflicting items.
- **A person** sets `confirmed`, `refuted` or `inconclusive`, by creating a **review record**. A review record is never an overwrite: it holds `reviewer`, `reviewed_at`, `status`, `basis` (a primary record id or URL, or a reason), and `previous_status`. The current status is the latest review record.
- **Corroboration is not review.** Two independent sources agreeing is stored as evidence on the fact. It never changes `review_status`.

Meaning of each value:

| Value | Meaning |
| --- | --- |
| `unreviewed` | No person has checked the fact. The default. |
| `contested` | Records or reports disagree; none is decisive. Set by the pipeline or by a person. |
| `confirmed` | A person checked it against a primary record that states the same thing. |
| `refuted` | A person checked it and a primary record contradicts it. |
| `inconclusive` | A person checked and could not decide. |

Where the property is required:

- **Required** on Type II links, reported claims (`published_reporting`), and web or document findings.
- **Not written** on Type I rows loaded from the datasets (PLUTO, ACRIS, HPD, DOS). A missing value means `unreviewed`. Writing it on millions of recorded rows would add noise and no information.

## Context
- Note 0002 added `review_status` and left open who sets it. Without a rule, the pipeline could mark a fact `confirmed` because two sources agree, and the status would then look like a human check.
- The competency questions already assume this split: Q16 and the end-to-end requirement keep claims `unreviewed` unless a person has checked them, and two contradicting articles are shown `contested`.
- The agent's graph access is read-only, and web findings are session evidence. Nothing in the pipeline can write a review today.

## Alternatives considered
- **A. Humans only.** Simplest and honest, but `contested` would depend on someone noticing a conflict, and two plainly conflicting records would sit at `unreviewed`.
- **B. Rule-based statuses.** Scales, but it conflates "reviewed" with "corroborated" and can put a high-looking status on a link nobody checked.

## Consequences
- **Does not block the pipeline.** The ETL writes no `review_status` on Type I rows. The BOR/NLR Type II links, web findings and reported claims are written with `review_status: unreviewed`, a constant default. Weeks 2 to 7 need no review records, no reviewer interface and no promotion process.
- **Deferred:** the review-record store, the reviewer interface and any process that lets a finding reach the graph (competency questions, open item 5; deferred past week 8). Week 3 defines the review-record shape in the ontology and SHACL so it can be added later without a schema change.
- **Dossiers:** in a dossier, `review_status` is per session and set by the person running the investigation. The agent shows `unreviewed` or `contested` and nothing stronger.
- **Edits made with this note:** the `review_status` line in `CLAUDE.md` (Graph conventions), the "Publishing responsibly" exception for attributed reported claims (decided 2026-10-17, competency questions open item 3), and a pointer in note 0002.
- **Revisit:** whether a corroboration count should be a standard evidence property, and who counts as an authorized reviewer, once a promotion process is designed.
