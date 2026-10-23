# 0002: Reliability stays two-level; source category and review status are separate properties

Date: 2026-10-15

Status: **accepted 2026-10-15.** `CLAUDE.md` and `docs/competency-questions.md` updated to match.

## Decision
Keep two reliability levels, defined by how an assertion was obtained:

- **I, recorded assertion:** a public record states it, or it follows from joining records on an official identifier (BBL, BIN, document id, registration id).
- **II, derived conclusion:** a method links or classifies where the records do not say so.

Add two properties that answer different questions:

- **`source_category`:** what kind of source supplied the assertion. Values: `public_record`, `published_reporting`, `web_content` (other).
- **`review_status`:** whether anyone has checked it. Values: `unreviewed`, `confirmed`, `refuted`, `inconclusive`, `contested`.

Web search is a retrieval channel, not a category. A primary record found by search is `public_record`, Type I, with its URL and `retrieved_at` in the provenance.

A third party's claim (for example a news article's statement that a fund controls an LLC) is stored as its own relationship type, such as `REPORTED_AFFILIATION`, never as a property on a recorded relationship. It carries `publisher`, `url`, `published_at`, `quoted_claim`, `retrieved_at`, and `source_category: published_reporting`. Its reliability is **I** only as to the fact that the claim was published. Whether the claim is true and applies to the subject is a separate judgment, and any link our method draws from it is a Type II relationship that cites the claim as evidence.

## Context
- `CLAUDE.md` defines Type I as "recorded in a public record" and Type II as inferred links, including "web research". A news claim is not a public record, so by exclusion it fell into II. That mixes "our method inferred this" with "someone else asserted this", two different risks.
- Competency question requirement 6 and open item 2 (draft 3) already treat a published claim as a recorded assertion that it was published, with its truth a separate matter.
- The agent's week 6 rule ("interrupt on Type II-only answers") needs a clear definition of which answers it covers.

## Alternatives considered
- **A third level "III: reported".** One simple ordinal, but it mixes source type into the derivation axis. Reporting quality varies more than one level can express, and a Type II link resting on a news claim has no clear level.
- **Split II into IIa (our method) and IIb (third party).** Same ordinal problem, and "II" would name two unlike things.
- **Keep the current definition unchanged.** Cheapest, but keeps the conflation above.

## Consequences
- **Three properties per fact** (`reliability`, `source_category`, `review_status`) instead of one. Provenance (`source`, `source_record_id`, `retrieved_at`) is unchanged.
- **Agent rule:** interrupt, and label as a lead, any answer whose chain contains a non-Type-I link or a `published_reporting` or `web_content` source. Reported claims are shown as attributed ("an article by X dated Y states…"), never as findings.
- **Publishing rules** (`CLAUDE.md`, "Publishing responsibly") are unchanged. People still appear only in roles recorded in HPD, ACRIS or DOS filings. Whether attributed statements about people from reporting may be shown is a separate decision, still open.
- **Ontology:** week 2 vocabulary needs `SourceCategory` and `ReviewStatus` concept schemes, and week 3 needs a reported-claim relationship with its own SHACL shape.
- **Edits needed on acceptance:** the "Reliability on every fact" and "Provenance" lines in `CLAUDE.md`'s Graph conventions, and the reliability paragraph of `docs/competency-questions.md`.
- **Revisit:** who sets `review_status`, and what justifies a change (`confirmed` after checking a primary record, say). Not decided here. Decided in note 0003 (2026-10-17).
- **Update 2026-10-17:** the open question on attributed statements about people from reporting is decided: they are allowed only as reported claims, attributed and `unreviewed`, never as roles (`CLAUDE.md`, "Publishing responsibly").
- **Update 2026-10-18:** `source_category` gains a fourth value, `project_derived`, for the BOR/NLR layers and the curated mail-drop list; see note 0004.
