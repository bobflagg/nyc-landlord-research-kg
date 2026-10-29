# 0029: Slice 6 exit check (beyond the graph)

Date: 2026-10-29

Status: **proposed for acceptance.** The Tavily key was replaced on 2026-10-29 and the live search works (see "Live check"). Plan: note 0028.

## What was built

| Q | Tool | Delivers |
| --- | --- | --- |
| Q16 | `search_reports` | For a recorded organization name or a lot: items from a web and news search, each with publisher, date, URL, a verbatim quote, retrieval time, extraction method, source category, review status, the basis for treating it as about the entity, its relation to the recorded facts and flags; or "no reports or documents found in the sources searched" with the queries, dates and budget; or "search unavailable" |
| Q25 | `lookup_registry` | Another state's registry record as that registry's assertion, or an unresolved lead with the reason |

Under them: `agent/web/` (evidence model, SQLite retrieval cache, Tavily client, registries, passage matching and the reader), four vocabularies, 28 offline tests, a live smoke test off by default, replay fixtures made from synthetic pages, 9 evaluation examples.

## Checks

- **Tests.** 619 pass with 2 skipped (the live tests), in about two minutes. One live-model test of an earlier slice (`test_q4_managing_agent_is_management_not_ownership`) failed once and passed on rerun, as `test_q3_a_deed_and_the_hpd_owner` did in Slice 4; neither touches this slice.
- **Offline tests (28)** cover: coded values checked against the vocabularies; the cache's time to live and original retrieval time; a repeated search served from the cache with its first time; the key sent as a Bearer token and never logged; replay mode never touching the network and a miss being an error; a provider error being an unresolved step; the budget; verbatim passages and the L.L.C. and "&" forms; a similar name as a lead and a swapped word not; and for Q16 the contract's cases: an article naming the exact LLC, a similar-name article, nothing found, a failed search, two contradicting articles (both contested), a report after the as-of date and an older conflicting one (flagged, superseded), an unreadable page (a lead, snippet only), an injected instruction (the reader gets only the quoted sentence and the queries never contain page text), an individual and an unrecorded name (not searched); for Q25 a Connecticut record (the email never read or cached), a similar name as a lead, a challenged request as an unresolved lead, a 402 as `needs_payment`, an unsupported state and replay mode.
- **Evaluation.** 132 examples (123 earlier, 9 new), run locally with Q16 and Q25 replaying recorded responses, nothing uploaded. The new examples score 9 of 9 on every evaluator in the first full pass of the final wording, and Q16 6 of 6 after the last phrase fixes. The full run before the final fixes: tool trajectory 132, snapshot cited 132, required facts 130, caveats 131, no overreach 130, judge 127. The misses were Q24 C, Q15 F, Q13 A, Q9 D and Q26 F (earlier slices, usual variance), and in Slice 5 and 6 answers Q7 A-B (the phrase "under common control" in a sentence the checker read as an assertion), Q18 B (a list of support kinds the tool had not named), Q23 BIG BROOKLYN (a description of how the layers are built), and Q16 on a phrase list that was too narrow. Each of those was fixed in the tool output or the prompt (see below) and the affected groups rerun.

## Findings

- **The first key was rejected** (401), which exposed that a failed search had been reported as an empty result; it is now `search_unavailable`. With the new key the live smoke test passes (search and registry).

## Live check (2026-10-29)

`search_reports` on `5413 PLAZA LLC` with the real provider and the real reader returned 11 items from 2 searches and 3 fetches in 23 seconds. They are mostly data aggregators and city documents (augrented.com, whoownswhat.justfix.org, a DOF tax statement, weverit.com, displacementalert.org), not news; the news query returned one hit. Published dates came back empty on general results. One city tax statement was read as conflicting with the recorded managing agent (it lists a different agent for 2024), a good catch. `BRIGHTON MANAGEMENT` returned 11 items about a company of that name (a LinkedIn profile, its own site), which the exact-name rule cannot tell from other companies of the same name; the items say `exact_name`, and the answer must still call it a name match. Two fixes followed: a bare name (a page title or table cell) is not an item, and a `.gov` or `.edu` page is `web_content`, not `published_reporting`.
- **Connecticut is the one registry that works by plain request** (open data; the owner count is small: 130 HPD owners have a Connecticut business address). Delaware (CAPTCHA), Florida (browser challenge) and New Jersey (browser form) are unresolved leads with the reason `inaccessible` and the registry's address for a person to use. The most useful registry for New York owners, Delaware, is therefore a lead, not a record. The adapter reports exactly what it saw and bypasses nothing.
- **Reading is the weak point.** The reader (a model with no tools, given the quote and a short summary of the recorded facts) can call the same sentence "agrees" or "adds" on different runs. The relation is labelled `model_reading`; the quote and the match are deterministic. The evaluation accepts either of the two for that case.
- **Prompt injection.** The reader receives only the quoted sentence, never the page, and nothing from a page reaches a query or Cypher; the test with an injected instruction passes. This is a design property, not a guarantee against a model following text inside the sentence itself, which is why the reader has no tools and returns a fixed schema.

## Changes made during the check

- A search that could not run was first reported as "no reports found": it is now `search_unavailable`, and an answer may not call it an empty result.
- `temperature` is rejected by the model for the reader and was removed.
- `classify_deeds` now lists the kinds of independent support it searched, `get_agent_footprint` carries the layers' definitions, and the prompt forbids "common control" and "are related" even to deny them.
- `search_reports` on a lot with no registered organization says that only the address was searched.

## Limits, stated

- **The fixtures are synthetic.** The articles are invented and bland, about real recorded entity names (the tool searches only recorded names), so the evaluation tests behavior, not what the web holds about those companies. The Connecticut record is a modelled public-domain row.
- **No claim here is a fact.** Every item is unreviewed, published-claim reliability, and kept out of the graph; a finding enters the graph only through a later reviewed process (not in scope).
- **The search index is not published.** "No reports found" is bounded by the provider, the queries, the dates and the budget (5 searches, 10 fetches, 90 seconds by default), all stated in the answer.
- **Only organization names and addresses are searched.** An individual's name, or a name not recorded in HPD, ACRIS or DOS, is refused.
- **Costs and terms.** Search and extract spend Tavily credits; the cache limits repeats (a day for searches, a week for documents). The registry adapters send a plain request with a descriptive user agent and respect what the registry shows.

## Open, not blocking Slice 7 design

- Replace the Tavily key, run `WEB_LIVE_TESTS=1 uv run pytest tests/test_web_live.py`, and record one real search for a neutral anchor to check the live shape.
- Add registries as owners demand (Delaware needs a route that is not a CAPTCHA page: a paid or official data service is a decision for the user).
- The LangSmith upload stays off, as decided.
