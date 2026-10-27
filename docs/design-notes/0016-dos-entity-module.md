# 0016: DOS entity module

Date: 2026-10-27

Status: **accepted 2026-10-27** ("all as recommended" on E1 to E4). Builds on notes 0006, 0009, 0010 and 0015.

## Decision

1. **Class (settled by notes 0006 and 0010).** `DosEntity`, a `Party` subclass, loaded with the labels `Party` and `DosEntity`. Key `party_id` = `dos:<dosid>`; `dos_id` holds the id as a string. Source `dos_active_corporations`, record id the DOS id, Type I `public_record`. Active entities only: "no record" is never "does not exist" (Q5).
2. **Scope (E1).** Every row of `dos_active_corporations`: 4,242,054 entities, statewide. A name search for Q24 can start from any entity, and no county filter works (anchors F and G are filed from Nassau addresses). Selecting only entities that match an HPD or ACRIS name was rejected: the selection would depend on the other loads.
3. **Named people and addresses are properties (E2).** `process_name`, `registered_agent_name`, `ceo_name`, `location_name` and each one's address lines, city, state and zip, as written; empty fields are left off. They are attributes of the DOS record, shown with its source and snapshot, not roles: the process name is where the state forwards service and does not say who runs the entity (note 0009). The CEO's address line 1 often repeats the name in this source and is loaded as written. No officers, managers or members exist for LLCs, so absence of a CEO is reported as "not carried", not as "none". Roles for registered agent, CEO and process contact are decided in Slice 5 (Q6, Q7, Q11, Q23), when traversal needs them.
4. **Entity type (E3).** The raw `entity_type` only; no vocabulary, since no question filters on it (note 0004, D5).
5. **Address keys (E4).** No A2 key is computed or indexed for process or agent addresses yet; a rerun adds them when Slice 5 needs them.
6. **Name key.** `name_n1` (rule N1) is stored and indexed with `dos_id`, so Q3, Q5 and Q24 look names up through an index. It is a normalized spelling, not a stored match (note 0009 item 4). Exact normalization only: the HPD spelling `KS Turnpike LLC` does not find `K S TURNPIKE LLC` (anchor G).
7. **Dates.** `initial_filing_date` is a date; no source value is out of range.

## Context

- Q5 shows the entity record, or "no record" with its reason; Q3 compares a deed grantee's name with the HPD owner and the DOS record; Q24 starts from a name.
- Fill rates: process name 4.17M, registered agent 864k, CEO 474k, location name 346k. Entity types: domestic LLC 2.02M, domestic business corporation 1.45M, domestic not-for-profit 286k.
- One DOS address is shared by about 93,000 entities (note 0010), which is why address keys wait for Slice 5.

- **Found by the citywide load (2026-10-27):** anchor C's DOS name is `438 52ND ST. OWNERS' CORP.`, which equals the deed and PLUTO spelling under N1 (punctuation deleted). The expected Q5 answer for C had said no record under two spellings, from a check that did not delete the apostrophe and periods. Corrected in `evals/expected/slice1.json` and `docs/competency-questions-detail.md`; the HPD spelling `438 52 ST OWNERS CORP` still does not match. Anchor D is now the "absent" example.

## Alternatives considered

- **Only name-matched entities** (E1 b): smaller, but the selection depends on the other loads.
- **Role nodes for agent, CEO and process contact** (E2 b): traversal for Slice 5, at the cost of millions of role nodes that imply neither ownership nor control.
- **A SKOS scheme for entity type** (E3 b): a concept for a value no question uses.
- **Address keys now** (E4 b): an index no Slice 1 question uses.

## Consequences

- **Added:** `ontology/dos.ttl` and `dos.shapes.ttl` (shapes compile with the rest); `etl/dos.py`; `build_dos`; `source.dos_entities`; `run_build --modules dos`; indexes on `DosEntity.name_n1` and `dos_id`.
- **Tests:** `tests/test_dos_build.py` (17: transforms; the anchor entities match the Q5 expected records, including the statutory default `THE COMPANY`; exact N1 lookups find `5413 PLAZA LLC` and `K S TURNPIKE LLC` and not `KS Turnpike LLC` or either spelling of anchor C). Fixture `tests/fixtures/slice1_dos.json` holds seven real entities.
- **Not run:** the citywide load (4.24M entities).
- **Open:** the Q3 and Q5 comparison tools; the 29 `unknown` rows of the mail-drop list; roles for agents (Slice 5).
