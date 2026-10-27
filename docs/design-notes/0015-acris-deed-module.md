# 0015: ACRIS deed module

Date: 2026-10-27

Status: **accepted 2026-10-27** ("all as recommended" on C1 to C4). Builds on notes 0004, 0006, 0009, 0010 and 0014. Closes the open ACRIS-party question in note 0006. Amends the core shapes as listed under Consequences.

## Decision

1. **Scope (C1).** Slice 1 loads the **deed family only**: ACRIS document types `DEED`, `DEED, TS`, `DEED, LE`, `DEEDO`, `DEED COR`, `DEED, RC`, `DEEDP`, the codes that have a concept in `vocab/document-type.ttl`. About 3.8M documents and 11.7M party rows before the lot filter. A document is loaded only when one of its legals is a lot in the graph (PLUTO or HPD-registered), and is linked to each such lot. Mortgages, satisfactions, assignments and the other types wait for Slice 3 (Q12, Q13), and Q24's non-deed documents move there with them; Q24 reports deed documents only and says so as a coverage limit.
2. **Document, party and role (C2).**
   - `Document`, keyed by `document_id`: `crfn`, `doc_type` (vocabulary notation) and `doc_type_raw`, `doc_date`, `recorded`, `amount`. Source `acris_master`, record id the document id. `ON_LOT` to each lot in its legals. Structural, no provenance of its own.
   - The source repeats a document once per modification (4,663 extra rows among deed documents); the **latest `modifieddate` row** is loaded.
   - **Dates.** `doc_date` is stored only inside 1900 to the snapshot date. ACRIS holds dates from year 0001 and some in 2028; outside the range the value is kept as text in `doc_date_raw` and `doc_date` is absent: reported and flagged, never repaired. Recorded dates in the deed family are all in range.
   - `AcrisParty` (subclass of `Party`) at the (name, address line 1 and 2, city, state, zip, country) grain, key `party_id` = `acris:` + md5 of those fields, upper-cased and whitespace collapsed. The prefix keeps the key apart from HPD's.
   - `AcrisRole` (subclass of `Role`) per party row, key `role_id` = `acris:` + md5 of the document id, party type and the party fields (the source has no row id, so an exact repeat of a row collapses). `IN_DOCUMENT` to its document and `HELD_BY` to its party. A role is **in a document, not on a building or lot** (the document is on the lots), so the exactly-one-of-building-or-lot check skips `AcrisRole` and `AcrisRoleShape` forbids both edges.
3. **Role values (C3).** `role-type.ttl` gains the grouping `deed_party` and `grantor` (party 1), `grantee` (2) and `life_estate_retained` (3, confirmed only on `DEED, LE`). Codes sit on `skos:hiddenLabel` with the tag `@x-acris`. Party 3 on any other deed code has no concept: the role is loaded with `role_type` absent and the raw code in `source_role_code` (78 rows, on `DEED` and `DEEDO`). The vocabulary says what the document records; a grantee is not a finding of ownership.
4. **Name key (C4).** `name_n1`, the rule N1 form of the name (note 0006), is stored on `HpdParty` (organization name, else person name) and `AcrisParty`, and indexed, together with `AcrisParty.address_key`. It is a normalized spelling, not a stored match, so note 0009 item 4 holds: Q3 and Q24 compare at query time and a match is a lead.

## Context

- Q3 compares the latest deed's grantee with the HPD owner; Q24 starts from a name and lists its documents. Anchor lots A to G give expected deeds, dates, amounts and grantees (`evals/expected/slice1.json`).
- Source tables (`real_property_master` 17.0M rows, `real_property_parties` 46.3M, `real_property_legals` 22.7M) have `documentid` indexes, so a chunk of documents fetches its parties and legals by lookup.
- Document ids are strings: 16 digits, or `FT_` plus digits for older documents.
- Correction documents `CORRD`, `CORRM`, `CORR` and `CORR, LE` are **not** in the deed family of note 0004 and are not loaded.

## Alternatives considered

- **All document types now** (C1 B): Q24 would match its expected answer, at 17M documents and 46M party rows before any question needs them.
- **Party fields on each role row, no identity node** (C2 alternative): 11.7M party-like nodes with no shared identity.
- **Compute N1 in the query** (C4 alternative): scans every party.
- **A single `role_type` for every party 3**: invents a meaning note 0004 says is unsettled.

## Consequences

- **Edits made with this note:**
  - `vocab/document-type.ttl` (new); `vocab/role-type.ttl` gains `deed_party`, `grantor`, `grantee`, `life_estate_retained`.
  - `ontology/acris.ttl` and `acris.shapes.ttl` (new). Core: `wl:name_n1` added; `RoleShape` no longer requires `role_type` (HPD's shape still does, ACRIS's allows it absent).
  - `etl/checks/role_attachment.cypher` skips `AcrisRole`.
  - `etl/acris.py`, `build.load_acris` and `build_acris`, source readers, and `run_build --modules acris`.
  - `HpdParty` gets `name_n1`. Existing HPD parties get it on the next HPD load, which is idempotent.
- **Tests:** `tests/test_acris_build.py` (23 transform and graph tests on the anchors; deeds, dates, amounts and grantees match the Q3 expected answers). Fixture `tests/fixtures/slice1_acris.json` holds the 37 deed documents on the seven anchor lots.
- **District 307** loaded: 57,847 documents, 153,991 parties, 198,250 roles in about 3 minutes. The ACRIS shapes report no violation. The five `5413 PLAZA LLC` deed rows of Q24 (the 2021 and 2025 deeds) are found.
- **Not loaded, so not answerable yet:** Q24's mortgage, assignment and similar documents; condo unit lots that PLUTO does not hold; documents whose legals name no lot in the graph.
- **Citywide ACRIS load** is not run. At the district rate it would take about one to two hours.
- **Open:** the DOS module (Q5); the Q3 and Q24 tools; party-type meanings for the non-deed types (Slice 3).
