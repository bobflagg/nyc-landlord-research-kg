# 0014: The HPD and PLUTO module

Date: 2026-10-26

Status: **accepted 2026-10-26** (decisions 1 to 5 chosen as recommended). Builds on notes 0004, 0006, 0009, 0010 and 0013. Amends note 0010's count of registrations without a real BIN.

## Decision

1. **A role attaches directly to its building (or its lot), and also points to its registration.** A `Registration` is on its lot always and on its building when it has a real BIN. The core Role shape and the `role_attachment` check are unchanged. These structural edges carry no provenance (note 0010, item 4).
2. **Seven role types** in `vocab/role-type.ttl`: `registered_owner` (HPD CorporateOwner, IndividualOwner, JointOwner), `head_officer`, `officer`, `shareholder`, `managing_agent` (Agent), `site_manager`, `lessee`. Two groupings that name what the record says, `registered_principal` and `management`. The HPD codes sit on `skos:hiddenLabel` with the language tag `x-hpd`, and the loader reads its mapping from there. An unknown HPD type raises an error and no role is dropped.
3. **Owner kind** in `vocab/entity-kind.ttl`: `individual`, `joint`, `corporation`, `partnership_or_llc` (GEN.PART, PARTNERSHIP/LLC, LLC), `trust` (any case), `co_op`, `condo`. It is a property of the registration (`owner_kind`), and the recorded value stays in `owner_kind_raw`. ESTATE, TRUSTEE and free text map to nothing. The GEN.PART reading is an inference from names (88.7% of GEN.PART owners end in LLC); no HPD codebook confirms it.
4. **Lot attributes from PLUTO:** `address_text`, `address_key`, `zip5`, `building_class`, `units_residential`, `units_total`, `buildings_count`, `year_built`, `assessed_total`, `owner_name_pluto`, `community_district`. All optional. PLUTO's year 0 (unknown) is not stored. No land use, FAR, coordinates or zoning: no question uses them.
5. **An HPD lot PLUTO does not hold** (1,032 BBLs) is created from the HPD record with source `hpd_registrations` and none of the PLUTO attributes. PLUTO loads first, and the HPD load sets a lot's provenance only when it creates the lot, so a lot PLUTO holds keeps `source: pluto`.

## Details settled while building

- **Classes:** `Registration` (key `registration_id`), `HpdParty` (a `Party` with the label `HpdParty`), `HpdRole` (a `Role` with the label `HpdRole`). The key constraints sit on `Party` and `Role`.
- **Party identity** is `md5` over the HPD contact type, organization name, first name, middle initial, last name, and business house, street, apartment, city, state and zip, each upper-cased and trimmed. The contact type is always part of it, so an agent and an owner with the same name and address are separate parties (Q23). This is our own key: BOR's nodes are run-scoped and do not use it (note 0007), so it does not need to match NLR's. Names are stored as `organization_name` and `person_name`, separately, and shown with their role and source (note 0009).
- **Business address** is stored as house, street, apartment, city, state, zip, plus `business_address_key` (rule A2, indexed). A shared key is a lead, never a link by itself.
- **Dates** are stored as Neo4j `DATE`.
- **A building** is keyed by BIN. Several HPD building ids can share one BIN (1,188 do), and 76 building ids have two registrations; the building takes the latest registration's address, and each registration keeps its own `hpd_building_id`.
- **Registration-level owner kind:** `contactdescription` repeats on every contact row of a registration, so the first non-empty value is used.
- **Count correction:** note 0010 says 396 of 203,236 registrations lack a real BIN. By today's definition (null, blank, `0`, padded `0` and `x000000` placeholders) it is 757. The roles of those registrations attach to the lot.
- **Build:** `etl/build.py` loads PLUTO, then HPD in chunks of 2,000 registrations, each in its own write transaction. `etl/run_build.py` streams the justfixwow database through a server-side cursor (`JUSTFIX_DATABASE_URL` in `.env`), optionally for one community district, and then validates. The build is re-runnable.
- **Shapes compile together** (`ontology/generated/shapes.cypher`, 113 rules). Compiled one module at a time, a shape used from another module (the provenance shape) was treated as empty and its rule passed silently; `scripts/compile_shapes.py` now compiles all modules in one pass.

## Context

- Q1, Q2 and Q4 need the lot, the registration with its dates, and the roles. Q3 and Q5 need the HPD owner name and business address on the party. Q24 needs roles by lot. Q26 needs registrations that are missing or lapsed.
- The expected answers (`evals/expected/slice1.json`) are the check: the seven anchor lots, loaded from `tests/fixtures/slice1_anchors.json`, give the expected Q1 lot attributes and buildings, Q2 registrations and Q4 roles with names, titles and contact ids.

## Alternatives considered

- **Role only points to its registration** (decision 1, option B): normalized, but changes the core Role shape and doubles the hops for Q4.
- **HPD's nine contact types as concepts** (decision 2, option B): leaves no room for ACRIS and DOS roles in one scheme.
- **LLC kept apart from GEN.PART** (decision 3, option B): closer to the codes, but splits the commonest kind.
- **Drop registrations for lots PLUTO lacks** (decision 5, option B): loses them for Q2 and Q26 with no way to say why.

## Consequences

- Vocabulary: `vocab/role-type.ttl`, `vocab/entity-kind.ttl`. Ontology: `ontology/pluto.ttl`, `hpd.ttl` and their shapes.
- The citywide build has not been run: it needs `JUSTFIX_DATABASE_URL`. Everything else is tested on the anchor lots.
- Open: the ACRIS and DOS modules (deeds, grantee comparison, entity records) for Q3, Q5, Q24; the `role_type` values for ACRIS and DOS roles; corner addresses.
