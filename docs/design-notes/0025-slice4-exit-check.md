# 0025: Slice 4 exit check (ownership layers)

Date: 2026-10-29

Status: **proposed for acceptance.** Slice 4 is built and loaded citywide; this note records what was checked. Plan: note 0024.

## What was built

The Owner Portfolio and Operational Network layers of BOR release v0.2.1 (run `2026-05-29-149e871f`, snapshot `justfixwow-2026-05-29`, the same snapshot as the graph) and six tools over them:

| Q | Tool | Delivers |
| --- | --- | --- |
| Q9 | `get_owner_portfolio` | Lots, buildings and residential units (apart, with the lots missing a unit count and the co-op or condo lots outside the footprint), the landlord records, the signals behind the group, the published precision of those stages, the difference from the other layer |
| Q8 | `get_operational_network` | The same, plus whether the network is a whole component or a community split from a larger one, and the accepted links with their kinds |
| Q19 | `explain_why_grouped` | Per layer: same group (the representative path, step by step, each step with the evidence it cites), different groups (connected before a split or not), or the reason a lot is in no group |
| Q10 | `compare_ownership_layers` | The lots in one layer and not the other, each explained by the other layer's group, BOR's reason, the masked address, or the signal that linked it; how many portfolios a network holds and how many networks a portfolio spans |
| Q21 | `rank_violations_in_group` | Open violations per class and per residential unit over a layer's lots, the share held by the top three, the same figures for the other layer |
| Q26 | `explain_what_is_missing` | Each source with no record (HPD registration and contacts, DOS entity, each layer, violations, complaints, Housing Court actions, deeds) with one of the five reasons and what it does not mean |

## Checks

- **Release verification (O4).** Every check passed on v0.2.1 against the justfixwow database: schema version, no synthetic, excerpt or dirty flag, snapshot id and date, all 32 file checksums, every key beginning with the run id, the row counts and fingerprints of the six required source tables and the two warning-tier ones, and the snapshot-date basis. The run is recorded `source_verified: true`.
- **Citywide load and validation.** 16,196 groups, 46,547 nodes, 114,986 memberships, 246,722 absences and the rest as listed in note 0024; the full-graph validation after the load returned **0 violations**. Two edge shortfalls are the data, not the loader: 10 decision-to-deed edges whose deed is not in the graph, and 2,726 decision-to-group edges whose group BOR dropped (219 groups dropped as co-op or condo dominated, and the 2,507 lots excluded with them).
- **Tests.** 555 pass (about two minutes). New: 37 in `tests/test_bor_build.py` (verification and refusals, the loader on a cut of the release, idempotence, validation that catches bad nodes and edges) and 49 in `tests/test_expected_slice4.py` (the citywide graph against expected answers derived from the release files and the source database, without the graph). One live-model test (`test_q3_a_deed_and_the_hpd_owner`) failed once in a full run and passed on rerun; it was not touched by this slice.
- **Evaluation.** 110 examples (84 earlier, 26 new), run locally, nothing uploaded. The full run: tool trajectory 110 of 110; caveats 110 of 110; snapshot cited 110 of 110; required facts 109 of 110; no overreach 109 of 110; grounded (model judge) 106 of 110. Of the 26 new examples, the first run had the judge flag 16 answers (a method term the tool had not returned, a unit source, an unexplained empty precision); after the fixes below the full run missed four (three Q19 answers on the judge, one Q26 answer on a forbidden word). After the last fixes, Q19 scored 7 of 7 on every evaluator, and Q21 and Q26 6 of 6. The other full-run misses are in earlier slices and none comes from a Slice 4 tool: Q24 C (the answer did not name the head officer role), Q13 D (a sentence about which document cites which that the tool does not support) and, in a rerun, Q13 A and Q24 A (a termination said to cite a mortgage; "not a sale" for a $0 deed).

## Anchors

| Lot | Owner Portfolio | Operational Network |
| --- | --- | --- |
| A 3008260002, B 3008260005 | none: `no_linkage` | none: `no_linkage` |
| C 3008070024 | OP-98617, 5 lots, 5 buildings, 116 units | ON-98617, the same 5 lots (a whole component) |
| D 3008210012 | OP-53559, 33 lots | ON-18742, 35 lots; the two extra lots are linked only by a shared business address and are `no_linkage` in the portfolio layer |
| E, G | none: `no_linkage` | none: `no_linkage` |
| F 3008970014 | none: `no_registration` | none: `no_registration` |

- **C is not excluded as a co-op.** The detail document expected the Owner Portfolio to exclude it by policy. In this release BOR keeps it, in both layers, joined to four other lots through resolved identities of HPD head-officer contacts that carry the same name. The detail document now says so. The tools report the group as it is and do not call the lot a co-op.
- **A and B, the candidate pair of the earlier plan, are in no group in either layer.** The graph holds a candidate trail for them in the records (same business address, a joint mortgage, DOS filings a day apart: Q7, Slice 5), but BOR's method found no accepted link. Q19 answers "no path, and that is not evidence about their owners".
- **Release-wide.** 43,556 lots are in both layers, 27,700 only in a network, 174 only in a portfolio; 476 networks hold more than one portfolio (largest 14); 14 portfolios span more than one network.

## What the evaluation found and what changed

- The judge flagged the model repeating a method term ("Louvain") the tool never returned: the prompt had named it. The tool now states, for a network that was not split, that it was not split into communities, and the prompt says to repeat only the tool's split field.
- A unit count described as PLUTO's with no source in the tool result: the lot block now carries `units_source`.
- A claim about a precision that was empty with no stated reason: a pair with no path now returns an explicit note that no stage precision applies, and `compare_ownership_layers` returns the precision of the stages both layers use.
- Layer definitions repeated from memory: each group result now carries `what_this_layer_is`.
- The word "owns" in a negated sentence split across a line (a deterministic false hit): the prompt now says not to use the verbs own, owns, owned or control about the group even to deny them. The word "exempt" was echoed from a tool caveat and removed from it.
- A regression in scoped validation: relationship rules compiled from the new edge shapes begin at no node, so scoped test validation now drops them (the unscoped build validation checks them).

## Limits, stated

- **The gold is provisional.** Every published precision is `human_llm_provisional` (one human annotator, an LLM second reader, an LLM-run resolution of their disagreements; blind human re-adjudication is pending). Only `identity.splink_base` (0.967, interval 0.924 to 0.986), `deed.held_since` (0.971) and `deed.linked_successor` (0.72 inclusive) have estimates. The network stages, the feedback pass, the curated list and the registered-LLC stage have none, and the answers say they were not evaluated. `identity.splink_base` pools pairs linked directly with pairs linked through a shared-company merge, and the answer carries that.
- **A group is a lead.** The tools never say a group owns anything; they say the run places lots in it.
- **Names.** The landlord name is as filed and display only; the group anchor is called the member with the most lots. Test fixtures use placeholder names.
- **Only 358 of the 4,117 records that use a masked address sit in a group.** The rest are explained through the lot's absence edge, which carries the masked address.
- **Buildings come from HPD registrations.** A lot with no registration has none in the graph; the counts say so (`lots_with_no_building_in_graph`).
- **A new snapshot needs a new frozen release and a rebuild.** The loader refuses a release built from a different dump.

## Open, not blocking

- Q19 explains a pair through the release's representative path only. The identity-grain tables (not loaded, O1) would let it show the contacts behind each identity match; no question needs that yet.
- The Q7 and Q22 comparisons (Slice 5) will use the same nodes; nothing here stores a name-match edge of the graph's own (note 0009).
- The LangSmith upload stays off, as decided.
