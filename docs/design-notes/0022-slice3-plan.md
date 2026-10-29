# 0022: Slice 3 plan (transactions and history)

Date: 2026-10-28

Status: **accepted 2026-10-28:** the user chose the recommended option for T1 to T6. Steps 1 to 4 are built; the exit check is note 0023.

## What Slice 3 delivers

Roadmap: deed transfers, mortgages and satisfactions; title holder and registrant on a past date. Questions Q12, Q13, Q14, all Type I (recorded facts, with the dates and gaps stated), on the snapshot `justfixwow-2026-05-29`. Slices 0 to 2 must still pass.

| Q | Contract | New data | Answer shape |
| --- | --- | --- | --- |
| Q12 | Transfers of a lot: deeds with dates, amounts, parties; a $0 deed is not a sale; count deeds, not lots; no attribution to the current owner | none: the deed family is loaded on every lot (note 0015) | timeline |
| Q13 | Mortgages, assignments, satisfactions: the documents, their types, dates and parties; no satisfaction recorded is not proof the loan is outstanding | the mortgage family of ACRIS documents (T2, T3) and recorded references between documents (T4) | list |
| Q14 | Title holder and registered owner on a violation date, whether they coincide, each gap or conflict | none: deeds, registrations and violations are loaded | timeline with a conflict statement |

## What the source holds (checked 2026-10-28 in the justfixwow database)

- **Documents by type (latest version of each):** MTGE 4,208,815; DEED 3,630,694; SAT 2,621,910; ASST 2,204,036; AGMT 918,571; AL&R 198,455; TL&R 150,021; SAGE 133,502; M&CON 72,765; AALR 44,597; CORRM 10,729; many smaller types. ACRIS runs to a recording date before 2026-05-30, consistent with the snapshot date.
- **How many would load.** A sample of 3,000 lots, scaled: on the 181,863 lots HPD registered, about 2.9 million mortgage-family documents (MTGE about 983k, ASST 704k, SAT 489k, AGMT 366k, AL&R 148k, TL&R 113k, SAGE 62k, AALR 41k); on all 858,602 PLUTO lots about 9.4 million. At about 2.5 parties per document that is about 7 million party rows for registered lots, about 24 million for all lots. The deed load already holds 3.0M documents and 9.96M roles.
- **Party meanings change by document type.** ACRIS's own control-code table (the local copy has blank `doctype` values, note 0015) gives pairs such as mortgagor/borrower and mortgagee/lender, assignor and assignee, "party one" and "party two", payer, and a single lender. The meaning of party 1, 2 and 3 therefore has to be confirmed code by code; where it is not, the role type is left off, as with party 3 on deeds.
- **Documents cite each other.** `real_property_references` records, for a document, the documents it refers to by CRFN, document id or reel and page. In a sample of 19,993 satisfactions recorded since 2020, every one has a reference row (26,080 by CRFN, 77 by document id, 30,434 by reel and page). So a satisfaction can be tied to the mortgage it cites by the filer's own record, which is recorded fact, not inference.
- **Registration history is thin.** `hpd_registrations` holds each registration's last registration date and period end, but no earlier periods and no start date. The registrant on a past date is therefore known only where the current period covers it.
- **Violation history is partial** (note 0020): the violations table holds about a fifth of all HPD violations, and closed history is incomplete. A violation not in the table cannot be asked about.

## Decisions for the user

**T1. Q12 uses the loaded deeds, no new load, recommended.** A tool lists the deed family documents on a lot as a timeline (document date, recorded date, amount, grantors, grantees, document type), counts documents not lots (a document on several lots counts once), excludes corrections (`DEED COR`), flags `$0`, a grantor and grantee with the same normalized name, and DEEDO (a catch-all, a transfer only after the document is read), and takes an optional since-date. It never attributes a transfer to the current owner. The alternative, a stored `Transfer` node that decides what counts as a sale, would freeze a judgment in the graph (note 0004 keeps that rule in the tools).

**T2. Scope of the mortgage family.**
- **(a) Documents on HPD-registered lots, recommended:** about 2.9M documents and 7M party rows. These are the buildings the project is about (landlords of multiple dwellings); a one- or two-family lot without a registration is outside the mission.
- (b) All PLUTO lots: about 9.4M documents and 24M party rows, roughly tripling the load for lots no question asks about.
- (c) A lot-by-lot load on demand: not possible, the agent's graph access is read-only.

Document types, **recommended** set, each to be confirmed against ACRIS's control codes before loading: MTGE (mortgage), ASST (assignment of mortgage), SAT (satisfaction), AGMT (agreement), M&CON (consolidation), AL&R (assignment of leases and rents), AALR (assignment of the assignment), TL&R (termination), SAGE (sundry agreement), CORRM (mortgage correction). Types whose meaning cannot be confirmed are left out and listed in the note. The vocabulary (`document-type`) gets a family grouping and the ACRIS code and description for each, as for deeds.

**T3. Parties and roles of mortgage documents.** Reuse `AcrisParty`, `AcrisRole` and `IN_DOCUMENT` (note 0015). New role types `borrower`, `lender`, `assignor`, `assignee` (and, if the control codes confirm them, a few more) are added to the role-type vocabulary, and a role gets a type only where the document type's party meaning is confirmed; otherwise it has the source role code and no type. **Recommended.** The alternative is to load documents without parties, which would lose "who is the lender", the audience point of Q13.

**T4. Recorded references between documents, recommended.** A `REFERENCES` relationship from a document to a document it cites, made when the cited CRFN (or document id) matches a document in the graph; unmatched references (reel and page, documents outside the graph) are counted, not made into edges. It is structural, like `ON_LOT` (note 0010 item 4); the reference kind is a property. The answer may say "this satisfaction cites this mortgage" (recorded) and never "this loan is outstanding" or "paid". `Document.crfn` gets an index. The alternative, no references, lists the documents by date only, as the old Q13 example did, and cannot say which mortgage a satisfaction concerns.

**T5. Q14 reports the history gap, recommended.** The answer states what the loaded records support: the title holder on the date from deeds (the grantee of the latest deed recorded on or before the date; a deed dated before and recorded after is reported as in between), the registrant whose registration covers the date where the latest period does, whether they coincide, and each gap or conflict. It says the violations and registrations are today's version of the past, and that a past title holder missing from DOS may have dissolved. The alternative, backfilling the missing violation history and earlier registration periods from the city's open-data service, is a network load of about 11M violations and belongs to the production-snapshot work in the roadmap; it can be added later without changing the tools.

**T6. Date semantics for Q14.** The violation date is the inspection date by default, with the notice-issue date as an option the question can name; title is dated by the recorded date, with the document date shown; a registration is in force on a date between its last registration date and its period end (HPD gives no start date, so this is stated as an assumption and the registration's own dates are shown). **Recommended.** The alternative is the document date for title, which would credit a buyer before the deed was recorded.

## Build order

1. T1: the Q12 tool, tests on the anchors and the expected deed timelines (derived from the source without the graph), evaluation examples. No load.
2. T2 and T3: confirm the control codes, extend the vocabularies and the ACRIS shapes, load the mortgage family on registered lots (batched, scoped validation in tests, full validation after the load).
3. T4: the references load and the CRFN index, then the Q13 tool and tests.
4. T5 and T6: the Q14 tool, which composes deeds, registrations and violations; tests on the anchors including a deed recorded after a violation and a lapsed registration.
5. Expected answers for the anchors (A and C have mortgage examples in the detail document, from an older check on the city service), evaluation examples for Q12 to Q14, and the Slice 3 exit check (note 0023) with the Slice 1 and 2 regression.

Each step ends with tests on the anchors against expected answers, a validated citywide load where there is one, and no commit until asked.

## Risks

- **Party meaning errors.** A wrong borrower/lender assignment would put a lender in a borrower's role. Mitigation: type a role only where the code's meaning is confirmed, and test each code on a recorded example.
- **Load size.** About 2.9M documents and 7M party rows add to a graph that already holds about 25M nodes. The deed load is the precedent; the validation pass after it is the slow part (about 20 minutes).
- **References are the filer's citation.** A cited CRFN can be wrong or point outside the graph. The answer reports a cited mortgage as cited, and counts the references it could not match.
- **Q14 is mostly gaps.** With one registration period per registration and a fifth of the violations, many dates will end in "cannot attribute", which the contract allows if the reason is given.
- **Names across time.** The current DOS record does not describe a past owner; a missing record says nothing about whether the entity existed (Q5).

## Step 1 built: Q12 (2026-10-28)

`get_deed_history(bbl, since_year)` in `agent/tools/transfers.py`, with a prompt rule; no load. It lists the deed-family documents recorded on the lot oldest first (document and recorded dates, amount, grantors, grantees, the lots the document names), counts deeds as documents, reports deeds for value, deeds for $0 and corrections apart, flags a grantor and grantee that share a normalized name, notes DEEDO and life estate deeds, and with `since_year` reports how many earlier deeds were left out. It never attributes a transfer to the current owner. Expected timelines for the seven anchors are derived from the source database without the graph (`evals/expected/derive_slice3.py`, `slice3.json`, `slice3.sql`), and `tests/test_deed_history.py` (16 tests) compares the citywide graph with them and checks the counting rules on small loads (a deed on two lots counts once, corrections apart, $0 not for value). Anchor A gives the two deeds since 2015 of the detail document (a $5,000,000 sale recorded 2021-02-26 and a $0 deed recorded 2025-04-02 with the same name as grantor and grantee). Seven new evaluation examples score 7 of 7 on every evaluator in two runs; the suite is 353 passing.

## Step 2 built: the mortgage family (2026-10-28)

The ACRIS control codes were read from the city's open-data service (the local copy has blank `doctype` values). Party 1 and 2 are borrower and lender on a mortgage, consolidation, correction, satisfaction and partial satisfaction (checked against live records, including satisfactions where the bank is party 2), assignor and assignee on an assignment of mortgage, of leases and rents and of an assignment; agreement, sundry agreement and termination name them only as party 1 and party 2 and carry no role type. Eleven document types are in the vocabulary as the mortgage family; the rest of the mortgage class (CMTG, SMTG, DEMM, ASPM, SPRD, SUBM, REL, PREL, WSAT and others) is not loaded. The roles are `borrower`, `lender`, `assignor` and `assignee`, mapped per document type from the vocabulary (`x-acris-by-type`). Citywide load on the 181,863 HPD-registered lots took about five hours: 2,574,999 documents (2,960,530 lot edges), 6,491,978 roles; validation 0 violations. The loader's document and role queries were reused unchanged.

## Step 3 built: references and Q13 (2026-10-28)

`REFERENCES` (Document to Document) is made from the recorded references by CRFN or document id when the cited document is in the graph: 1,634,982 edges from 1,694,774 such references (96.5%); 888,000 references cite only a reel and page and make no edge, as decided in T4 (a later refinement could index the reel key). The edge carries no kind property (it is structural); the by-CRFN or by-id split is in the load counts. `get_mortgage_history(bbl, since_year)` lists the documents oldest first with parties by role, what each cites and is cited by, mortgages with no satisfaction citing them, and the plain caveats (a missing satisfaction is not proof a loan is outstanding; a citation is the filer's record; the family is loaded for registered lots only). The graph agrees with expected answers derived from the source without the graph for all seven anchors (documents, types, dates, amounts, citations).

A regression was caught on the way: after the mortgage load, four deed queries (Q3, Q12, Q17, Q14) took any document with a type as a deed. They now select the deed family explicitly (`deed_family_types()`), and Q24 now says it searched the deed family on all lots and the mortgage family on registered lots.

## Step 4 built: Q14 (2026-10-28)

`get_title_and_registrant_on_date` takes a violation id or a lot and a date. Title is the grantee of the latest deed recorded on or before the date; a deed dated on or before but recorded after is reported as uncertain; a $0 deed is flagged; each grantee carries a DOS note (no record in the active-entity snapshot says nothing about the past). The registered owner is the one whose registration runs from its last registration date to its period end; with none in force, the tool says why (before the earliest, after the latest, between). It states whether the names agree (exact normalized name, a lead) and lists every gap, and never substitutes the current owner. 65 tests check it on the citywide graph against Q12 timelines, Q2 registrations and Q15 violations derived from the source.
