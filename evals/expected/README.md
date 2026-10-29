# evals/expected/

Expected answers, taken from the snapshot the graph is built from (`specs/roadmap.md`: expected answers come from the build snapshot).

| File | What |
| --- | --- |
| `slice1.json` | Q1–Q5 and Q24 on the anchor properties A–G of `docs/competency-questions-detail.md`, snapshot `justfixwow-2026-05-29` |
| `slice1.sql` | The read-only queries behind it |
| `slice3.json`, `slice3.sql`, `derive_slice3.py` | Q12 (deed timelines) and Q13 (mortgage-family documents and citations) on the anchors, derived from the source database without the graph; Q14 is checked in `tests/test_title_history.py` against these and the Slice 1 and 2 files. `tests/test_deed_history.py` and `tests/test_mortgage_history.py` check the citywide graph against it |
| `slice4.json`, `slice4.sql`, `derive_slice4.py` | Q8, Q9, Q10, Q19, Q21 and Q26 on the anchors and on groups found in the BOR release (a network holding two portfolios, a portfolio spanning two networks, a Louvain community, a registered-LLC link set, a curated list, a masked address). Group facts are read from the release CSVs, lot facts from the source database, without the graph. `tests/test_expected_slice4.py` checks the citywide graph against it |
| `slice5.json`, `slice5.sql`, `derive_slice5.py` | Q6 (parties at three addresses, list membership), Q22 (name relations and DOS ids), Q7 and Q11 (anchors A, B and C), Q18 (B's deeds) and Q23 (two managing agents), derived from the source database, the mail-drop CSV and the earlier expected files without the graph. `tests/test_expected_slice5.py` checks the graph against it |
| `slice2.json`, `slice2.sql`, `derive_slice2.py` | Q15, Q17, Q27 and Q28 on the anchors, derived from the source database without the graph; `tests/test_expected_slice2.py` checks the citywide graph against it. The violation, complaint and litigation tables are newer than the snapshot date, so the file records each source's as-of date |

Names appear with their role, source and HPD contact id (design note 0009); a name asserts nothing beyond the role the record gives it. Comparison fields (name and address agreement) follow rules N1 and A2 and are rechecked by `tests/test_expected_slice1.py`.

The file is a record of what the snapshot says on 2026-10-26. When the graph loads these lots (Slice 1), a graph test compares its answers with this file. A new snapshot means re-running the queries and re-deriving the file.
