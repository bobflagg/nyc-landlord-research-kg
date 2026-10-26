# evals/expected/

Expected answers, taken from the snapshot the graph is built from (`specs/roadmap.md`: expected answers come from the build snapshot).

| File | What |
| --- | --- |
| `slice1.json` | Q1–Q5 and Q24 on the anchor properties A–G of `docs/competency-questions-detail.md`, snapshot `justfixwow-2026-05-29` |
| `slice1.sql` | The read-only queries behind it |

Names appear with their role, source and HPD contact id (design note 0009); a name asserts nothing beyond the role the record gives it. Comparison fields (name and address agreement) follow rules N1 and A2 and are rechecked by `tests/test_expected_slice1.py`.

The file is a record of what the snapshot says on 2026-10-26. When the graph loads these lots (Slice 1), a graph test compares its answers with this file. A new snapshot means re-running the queries and re-deriving the file.
