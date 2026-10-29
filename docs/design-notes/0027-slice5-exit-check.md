# 0027: Slice 5 exit check (links and identity)

Date: 2026-10-29

Status: **proposed for acceptance.** Slice 5 is built and loaded; this note records what was checked. Plan: note 0026.

## What was built

| Q | Tool | Delivers |
| --- | --- | --- |
| Q6 | `check_address_aggregator` | Per method (the project's mail-drop list, BOR's masking, the parties at the address in the graph) whether the address is flagged, with the reasons, the run or snapshot, and the key tried |
| Q7 | `get_shared_evidence` | Evidence items between two names or two lots' registered owners, each used or set aside with the reason, what was searched and not found, and no score |
| Q11 | `get_affiliations` | Lenders (financing), documents with several borrowers (a shared borrower record), managing agents, registered principals and process agents, and "no documented parent" |
| Q18 | `classify_deeds` | Each deed's patterns (a hint, not a finding) and independent support for a grantor and grantee relationship, or "no relationship established" |
| Q22 | `compare_entities` | The relation under N1 and N2 and the judgment, with evidence for, set aside and against |
| Q23 | `get_agent_footprint` | A managing agent's lots, registrations, buildings, units, owners, addresses, commercial flag and comparison with both layers |

## Checks

- **Load and validation.** The mail-drop list is in the graph as 121 `MailDropAddress` nodes; the full-graph validation after the load returned **0 violations**. A first load exposed that one list row has no ZIP and could not match a key; it is no longer loaded and the README says so.
- **Tests.** 591 pass (about three minutes): 13 for rules N1/N2, the name relation, the ordinal variant of a street, the list as nodes and the vocabularies, and 23 comparing the graph with expected answers derived from the source database, the CSV and the earlier expected files.
- **Evaluation.** 123 examples (110 earlier, 13 new), run locally, nothing uploaded. The full run: tool trajectory 123, required facts 123, snapshot cited 123, grounded (model judge) 123 of 123, caveats 122, no overreach 122. The two misses are in earlier slices (Q13 F, a caveat worded another way; Q3 C, the phrase "controls the building" in an asserting sentence) and none touches a Slice 5 tool. Before three small fixes (below) the judge flagged two Q22 answers.

## The anchors

- **A and B (Q6, Q7, Q11, Q22).** Their shared HPD business address `746 61ST ST 11220` is on neither the mail-drop list nor BOR's masked addresses and is carried by six HPD parties, so no method flags it and the evidence item is used. The same list of used items: the head officer `BAOZHEN CHEN` on both, the shareholder `BAO ZHEN CHEN` on A (a spacing match, rule N2), the managing agent `JAY WONG` (registered on two lots), three ACRIS documents naming both entities including the $8,750,000 mortgage `2021031601183001` (joint borrowers; lender ConnectOne Bank), and the same DOS process address, which five DOS entities share. The answer calls each a lead and none common control. BOR put A and B in no group (`no_linkage`); the tools report both and do not choose.
- **G (Q22).** `KS Turnpike LLC` and `K S TURNPIKE LLC` are a spacing match (N2) and nothing else connects them in the loaded sources; DOS holds only the spaced spelling (id 3574572).
- **B (Q18, Q22).** The two deeds recorded 2021-02-26, a $0 deed to `702 54 STREET LLC` and a $6,800,000 deed to `702 PLAZA LLC`, are classified `paired_with_sale` (and the first `zero_consideration`; the sale also `to_new_entity`, the grantee having filed with DOS in 2020). No record other than the deeds connects the buyer to `702 54 STREET LLC`: "no relationship established", which the answer says is not "unrelated". `702 54 STREET LLC` and `702 PLAZA LLC` are different names with distinct DOS entities.
- **Q23.** `BRIGHTON MANAGEMENT`: 39 lots, 40 registrations, 750 units, 36 registered owners, flagged commercial; all but one lot fall in one Owner Portfolio and all in one Operational Network, which the layers reached on their own evidence. `BIG BROOKLYN REHAB INC`: 4 lots, 9 units, not flagged.
- **Q6.** `418 BROADWAY 12207` is on the list as a registered-agent address; `575 FIFTH AVE 10017` is on the list and masked by BOR (334 HPD parties).

## What the evaluation found and what changed

- A Q22 answer said the loaded sources hold no record under either name when the tool had searched only HPD, DOS and ACRIS parties: the result now states `sources_searched`, the ACRIS party count, and that DOS holds active entities only.
- A deed naming both parties was counted as support for a relationship between them. It is the transfer being tested, so deed-family documents are excluded from support.
- A Q23 reading called a large agent "a service" while the layers grouped its lots; the wording now says only that the registration alone ties none of the owners and that the layers group the lots on their own evidence.

## Limits, stated

- **Every join on a name is exact N1 or N2 and a lead.** Q7, Q22 and Q23 report the count of other parties that share a person's name; nothing here stores a link or changes a group.
- **Thresholds are first cuts.** 25 parties at an address or with a name, 25 lots for a commercial agent, 90 days for a paired deed, 180 days for a new entity and $100 for nominal consideration (BOR's) are parameters in `agent/tools/linkrules.py` and `restructuring.py`, stated in the output.
- **The mail-drop list is unreviewed.** Every row says so, and BOR's masking can only be matched through the list.
- **No parent relationship is documented anywhere in the loaded sources**, so none is reported. DOS carries no officers for LLCs, so the people behind an entity come from HPD and ACRIS roles.
- **Mortgage-family parties are loaded for registered lots only**, so a lender or joint borrower on an unregistered lot is not here.
- **Common agents.** An agent named identically at several addresses is grouped by name and shown with each address; that grouping is a lead.

## Open, not blocking

- Review of the mail-drop list's `unknown` rows, and a decision on whether BOR takes the list over (open in note 0001).
- DOS degree of an address is counted for process addresses in the evidence tool only; the Q6 tool reads DOS only through the list.
- The LangSmith upload stays off, as decided. Slice 6 (Q16, Q25) needs the web search tool and retrieval cache decisions.
