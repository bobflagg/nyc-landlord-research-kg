# 0023: Slice 3 exit check

Date: 2026-10-28

Status: **accepted: Slice 3 is done (2026-10-28).** Roadmap rule: a slice is done when its questions pass and every earlier slice still passes. Q14 is the temporal test and is mostly gaps by design (note 0022): its contract allows "cannot attribute" when the reason is given.

## What was checked

Slice 3 delivers Q12, Q13 and Q14, all Type I, on snapshot `justfixwow-2026-05-29` (design note 0022). Evidence:

- **Graph:** the mortgage family is loaded on the 181,863 HPD-registered lots: 2,574,999 documents (2,960,530 lot edges), 6,491,978 roles, and 1,634,982 `REFERENCES` edges. Full validation reported 0 violations after the documents and after the references.
- **Expected answers** for the seven anchors, derived from the source database without the graph (`evals/expected/derive_slice3.py`): the Q12 timelines (deeds, dates, amounts, parties, lots) and the Q13 documents with the citations that land on a document in the graph. The tools running on the citywide graph agree on every anchor. Q14 is checked against those timelines, the Q2 registrations and the Q15 violations: 65 tests over eight dates and seven anchors, a violation id, a lapsed registration, a lot with no registration, a deed dated before and recorded after, and a mortgage that is not a deed.
- **Tests:** 469 pass in about 75 seconds.
- **Evaluation:** 84 examples (63 from Slices 1 and 2, 21 new), local, nothing uploaded. All five deterministic evaluators 84 of 84; the judge 82 of 84.
- **Earlier slices:** Slices 0 to 2 pass in the same run.

## By question

| Q | Contract | Result |
| --- | --- | --- |
| Q12 | Transfers of a lot; count deeds, not lots; a $0 deed is not a sale; no attribution to the current owner | Met: timeline oldest first, documents counted once, corrections apart, deeds for value and for $0, same-name grantor and grantee as a name, the since-year with earlier deeds counted, no attribution |
| Q13 | Mortgages, assignments, satisfactions; no satisfaction recorded is not proof the loan is outstanding | Met for HPD-registered lots: documents with parties by role, citations both ways, mortgages with no satisfaction citing them, and the caveats; a lot without a registration says the family is not loaded for it |
| Q14 | Title holder and registered owner on a violation date, whether they coincide, each gap | Met: title by recorded date with the deed document, the registrant whose registration covers the date, agreement by exact name, every gap stated, a deed crossing the date reported, and "today's records of the past" always said |

## Findings along the way

- **A regression from adding a document family.** Once mortgage documents were in the graph, four deed queries (Q3, Q12, Q17, Q14) treated any typed document as a deed. The full suite caught it before the evaluation; the queries now name the deed family, and the Q24 name search says which families it searched.
- **Fewer links than it looks.** 96.5% of the references that cite a CRFN or a document id land on a document in the graph, but a third of all references cite only a reel and page, mostly older satisfactions. For older mortgages a missing satisfaction is therefore weak evidence either way, and the answer says so. A reel-key index on documents would link many of them; it is a later refinement, not a Slice 3 requirement.
- **Evaluation caught tool-output slips**, fixed in the output: the "default date kind" claim for a date the caller supplied (the tool now says how the date was given), the unsupported gloss on a $0 amount (now in the caveats), and the no-title and no-registrant answers dropping "today's records of the past" (now required in the prompt). The remaining judge misses are a flat "not a sale" for a $0 deed in a Q24 answer (the caveat says "not necessarily a sale") and a satisfaction said to cite an assignment the tool did not show.
- **Supernodes.** Lenders and servicers hold large numbers of roles (one name has hundreds of thousands). Reads start from a lot, so Q13 and Q14 are not affected; a name search for a big lender (Q24) is bounded by its limit and reports the true totals.
- **An evaluation run hung once** for an hour with no progress (not in the tools or the database, which showed no long query); a rerun with lower concurrency completed in under half an hour.

## Open and not blocking

- Reel-and-page references (888,000) make no link; a reel-key index could add them.
- Other mortgage-class codes (CMTG, SMTG, SPRD, SUBM, REL, PREL, WSAT, and the rest) are not loaded; neither are mortgage documents on lots without an HPD registration.
- Q14 is limited by the data: one registration period per registration, about a fifth of all violations. Backfilling both from the city's open-data service belongs to the production-snapshot work.
- The LangSmith upload stays off. Slice 4 (ownership layers, Q8, Q9, Q10, Q19, Q21, Q26) needs the BOR edge-level evidence export; its plan is next.
