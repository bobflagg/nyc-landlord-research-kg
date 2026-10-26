# Competency questions

The questions the graph and agent must answer. They drive the ontology (week 2), become the evaluation dataset (week 8), and define what the demo slice must support.

**Status: 28 candidates (draft 5), awaiting ratification.** Nothing here is approved. The count is a result of coverage, not a target: a question is added when a need cannot be tested by the existing ones, and split when it bundles separate needs. Draft 5 splits three compound questions, adds eight (including HPD complaints and litigation, Q27 and Q28), and records the decisions on open items 3, 5, 6 and 8; what changed is listed under "Changes from draft 4" and earlier. The graph consumes BOR's output (`docs/design-notes/0001-consume-bor-output.md`), and BOR will export edge-level evidence.

Each question also has a block in `docs/competency-questions-detail.md`: a real example on a neutral building, the shape of the answer, who asks it and why, and the caveat the agent must give. Source names there are the keys in `data/sources.yaml`.

For each question, record the reliability its answer can reach: **I** (recorded assertion: a public record states it, or it follows from joining records on an official identifier), **II** (derived conclusion: a method links or classifies where the records do not say so), or **I+II** (a recorded chain with derived links).

Type I and II describe how an assertion was obtained, not how much to trust it. Source quality, identity uncertainty and inference strength are separate dimensions that an answer also reports. Two properties carry them (design note 0002): `source_category` (public record, published reporting, web content, project-derived; design note 0004) and `review_status` (unreviewed, confirmed, refuted, inconclusive, contested). Web search is a retrieval channel, not a category. A published claim is a recorded fact that it was published; its truth and applicability are a separate, derived judgment.

## Vocabulary used in the questions

Working terms, to be settled in the week 2 vocabulary. They follow the layers BOR already implements.

| Term | Meaning | Reliability |
| --- | --- | --- |
| **Title / registration facts** | Who a deed conveys to (ACRIS); who HPD lists as owner, agent or contact (HPD); what DOS records for an entity | I |
| **Management relationship** | A building's *disclosed* managing agent (`MANAGED_BY`). A relationship, not a grouping and not a rung in an ownership hierarchy | I |
| **Operational Network** | Buildings that connect through registration infrastructure: shared names, business addresses or resolved identities, with aggregator addresses masked. Connected components; components over 300 lots are cut into communities by Louvain | II |
| **Owner Portfolio** | Buildings *attributed* to one apparent owner from ownership signals only: resolved shared identity, or a qualifying shared deed. BOR also calls it the Owner Portfolio (it was a "beneficial owner group" before 2026-10-21). Connected components of those edges; co-op/condo buildings are excluded | II |

Two cautions apply to the last two terms in every answer. Both are derived partitions, so each is a lead to verify, never a finding of legal ownership. And a group's "person anchor" in BOR's export is a display choice, not a named owner.

## Requirements that apply to every answer

Taken from what the repos' own documentation says about their outputs.

1. **Name the run.** A membership claim states the source-data snapshot and pipeline run (BOR's group ids are stable within a build, not across builds). A historical question needs historical evidence, never today's group id.
2. **Name the layer and the counting unit.** Operational Network, Owner Portfolio or management; counts are lots (BBL), buildings (BIN) or residential units, and the answer says which. BOR's `building_count` (renamed `lot_count` in the release contract, with `total_lot_count` for the full footprint) is a count of distinct BBLs, and its Owner Portfolio count is of rental lots only, so it is not the full footprint.
3. **Say why a building is not grouped.** Absence of a link is not evidence of different owners, because recall is not measured. State which applies: *no qualifying linkage*; *excluded by policy* (co-op or condo, a masked aggregator address); *below the eligibility rule*; *outside source coverage* (the source holds no record); or *outside method input* (the source holds the record but the method did not use it, such as an older registration; design note 0007). State the eligibility rule in terms of what it counts. BOR's Owner Portfolio needs at least two member registration identities (nodes), not two buildings, and a group is dropped when rental buildings are under half its footprint.
4. **Explain membership with evidence.** Each membership claim has an accessible evidence path: the supporting records, the stage that made each edge, and the clustering method. Summaries give a representative path; full paths on request or for a disputed link. For an Owner Portfolio the path is within a connected component. For a subdivided Operational Network, the answer separates connectivity in the original component from membership in the selected community: two buildings can have a path before subdivision and still fall in different networks.
5. **Method strength is a property of the method, not of the link.** An answer may quote a stage's benchmark precision with its interval (deed-linked successors are the weakest stratum). It must not present that figure as the probability that this link is right.
6. **Recorded and derived stay apart.** Each recorded assertion carries its source record. Membership is derived even when every supporting edge is a recorded document. A published claim is a recorded assertion that the claim was published; whether it is true and applies to the subject is a separate, derived judgment.
7. **Never infer ownership from a group's person anchor.** Whenever a person is named, say whether the role is recorded in a filing, attributed to a source, or inferred, and show inferred links as leads with their evidence (`docs/demo-slice.md`, "Publishing responsibly").

## Scope

The system automates the PESP *How to Research Your Landlord* method for New York City from an address. Three kinds of work are in scope, and they differ in where the answer comes from and how it is labeled.

| Work | What it covers | Result is held as |
| --- | --- | --- |
| **Graph answers** | Recorded facts from PLUTO, ACRIS, HPD (registrations, violations, complaints, litigation) and NY DOS, and the Owner Portfolio and Operational Network layers loaded from BOR/NLR | Type I (recorded), or Type II (derived) for the layers |
| **Web research** | Searching an entity name or address; finding the entity's state business filing, an OpenCorporates page, a foundation or nonprofit filing at an address, a program list, or a news report; free public business registries of other states when the owner is an out-of-state entity | `public_record` if a primary record is retrieved; `published_reporting` or `web_content` otherwise (design note 0002) |
| **Document retrieval and extraction** | Fetching filings and attachments (incorporation papers, annual reports, tax filings) and reading names, titles and addresses from them | The document is the source. Each extracted value cites document, page and extraction method |

**How web and document results are handled** (defaults, to confirm):

1. **Session evidence, not graph facts.** The agent's graph access is read-only (`CLAUDE.md`). Web and document findings are held in the dossier with their provenance (`url`, `retrieved_at`, `source_category`). Writing them to the graph would be a separate, reviewed process, deferred until after week 8.
2. **Same rules as the graph.** A retrieved record is Type I. A third party's claim is a reported claim, Type I only as to its publication. Any link the agent draws from it is Type II and is shown as a lead with its evidence. The `review_status` is `unreviewed` unless a person has checked it.
3. **Mail-drop rule applies.** An address search that returns many unrelated organizations at a hub address supports no link between them. The count and sample are reported, not the connection.
4. **Names with their source; no personal information.** A name is shown wherever the data has it, with its role (if any), source and reliability (`docs/demo-slice.md`, "Publishing responsibly"; design note 0009, which replaced the earlier recorded-roles-only rule of 2026-10-17). A name never asserts a role: a person named in a news report is a reported claim, attributed to the publisher, unreviewed, and never a role in the graph or dossier findings. A professional page (such as LinkedIn) that only states an employer or title is `web_content` for that business role. The agent does not follow results to personal addresses, personal profiles or other non-business information.
5. **No paid or proprietary sources.** The guide advises avoiding them, and results could not be cited. A step that needs one (some state registries charge for formation documents) is reported as an unresolved lead, not as a gap in the investigation.
6. **Reproducibility.** Web results change. Evaluation (week 8) runs against cached retrieval, and the answer records what was retrieved and when.

**Process requirements** (the guide's method is iterative; these are tested in weeks 6–8, not as competency questions):

- A lead (defined in the end-to-end acceptance requirement below) is followed in turn, within a stated step and time budget.
- The loop stops with one of the stop reasons in that requirement, and says which.
- Every retrieved item is logged with its source and time, whether or not it is used.

**Out of scope:** legal determinations of ownership; anything about tenants or individual apartments; non-public records. HPD complaint records are filed per apartment, so the graph and the agent use them only as building-level counts (Q27): no apartment, unit or complainant detail is loaded or returned, even where the dataset carries it.

## Candidates

| # | Question | Example | Reliability | Sources | Graph pattern (fill in week 3) |
| --- | --- | --- | --- | --- | --- |
| 1 | Which tax lot (BBL) and building(s) (BIN) does this street address resolve to, is the match unambiguous, and what characteristics do the records give (year built, building class, residential units, assessed value)? | `123 Example St, Brooklyn` → BBL `3012340056`, one BIN, built 1931, class C1, 24 units; or one lot with three BINs | I | PLUTO; HPD registrations | |
| 2 | Who is the HPD-registered owner of this building, and when was the registration last filed? | Registered owner `Example Holdings LLC`, filed 2025-09-01, expires 2026-09-01 | I | HPD registrations, contacts | |
| 3 | Who is the grantee on the most recent ACRIS deed for this lot, and does the deed name the same party as the HPD registration, compared by exact normalized name? | Exact agreement on `123 Example St LLC`; or the deed names `Example Holdings II LLC` and the registration `Example Holdings LLC`: reported as a difference, not resolved here (see Q22) | I | ACRIS master, parties, legals; HPD | |
| 4 | Who is the managing agent, head officer or site manager HPD lists for this building? | Managing agent `Example Management Corp`, with registration dates | I | HPD contacts | |
| 5 | What does the NY DOS active-entity record show for this owner entity: type, filing date, DOS process name and address, and registered agent? Where the record is absent or silent, what is known and from what source? | `Example Holdings LLC`, domestic LLC filed 2016, process address `...`, no registered agent listed; no officers, managers or members are carried for LLCs; a dissolved entity is absent from the dataset | I | NY DOS corporations (active entities only) | |
| 6 | Was this address masked or down-weighted by a given method as an aggregator address, why, and is it also on the curated mail-drop list? | A hub office registered for 84 buildings and 35 owner-role people: masked in the Operational Network and Owner Portfolio; listed as a registered-agent service in `resolution/` | II | NLR, BOR masking; `resolution/` mail-drop list; HPD contacts | |
| 7 | What shared evidence (people, business addresses, resolved identities) do these two entities or buildings have, and which of it was set aside as non-evidence? | Same head officer on two registrations; same hub address, set aside as an aggregator | II | HPD contacts; DOS; NLR | |
| 8 | Which buildings belong to this building's Operational Network in the selected run, which registration and identity links connect them, and was the network a whole component or a Louvain community? | 41 BBLs; whole component; connected by a shared business address and a resolved identity | II | HPD registrations, contacts; BOR operational network | |
| 9 | Which lots, buildings and residential units are attributed to this building's Owner Portfolio, through which ownership signals, and how does that footprint differ from its Operational Network? | 14 lots, 17 buildings, 612 units, composition "deed-bridged"; Operational Network is 41 lots | II | BOR Owner Portfolios; ACRIS; PLUTO (`unitsres`) | |
| 10 | Where do the two layers disagree: an Operational Network containing several Owner Portfolios, or an Owner Portfolio spanning several Operational Networks? What evidence explains each difference? | *(a)* An unmasked management office connects lots held by three Owner Portfolios into one network. *(b)* One Owner Portfolio of 15 lots, re-deeded into 12 shells, spans three network fragments because the only address they share is masked. *(c)* Baseline: an unmasked Who Owns What network of 27 lots from one hub office splits into five Owner Portfolios; the answer says what remains connected in BOR's masked network | II | BOR layers; ACRIS; HPD | |
| 11 | What evidence supports an ownership, parent-company, management, financing or other affiliation involving this entity, which relationship is documented, and which is only hypothesized? | A mortgage lender (a financing relationship, not control); a shared officer with `Example Capital Partners` (a lead, separate from the Owner Portfolio); a disclosed agent (management) | I+II | ACRIS parties; DOS; HPD contacts | |
| 12 | What deed transfers are recorded for this lot in the selected period, and for the lots currently attributed to its Owner Portfolio? Which of them can be attributed to the currently identified owner? | Lot sold 3 times since 2015. The portfolio's current lots changed hands 9 times in 2021, but 2 of those were by previous owners with no established link to the current one | I+II | ACRIS; BOR | |
| 13 | What mortgages, assignments and satisfactions are recorded against the lot, in what amounts and with which lenders? | A $4.2M mortgage recorded 2021-07 to `Example Bank`, no satisfaction recorded | I | ACRIS master, parties | |
| 14 | Which title holders and HPD-registered owners do the records support for the date of a given violation, and what gaps or conflicts prevent a definite attribution? | Class C violation issued 2023-01-10: `Prior Owner LLC` is the title holder and registrant; or a deed dated 2022-12 but recorded 2023-02, with no registration in force on the date; or the title holder is absent from the active-only DOS snapshot | I | HPD violations; ACRIS; HPD registrations | |
| 15 | What open violations does a building have, by class, how long have they been open, and what is the rate per residential unit? | 7 open (1 class C, 4 B, 2 A), oldest open since 2022-02, 0.12 per unit, as of the snapshot date | I | HPD violations; PLUTO | |
| 16 | What do published reports and retrieved filing documents say about this owner or entity, how do they relate to the recorded facts, and what is each one's review status? | A news article states that `Example Capital Partners` controls the owner's parent company: a reported claim, unreviewed. An incorporation attachment names a manager and a second address, with page and extraction method. Neither is shown as ownership | I+II | Web research; retrieved filings (state registries, nonprofit filings, news) | |
| 17 | Is this building's registration missing, lapsed, or older than the latest deed transfer? Does the building meet the unit threshold of the registration dataset (3+ units), so that a gap is worth reporting? | Last registration 2021, deed to a new entity recorded 2023, none since; PLUTO shows 24 units. The answer does not decide legal applicability beyond the stated threshold | I | HPD registrations; ACRIS; PLUTO | |
| 18 | Which deed transfers among a portfolio's lots look like restructuring (a `$0` re-deed into single-purpose LLCs) rather than a sale, what supports that reading independently of the grouping itself, and what remains uncertain? | One 2008 multi-lot deed, then 12 `$0` deeds in 2015 from the same grantee into 12 LLCs; versus a sale at $3.1M to a buyer for whom no relationship was established | I+II | ACRIS; BOR deed linkage | |
| 19 | Why are these two buildings grouped together, or left unlinked, in each layer? Give the supporting records, linkage stages, connecting path, exclusions and the run. | Same Owner Portfolio via a path through a third lot; the direct pair shares nothing. In the Operational Network they are unlinked because their only shared address is masked | I+II | All | |
| 20 | **Integration scenario.** Given an address, what is the traced dossier: title and registration facts, management relationship, Owner Portfolio, Operational Network, then any parent or control lead, each with a cited record, run and limits, and where does the trail stop? | `123 Example St`: five findings kept apart; two recorded, two derived layers, one parent lead; "trail ends at a registered-agent address" | I+II | All | |
| 21 | For a chosen layer (Owner Portfolio or Operational Network), which of its buildings have the most open hazardous violations per unit, and how concentrated are they? How does the answer change between the two layers? | 3 of 14 lots hold 80% of the portfolio's open class C violations; the same measure over the Operational Network gives a different list | I+II | HPD violations; PLUTO; BOR layers | |
| 22 | Where two records name entities differently (deed grantee vs HPD owner, or two registrations), what supports treating them as one entity, what argues against it, and what is left unresolved? | `Example Holdings LLC` vs `Example Holdings II LLC`: shared agent and address support a possible connection; the names alone support nothing | II | ACRIS; HPD contacts; DOS; NLR | |
| 23 | Which buildings does this managing agent disclose in HPD registrations, and how does that set relate to the building's Operational Network and Owner Portfolio? Is the agent an operator tied to the owner, or a commercial service? | Agent `Example Management Corp` is disclosed for 63 buildings; 41 are in the Operational Network, 22 are other clients. A shared agent is a management relationship, not ownership | I+II | HPD contacts; BOR layers; `resolution/` mail-drop list | |
| 24 | Starting from an entity name (LLC or other organization), or from a person named in a recorded role, which lots and buildings does it appear against, in which recorded roles, and with what name variants? | `Example Holdings LLC`: grantee on 3 deeds (2016–2021), HPD owner of 2 buildings, agent for 1; one variant spelling matched by normalization and reported as such | I | ACRIS parties, legals; HPD registrations, contacts; DOS | |
| 25 | When a recorded owner entity is absent from the NY DOS snapshot or appears to be registered elsewhere, what do the free public registries of other jurisdictions show, and what remains unresolved? | A Delaware LLC grantee: the state's free search gives the entity's name and status; the formation document is paid, so reported as an unresolved lead ("needs payment") | I+II | Web research; other states' registries | |
| 26 | For this address, which sources hold no record (HPD registration, DOS entity, either layer, any violation), and what does each absence mean in terms of the reason codes in requirement 3? | No DOS match for the owner: "no record in the active-entity snapshot". Not in the Owner Portfolio: "excluded by policy (co-op)". Not in either layer: "no qualifying linkage", with the statement that recall is unmeasured | I+II | All | |
| 27 | What complaints has HPD recorded for this building, by type, category and status, over what period, and what is the rate per residential unit? | 112 problem records in 2023-2025: 9 emergency, 3 immediate emergency, 0 hazardous; 41 still open at the snapshot; 0.19 per unit. Counts are of problems, not of distinct complaints, and say what was reported, not what was found | I | HPD complaints and problems; PLUTO | |
| 28 | What Housing Court actions has HPD brought against this building's owner, by case type and status, and was any harassment finding made? Who is named as respondent, and does the respondent match the registered owner? | Heat and Hot Water case opened 2022, closed; Tenant Action/Harassment case, finding "After Inquest"; respondents as recorded: `Example Holdings LLC` and a managing agent, exact match to the HPD registration | I | HPD litigations; HPD registrations; ACRIS | |

## Answer contracts

Four questions have full contracts now, because they test the hardest requirements: portfolio attribution (Q9), historical uncertainty (Q14), reproducible evidence (Q19), and reports and retrieved documents (Q16), where wrongful attribution is most likely. Contracts for the rest are written before the evaluation set is built in week 8. Q20 is an integration scenario, not a single question: its required components are the contracts of Q1–Q4, Q9, Q10, Q16 and Q19, plus the end-to-end acceptance requirement below.

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
| Acceptable incomplete | Title holder supported, no registration in force; or "cannot attribute", with the reason. The records are today's version of the past, and the answer says so. A title holder that is absent from the DOS dataset is reported as "no record in the active-entity snapshot", which says nothing about whether the entity existed on the date (the dataset holds active entities only) |
| Failure | The current owner substituted for the historical one; one owner asserted despite a conflict; the owner of record presented as the party responsible |
| Test cases | Ordinary: one deed, continuous registration. Difficult: deed dated before and recorded after the violation date; a lapsed registration; a sale between inspection and notice; a past title holder that has since dissolved and is missing from DOS |

This needs historical records and explicit date semantics (document date, recorded date, registration period, violation dates), not just `valid_from` / `valid_to` on a role.

### Q19: Membership explanation

| Element | Specification |
| --- | --- |
| Inputs | Two buildings (BBL); layer or layers; run |
| Required output | Per layer: same group, different groups, or one or both ungrouped (with reason code). For same group: composition, a representative edge path with the stage and records behind each edge, and full detail on request. For networks: connected in the original component or not, and whether subdivided. Benchmark precision of the stages used, as a method property |
| Acceptable incomplete | Edges not exported: membership only, with the statement that evidence is not available |
| Failure | Different owners inferred from a non-link; direct evidence claimed where there is only a path; stage precision presented as a link probability; pre-subdivision connectivity presented as network membership |
| Test cases | Ordinary: a direct identity link. Difficult: a path through a third lot; a masked hub; a Louvain-split pair connected before subdivision |

### Q16: Reports and filing documents

| Element | Specification |
| --- | --- |
| Inputs | Entity or address; sources searched; as-of date; step and time budget |
| Required output | Each item with publisher or filing body, date, URL or document id, page, the quoted claim or extracted value, extraction method, `source_category`, `review_status`, and how it relates to the recorded facts (agrees, adds, conflicts, unrelated). For each: the basis for treating it as about this entity (exact name or address, or a lead only) |
| Acceptable incomplete | Nothing found: "no reports or documents found in the sources searched", with the queries and dates, never "no news" or "no issues". A document unreadable, partial or behind payment: reported as an unresolved lead with the reason. An uncertain scanned name: reported with a low-confidence flag and not used as a link |
| Failure | A claim stated as fact; ownership inferred from a report or from a document's signatory; a person's name shown without its source and role; an entity matched on name alone without saying so; contradicting reports resolved silently; a missing report read as nothing having happened |
| Test cases | Ordinary: an article naming the exact LLC; a retrieved filing with a named manager. Difficult: an article naming a similarly named entity; two contradicting articles; a scanned attachment with an uncertain name; a paid-only registry step; a report dated after the as-of date |

## End-to-end acceptance requirement

> Starting from an address, the investigator identifies the property and its recorded entities. It follows leads that meet the stated rule through public records, filing attachments and web sources, including free public registries in other jurisdictions. It produces a dossier in which every claim cites a source, retrieval time and source category, and keeps recorded assertions apart from derived or reported leads. Unresolved leads are listed with their reasons, and the investigation ends with one of the stated stop reasons.

This is tested as the integration scenario (Q20), which is scored as a whole rather than as a single question. Q20's required components are the contracts of Q1–Q4, Q9, Q10, Q16 and Q19. The requirement adds the following, each checkable:

1. **Lead rule.** A lead is a new entity name or address that appears in a recorded or retrieved source, is not masked as an aggregator or mail-drop address, and falls within the step and time budget. Everything else found is logged but not followed.
2. **Claim-to-source.** Every claim in the dossier has a source record or URL, a retrieval time and a source category. No claim states ownership on the strength of a derived layer or a group's person anchor.
3. **Labels.** Each claim is shown as a recorded assertion (Type I), a derived lead (Type II) or a reported claim, with its review status. A "hypothesis" is a derived or reported lead, never a finding.
4. **Unresolved leads.** Each lead not followed or not resolved is listed with its reason: masked address, no further record, source needs payment or is inaccessible, budget reached, or conflicting records.
5. **Stop reason.** The investigation ends with exactly one of: reached a registered-agent, mail-drop or masked address; no further recorded link; next source needs payment or is inaccessible; budget reached; conflicting records left unresolved. The dossier states which.
6. **Other jurisdictions.** When a recorded entity is registered elsewhere (a foreign LLC), the agent searches that state's free public registry. A paid-only step is an unresolved lead with the reason "needs payment".
7. **Reproducibility.** The dossier records the run, the snapshot dates and everything retrieved, so the investigation can be replayed from the cache (Scope rule 6).

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
- The entity is not in the dataset (dissolved, or never filed in New York): reported as "no record in the active-entity snapshot", not as non-existent. The agent then looks for a retrieved filing or an ACRIS or HPD mention, each labeled by source.
- The DOS process name is the statutory default ("THE LIMITED LIABILITY COMPANY") or a commercial agent: reported as such and treated as no person and no lead.
- The CEO or location fields are empty for the LLC: reported as "not carried for this entity type", and the answer does not say the entity has no officers.

**Q7 and Q8: similarly named entities**
- `Example Holdings LLC` and `Example Holdings II LLC` share an agent and addresses: reported as a possible connection with that evidence, not as the same entity. A name match is a lead, shown with its evidence.
- Similar names with no shared record: not reported as related.
- A similarly named entity's filing names a person or address missing from the first: reported as new evidence for that entity, with its source.

**Q22: entity identity**
- Two names differ only by punctuation, case or a legal suffix (`LLC` vs `L.L.C.`): reported as a normalization match, with the rule used.
- Two names differ by a numeral or a word (`Holdings` vs `Holdings II`): not the same entity unless a record other than the name connects them; the evidence for and against is shown.
- The only shared record is a masked or mail-drop address: no support for identity.

**Q23: managing agents**
- The agent is a commercial service that manages unrelated owners' buildings: reported as a management relationship across clients, with no ownership inferred and no network built from it unless the layers independently include it.
- The agent's address is on the mail-drop list: the address links nothing.
- A managing agent shares a name with an owner entity: reported as a possible connection with the evidence, not as one party.

**Q24: starting from a name**
- The name matches several entities in different boroughs or states: all candidates are returned with what distinguishes them; none is chosen silently.
- The name is a person in an HPD or ACRIS role: returned only in that recorded role, with no search for other information about the person.
- No match: "no record under this name or the variants tried", with the variants.

**Q25: other jurisdictions**
- The free registry lists the entity but the formation documents or officers require payment: the free fields are reported, the rest is an unresolved lead ("needs payment").
- The registry has a similarly named entity but no shared record: reported as a lead about a different entity.
- The registry cannot be reached or has no free search: the step is an unresolved lead with the reason "inaccessible".

**Q26: absence**
- The building is missing from the HPD registrations: reported with the PLUTO unit count and class, without saying a registration is legally required.
- The building is in one layer but not the other: each layer states its own reason code (Q9, Q10).
- A source's snapshot predates the period asked about: reported as "outside source coverage" for that period.

**Q27: complaints**
- A building has many complaints and few violations (or the reverse): both reported, with the statement that a complaint is a report and a violation a finding. Neither is a measure of conditions.
- Counts are of problem records: one complaint can hold several problems, and duplicates are flagged in the data. The answer states the counting unit and whether duplicates were excluded.
- A request for which apartment or who complained: declined. The dataset carries apartment and an anonymous flag; neither is loaded.
- A building has no complaint records: "none recorded in the snapshot period", not "no problems".

**Q28: litigation**
- The respondent field is free text and can list several parties (entities, individuals, "ET AL"). Each is reported as recorded, and an individual is shown with that recorded role and source. The answer does not match a respondent to an owner except by exact normalized name, and says so.
- The case status field mixes a status with a date (for example `GRANTED - 10/20/2006`) and some open dates are implausible: the answer reports the value as recorded, flags the implausible date, and does not repair it.
- An HPD case is an action HPD brought against an owner. It is not an eviction case and not a finding of liability by itself: the answer says which finding the record carries (for example a harassment finding after trial or inquest).
- A case against a prior owner is reported against the owner named at the time, with no attribution to the current owner (see Q14).

**Q7: other organizations at an address**
- A business address in a filing is searched: other companies, foundations or nonprofits that list it are returned with their filings. If the address is a hub (many unrelated organizations), the answer gives the count and says whether the list is complete or a sample, and supports no link.
- An organization's tax filing lists the address "care of" a management company: reported as an affiliation recorded in that filing, not as ownership.

**Q11: affiliations**
- A mortgage lender is named on a recorded document: reported as a financing relationship, not as control or parenthood.
- A disclosed managing agent is recorded: reported as a management relationship, not as ownership.
- A shared officer links the owner to a named parent company: reported as a derived lead, separate from the Owner Portfolio, with its evidence.
- A reported claim of a parent relationship (see Q16) is present: shown as reported, not as a documented affiliation.

**Q16: reports and filing documents**
- A news article states that a fund controls the owner's parent company: shown as a reported claim, with publisher, date and quoted text, unreviewed, and kept apart from the Owner Portfolio.
- Two articles contradict each other: both are shown, contested, and neither is chosen.
- A claim names a person whose recorded role in the filings differs: both are returned, and the person is shown only in the recorded role.
- A claim from before the as-of date is superseded by later records: reported with both dates.
- An article names an LLC with a similar but not identical name: reported as a lead about a different entity, not attached to this one.
- Searches return nothing: "no reports found in the sources searched", with queries and dates; never "no news".
- A retrieved filing is partly unreadable: reported with the extraction method and a low-confidence flag, and not used as a link on its own.

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
| Who is my landlord? | 1–5, 17, 22, 24 | |
| How many properties does my landlord own, and where? | 7–10, 23 | Answered separately for ownership and for shared operation; the two lists differ by design (Q10). Q23 adds the management footprint, a third and separate list |
| Does my landlord sell frequently, or hold? | 12, 18 | Transfers are recorded facts; attributing them to the current owner is derived. Historical membership is not derivable from a current snapshot |
| What are conditions at my building? | 14, 15, 21, 27, 28 | Violations are a record of what was cited, not of conditions |
| Has there been notable news? | 16 (core), 20 | Web research. A report supports "this article states X" (recorded); whether X is true and applies is a separate, derived judgment. The guide's focus list includes this question |
| What is the financial standing? | 13 | Mortgages only; no tax-lien or distress data in the current sources |
| Who are the people behind the company? | 5, 7, 11, 16, 24 | |
| Is my building overseen by a federal or state entity? | 20 (scenario) | Program lists retrieved on demand; not loaded in the graph |
| What kind of company is my landlord, and who are its investors? | 5, 11, 16, 25 | Investors are usually not in NYC filings; expect leads only |
| Which local regulatory agencies may influence my landlord? | not covered | Out of scope for the graph |

**The guide's worked example.** Its trail is: property record → LLC → registered address → a person → a news article → a hedge fund. In NYC the first steps use open records, but each can return names and addresses without establishing the identity or relationship the next step needs. Q20 asks for the trail with recorded facts and derived links kept apart, and must state where it stops.

**NY DOS dataset (checked 2026-10-15, `n9v6-gdp6`).** Findings from the dataset's column list and counts over its 2.29M active LLCs (1.00M with a NYC county):

| Field | Populated for LLCs | Meaning |
| --- | --- | --- |
| DOS process name and address | 100% | Where the state forwards legal service; not who runs the entity |
| Registered agent name and address | 26.8% (26.3% NYC) | Present for about a quarter |
| CEO name and address | 1 row | Not carried for LLCs |
| Location name and address | 0 rows | Not carried for LLCs |

- **No officers, managers or members** are available for LLCs. People behind an LLC come from HPD contacts, ACRIS parties, or retrieved filing documents (Q5, Q7, Q11).
- **Process name is often not a person.** 92,591 LLCs show the statutory default "THE LIMITED LIABILITY COMPANY", and the most common other values are commercial agents (Northwest Registered Agent, Registered Agents Inc., Corporation Service Company, ZenBusiness). Matching on DOS process name or address meets mail-drop addresses constantly, so the mail-drop rule applies here (requirement 3, Scope rule 3).
- **Active entities only, as of a month-end snapshot.** Dissolved entities and change history are absent. An answer about a past owner entity may find no DOS record (Q5, Q14). A sample check (2026-10-15 to 16) matched LLC grantee names on ACRIS deeds against the dataset by exact normalized name. Of 356 distinct LLC grantee names from 300 random deeds in each of 2010, 2015, 2019, 2022 and 2024, 293 (82%; roughly 78–86%) matched an active LLC, and the rate did not fall with deed age (80–85% in every year with at least 70 names; 83% in 2010 on only 29). About one in five LLC grantees therefore has no DOS match. The sample says nothing about why. A non-match can mean the entity was dissolved, was never registered in New York (a foreign LLC), was renamed, or is spelled differently from its DOS name. It covers all NYC deeds, not only HPD-registered rental buildings, so the rate for this project's owners is unmeasured. Scripts: scratchpad `acris_dos_check.py` and `acris_dos_check_b.py`.
- **Retrieval date:** `retrieved_at` for `nys_corporations` in `sources.yaml` is still null; the counts above came from the live API, not from a downloaded copy.

**Coverage.**

- Reliability counts: 12 recorded (Q1, 2, 3, 4, 5, 13, 14, 15, 17, 24, 27, 28), 6 derived (Q6–10, 22), 10 mixed (Q11, 12, 16, 18, 19, 20, 21, 23, 25, 26). Q20 is the integration scenario.
- Q6, Q10, Q19 and Q22 test the project's distinctive contribution: explaining why a link was made, why it was refused, and why the two layers disagree.
- Q23 and Q24 test the other entry points: starting from a managing agent or from a name, not an address.
- Q25 and Q26 test the limits: other jurisdictions, and what each absence means.
- Q14 is the temporal test and Q12 the attribution test; neither can rely on a current-owner property.
- Q3 and Q17 test whether ACRIS and HPD are modelled separately (title holder versus registered owner).
- Q1 and Q9 test that lots, buildings and units are never silently equated.

## Changes from draft 4

- **Dropped the fixed count.** The set grows or splits where coverage requires it; it is now 28 (Q20 is the integration scenario, labeled as such).
- **Split** Q3 (exact name agreement stays in Q3, recorded; the same-entity judgment becomes Q22, derived) and Q15 (building violations stay in Q15, recorded; the layer concentration becomes Q21, mixed).
- **Added** Q23 (managing agent footprint), Q24 (start from a name), Q25 (other jurisdictions), Q26 (what each absence means), with scenarios for Q22–Q26.
- **Reframed** Q17: it reports missing or lapsed registrations against the dataset's 3+ unit threshold and does not decide legal applicability.
- **Added** Q27 (HPD complaints) and Q28 (HPD litigation) with scenarios, and two sources in `data/sources.yaml` (`hpd_complaints` `ygpa-z7cr`, `hpd_litigations` `59kj-x8nc`). Complaints are filed per apartment, so only building-level counts are used (Scope, out of scope).
- **Decided** open items 3, 5, 6 and 8 (see Open items). Scope rule 4 now carries the bounded exceptions for people in news and professional pages.
- **Corrected** the reliability counts. Q11 is mixed, as the table says.
- **Added** `docs/competency-questions-detail.md`: per-question example (neutral Sunset Park buildings, checked against Socrata on 2026-10-17), answer shape, audience and caveat. Examples that need the BOR export, web research or a better-fitting building are marked pending. `bor_layers`, `mail_drop_list` and `web_research` were added to `data/sources.yaml` as non-dataset sources.
- **Recorded** that BOR will export edge-level evidence, which resolves open item 1 on the producer side.

## Changes from draft 3

- **Added** a Scope section: graph answers, web research and document retrieval are in scope, with the default handling rules and process requirements for the agent's loop.
- **Added** the "Additional scenarios" section (Q1, Q5, Q7, Q8, Q11, Q12, Q20), one per step of the guide's method the questions did not exercise.
- **Extended** Q1 to ask for building characteristics (year built, class, units, assessed value).
- **Promoted** news and additional-document research to core: new Q16 (reports and filing documents) with a full contract. Q15 and old Q16 are merged into a single Q15 (building and layer), so numbers stay stable. Q11's reported-claim scenarios moved to Q16, and Q11 now has affiliation scenarios.
- **Added** the end-to-end acceptance requirement (lead rule, claim-to-source, labels, unresolved leads, stop reasons, other jurisdictions, reproducibility). It widens scope to free public registries of other states, bounded by Scope rule 5.
- **Updated** the guide mapping: news and oversight are covered by scenarios; regulators remain out of scope.
- **Recorded** the NY DOS dataset check (fields, fill rates, active-only), rewrote Q5 to match, and added the absent-entity caveat to Q14's contract and to Q5's scenarios.

## Changes from draft 2

- **Corrected** requirement 3: the Owner Portfolio eligibility rule counts member registration identities, not buildings (checked in BOR's `owner_portfolios.py`, formerly `owner_groups.py`: `min_size` applies to node ids). Requirement 4 now separates component connectivity from community membership.
- **Replaced** Q10's example, which described the unmasked Who Owns What baseline as BOR's network. It now has two BOR-layer cases and labels the baseline.
- **Rewrote** Q12 (transfers of the lot versus attribution to the current owner) and Q14 (supported title holders and registrants, with gaps).
- **Rewrote** Q11 (distinct relationship types, documented versus hypothesized), Q18 (independent support; the buyer is "no relationship established") and Q3 (exact agreement is recorded; same-entity is derived).
- **Redefined** Type I and II as recorded assertion versus derived conclusion. Softened the news and worked-example notes accordingly.
- **Narrowed** requirement 7 (people) and requirement 4 (paths).
- **Added** answer contracts for Q9, Q14 and Q19, and corrected the reliability counts.

## Open items

1. **Evidence export.** Producer side resolved: BOR will export edge-level evidence (stage, records, path). Still open: the file format and how it is loaded (design note to follow, week 5).
2. **Reliability convention.** Resolved by design notes 0002 and 0003 (2026-10-17): pipeline and agent write only `unreviewed` or `contested`, a person sets the rest through a review record, and the review store is deferred past week 8 without blocking any earlier work.
3. **People in agent output.** Resolved 2026-10-17, amended by design note 0009 (2026-10-24): a name is shown with its source, role and reliability; a person named in news is a reported claim (attributed, unreviewed, never a role). `docs/demo-slice.md`, "Publishing responsibly", updated to match.
4. **Contracts for the other 24 questions**, and for Q15 (snapshot date and denominator), Q17 (registration applicability and ingestion completeness) and Q5 in particular. DOS field availability is closed (see Notes); Q5's contract can now be written. About 18% of sampled LLC grantees had no active DOS match, so the absent-entity cases in Q5, Q14 and Q26 are common. Still open: why they are absent, and the rate for HPD-registered rental owners.
5. **Web and document findings: storage.** Resolved 2026-10-17: session evidence only; any promotion process is deferred until after week 8.
6. **LinkedIn and similar pages.** Resolved 2026-10-17: a page that only states an employer or title is `web_content` for that business role; no following to personal information.
7. **Retrieval tooling and cache design** for the agent (week 6), and how evaluation fixtures are frozen (week 8).
8. **DOB permits.** Resolved 2026-10-17: retrieved on demand only, not loaded.
9. **Regulators** (the guide's last question) remain out of scope.
10. **Complaint and case types.** Resolved 2026-10-17: included. HPD complaints and Housing Litigation are added as sources, with Q27 and Q28. The vocabulary covers violation classes, complaint types and categories, and litigation case types. Data findings: complaints are about 16.4M problem rows (type EMERGENCY, NON EMERGENCY, IMMEDIATE EMERGENCY, HAZARDOUS, REFERRAL); litigation is about 241.6K cases with 14 case types; its `casestatus` mixes a status and a date, `caseopendate` has implausible values (years 0204 and 2030), and `respondent` is a free-text list of names. Also checked: complaint `problem_status` is OPEN (35,317) or CLOSE (16.35M); the top `major_category` values are HEAT/HOT WATER, HEATING, PLUMBING, PAINT/PLASTER, GENERAL; violation classes are A, B, C and I (11.3M rows, so the vocabulary needs class I as well as A/B/C).

    **Value lists from the JustFix/WoW Postgres mirror (checked 2026-10-17).** Used for profiling only; Socrata stays the source of record. The mirror is partial and stale, so its counts must not be quoted:

    | Table | Mirror rows | Socrata rows | Latest date in mirror |
    | --- | --- | --- | --- |
    | `hpd_violations` | 1.97M | about 11.3M | inspection 2026-07-02 |
    | `hpd_complaint_problems` | 6.0M | about 16.4M | status 2023-12-01 |
    | `hpd_complaints` | 3.34M | n/a | received 2023-11-30 |
    | `hpd_litigations` | 239K | 241.6K | open date has the same bad values (0204, 2030) |

    - **Violations:** class A, B, C, I (plus 5 rows with a null class); `violationstatus` Open or Close; `novtype` Original, Reissued or null. Column `rentimpairing` exists. The mirror has no 9999 date problem in `inspectiondate`, but `currentstatusdate` reaches 9999-12-11, so sentinel dates exist.
    - **Complaint problem type:** EMERGENCY, NON EMERGENCY, IMMEDIATE EMERGENCY, HAZARDOUS. Socrata also has REFERRAL (4 rows).
    - **Major categories (16):** HEAT/HOT WATER, UNSANITARY CONDITION, PAINT/PLASTER, PLUMBING, DOOR/WINDOW, WATER LEAK, ELECTRIC, GENERAL, FLOORING/STAIRS, APPLIANCE, SAFETY, OUTSIDE BUILDING, ELEVATOR, HEATING, NONCONST, CONSTRUCTION. Each has 1 to 17 minor categories. HEATING and NONCONST look like legacy values (the mirror holds 3.7K and 570 rows; Socrata holds 2.5M and 775K).
    - **Complaint and problem status:** OPEN or CLOSE, plus a free-text `statusdescription` that carries the outcome (violations issued, no violations issued, no access, tenant confirmed correction, still open). The outcome is the useful vocabulary and is not a coded field.
    - **Litigation case types (14):** Tenant Action, Heat and Hot Water, Tenant Action/Harrassment (sic), Access Warrant - Non-Lead, Access Warrant - lead, Comprehensive, False Certification Non-Lead, Lead False Certification, CONH, Comp Supplemental Cases, Heat Supplemental Cases, 7A, Failure to Register Only, HLD - Other Case Type.
    - **Litigation status:** after stripping a trailing date, the stems are CLOSED, PENDING, APPLICATION PENDING, GRANTED, DENIED, Exempt, WithDrawn/Abandoned, Rejected, Rescinded, Settlement With Cure. The date-bearing ones (GRANTED, Exempt, DENIED, Rejected, WithDrawn, Rescinded) occur only on the CONH case type (all 12 non-CLOSED, non-PENDING stems, about 2.7K rows); a few have a dangling hyphen with no date. Every other case type uses CLOSED or PENDING.
    - **Harassment finding:** null (231K), No Harassment, After Inquest, After Trial. A finding appears on about 8.2K rows of the "Tenant Action/Harrassment" case type and on 2 of "Tenant Action".
    - **Column name differences:** the mirror calls Socrata's `casejudgement` `openjudgement`, and `boroid`/`boro` differ; load from Socrata, not by copying the mirror.

    Still open: whether the vocabulary maps these to controlled status lists or keeps the recorded value, and re-checking the Socrata-only values (REFERRAL, class I counts) when the data is downloaded.
