# 0008: The snapshot identifier

Date: 2026-10-22

Status: **accepted 2026-10-22.** Settles the open decision "the snapshot identifier's form" in `specs/tech-stack.md`. Answers BOR's request for the first frozen release (`beneficial-ownership-resolution/docs/release.md`, "The snapshot id"; `docs/kg-mapping.md`). Builds on notes 0005 and 0007.

## Decision

1. **A snapshot id identifies one source dump,** not a graph build. The justfixwow dump is one snapshot: PLUTO, ACRIS, HPD and the DOS table in it all share its id. A separately downloaded source gets its own id.
2. **Form:** `<source>-<YYYY-MM-DD>`, with a revision suffix `-rN` when the same date is extracted again with different content. Example: `justfixwow-2026-05-29`, then `justfixwow-2026-05-29-r2`. Rules: lowercase letters, digits and hyphens; at most 40 characters. The loader checks `^[a-z][a-z0-9]*-\d{4}-\d{2}-\d{2}(-r\d+)?$`. The date is also a separate field, `snapshot_date` (ISO 8601); nothing parses it out of the id.
3. **The date is the data's date,** not the build or download day. For the justfixwow dump it is the earlier of the newest `real_property_master.recordedfiled` and the newest `hpd_registrations.lastregistrationdate`, so the id means "complete through" that date and an answer never claims more recent data than the dump holds. Both maxima are recorded alongside it. On the reference dump both are 2026-05-29.
4. **A revision suffix is added only when fingerprints differ** from an already-released id for the same date. The fingerprints, not the suffix, are what establish identity.
5. **Facts carry the id of the dump their source rows came from.** Every graph fact, including BOR's Type II links, carries the dump's `snapshot_id` as the flat property of note 0005. The BOR `run_id` is recorded separately on Type II links and in the catalog.
6. **The id is not a freshness claim for each table.** The snapshot catalog (the small catalog of snapshot and run nodes in note 0005) holds an `as_of` date per source table and answers cite it beside the snapshot, for example "snapshot justfixwow-2026-05-29; violations through 2026-07-02". `as_of` is the newest valid date in the table, ignoring sentinel and future dates, which are counted and reported.
7. **The loader reads the id from the release manifest and verifies it by fingerprint;** it does not re-derive it. As a cross-check it runs the two date queries on its own load and refuses a mismatch.
8. **Fingerprint checks.** Using BOR's `bor.manifest.fingerprint_sql` (row count and an order-independent sum of 60 bits of the md5 of each row):
   - *Required, refuse on mismatch:* `hpd_contacts`, `hpd_registrations`, `pluto_latest`, `real_property_master`, `real_property_legals`, `real_property_parties`.
   - *Warning only:* `wow_landlords`, `hpd_registrations_grouped_by_bbl_with_contacts`, which the graph does not read.
   - *Skipped:* `landlords_with_connections`, which is built by BOR and matches only its own build.
   - The graph reads the justfixwow database directly as a build input and does not mirror it, so these checks run against that database. The catalog records `row_count`, `fingerprint` and the method for every table the graph loads, including the ones BOR does not fingerprint (violations, complaints, litigations, DOS).

## Context

- BOR releases are frozen and valid only with the matching source snapshot (note 0007). The id appears on every fact the graph loads, so its form had to be settled before the first frozen release. BOR's first placeholder used the build day (2026-10-21), which would have overstated the data's currency by about five months.
- Newest dates in the dump, measured on 2026-10-22: ACRIS `recordedfiled` 2026-05-29; HPD `lastregistrationdate` 2026-05-29; HPD violations (inspection) 2026-07-02; HPD complaints (received) 2026-07-07; HPD litigations (case open) 2026-07-09 once dates later than that are excluded (the raw maximum is 2030-10-05); DOS (initial filing) 2026-07-06. So the id's date understates several tables, which is the safe direction but needs the per-table dates of item 6.
- Verified on the database the graph reads: the row counts and fingerprints of `hpd_contacts` (782,024), `hpd_registrations` (203,236), `pluto_latest` (858,602) and `wow_landlords` (171,347) equal those in the manifest of a BOR build, so both read the same dump. The three ACRIS tables (17M to 46M rows) were not fingerprinted in that check. That manifest still carries BOR's placeholder id, so it predates the date fix.
- The mission requires answers to state their snapshot date, and the competency questions treat a source whose snapshot predates the period asked about as "outside source coverage" (Q26). That needs a date per source table, not one for the whole dump.

## Alternatives considered

- **The build or download date.** Overstates currency, and two builds of the same dump would get different ids.
- **A content hash as the id.** Exact, but unreadable in an answer. Fingerprints already do this job.
- **One id for the whole graph build.** Mixes sources of different vintages and cannot say which source a fact came from. DOS, for instance, may be refreshed on a different schedule.
- **The later of the two maxima.** Would claim data the dump may not hold for the other table.
- **A separate PLUTO snapshot id.** PLUTO is part of the dump, so it shares the id. PLUTO's own `version` and `appdate` columns are recorded in the catalog as they are (values not yet read).

## Consequences

- **Edits made with this note:** `specs/tech-stack.md` (the snapshot row names the form; the identifier is removed from "Open decisions").
- **Catalog:** the snapshot node holds `snapshot_id`, `snapshot_date`, both date maxima, per-table `as_of`, fingerprints and the PLUTO version. The columns used for `as_of` (`recordedfiled`, `lastregistrationdate`, `inspectiondate`, `receiveddate`, `caseopendate`, `initialdosfilingdate`) are an initial choice and may change when the loaders are written.
- **Shapes:** SHACL checks `snapshot_id` against the pattern above on every fact, and rejects a fact whose id is not in the catalog.
- **Live data:** Socrata and web results keep their retrieval time (tech stack); they are not snapshots.
- **Revisit:** the `as_of` columns per table; what to do when the earlier-of-two rule leaves a gap of more than a few weeks between the two maxima (the manifest shows both, so it is visible).
