# Competency questions

The questions the graph and agent must answer. They drive the ontology (week 2), become the evaluation dataset (week 8), and define what the demo slice must support.

**Status: 20 candidates (draft 4), awaiting ratification.** Nothing here is approved. Draft 4 adds a scope statement (web research and document retrieval are in scope for the agent) and extra scenarios; what changed is listed under "Changes from draft 3" and "Changes from draft 2". The graph consumes BOR's output (`docs/design-notes/0001-consume-bor-output.md`).

For each question, record the reliability its answer can reach: **I** (recorded assertion: a public record states it, or it follows from joining records on an official identifier), **II** (derived conclusion: a method links or classifies where the records do not say so), or **I+II** (a recorded chain with derived links).

Type I and II describe how an assertion was obtained, not how much to trust it. Source quality, identity uncertainty and inference strength are separate dimensions that an answer also reports. Two properties carry them (design note 0002): `source_category` (public record, published reporting, web content) and `review_status` (unreviewed, confirmed, refuted, inconclusive, contested). Web search is a retrieval channel, not a category. A published claim is a recorded fact that it was published; its truth and applicability are a separate, derived judgment.

## Vocabulary used in the questions

Working terms, to be settled in the week 2 vocabulary. They follow the layers BOR already implements.

| Term | Meaning | Reliability |
| --- | --- | --- |
| **Title / registration facts** | Who a deed conveys to (ACRIS); who HPD lists as owner, agent or contact (HPD); what DOS records for an entity | I |
| **Management relationship** | A building's *disclosed* managing agent (`MANAGED_BY`). A relationship, not a grouping and not a rung in an ownership hierarchy | I |
| **Operational Network** | Buildings that connect through registration infrastructure: shared names, business addresses or resolved identities, with aggregator addresses masked. Connected components; components over 300 lots are cut into communities by Louvain | II |
| **Owner Portfolio** | Buildings *attributed* to one apparent owner from ownership signals only: resolved shared identity, or a qualifying shared deed. BOR calls it a "beneficial owner group". Connected components of those edges; co-op/condo buildings are excluded | II |

Two cautions apply to the last two terms in every answer. Both are derived partitions, so each is a lead to verify, never a finding of legal ownership. And a group's "person anchor" in BOR's export is a display choice, not a named owner.

## Requirements that apply to every answer

Taken from what the repos' own documentation says about their outputs.

1. **Name the run.** A membership claim states the source-data snapshot and pipeline run (BOR's group ids are stable within a build, not across builds). A historical question needs historical evidence, never today's group id.
2. **Name the layer and the counting unit.** Operational Network, Owner Portfolio or management; counts are lots (BBL), buildings (BIN) or residential units, and the answer says which. BOR's `building_count` is a count of distinct BBLs, and its Owner Portfolio count is of rental buildings only, so it is not the full footprint.
3. **Say why a building is not grouped.** Absence of a link is not evidence of different owners, because recall is not measured. State which applies: *no qualifying linkage*; *excluded by policy* (co-op or condo, a masked aggregator address); *below the eligibility rule*; or *outside source coverage*. State the eligibility rule in terms of what it counts. BOR's Owner Portfolio needs at least two member registration identities (nodes), not two buildings, and a group is dropped when rental buildings are under half its footprint.
4. **Explain membership with evidence.** Each membership claim has an accessible evidence path: the supporting records, the stage that made each edge, and the clustering method. Summaries give a representative path; full paths on request or for a disputed link. For an Owner Portfolio the path is within a connected component. For a subdivided Operational Network, the answer separates connectivity in the original component from membership in the selected community: two buildings can have a path before subdivision and still fall in different networks.
5. **Method strength is a property of the method, not of the link.** An answer may quote a stage's benchmark precision with its interval (deed-linked successors are the weakest stratum). It must not present that figure as the probability that this link is right.
6. **Recorded and derived stay apart.** Each recorded assertion carries its source record. Membership is derived even when every supporting edge is a recorded document. A published claim is a recorded assertion that the claim was published; whether it is true and applies to the subject is a separate, derived judgment.
7. **Never infer ownership from a group's person anchor.** Whenever a person is named, say whether the role is recorded in a filing, attributed to a source, or inferred, and show inferred links as leads with their evidence (`CLAUDE.md`, "Publishing responsibly").

## Scope

The system automates the PESP *How to Research Your Landlord* method for New York City from an address. Three kinds of work are in scope, and they differ in where the answer comes from and how it is labeled.

| Work | What it covers | Result is held as |
| --- | --- | --- |
| **Graph answers** | Recorded facts from PLUTO, ACRIS, HPD and NY DOS, and the Owner Portfolio and Operational Network layers loaded from BOR/NLR | Type I (recorded), or Type II (derived) for the layers |
| **Web research** | Searching an entity name or address; finding the entity's state business filing, an OpenCorporates page, a foundation or nonprofit filing at an address, a program list, or a news report | `public_record` if a primary record is retrieved; `published_reporting` or `web_content` otherwise (design note 0002) |
| **Document retrieval and extraction** | Fetching filings and attachments (incorporation papers, annual reports, tax filings) and reading names, titles and addresses from them | The document is the source. Each extracted value cites document, page and extraction method |

**How web and document results are handled** (defaults, to confirm):

1. **Session evidence, not graph facts.** The agent's graph access is read-only (`CLAUDE.md`). Web and document findings are held in the dossier with their provenance (`url`, `retrieved_at`, `source_category`). Writing them to the graph would be a separate, reviewed process.
2. **Same rules as the graph.** A retrieved record is Type I. A third party's claim is a reported claim, Type I only as to its publication. Any link the agent draws from it is Type II and is shown as a lead with its evidence. The `review_status` is `unreviewed` unless a person has checked it.
3. **Mail-drop rule applies.** An address search that returns many unrelated organizations at a hub address supports no link between them. The count and sample are reported, not the connection.
4. **Business roles only.** Results about people stay within roles recorded in filings (`CLAUDE.md`, "Publishing responsibly"). The agent does not follow results to personal addresses, social profiles or other non-business information.
5. **No paid or proprietary sources.** The guide advises avoiding them, and results could not be cited.
6. **Reproducibility.** Web results change. Evaluation (week 8) runs against cached retrieval, and the answer records what was retrieved and when.

**Process requirements** (the guide's method is iterative; these are tested in weeks 6–8, not as competency questions):

- A new entity name or address found in a result is searched in turn, within a stated step and time budget.
- The loop stops, and says so, at a registered-agent or mail-drop address, at an entity with no further recorded link, or at the budget.
- Every retrieved item is logged with its source and time, whether or not it is used.

**Out of scope:** legal determinations of ownership; anything about tenants or individual apartments; non-public records.

## Candidates

| # | Question | Example | Reliability | Sources | Graph pattern (fill in week 3) |
| --- | --- | --- | --- | --- | --- |
| 1 | Which tax lot (BBL) and building(s) (BIN) does this street address resolve to, is the match unambiguous, and what characteristics do the records give (year built, building class, residential units, assessed value)? | `123 Example St, Brooklyn` → BBL `3012340056`, one BIN, built 1931, class C1, 24 units; or one lot with three BINs | I | PLUTO; HPD registrations | |
| 2 | Who is the HPD-registered owner of this building, and when was the registration last filed? | Registered owner `Example Holdings LLC`, filed 2025-09-01, expires 2026-09-01 | I | HPD registrations, contacts | |
| 3 | Who is the grantee on the most recent ACRIS deed for this lot? Do the deed and the HPD registration name the same party exactly, and where they differ, what supports treating them as one entity? | Exact agreement on `123 Example St LLC`; or `Example Holdings LLC` vs `Example Holdings II LLC` with a shared officer, reported as unresolved | I+II | ACRIS master, parties, legals; HPD | |
| 4 | Who is the managing agent, head officer or site manager HPD lists for this building? | Managing agent `Example Management Corp`, with registration dates | I | HPD contacts | |
| 5 | What does the NY DOS filing for this owner entity record: type, filing date, status, process address, and the officers or agents it names, and which of those fields does the dataset carry? | `Example Holdings LLC`, domestic LLC filed 2016, registered agent `...`; officers not carried | I | NY DOS corporations | |
| 6 | Was this address masked or down-weighted by a given method as an aggregator address, why, and is it also on the curated mail-drop list? | A hub office registered for 84 buildings and 35 owner-role people: masked in the Operational Network and Owner Portfolio; listed as a registered-agent service in `resolution/` | II | NLR, BOR masking; `resolution/` mail-drop list; HPD contacts | |
| 7 | What shared evidence (people, business addresses, resolved identities) do these two entities or buildings have, and which of it was set aside as non-evidence? | Same head officer on two registrations; same hub address, set aside as an aggregator | II | HPD contacts; DOS; NLR | |
| 8 | Which buildings belong to this building's Operational Network in the selected run, which registration and identity links connect them, and was the network a whole component or a Louvain community? | 41 BBLs; whole component; connected by a shared business address and a resolved identity | II | HPD registrations, contacts; BOR operational network | |
| 9 | Which lots, buildings and residential units are attributed to this building's Owner Portfolio, through which ownership signals, and how does that footprint differ from its Operational Network? | 14 lots, 17 buildings, 612 units, composition "deed-bridged"; Operational Network is 41 lots | II | BOR owner groups; ACRIS; PLUTO (`unitsres`) | |
| 10 | Where do the two layers disagree: an Operational Network containing several Owner Portfolios, or an Owner Portfolio spanning several Operational Networks? What evidence explains each difference? | *(a)* An unmasked management office connects lots held by three Owner Portfolios into one network. *(b)* One Owner Portfolio of 15 lots, re-deeded into 12 shells, spans three network fragments because the only address they share is masked. *(c)* Baseline: an unmasked Who Owns What network of 27 lots from one hub office splits into five Owner Portfolios; the answer says what remains connected in BOR's masked network | II | BOR layers; ACRIS; HPD | |
| 11 | What evidence supports an ownership, parent-company, management, financing or other affiliation involving this entity, which relationship is documented, and which is only hypothesized? | A mortgage lender (a financing relationship, not control); a shared officer with `Example Capital Partners` (a lead, separate from the Owner Portfolio); a disclosed agent (management) | I+II | ACRIS parties; DOS; HPD contacts | |
| 12 | What deed transfers are recorded for this lot in the selected period, and for the lots currently attributed to its Owner Portfolio? Which of them can be attributed to the currently identified owner? | Lot sold 3 times since 2015. The portfolio's current lots changed hands 9 times in 2021, but 2 of those were by previous owners with no established link to the current one | I+II | ACRIS; BOR | |
| 13 | What mortgages, assignments and satisfactions are recorded against the lot, in what amounts and with which lenders? | A $4.2M mortgage recorded 2021-07 to `Example Bank`, no satisfaction recorded | I | ACRIS master, parties | |
| 14 | Which title holders and HPD-registered owners do the records support for the date of a given violation, and what gaps or conflicts prevent a definite attribution? | Class C violation issued 2023-01-10: `Prior Owner LLC` is the title holder and registrant; or a deed dated 2022-12 but recorded 2023-02, with no registration in force on the date | I | HPD violations; ACRIS; HPD registrations | |
| 15 | What open violations does this building have, by class, how long have they been open, and what is the rate per residential unit? | 7 open: 1 class C, 4 B, 2 A; oldest open since 2022-02; 0.12 per unit | I | HPD violations; PLUTO | |
| 16 | Across a chosen layer (Owner Portfolio or Operational Network), which buildings have the most open hazardous violations per unit, and how concentrated are they? | 3 of 14 lots hold 80% of the portfolio's open class C violations; the same measure over the Operational Network gives a different list | I+II | HPD violations; PLUTO; BOR layers | |
| 17 | Is this building's registration missing, lapsed, or older than the latest deed transfer, and is a registration required for it? | Last registration 2021, deed to a new entity recorded 2023, none since | I | HPD registrations; ACRIS | |
| 18 | Which deed transfers among a portfolio's lots look like restructuring (a `$0` re-deed into single-purpose LLCs) rather than a sale, what supports that reading independently of the grouping itself, and what remains uncertain? | One 2008 multi-lot deed, then 12 `$0` deeds in 2015 from the same grantee into 12 LLCs; versus a sale at $3.1M to a buyer for whom no relationship was established | I+II | ACRIS; BOR deed linkage | |
| 19 | Why are these two buildings grouped together, or left unlinked, in each layer? Give the supporting records, linkage stages, connecting path, exclusions and the run. | Same Owner Portfolio via a path through a third lot; the direct pair shares nothing. In the Operational Network they are unlinked because their only shared address is masked | I+II | All | |
| 20 | Given an address, what is the traced dossier: title and registration facts, management relationship, Owner Portfolio, Operational Network, then any parent or control lead, each with a cited record, run and limits, and where does the trail stop? | `123 Example St`: five findings kept apart; two recorded, two derived layers, one parent lead; "trail ends at a registered-agent address" | I+II | All | |

## Answer contracts

Three questions have full contracts now, because they test the hardest requirements: portfolio attribution (Q9), historical uncertainty (Q14) and reproducible evidence (Q19). Contracts for the rest are written before the evaluation set is built in week 8. Q20 will be an integration scenario with the contracts of Q1–Q4, Q9, Q10 and Q19 as required components.

### Q9: Owner Portfolio footprint and comparison

| Element | Specification |
| --- | --- |
| Inputs | Address or BBL; run; layers; counting units wanted |
| Required output | Per layer: run-scoped group id, member count in lots, buildings and units, boroughs, composition (identity, deed-only, deed-bridged) for portfolios, whole-component or Louvain for networks, and the signals behind each member. Between layers: members in one and not the other, with counts |
| Acceptable incomplete | Building in no group, with the reason code from requirement 3. Units missing for some lots: partial total, with the number of lots missing a count |
| Failure | A lot count reported as buildings; layers mixed; group presented as legal ownership; person anchor used as owner; run omitted |
| Test cases | Ordinary: a building in a multi-lot identity group. Difficult: a lot with several BINs; a co-op/condo exclusion; a deed-bridged group |

### Q14: Title holder and registered owner on a violation date

| Element | Specification |
| --- | --- |
| Inputs | Violation, or building and date; which date counts (inspection, notice or issue); perspective (as now known) |
| Required output | Title holders supported for that date, from deeds, with document and recorded dates; registered owners in force on that date, with registration periods; whether they coincide; each gap or conflict |
| Acceptable incomplete | Title holder supported, no registration in force; or "cannot attribute", with the reason. The records are today's version of the past, and the answer says so |
| Failure | The current owner substituted for the historical one; one owner asserted despite a conflict; the owner of record presented as the party responsible |
| Test cases | Ordinary: one deed, continuous registration. Difficult: deed dated before and recorded after the violation date; a lapsed registration; a sale between inspection and notice |

This needs historical records and explicit date semantics (document date, recorded date, registration period, violation dates), not just `valid_from` / `valid_to` on a role.

### Q19: Membership explanation

| Element | Specification |
| --- | --- |
| Inputs | Two buildings (BBL); layer or layers; run |
| Required output | Per layer: same group, different groups, or one or both ungrouped (with reason code). For same group: composition, a representative edge path with the stage and records behind each edge, and full detail on request. For networks: connected in the original component or not, and whether subdivided. Benchmark precision of the stages used, as a method property |
| Acceptable incomplete | Edges not exported: membership only, with the statement that evidence is not available |
| Failure | Different owners inferred from a non-link; direct evidence claimed where there is only a path; stage precision presented as a link probability; pre-subdivision connectivity presented as network membership |
| Test cases | Ordinary: a direct identity link. Difficult: a path through a third lot; a masked hub; a Louvain-split pair connected before subdivision |

## Additional scenarios

Each follows a step of the guide's method that the 20 questions did not exercise. They extend existing questions and are not new questions. Names and addresses are placeholders.

**Q1: address not found**
- The address is absent from the lot data but the lot appears under an alternate address, a street-name variant or a corner address: the answer reports the match it used and the alternate address, and says the resolution is inferred.
- No match at all: reported as "no lot found" with the variants tried, and the agent does not guess a nearby lot.

**Q5: filing documents beyond the dataset**
- The dataset names only a process address and registered agent: the agent retrieves the entity's state filing and its attachments, and reports any manager, member or officer the documents name, each with document, page and extraction method.
- The only agents named are corporate service companies: reported as such, with no person or address treated as a lead (mail-drop rule).
- A name read from a scanned document is uncertain: reported with the extraction method and a low-confidence flag, and not used as a link on its own.
- A retrieved filing gives a different address from the dataset: both are returned with their dates; the answer does not choose.

**Q7 and Q8: similarly named entities**
- `Example Holdings LLC` and `Example Holdings II LLC` share an agent and addresses: reported as a possible connection with that evidence, not as the same entity. Names alone support no link.
- Similar names with no shared record: not reported as related.
- A similarly named entity's filing names a person or address missing from the first: reported as new evidence for that entity, with its source.

**Q7: other organizations at an address**
- A business address in a filing is searched: other companies, foundations or nonprofits that list it are returned with their filings. If the address is a hub (many unrelated organizations), the answer gives the count and says whether the list is complete or a sample, and supports no link.
- An organization's tax filing lists the address "care of" a management company: reported as an affiliation recorded in that filing, not as ownership.

**Q11: reported claims and affiliations**
- A news article states that a fund controls the owner's parent company: shown as a reported claim, with publisher, date and quoted text, unreviewed, and kept apart from the Owner Portfolio.
- Two articles contradict each other: both are shown, contested, and neither is chosen.
- A claim names a person whose recorded role in the filings differs: both are returned, and the person is shown only in the recorded role.
- A claim from before the as-of date is superseded by later records: reported with both dates.

**Q12: timing of transfers**
- A sale recorded within a month of a new registration: both reported with dates, and the answer says nothing about intent.
- A lot sold as part of a multi-lot deed: reported once as a deed with the lots it covers, and the answer states that it counts deeds, not lots.

**Q20: the dossier on a real trail**
- The trail ends at a registered-agent address after two entities: reported as the end, with the reason.
- The trail reaches a parent company only through a news claim: the dossier presents it as a lead, and says the recorded part of the trail ended earlier.
- Permits (DOB) or program and subsidy lists are retrieved on demand: reported with their source and not added to the graph. If DOB permits become a loaded source, a question is added.

## Notes

**Mapping to the PESP guide's ten questions (p. 5).** The guide says it focuses on the first five.

| PESP question | Covered by | Note |
| --- | --- | --- |
| Who is my landlord? | 1–5, 17 | |
| How many properties does my landlord own, and where? | 7–10 | Answered separately for ownership and for shared operation; the two lists differ by design (Q10) |
| Does my landlord sell frequently, or hold? | 12, 18 | Transfers are recorded facts; attributing them to the current owner is derived. Historical membership is not derivable from a current snapshot |
| What are conditions at my building? | 14–16 | Violations are a record of what was cited, not of conditions |
| Has there been notable news? | 11, 20 (scenarios) | Web research. A report supports "this article states X" (recorded); whether X is true and applies is a separate, derived judgment |
| What is the financial standing? | 13 | Mortgages only; no tax-lien or distress data in the current sources |
| Who are the people behind the company? | 5, 7, 11 | |
| Is my building overseen by a federal or state entity? | 20 (scenario) | Program lists retrieved on demand; not loaded in the graph |
| What kind of company is my landlord, and who are its investors? | 5, 11 | Investors are usually not in NYC filings; expect leads only |
| Which local regulatory agencies may influence my landlord? | not covered | Out of scope for the graph |

**The guide's worked example.** Its trail is: property record → LLC → registered address → a person → a news article → a hedge fund. In NYC the first steps use open records, but each can return names and addresses without establishing the identity or relationship the next step needs. Q20 asks for the trail with recorded facts and derived links kept apart, and must state where it stops.

**Coverage.**

- Reliability counts: 8 recorded (Q1, 2, 4, 5, 13, 14, 15, 17), 6 derived (Q6–11), 6 mixed (Q3, 12, 16, 18, 19, 20).
- Q6, Q10 and Q19 test the project's distinctive contribution: explaining why a link was made, why it was refused, and why the two layers disagree.
- Q14 is the temporal test and Q12 the attribution test; neither can rely on a current-owner property.
- Q3 and Q17 test whether ACRIS and HPD are modelled separately (title holder versus registered owner).
- Q1 and Q9 test that lots, buildings and units are never silently equated.

## Changes from draft 3

- **Added** a Scope section: graph answers, web research and document retrieval are in scope, with the default handling rules and process requirements for the agent's loop.
- **Added** the "Additional scenarios" section (Q1, Q5, Q7, Q8, Q11, Q12, Q20), one per step of the guide's method the questions did not exercise.
- **Extended** Q1 to ask for building characteristics (year built, class, units, assessed value).
- **Updated** the guide mapping: news and oversight are covered by scenarios; regulators remain out of scope.

## Changes from draft 2

- **Corrected** requirement 3: the Owner Portfolio eligibility rule counts member registration identities, not buildings (checked in `owner_groups.py`: `min_size` applies to node ids). Requirement 4 now separates component connectivity from community membership.
- **Replaced** Q10's example, which described the unmasked Who Owns What baseline as BOR's network. It now has two BOR-layer cases and labels the baseline.
- **Rewrote** Q12 (transfers of the lot versus attribution to the current owner) and Q14 (supported title holders and registrants, with gaps).
- **Rewrote** Q11 (distinct relationship types, documented versus hypothesized), Q18 (independent support; the buyer is "no relationship established") and Q3 (exact agreement is recorded; same-entity is derived).
- **Redefined** Type I and II as recorded assertion versus derived conclusion. Softened the news and worked-example notes accordingly.
- **Narrowed** requirement 7 (people) and requirement 4 (paths).
- **Added** answer contracts for Q9, Q14 and Q19, and corrected the reliability counts.

## Open items

1. **Evidence export.** The BOR release files hold only memberships. I found no edge-level file. Q8, Q9 and Q19 need the edges, their stage and the connecting path to be exported or reproducible (requirement on the repos; design note to follow).
2. **Reliability convention.** Resolved by design note 0002 (accepted 2026-10-15). Still open from it: who sets `review_status`, and what justifies a change.
3. **People in agent output.** `CLAUDE.md` limits people to roles recorded in HPD, ACRIS or DOS filings. Requirement 7 allows inferred links as labeled leads, as `CLAUDE.md` already does, but not attributed statements from news. Whether to allow those is your decision.
4. **Contracts for the other 17 questions**, and for Q5 (DOS field availability), Q15–16 (snapshot date and denominator) and Q17 (registration applicability and ingestion completeness) in particular.
5. **Web and document findings: storage.** Scope item 1 holds them as session evidence because the graph is read-only for the agent. Decide whether a reviewed process may later promote a finding into the graph.
6. **LinkedIn and similar pages.** The guide's example used a LinkedIn page to tie an officer to a company. Scope rule 4 excludes personal social profiles by default, which would drop that step. Your call whether a profile that only states an employer counts as a business role.
7. **Retrieval tooling and cache design** for the agent (week 6), and how evaluation fixtures are frozen (week 8).
8. **DOB permits** as a loaded source, or retrieved on demand only.
9. **Regulators** (the guide's last question) remain out of scope.
