# 0006: Recorded-party identity nodes, and name and address comparison rules

Date: 2026-10-19

Status: **accepted 2026-10-19**, with name rule N1 and address rule A2 chosen. Builds on notes 0001, 0004 and 0005. ACRIS party nodes remain open (see Open).

## Decision

1. **Identity nodes for recorded parties.** Each distinct party as recorded in a source is a node: one per (contact kind, name, business address) for HPD contacts, the same grain NLR and BOR use. The node asserts only that this exact name and address were recorded. It never asserts that two records are one party; that judgment stays with BOR (Type II) and Q22.
   - **Key for the four owner roles** (HeadOfficer, IndividualOwner, CorporateOwner, JointOwner): NLR's formula unchanged, `md5(contact_kind | name_full | biz_house | biz_street | biz_apt | biz_zip | biz_city | biz_state)` over the same upper-cased, trimmed values. The key is a function of record content, so it is stable across builds (BOR group ids are not). **BOR's evidence edges do not attach to this key**; see "Correction" below.
   - **Key for the other contact types** (Agent, SiteManager, Officer, Shareholder, Lessee): the same formula prefixed with the HPD contact type, so an agent with the same name and address as an owner is a separate identity (Q23). The alternative is a coarser role-family prefix (management, officer, other).
   - **Properties:** the flat provenance set from note 0005 (`reliability: I`, `source_category: public_record`, `source: hpd_contacts`, `snapshot_id`). `source_record_id` and the building, role and dates live on the role node, one per registration contact.
2. **All nine HPD contact types are loaded as recorded roles.** NLR's restriction to the four owner roles is a matcher choice (agents and managers are shared across unrelated landlords, so they create false links through registered-agent addresses). It is not a limit on what the graph records. The PESP guide treats officers, registered agents and management companies as leads, and Q4, Q7, Q11 and Q23 need them. The mail-drop rule controls links at link time. The Type II layers state that BOR's matcher used the four owner roles.
3. **DOS and ACRIS.** `DOSEntity` is keyed by `dosid`. ACRIS party nodes at the same (name, address) grain are proposed but **open**, pending the BOR edge-level evidence export, which may attach deed-linkage evidence to ACRIS parties (note 0001).
4. **Q3 compares names, and reports address agreement separately.** The match stays on the exact normalized name, as Q3 is worded. The result also carries an address-agreement field, and the answer never says "same party" on name agreement alone.
   - **Name agreement:** exact normalized match, normalization match (with the rule id), or different.
   - **Address agreement:** same, differs, or absent on either side, compared by the address rule below, with unit reported separately and not part of the match.
   - **Mail-drop addresses:** agreement at an address on the mail-drop list is flagged as non-evidence.
5. **Comparison rules are versioned and named in the result.** NLR's own `name_normalized` (which drops legal suffixes) is a blocking device and is not reused as the exact-match key.

## Rule options

**Name normalization** (the rule id is stored with every comparison):

- **N1, chosen:** uppercase, delete punctuation, collapse runs of whitespace. `L.L.C.` and `LLC` agree (Q22's example). Internal spaces are kept, so `K S TURNPIKE LLC` and `KS TURNPIKE LLC` (Q3 example G) stay a reported difference, which Q3's caveat requires.
- **N2:** N1 plus a map of suffix spellings (`LIMITED LIABILITY COMPANY` to `LLC`, `INCORPORATED` to `INC`). More matches, a larger rule to test.
- **N3:** NLR's, which removes the legal suffix. It makes `X LLC` and `X INC` agree, which is too loose for an exact comparison.

**Address normalization:**

- **A1:** uppercase, delete punctuation, collapse whitespace; compare house number, street name and 5-digit zip.
- **A2, chosen:** A1 plus a small street-suffix map (`ST`/`STREET`, `AVE`/`AVENUE`, …), since that is the commonest variation. Unit and apartment are reported, not matched.
- **A3:** full standardization (Geosupport or libpostal), as NLR plans. Deferred past Stage 1.

## Context

- **Grain.** In `nyc-landlord-resolution/src/nlr/splink_source.py` the unit is one row per distinct (kind, name, raw business address), `bbls` aggregated, `unique_id` an md5 of those fields. On the justfixwow mirror, 341,928 owner-role contact rows collapse to 242,086 such identities. BOR's edges connect identities, so Q8, Q9 and Q19 paths (building, identity, identity, building) need nodes at this grain.
- **Names alone are weak but not useless.** 55,754 of 88,542 distinct normalized HPD owner names (63%) match an active DOS entity name, and 71 match more than one. HPD owners include co-ops, condos and trusts, DOS is active-only, and the mirror may be stale, so these figures are not a quality measure.
- **Agents and owners overlap.** Of 91,889 distinct agent (name, address) keys, 26,029 (28%) also appear as an owner-role key. Merging across roles would collapse agents into owners against Q23.
- **Addresses differ by source.** An ACRIS party address is what a document says; an HPD business address belongs to the registration contact. Requiring address agreement would report false differences for one entity.
- **NLR coverage.** It uses only the most recent registration per BBL, so older registrations get identity nodes but no BOR evidence.
- **The PESP guide** never names HPD data. Its method uses officers, directors, registered agents and management companies as clues, and warns that corporate servicers hide the people behind a company.

## Alternatives considered

- **Names only on role nodes** (no identity node; the first option I proposed for this question). It cannot carry BOR's identity-level evidence edges. Rejected once the NLR grain was confirmed.
- **A shared `Name` node per normalized name.** Makes name equality visible but adds a hop, and common names and commercial agents become supernodes.
- **One resolved entity node per real owner.** Ruled out by the mission non-goal (no entity resolution of our own).
- **Requiring address agreement in Q3.** Changes the claim from string agreement to something closer to identity (Q22), and fails on source-specific address differences.

## Consequences

- **Edits made with this note:** the Q3 shape and caveat in `docs/competency-questions-detail.md`.
- **Role nodes keep per-contact provenance;** identity nodes carry source-level provenance only.
- **High-degree identities** (large management companies, commercial agents) are legitimate domain supernodes. Queries start from a building, so they are not traversed from the identity side by default.
- **Open:** ACRIS party nodes; whether the mail-drop list keys on the normalized address of rule A2.
- **Revisit:** N2 if the sample shows many suffix-spelling differences; A3 when address typos block real matches; the identity grain if the BOR export uses a different one.

## Correction (2026-10-19, after reading the BOR repo)

I assumed BOR's edges connect NLR's md5 identities. They do not (`beneficial-ownership-resolution/src/bor/`).

- **BOR's nodes are `landlords_with_connections` (lwc) rows,** built from WoW's `wow_landlords`: one per (name, *standardized* business address), with `nodeid = row_number()`, a per-build surrogate that is not stable across builds. Owner Portfolio group ids are `OP-<min nodeid>` and Operational Network group ids are `ON-<min nodeid>` (BOR renamed them from `OG-` and `PF-` on 2026-10-21). The `stable_key` on a group is a placeholder.
- **NLR/Splink entities are mapped onto lwc nodes** by an exact (owner name, bbl) join (`splink_bridge.py`: 99.9% of lwc nodes in the production run).
- **So BOR's evidence edges will connect lwc nodes,** not our identity keys. The standardized address in lwc comes from WoW's geocoding step, which this repo cannot reproduce.
- **What stands:** identity nodes at the recorded-party grain, covering all nine contact types, with the content key. They are still needed as anchors for recorded roles and for Q3.
- **What is open:** how lwc nodes enter the graph (run-scoped nodes with a mapping to identity nodes, or edges expanded onto identity nodes), and what BOR must export to make either work.
- **Current release:** `release/` holds only group-to-BBL and network-to-BBL maps, with no edges. The local build also includes owner names (person anchors).

- **Update 2026-10-20:** BOR identity ids will be opaque (note 0007), so our owner-role key no longer has to equal NLR's md5. The formula stays for continuity.
