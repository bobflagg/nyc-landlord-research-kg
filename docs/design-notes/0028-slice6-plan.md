# 0028: Slice 6 plan (beyond the graph)

Date: 2026-10-29

Status: **accepted 2026-10-29:** W2 to W6 as recommended; W1 option (a) with **Tavily** chosen by the user. All five build steps are done; the exit check is note 0029. Builds on `specs/tech-stack.md` ("web and document findings are session evidence, not graph facts"; "live web results are labeled with their retrieval time and kept apart from graph facts"), notes 0005, 0009 and 0024.

## What Slice 6 delivers

Roadmap: reports and filing documents; out-of-state registries, held as session evidence. Questions Q16 and Q25. Slices 0 to 5 must still pass.

| Q | Contract | Answer shape |
| --- | --- | --- |
| Q16 | For an entity or address: each report or filing document with its publisher or filing body, date, URL or document id, the quoted claim or extracted value, the extraction method, `source_category`, `review_status`, the basis for treating it as about this entity, and how it relates to the recorded facts (agrees, adds, conflicts, unrelated). Nothing found is "no reports or documents found in the sources searched", with the queries and dates | list of items |
| Q25 | For an entity formed outside New York: the record from a free registry, or an unresolved lead with the reason (needs payment, inaccessible) | record or unresolved lead |

Both are reported claims or retrieved records, not recorded facts of the graph. A claim in a report is a claim that was published, not a fact; a person named only in a report is an attributed, unreviewed claim, not an owner; an entity matched on name alone is said to be a lead.

## What exists, and what does not

- **No web access exists yet.** The agent's tools read the graph. The model string is Anthropic Claude through LangChain; the Deep Agents investigator is Slice 7.
- **The graph tells us where Q25 matters.** Of the HPD registered owners that match a DOS entity by exact normalized name, 2,583 are Delaware entities (foreign entities authorized in New York), 92 New Jersey, 47 Florida, and a few dozen each Georgia, California, Nevada and Wyoming. HPD owner business addresses outside New York are mostly New Jersey (1,259 organizations), then Florida, California and Connecticut. So the state registries that matter first are Delaware and New Jersey, with Florida and Connecticut as the free ones to try.
- **The evidence shape is already agreed.** Q16's required output lists the fields; the source-category vocabulary already has `published_reporting` and `web_content`; review status `unreviewed` or `contested` applies; reliability is II or "reported" per note 0002 (to be checked in step 1 against that note's exact property values).
- **Rules already settled** apply unchanged: a name match is a lead (note 0009); people appear only in the role a record gives; the typed or recorded entity name is the query, and no search is made for a person's other information.
- **Not verified yet, and the first thing step 1 does:** the current LangChain, LangGraph and Deep Agents documentation for tools and web search (CLAUDE.md: they change quickly), the terms of use, rate limits and output of each candidate search API, and for each state registry whether a free search exists without a login or CAPTCHA and what it returns.

## Decisions for the user

**W1. The web search tool.**
- **(a) Our own interface over a search API, recommended:** `search_web(query)` returns URL, title, snippet and publication date where the provider gives one; `fetch_document(url)` returns the text with its retrieval time and a content hash. We choose the provider in step 1 (a news-capable search API with a free or low tier; Brave and Tavily are candidates) after checking terms, cost and date metadata. Every query, result and fetch passes through our code, so each can be logged, cached, replayed in tests and stamped with its retrieval time.
- (b) The model provider's built-in web search tool. Least code, but the queries and results happen inside the model call, our evidence record cannot be made from them without parsing the model's own citations, tests cannot replay them, and the retrieval time and the exact text read are not ours.
- (c) No open search: a curated list of sources only (a few news feeds, court and government sites, the registries of W4). Predictable and safe, but "no reports found in the sources searched" would then be weak, and a story on an unlisted outlet is missed.

**W2. The session evidence model.** Recommended: findings are typed objects (Pydantic) held in the session and never written to the graph (tech-stack). An `EvidenceItem` carries exactly the Q16 fields: `item_id`, `publisher_or_body`, `published` (date or null), `retrieved_at`, `url` or `document_id`, `page`, `quote` (verbatim, short), `extraction_method`, `source_category`, `review_status`, `match_basis`, `relation_to_records`, `confidence` and a list of `flags` (after the as-of date, uncertain scan, paid-only, contradicted by another item). Four small vocabularies hold the coded values, as everywhere else: `evidence-relation` (agrees, adds, conflicts, unrelated), `match-basis` (exact_name, exact_address, lead_only), `extraction-method` (verbatim_text, registry_field, model_reading, ocr), `lead-reason` (needs_payment, inaccessible, unreadable, partial, not_found). The alternative, free-form dictionaries, would let each tool invent its own fields and the Slice 7 dossier could not rely on them.

**W3. The retrieval cache.**
- **(a) A local on-disk cache, recommended:** SQLite under `data/cache/` (gitignored), keyed by the normalized request (provider, query or URL, parameters), storing the response body, the original `retrieved_at` and a content hash. A cache hit reports the original retrieval time and `cached: true`, so "retrieved just now" and "as of the snapshot" never blur. Time to live: a day for search results, a week for fetched documents and registry records, both parameters. The same store records the replay fixtures for tests (small, public pages only, committed under `tests/fixtures/web/` after checking each source's terms).
- (b) No cache. Simplest, but every evaluation run repeats live requests, costs money, hits rate limits and gives different answers each time.
- (c) A LangGraph store. It couples the cache to one agent run; the evaluation and the tools would each need the agent.

**W4. Which registries for Q25, and how.** Recommended: one adapter per registry behind a common `lookup_registry(name, jurisdiction)`, starting with **Delaware** (the volume: 2,583 owners; the free search reports existence, status and registered agent, and formation documents are paid, which is the contract's "needs payment" case) and **one fully free registry** (Florida or Connecticut, chosen in step 1 by what the free search actually returns), then New Jersey if its free search is usable. An adapter reads only what the registry shows free to a plain request. It never signs in, solves a CAPTCHA, pays or hides what it is, and respects robots rules and rate limits; a registry that blocks us or has no free search is an unresolved lead with the reason `inaccessible`. The alternatives are a generic web search for "<name> <state> secretary of state" (unreliable, and the page found may not be the registry) or a paid commercial aggregator (against the free-sources constraint).

**W5. Matching and safety rules.** Recommended, stated in every result:
- The **query is the recorded entity's exact name** (and name variants the graph gives, each tried and listed), or a recorded address key's text. No query about a person's other information, and no query built from a report's text.
- An item is **about this entity** (`match_basis: exact_name` or `exact_address`) only when the exact normalized name or address appears in the text with the quote shown; a similar name is `lead_only` and "a lead about a different entity", never attached.
- **Relation to the records** is computed against the graph by tools already built (the registered owner, deed grantees, DOS entity, layers): `agrees` when a person or entity appears in the role the records give, `adds` when it is new, `conflicts` when it differs from a recorded role, `unrelated` otherwise. Contradicting items are both shown and marked contested; neither is chosen.
- An item **dated after the as-of date** is flagged; one **superseded by later records** is shown with both dates. A signatory is not an owner.
- **Web text is untrusted data.** It is read only in an extraction step that has no tools, its instructions are never followed, and its text is never put into a query or a Cypher statement.
- The alternative of letting the model decide relation and matching freely is faster but cannot be tested or explained.

**W6. Evaluation without a live web.** Recommended: tests and the evaluation dataset replay recorded responses (W3) so they are deterministic; a small live smoke test (a few requests, off by default) checks that each provider and adapter still works. Expected answers are written for the contract's test cases: an article naming the exact LLC; a retrieved filing with a named manager; an article naming a similarly named entity; two contradicting articles; a scanned attachment with an uncertain name; a paid-only registry step; a report dated after the as-of date; no results; an inaccessible registry. Neutral anchor buildings are expected to return "no reports found in the sources searched", with the queries and dates, which is itself a test. The judge checks every claim against the evidence items returned. The alternative of live-only evaluation would make the score depend on the day.

## Tools and build order

Tools (read-only for the graph, network-using for the web, all with step and time budgets as inputs): `search_reports(entity_or_address, as_of?, budget?)` for Q16 and `lookup_registry(name, jurisdiction)` for Q25, each returning `EvidenceItem` lists, the queries tried with their times, and what was not done and why. A budget (at most 5 searches and 10 fetches by default, a total time limit) makes "nothing found" mean "nothing found within this budget" and says so.

1. **Verify and decide.** Read the current LangChain/LangGraph/Deep Agents documentation and the candidate providers' and registries' terms; settle W1 and W4 with the evidence; record in a short addendum. Add the vocabularies and the `EvidenceItem` model with tests (no network).
2. **Retrieval layer.** `search_web`, `fetch_document`, the cache, the query log, budgets and replay fixtures; tests entirely offline.
3. **Q25.** The registry adapters and `lookup_registry`; unresolved leads for paid, blocked and unreachable cases.
4. **Q16.** Query construction from recorded names, matching, quote extraction, relation to records, contradiction and date handling.
5. **Expected answers (recorded fixtures), evaluation examples, the live smoke test, the prompt rules, the spec lines (`specs/tech-stack.md` row and open decisions) and the exit check (note 0029)** with the regression of Slices 1 to 5.

## Risks

- **Misattribution.** A report about a similarly named company attached to the wrong landlord is the most harmful failure (Q16's failure list). Mitigation: W5, the quote shown, `lead_only`, and tests for the similar-name and contradiction cases.
- **Prompt injection.** A page can contain instructions. Mitigation: extraction without tools, a fixed output schema, and never executing or following fetched text; a test page with an injected instruction.
- **Terms, robots and cost.** Each provider and registry has terms and limits. Mitigation: step 1 reads them before any adapter is written, the cache limits repeat requests, and there is no scraping past what a plain request shows.
- **Nondeterminism.** Search results change. Mitigation: replay fixtures for the evaluation, the stated retrieval time on every item, a live smoke test kept separate.
- **A missing report read as nothing having happened.** The empty result always carries the queries, dates, sources and the budget used.
- **Paywalls and scans.** Partial or unreadable documents are unresolved leads with a low-confidence flag, never links.
- **Quotes and copyright.** Quotes are short and verbatim with the source; the cache is local and gitignored; committed fixtures are limited to public pages whose terms allow it, or are synthetic.
- **People.** A report may name individuals. They appear only as attributed claims with their source and role, and nothing is searched about them beyond the recorded entity.

## Step 1 findings (2026-10-29)

- **Tavily** (docs.tavily.com, read today): `POST /search` takes `query`, `topic` (general, news), `max_results`, `search_depth`, `start_date`/`end_date`, `include_published_date`, `exact_match` (quoted phrases must match exactly), `include_domains`, and returns `results` with `title`, `url`, `content`, `score` and `published_date` (a best estimate, null when undetectable); `POST /extract` takes up to 20 URLs and returns `results` with `raw_content` and `failed_results` with an error per URL (a 200 can carry only failures). Auth is a Bearer key. The pages state no free tier; non-paying plans may get 434 under load. Search uses `exact_match` and `include_published_date`; fetch uses `extract` with the entity name as the relevance query.
- **The Tavily key in `.env` is rejected.** It has the right form (`tvly-` prefix) but `/search` answers 401 "missing or invalid API key", so no live search has been made. Everything below was built and tested against a mock provider and recorded fixtures; the live smoke test (`WEB_LIVE_TESTS=1`) fails at the search and passes at the registry until the key is replaced.
- **Registries, probed by a plain request:** Connecticut's Business Registry is open data (`data.ct.gov`, public domain) and answers; its `business_email_address` field is personal and is dropped before anything is cached. Delaware's search page is behind a CAPTCHA, Florida's (Sunbiz) answers 403 with a browser challenge, and New Jersey's is a browser form. W4 named Delaware as the case for "needs payment"; in practice Delaware is `inaccessible` (the CAPTCHA comes first), so the paid case is exercised by a 402 response in tests. Connecticut is the one working registry; the others report their lead.

## Built (2026-10-29)

- **Vocabularies:** `evidence-relation`, `match-basis`, `extraction-method`, `lead-reason` (with `budget_exhausted` and `not_found` added to the three in W2). `agent/web/evidence.py`: `EvidenceItem` (the Q16 fields; coded values checked against the vocabularies; review status unreviewed or contested), `Lead`, `Budget`.
- **Retrieval layer:** `agent/web/cache.py` (SQLite, original retrieval time, content hash, time to live, fixtures in and out), `agent/web/client.py` (Tavily search and extract; modes live and replay; the key is read from `.env`, sent as a Bearer token and never logged; every call logged; budget of 5 searches, 10 fetches and 90 seconds).
- **Q25:** `agent/web/registries.py` and `lookup_registry`: Connecticut through open data; Delaware, Florida and New Jersey re-probed and reported as leads; a 402 is `needs_payment`; an unsupported state is a lead.
- **Q16:** `agent/web/reports.py` and `search_reports`: the subject must be a recorded organization name or a lot (individuals and unrecorded names are not searched); queries are the exact name (general and news) and the lot's address; the quote is the verbatim sentence around an exact normalized-name match (N1, with L.L.C. and "&" handled); a similar name (a numeral, a number, a legal suffix or a spacing difference, not a swapped word) is a `lead_only` item; a tool-less reader classifies the quote against a short summary of the recorded facts (agrees, adds, conflicts, unrelated); dates after the as-of date and conflicts older than the snapshot are flagged; items that make different claims about one subject and predicate are both contested. A search that could not run is `search_unavailable`, never "no reports found".
- **Tests and evaluation:** 28 offline tests (`tests/test_web.py`) with a mock provider and registries, one live smoke test off by default, 9 evaluation examples that replay `tests/fixtures/web/replay.json` (made by `scripts/make_web_fixtures.py` from synthetic pages), `evals/run.py --web-live` for live runs; spec lines in `specs/tech-stack.md` and `specs/roadmap.md` updated.
