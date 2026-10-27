# 0017: The Slice 1 question tools (Q2, Q3, Q4, Q5, Q24)

Date: 2026-10-27

Status: **proposed**, written with the first version of the tools; the points below are judgment calls the user can change. Builds on notes 0004, 0009, 0015 and 0016.

## What was built

- `compare_deed_grantee_with_hpd_owner(bbl)` (Q3) and `find_records_by_name(name)` (Q24), in `agent/tools/records.py`: templated, parameterized, read-only Cypher, run through `read_session`. Both are registered with the agent in `agent/harness.py`, whose prompt gets matching answer rules.
- Every record returned carries its source, snapshot and reliability. Dates are ISO text.

- Added after the first two: `get_hpd_registrations(bbl)` (Q2) and `get_hpd_contacts(bbl)` (Q4) in `agent/tools/hpd.py`, and `get_dos_record(name)` (Q5) in `agent/tools/dos.py`.

## Choices made while building

1. **Which deed is "latest".** Order by recording date, then document date; every deed tied on both is reported (anchor D has two). `DEED COR` corrections are excluded, as note 0004 says. `DEEDO` is included and flagged in the caveats, since it counts as a transfer only after the document is read. The last deed *for value* is the latest with an amount above $0, returned beside the latest deed with `is_latest`.
2. **What is compared.** Each grantee of each latest deed against the `registered_owner` roles of every HPD registration on the lot, one comparison per registration, with the registration's dates so a lapsed registration is visible.
3. **Name agreement** is `exact_normalized` (rule N1) or `different`. **Address agreement** is `same`, `differs` or `absent` (rule A2 keys; `absent` when either side has no comparable key). The ACRIS second address line and the HPD apartment are reported apart, as note 0006 says.
4. **`not_comparable`.** When the HPD owner is a person (no organization name), name and address agreement are `not_comparable`, as in the expected answer for anchor E: a person's name is not compared with an entity's. A person-to-person comparison would rarely agree anyway, because the formats differ.
5. **Mail-drop flag.** An address on `resolution/mail_drop_addresses.csv` (A2 key plus zip) is flagged with its kind and basis; it links nothing on its own.
6. **How many other records share the name.** Counts of HPD parties, ACRIS parties and DOS entities with the same normalized name (note 0009 item 4).
7. **Q24 matching** is the exact normalized name only: `K S Turnpike LLC` and `KS Turnpike LLC` are different names, and the tool says what it searched. Several DOS entities with one name are all returned. Results are capped (`limit`, default 50) with totals and a `truncated` flag.
8. **Q24 covers deed documents only,** per note 0015. The expected Q24 answer for `5413 PLAZA LLC` is split: the deed rows are the Slice 1 answer; the mortgage, assignment, agreement and satisfaction rows moved to `not_loaded_yet` until Slice 3.

9. **Q2** returns each registration on the lot with its buildings, registered owners, last registration date, period end and the snapshot date, plus whether the end date is before the snapshot. It does not say "lapsed": the reader judges from the dates, and a newer registration may exist outside the snapshot. A lot with no registration says so and does not say the building is exempt.
10. **Q4** returns every contact per registration with the HPD type, the normalized role, a grouping (registered principal or management), title, name and business address. A person appears only in the HPD role recorded; a managing agent is management, not ownership.
11. **Q5** takes the name as a source spells it and matches the exact normalized name, so the agent is told to try each spelling the records give (anchor C matches under the deed spelling and not the HPD one). It labels the process name as the entity's own name, the statutory default, or another name, flags a process address on the mail-drop list, and says that CEO and officer fields are not carried for LLCs.
12. **Anchor A's Q2 text** in the detail document said the registration end date had passed at the snapshot; it ends 2026-09-01 and the snapshot is 2026-05-29, so the text is corrected.

## Consequences

- **Tests:** `tests/test_records_tools.py` (20, Q3 and Q24) and `tests/test_hpd_dos_tools.py` (30, Q2, Q4 and Q5), on the anchor lots in a rolled-back transaction against the expected answers; and `tests/test_q3_q24_agent.py` (6, with the model: trajectory, keys, lead wording, no ownership claim, stated limits). All pass.
- **Not done:** a LangSmith dataset and judge evaluators for these questions, unit counts in Q3, and Q26 (what each absence means).
