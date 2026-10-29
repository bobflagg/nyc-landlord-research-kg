# 0026: Slice 5 plan (links and identity)

Date: 2026-10-29

Status: **accepted 2026-10-29:** the user chose the recommended option for P1 to P6. All five build steps are done; the exit check is note 0027. Builds on notes 0006 (rules N1 and A2), 0009 (names are leads, computed at query time), 0010, 0016, 0024 and 0025.

## What Slice 5 delivers

Roadmap: aggregator and mail-drop addresses; shared evidence between entities; affiliations; restructuring deeds; same entity or not; a managing agent's footprint. Questions Q6, Q7, Q11, Q18, Q22, Q23. Slices 0 to 4 must still pass.

| Q | Contract | Answer shape | Type |
| --- | --- | --- | --- |
| Q6 | Is this business address an aggregator or mail drop? Yes or no per method (the project's mail-drop list, BOR's masking, the degree in the graph), with reasons; name the method and run | yes/no per method | II |
| Q7 | Evidence shared between two entities or buildings; each item marked used or set aside (a masked or mail-drop address is set aside, and said so) | list of evidence items | II |
| Q11 | Affiliations by relationship type: financing (lender), joint borrower, management, registered principal, process agent. Only a documented parent may be called a parent | list with types | mixed |
| Q18 | Deeds that may restructure ownership: a classification and open questions. $0 is a hint, not a finding; a buyer with no established relationship is "no relationship established" | list of deeds | mixed |
| Q22 | Same entity or not: a judgment with evidence for and against, and the rule used | judgment | II |
| Q23 | The lots where one managing agent is registered, and how they compare with the ownership layers; a commercial agent links nothing | list and comparison | mixed |

## What the graph already holds, checked 2026-10-29

- **The anchor puzzle is present.** A (`5413 PLAZA LLC`) and B (`702 Plaza LLC`) have the same HPD business address (746 61st Street, 11220: six parties and eight roles in the whole graph, so not a hub), the same managing agent (a person), a head officer written `BAOZHEN CHEN` on both and a shareholder written `BAO ZHEN CHEN` on one, the same joint mortgage (`2021031601183001`: lender ConnectOne Bank, both LLCs as borrowers), and DOS filings a day apart with the same process address (5 Cromwell Circle, shared by six DOS entities, none a known agent). BOR left A and B in no group in either layer (`no_linkage`, note 0025). Q7 and Q22 are where the graph's own evidence is set beside BOR's silence, and the answer must not turn either into a finding.
- **Names.** Rule N1 (case, punctuation, whitespace) is stored on parties and used at query time. `KS Turnpike LLC` and `K S TURNPIKE LLC` (anchor G) differ under N1 by a space, so Q22's example needs one more stated rule (P3).
- **Address.** Rule A2 keys exist on lots, buildings, HPD parties (`business_address_key`), ACRIS parties and DOS process addresses (computed in the tools). BOR's masked addresses are in the graph as text normalised by BOR's own function, not as A2 keys.
- **The mail-drop list** (`resolution/mail_drop_addresses.csv`, 122 rows, all unreviewed) is a CSV that two tools read at query time. It already includes BOR's masked addresses as one source, which settles the reconciliation that was open in note 0001 for the first version.
- **Agents.** HPD managing agents include companies with dozens of lots (one registered on 39 lots). HPD parties are keyed by contact type, name and address together (note 0006), so one agent name at two addresses is two parties.
- **Deeds.** 2.38M of the 3.0M deed-family documents are for $0. A $0 deed alone says little; the pattern (a $0 deed and a deed for value on one lot in one period, same-name grantor and grantee, a buyer in the same HPD or BOR group) is what Q18 classifies. BOR's own deed rules (nominal consideration up to $100, restructuring from 2005) are in the manifest.
- **No officers for LLCs** in DOS (mission); people behind an LLC come from HPD roles and ACRIS parties. No parent-company record exists in any loaded source, so nothing in the graph can be called a documented parent.

## Decisions for the user

**P1. The mail-drop list in the graph.**
- **(a) Load it as `MailDropAddress` nodes, recommended:** key `address_key`, with kind, basis, counts, `review_status` (unreviewed unless a person changes it), the snapshot and source, loaded from the CSV by the build. The tools then join parties to it in Cypher, Q6/Q7/Q23 share one source, and a person's review is a CSV change followed by a reload. The CSV stays the committed artifact.
- (b) Keep reading the CSV at query time, as Q3 and Q5 do. No schema change, but every new tool reimplements the join and cannot filter by it in a query.
- Either way the kinds (`registered_agent`, `law_firm`, `management_office`, `unknown`) become a small vocabulary if they are stored.

**P2. Q7 evidence items, and when one is set aside.** Recommended set: (1) same HPD business address; (2) same normalized person name in a registered-principal role; (3) a person name that differs only by spacing or order (P3's rule); (4) both named on one ACRIS document, with the role each has (joint borrower, grantor and grantee); (5) same DOS process address or registered agent; (6) a shared HPD managing agent; (7) both lots in one BOR group, with the layer; (8) similar names, shown only as the exact differences (a numeral, a legal suffix), never scored. Each item carries its source, record ids and reliability, and is marked **used** or **set aside** with the reason: the address is on the mail-drop list, is masked by BOR, or is shared by more than a stated number of unrelated parties (the degree is reported; the threshold is a parameter and starts at BOR's 25); a person name is common (the count of parties with that name is shown); the agent is commercial. A set-aside item is shown, not hidden. The tool never adds the items up into a score and never says "same owner". The alternative, returning only the used items, would hide why a trail was discounted, which is the point of the question.

**P3. Rules for Q22.** Recommended: keep N1 as the only stored key and add rule **N2** at query time: N1 with spaces also removed, so `KS TURNPIKE` and `K S TURNPIKE` agree, and nothing else (no fuzzy matching, no phonetic key). The judgment has four outcomes: **normalization match** (N1 equal: same string after case and punctuation), **spacing match** (N2 equal, N1 not), **differ by a numeral, ordinal or one word** (not the same unless a record other than the name connects them), and **different**; each is a lead with the evidence for and against (shared address, shared record, DOS dates, the lots they hold). N2 is derived, stored nowhere, and the answer states the rule. The alternative of adding a fuzzy-name library would give scores the project could not defend and is not recommended. For a person name that appears in a different order or with a split first name (`BAOZHEN CHEN`, `BAO ZHEN CHEN`) N2 on the person key gives the spacing match.

**P4. Q18 classification.** A small vocabulary `deed-pattern`, recommended: `zero_consideration` (a $0 deed), `nominal_consideration` (up to the nominal limit BOR uses, $100), `same_name_transfer` (grantor and grantee share a normalized name), `paired_with_sale` (a $0 deed and a deed for value on the lot recorded within a stated window, 90 days to start), `to_new_entity` (the grantee's DOS filing is within a stated period before the deed), `multi_lot_deed`. A pattern is a hint. The question's second half, the buyer, is answered by **independent support**, listed apart: the buyer is in the same BOR group, shares an HPD business address or officer with the seller, is the same name, or the deed is a BOR deed-evidence bundle; with none of these the answer is "no relationship established". The alternative of one "restructuring: yes or no" label is rejected: the contract says it is a hint.

**P5. Q23: what identifies a managing agent.** Recommended: start from a name or a lot; the agent is the set of `managing_agent` roles whose party has the same N1 name, grouped by party (so an agent at two addresses is shown as two parties with their lot counts, and the answer says they are grouped by name, a lead). The footprint is the lots those roles sit on, reported as counts (lots, buildings, units), the registrations and a bounded list, and compared with the layers: how many of the lots fall in one Owner Portfolio or Operational Network, how many in none. An agent whose address is on the mail-drop list or whose name appears as managing agent for many unrelated owners is reported as a commercial agent and builds no link. The alternative of keying on name and address together would split one company that moved.

**P6. Tools and where Q6 is answered.** Recommended: six tools (`check_address_aggregator` Q6, `get_shared_evidence` Q7, `get_affiliations` Q11, `classify_deeds` Q18, `compare_entities` Q22, `get_agent_footprint` Q23), each a lot, an address or a name in, each with a prompt rule. Q6 takes a typed address or an A2 key; the typed address goes through the Geosupport sidecar when it is a street address and a BBL is not given, and the business address of a party can be passed from another tool's result. The alternative of folding Q6 into Q7 would answer "is it a hub" only when two entities are compared.

## Build order

1. P1 to P6: vocabularies (`address-kind`, `deed-pattern`, and `affiliation-type` for Q11's relationship types), the `MailDropAddress` class and shape, the loader for the CSV, rule N2 in `etl/names.py` with tests.
2. Q6 and Q22 (smallest, and the others use their rules): `check_address_aggregator`, `compare_entities`, tests on the anchors (A and B's shared address is not masked and not on the list, with six parties; G's spelling pair is a spacing match; B's two LLC names are different).
3. Q7 and Q11: `get_shared_evidence` and `get_affiliations` on A and B (the joint mortgage is a financing relationship and a shared borrower record, not common control), C (the 2015 mortgage lender) and a pair with a masked address.
4. Q18 and Q23: `classify_deeds` on B and on a lot with a $0-then-sale pattern found in the source, `get_agent_footprint` on a commercial agent found in HPD (the contract asked for one).
5. Expected answers derived from the source database without the graph, evaluation examples, and the Slice 5 exit check (note 0027) with the regression of Slices 1 to 4.

## Risks

- **Joining on names.** Q7, Q22 and Q23 all lean on names. Every such join is exact N1 or N2, reported as a lead with the count of other parties that share the name, and never changes a group or creates a stored link.
- **Hubs and common names.** A shared address or a common name can make an unrelated trail look strong. The degree and the name count are shown, and a set-aside item is listed with its reason.
- **Reading the A and B trail as a finding.** The graph's evidence for A and B is real and BOR found none. The answer reports both, says the records do not show common control, and does not choose.
- **People.** Names are shown only in the role the record gives, with the source. No search for a person's other records, and no home addresses: only business addresses as filed (note 0009).
- **The mail-drop list is a first cut.** Every row is unreviewed and the thresholds are a guess; the tools say the list is unreviewed and name its snapshot.
- **Size.** Agent footprints and shared-address lookups can return hundreds of rows; tools return counts first and a bounded list with the true totals, as in Slice 4.

## Built (2026-10-29)

- **Step 1.** Vocabularies `address-kind`, `deed-pattern` and `affiliation-type`; `ontology/links.ttl` and `links.shapes.ttl` (`MailDropAddress`, Type II, keyed by the A2 key with the ZIP); `etl/maildrop.py` and the `maildrop` module of `etl.run_build` (121 addresses loaded; the one row without a ZIP, `120 BROADWAY`, cannot match a party's key and stays in the CSV, as `resolution/README.md` now says); rule N2 in `etl/names.py`; an index on `DosEntity.process_address_line1`.
- **Step 2.** `check_address_aggregator` (Q6, `agent/tools/addresses.py`): three methods (the list, BOR's masking read through the list because BOR's address text has no ZIP, the parties at the address) with the key tried and the ordinal variant of a numbered street, since A2 does not map ordinals. It takes an A2 key or house number, street and ZIP, and does not call Geosupport: A2 is the key parties carry, and a lot match is not needed. `compare_entities` (Q22): the relation under N1 and N2 (normalization match, spacing match, one-token difference, different), the records under each name, evidence for, set aside and against.
- **Step 3.** `get_shared_evidence` (Q7, `agent/tools/evidence.py`): eight kinds searched; each item used or set aside with its reason (mail-drop list, an address shared by at least 25 parties, a person name carried by at least 25 parties, a commercial managing agent, a DOS process address shared by at least 25 entities). `get_affiliations` (Q11, `agent/tools/affiliations.py`): lender, joint borrower, managing agent, registered principal, process agent, and an explicit "no documented parent".
- **Step 4.** `classify_deeds` (Q18, `agent/tools/restructuring.py`): the patterns of P4 with the windows stated in the output; independent support lists records other than the deed itself (a deed naming both parties is the transfer being tested and is not support). `get_agent_footprint` (Q23): lots, registrations, buildings, units, owners counted, addresses, a commercial flag and the comparison with both layers.
- **Step 5.** Expected answers (`evals/expected/derive_slice5.py`), 13 tests of the rules and the loader and 23 of the graph against the expected answers, 13 evaluation examples, the exit check (note 0027).
