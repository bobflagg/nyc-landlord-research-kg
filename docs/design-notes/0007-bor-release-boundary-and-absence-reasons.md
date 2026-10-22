# 0007: The BOR release boundary, and a fifth absence reason

Date: 2026-10-20

Status: **accepted 2026-10-22**; item 5 (how BOR nodes enter the graph) confirmed 2026-10-23 as run-scoped nodes. Amends `docs/competency-questions.md` (requirement 3), `specs/mission.md` (outcome 3) and `specs/tech-stack.md` (rebuild row) as listed under Consequences. Builds on notes 0001, 0005 and 0006. The BOR side is the draft in `beneficial-ownership-resolution/docs/release-contract.md`, with the findings in `docs/release-contract-review.md` in that repository.

## Decision

1. **BOR's release is the only source of the Owner Portfolio and Operational Network layers.** The KG loads a frozen release together with the matching source snapshot. It does not re-run BOR on each graph build. BOR runs once per snapshot (stochastic, about 99.95% agreement between fits), the result is frozen and checksummed, and a new snapshot needs a newly frozen release. The release schema and validator live in the BOR repository. This repository documents only the mapping and never imports BOR's schema into its ontology, and BOR does not import ours.
2. **Mapping into the graph.** Every BOR-derived assertion is loaded with `reliability: II`, `source_category: project_derived`, `review_status: unreviewed` and the flat provenance of note 0005, with `snapshot_id` taken from the manifest and the BOR `run_id` recorded. A membership's `link_id` is BOR's `assertion_key` followed by the BBL (`<assertion_key>#<bbl>`), because a BOR node can hold several BBLs and the graph models a membership per building. Keys are not stable across releases, so reviews do not carry across runs.
3. **Joining BOR evidence to recorded facts.** BOR cites HPD contacts as observations `registration:contact:k`. The graph's role nodes carry `registration_id` and `registrationcontactid`, so evidence attaches without joining on names. For the 0.08% of (registration, contact id) pairs that repeat with differing content, the KG joins on the pair alone and marks those observations ambiguous, unless BOR makes its digest and ordering normative (review finding 6). Identical duplicate rows collapse to one.
4. **Identity ids are opaque.** BOR's `identity_id` should not be NLR's md5 of name and address. The KG derives its own recorded-party key (note 0006) from the observations. Note 0006's rule that our owner-role key equals NLR's formula is relaxed: the formula stays for continuity but no longer has to agree with BOR.
5. **How BOR nodes enter the graph: run-scoped nodes (confirmed 2026-10-23).** BOR's nodes are `landlords_with_connections` rows (note 0006, Correction). Each is loaded as a run-scoped, `project_derived` node keyed by the run and the node id (the `/n<node>` part of `assertion_key`). It maps to role nodes through `node_observations`: the selected observation, or every candidate in `node_observation_alternatives` when the node is ambiguous (616 nodes, covering 642 lots). BOR's evidence edges and witness paths connect these nodes, and an explanation path runs building, role node, BOR node, BOR node, role node, building. Only the nodes that are in a group (31,035 of 118,493 in release v0.1.0) are needed to explain a grouping. Identity ids stay properties of the release (item 4).
   - **Why not expand edges onto identity nodes.** BOR's grouping, witness steps and network edges are at node grain, and most evidence does not join identities. Of 21,251 Operational Network path steps, 11,771 are shared-address and 156 are name matches between landlord records, and deed and owner-entity link sets join nodes through lots. 113 nodes match no identity, so their steps would vanish. 751 nodes straddle clusters (639 tied, resolved by a recorded rule), and expansion would connect such a node to both readings and undo that rule. Edge multiplication (about 1.2 to 1.3) was not the reason. Figures are BOR's, checked against its published release (`docs/kg-mapping.md`, "bor nodes are run-scoped nodes", commit c8b0988); the KG has not recomputed them.
6. **A fifth absence reason: `outside_method_input`.** The reasons that explain a missing building become: *no qualifying linkage*; *excluded by policy*; *below the eligibility rule*; *outside source coverage*; and *outside method input*.
   - **Outside source coverage:** the source holds no record (for example, no HPD registration for the lot, or a snapshot that predates the period asked about).
   - **Outside method input:** the source holds the record but the method did not use it. BOR's detailed codes `not_latest_registration`, `unmatched_node` and `no_owner_contact` (a registration with no qualifying person owner contact) belong here, not under source coverage.
   - **A building-level code** `coop_condo_excluded` is added under *excluded by policy*, distinct from the group-level `coop_condo_dominated` (review finding 2).
   - **Wording:** answers state which of the five applies and, for the last, say that the source has the record but the method did not use it. Recall stays unmeasured and absence is never evidence of different owners.

## Context

- Note 0001 left the evidence export open. BOR now has a draft contract (lineage tables built, decisions and groups planned) and the open questions are in that document.
- The BOR release in `release/` has only group-to-BBL maps, built on 2026-09-20, and the local build includes person names. The graph loads the person-free build, and a group's person anchor is never loaded as an owner (note 0001).
- W0 measured: each BBL is in exactly one node and at most one group per layer; 751 nodes (0.63%) straddle several clusters, 639 of them tied and resolved by an arbitrary rule; 113 nodes match no identity; 10,516 BBLs have a registration but no `wow_landlords` row; nlr and WoW pick different registrations for 1,249 BBLs. The first four are all cases of "the source has the record, the method did not use it".
- Requirement 3 of the competency questions enumerates exactly four reasons and calls the fourth "outside source coverage". Using that label for a lot that HPD does register would tell a user no source record exists when one does.
- `specs/tech-stack.md` says "BOR/NLR rerun on the same one" on each rebuild. With frozen, stochastic releases that row is wrong: a rerun on the same snapshot can change memberships slightly.

## Alternatives considered

- **Keep four reasons** and map the method-input codes to *outside source coverage*. Simple, but it blends "no record exists" with "the method skipped it". One can be fixed by finding another source and the other by changing the method, and a user should be told which.
- **Rename the fourth reason to a broader "outside input coverage".** Merges the two meanings into one label and loses the distinction.
- **Re-run BOR on every graph build.** Makes a rebuild self-contained but not reproducible, since resolution is stochastic, and it slows a routine build by BOR's runtime.
- **Expand edges onto identity nodes** (item 5). No extra node type, but it cannot express node-grain evidence, drops the 113 unmatched nodes and undoes the tie rule for straddling nodes.

## Consequences

- **Edits made with this note:**
  - `docs/competency-questions.md`, requirement 3: the list of reasons gains *outside method input*, with the source coverage definition tightened.
  - `specs/mission.md`, outcome 3: the same.
  - `specs/tech-stack.md`: the rebuild row now says BOR runs once per snapshot and the graph loads the frozen release.
  - Notes 0001 and 0006 each get a dated update line pointing here.
- **Vocabulary:** when the layers are loaded (Slice 4), the five reasons and BOR's detailed codes become an `AbsenceReason` SKOS scheme, with the detailed codes narrower than the top level, per the tech-stack rule.
- **Q26 and Q19** answers use the five reasons. Q26's example "outside source coverage for that period" is unchanged.
- **BOR-side changes this note depends on** (listed in the BOR repository's review): reason codes for vetoes, score below threshold and the deed gate clauses; a stage for group-level policy events; a defined primary-reason precedence; source fingerprints and rule versions in the manifest; a `lot_count` rename; and the fifth top-level reason in `TOP_LEVEL_REASONS`.
- **Revisit:** the primary-reason precedence once BOR states it; whether reviews should survive across runs when the review process is designed.
