# Competency questions: detail

One block per question in `docs/competency-questions.md`: a real example, the shape of the answer, who asks it and why, and the caveat the agent must give. Wording, reliability and the scenarios stay in the main file. Sources use the keys in `data/sources.yaml`.

**Status:** draft 5, awaiting ratification, like the main file.

## How the examples were chosen

- **Neutral buildings.** Ordinary rental buildings in one Brooklyn neighborhood (Sunset Park), picked by querying the data. They are not landlords from the news, and this file does not repeat individuals' names, to keep the examples neutral. Where a record names a person, the block says "a person (name not repeated)". The agent shows names with their role and source (design note 0009).
- **Where the expected answers come from.** Discovered in the JustFix/WoW Postgres mirror, then checked against the Socrata source. **Where they differ, Socrata wins.** The mirror is partial and stale (competency questions, open item 10): for 438 52 Street it shows 4 open violations, Socrata shows 20.
- **Snapshot date.** Socrata values were read on **2026-10-17**. They are the starting point for the week 8 evaluation answers and must be re-read before they are used as expected answers, because open counts and registration dates move.
- **Verified here:** PLUTO and HPD registration fields for every BBL below, the ACRIS documents named, and the DOS lookups. Items marked **pending** have no example yet and the reason is given.

### Anchor properties

| Short name | Address | BBL | What it is |
| --- | --- | --- | --- |
| **A** | 5413 7 Avenue, Brooklyn | `3008260002` | Class C1, 32 residential units, 1 building (BIN `3014788`), built 1911. HPD registration `316103`, owner `5413 PLAZA LLC`, last registered 2025-09-30, period ends 2026-09-01 |
| **B** | 702 54 Street, Brooklyn | `3008260005` | Class C7, 39 units, BIN `3014789`. HPD registration `300258`, owner `702 Plaza LLC`, last registered 2025-10-24 |
| **C** | 438 52 Street, Brooklyn | `3008070024` | Class C1, 32 units, BIN `3013901`, built 1931. A co-op: PLUTO owner `438 52ND ST OWNERS CORP`. HPD registration `350423` |
| **D** | 218, 220 and 224 54 Street, Brooklyn | `3008210012` | One lot, 3 buildings, 18 units, each registered separately with HPD: 218 (BIN `3324448`, registration `302437`), 220 (BIN `3324450`, `344220`), 224 (BIN `3324451`, `331116`). Owner is a housing development fund company |
| **E** | 234 54 Street, Brooklyn | `3008210019` | 6 units. Last registered 2020-08-31, period ended 2021-09-01, but a deed was recorded 2026-04-21 |
| **F** | 259 22 Street, Brooklyn | `3008970014` | 40 units, built 2025, class D7. No HPD registration found |
| **G** | 548 52 Street, Brooklyn | `3008080025` | Class C1, 23 units. HPD owner spelled `KS Turnpike LLC`, deed and DOS spell it `K S TURNPIKE LLC` |

A and B are linked by records: the same business address in HPD (a street address in Brooklyn, 11220), a joint mortgage, and DOS filings one day apart. That is the trail used for Q7, Q11 and Q20. The records do not say the two are owned together, and the examples do not assert it.

## Questions

### Q1: Address to lot and building
- **Example:** 224 54 Street resolves to `3008210012`, one lot with three BINs (D): 218 54 Street (`3324448`), 220 54 Street (`3324450`) and 224 54 Street (`3324451`). A tenant at any of the three resolves to the same lot, and the answer lists all three buildings, not only the one typed. 5413 7 Avenue resolves to `3008260002` with one BIN (A): class C1, 32 units, built 1911. Assessed value is read at test time.
- **Shape:** entity with attributes (lot, buildings), plus a match statement.
- **Audience:** every organizer starts from an address, and a lot with several buildings changes the unit count they should expect.
- **Caveat:** say when the address matched exactly or by variant, and report lots, buildings and units as separate counts.
- **Sources:** `pluto`, `hpd_registrations`.
- **Pending:** a corner or alternate-address case for the "address not found" scenario.

### Q2: HPD-registered owner
- **Example (A):** registered owner `5413 PLAZA LLC`, registration `316103`, last registered 2025-09-30, period ends 2026-09-01. The period had not ended at the snapshot date (2026-05-29).
- **Shape:** entity with dates.
- **Audience:** the registration is the legal owner of record for repairs and notices, and organizers address letters to it.
- **Caveat:** an HPD registrant is who registered, not proof of title. State the registration period and the snapshot date.
- **Sources:** `hpd_registrations`, `hpd_contacts`.

### Q3: Deed grantee against HPD owner
- **Example (A):** the most recent deed is recorded 2025-04-02 for $0 (`2025032100031001`), with the same name as grantor and grantee, `5413 PLAZA LLC`, equal to the HPD owner. The last deed for value is 2021-02-26 for $5,000,000 (`2021022201130003`) from `5413 7TH AVENUE LLC` to `5413 PLAZA LLC`.
- **Example, a difference (G):** the 2018 deed names `AADVA REALTY LLC / K S TURNPIKE LLC` as grantees; HPD names `KS Turnpike LLC`.
- **Shape:** entity pair plus two separate fields. *Name agreement:* exact normalized, normalization match (with the rule id), or different. *Address agreement:* same, differs, or absent, with the unit reported apart from the match (design note 0006).
- **Audience:** a mismatch is the first sign that the person holding the deed and the person registered with HPD may differ.
- **Caveat:** exact agreement is a recorded comparison of strings. The answer does not say "same party" on name agreement alone, and address agreement at a mail-drop address is flagged as non-evidence. A near match is not a finding; see Q22.
- **Sources:** `acris_master`, `acris_parties`, `acris_legals`, `hpd_registrations`.

### Q4: Managing agent, head officer, site manager
- **Example (A):** HPD lists five contacts for registration `316103`: the corporate owner, an agent, a head officer (title PRESIDENT), a shareholder and a site manager. The agent, officer, shareholder and site manager are people (names not repeated). All but the site manager share one business address.
- **Example (C):** the agent is the owners corporation itself, and the head officer's title is "PRESIDENT OF CO".
- **Shape:** list of roles.
- **Audience:** the agent and site manager are who a tenant can actually reach.
- **Caveat:** show a person only in the HPD role recorded. A managing agent is a management relationship, not ownership.
- **Sources:** `hpd_contacts`, `hpd_registrations`.

### Q5: NY DOS record for the owner entity
- **Example (A):** `5413 PLAZA LLC`, DOS id `5857246`, domestic LLC, filed 2020-10-14. The DOS process name is the entity's own name and no registered agent is listed.
- **Example, statutory default:** `606 56TH ST LLC` (5601 6 Avenue), filed 2023-01-06, process name `THE COMPANY`.
- **Example, a person as process name:** `K S TURNPIKE LLC` (G), filed 2007-10-01. The process name is a person (name not repeated); it is where the state forwards service and does not say who runs the entity.
- **Example, absent:** `HP SUNSET PARK I HDFC INC` (D) has no match under the HPD spelling or the deed spelling. **Example, spelling:** C's DOS name is `438 52ND ST. OWNERS' CORP.`, which equals the deed and PLUTO spelling `438 52ND ST OWNERS CORP` under N1 but not the HPD spelling `438 52 ST OWNERS CORP`.
- **Shape:** entity with attributes, or "no record".
- **Audience:** shows whether the owner is a single-purpose shell and where legal papers go.
- **Caveat:** "no record in the active-entity snapshot" is not "does not exist". No officers or members are carried for LLCs.
- **Sources:** `nys_corporations`, plus `web_research` for filings.

### Q6: Aggregator or mail-drop address
- **Example:** **pending.** The business address shared by A and B is a candidate; whether it is masked by BOR or on the mail-drop list is checked in week 5.
- **Shape:** yes/no per method, with reasons.
- **Audience:** tells an organizer that a shared address is a service address, so it is not a lead.
- **Caveat:** masking is a method's decision. Name the method and run.
- **Sources:** `bor_layers`, `mail_drop_list`, `hpd_contacts`.

### Q7: Shared evidence between two entities or buildings
- **Example (A and B):** the same HPD business address, one joint mortgage naming both entities as borrowers (`2021031601183001`), DOS filings on 2020-10-14 and 2020-10-15, and similar names. Whether the address is a hub is not yet checked.
- **Shape:** list of evidence items, each marked used or set aside.
- **Audience:** the question behind "is it the same landlord?"
- **Caveat:** a name match is a lead, shown with its evidence. A masked or mail-drop address is set aside and said so.
- **Sources:** `hpd_contacts`, `nys_corporations`, `acris_parties`, `bor_layers`.

### Q8: Operational Network of a building
- **Example (BOR run 2026-05-29-149e871f, release v0.2.1):** C is in a 5-lot network (a whole connected component) and D in a 35-lot network, both linked by accepted edges. A and B, the candidate pair, are in no network: the method found no accepted link for either lot (`no_linkage`), so the answer says so and gives no list.
- **Shape:** list of buildings with the connecting links.
- **Audience:** shows how many buildings share the same operation.
- **Caveat:** name the run, say whether it is a whole component or a Louvain community, and that it is a lead and not legal ownership.
- **Sources:** `bor_layers`, `hpd_registrations`, `hpd_contacts`.

### Q9: Owner Portfolio footprint
- **Example (BOR run 2026-05-29-149e871f):** D, a lot with three buildings, is in a 33-lot Owner Portfolio (the Operational Network has 35). C is in a 5-lot portfolio with 116 residential units; the earlier expectation that BOR would exclude it as a co-op does not hold in this release, so the answer reports the group as it is and does not call it a co-op.
- **Shape:** counts (lots, buildings, units) with a comparison list.
- **Audience:** the number tenants ask for first: how many buildings does this owner have.
- **Caveat:** see the contract in the main file; never present it as legal ownership.
- **Sources:** `bor_layers`, `acris_master`, `pluto`.

### Q10: Where the layers disagree
- **Example (BOR run 2026-05-29-149e871f):** D: the network holds two lots the portfolio does not, linked in the network only by a shared business address. Release-wide, 476 networks hold more than one portfolio and 14 portfolios span more than one network.
- **Shape:** two lists and a difference with explanations.
- **Audience:** explains why two honest lists of "the landlord's buildings" differ.
- **Caveat:** both layers are derived; neither is the true list.
- **Sources:** `bor_layers`, `acris_master`, `hpd_registrations`.

### Q11: Affiliations
- **Example (A and B):** a $8,750,000 mortgage recorded 2021-03-22 (`2021031601183001`) to ConnectOne Bank, with `5413 PLAZA LLC` and `702 PLAZA LLC` both named as borrowers. That is a financing relationship with a lender and a shared borrower record. It does not show common control.
- **Example (C):** a $1,546,326.61 mortgage recorded 2015-04-08 (`2015032301122001`) to Ridgewood Savings Bank.
- **Shape:** list of relationships, each with its type.
- **Audience:** the guide's "who are the people and companies behind my landlord".
- **Caveat:** lender, agent and shared-borrower records are different relationship types. Only a documented parent relationship may be called one.
- **Sources:** `acris_parties`, `hpd_contacts`, `nys_corporations`.

### Q12: Transfers of a lot
- **Example (A):** two deeds since 2015: 2021-02-26, $5,000,000 sale; and 2025-04-02, $0, with the same name as grantor and grantee. The answer counts 2 deeds, one of them not a sale.
- **Shape:** timeline.
- **Audience:** answers "does my landlord sell frequently, or hold?"
- **Caveat:** count deeds, not lots. A $0 deed is not a sale. Attributing a transfer to the current owner is derived.
- **Sources:** `acris_master`, `acris_parties`, `acris_legals`.

### Q13: Mortgages, assignments, satisfactions
- **Checked on Socrata, 2026-10-17** (`acris_legals` by borough, block, lot, then `acris_master`).
- **Example (C):** mortgages recorded 1996-10-31 ($500,000), 1999-09-24 ($100,000), 2002-11-20 ($580,390.07), 2005-06-22 ($840,180.05) and 2015-04-08 ($1,546,326.61). Satisfactions of mortgage (`SAT`): 1982-12-21 and 2001-08-23 only. A sundry agreement (`SAGE`) was recorded 2002-04-01. So **no satisfaction is recorded for the 2002, 2005 or 2015 mortgages**, and none after 2001. The 2005 and 2015 mortgages each come with an agreement (`AGMT`, $2,000,000 and $3,200,000) and an assignment of leases and rents (`AL&R`) recorded the same day, so the later loans may consolidate earlier ones. The answer reports the documents and does not say which loan is outstanding.
- **Example (A):** a $8,750,000 mortgage and an `AL&R` recorded 2021-03-22 (document date 2021-02-16). On 2023-06-15 a `TL&R` (termination of assignment of leases and rents, $0) was recorded, and on 2023-06-16 a `SAGE` (sundry agreement, $0). **No satisfaction (`SAT`) follows the 2021 mortgage.** A termination of the assignment suggests the loan ended, but the records do not say so, and that reading is derived (Type II), not recorded.
- **Shape:** list.
- **Audience:** the lender is the second party with leverage over repairs.
- **Caveat:** no satisfaction recorded is not proof the loan is still outstanding, and a termination is not proof it was paid. Report document types with their ACRIS descriptions.
- **Sources:** `acris_master`, `acris_parties`, `acris_legals`.

### Q14: Title holder and registered owner on a violation date
- **Example:** **pending.** No violation fell between the deed date and the recording date for the lots sampled in the neighborhood. Search wider, or accept a looser case (a deed recorded after the violation).
- **Shape:** timeline with a conflict statement.
- **Audience:** shows who was responsible when a violation was issued.
- **Caveat:** see the contract in the main file.
- **Sources:** `hpd_violations`, `acris_master`, `acris_parties`, `hpd_registrations`.

### Q15: Open violations of a building
- **Example (C), snapshot 2026-10-17:** 20 open violations: class A 4, class B 11, class C 5. The oldest open inspection date is 2023-01-20. Class I: 3, all closed. With 32 units: 0.63 open per unit.
- **Shape:** counts by class, plus an age and a rate.
- **Audience:** the main evidence of conditions an organizer can show a landlord or the city.
- **Caveat:** a violation is what an inspector cited. Open means open at the snapshot date; the rate uses PLUTO residential units.
- **Sources:** `hpd_violations`, `pluto`.

### Q16: Reports and filing documents
- **Example:** **pending web research.** Neutral buildings may have no coverage, which is itself a test ("no reports found in the sources searched").
- **Shape:** list of items with a relation to the recorded facts.
- **Audience:** news and filings answer "has there been notable news about my landlord".
- **Caveat:** a report is a claim that was published, not a fact.
- **Sources:** `web_research`.

### Q17: Missing, lapsed or stale registration
- **Example (E):** 6 units. Last registered 2020-08-31, period ended 2021-09-01, a deed recorded 2026-04-21. It is lapsed and older than the latest deed. The owner `234 54TH ST LLC` was filed with DOS on 2026-01-09.
- **Example, missing (F):** 40 units, built 2025, no registration in the dataset. New construction can be unregistered for a legitimate reason, and the answer must say it does not know.
- **Example (A):** the registration period ended 2026-09-01 and no later registration was in the snapshot.
- **Shape:** yes/no per condition, with dates.
- **Audience:** an unregistered or lapsed owner has no contact on file for tenants.
- **Caveat:** report the unit count and the dataset's 3+ unit threshold. Do not rule on legal applicability, and state the snapshot date.
- **Sources:** `hpd_registrations`, `acris_master`, `pluto`.

### Q18: Restructuring deeds
- **Example (B):** two deeds recorded 2021-02-26, a $0 deed to `702 54 STREET LLC` (dated 2021-02-05) and a $6,800,000 deed to `702 PLAZA LLC` (dated 2021-02-16). Whether this is a restructuring is not known from the names.
- **Shape:** list of deeds with a classification and open questions.
- **Audience:** repeated $0 deeds can show a landlord moving buildings into new LLCs.
- **Caveat:** $0 is a hint, not a finding. A buyer with no established relationship is "no relationship established".
- **Sources:** `acris_master`, `acris_parties`, `bor_layers`.

### Q19: Why two buildings are grouped
- **Example (BOR run 2026-05-29-149e871f):** C and the lot at 1704 East 15 Street (3067970008) are in one portfolio and one network, joined through one resolved identity cluster (an identity match of two HPD owner contacts). A and B are in no group in either layer (`no_linkage`), so there is no path and no finding about their owners.
- **Shape:** chain.
- **Audience:** lets an organizer check a claim before repeating it.
- **Caveat:** see the contract in the main file.
- **Sources:** `bor_layers`, plus the supporting records.

### Q20: The dossier (integration scenario)
- **Example:** the trail from 5413 7 Avenue (A): HPD registration, owner `5413 PLAZA LLC`, the 2021 deed, DOS record (the process name is the entity itself and there is no registered agent), the joint mortgage with `702 PLAZA LLC`, and the shared HPD business address. The expected stop is: "recorded trail ends at the entity's own process address; the shared HPD business address needs the mail-drop check". Layers to be added after the BOR export.
- **Shape:** chain.
- **Audience:** the whole of the PESP guide's method, as one document.
- **Caveat:** the acceptance requirement in the main file.
- **Sources:** all.

### Q21: Violations across a layer
- **Example (BOR run 2026-05-29-149e871f, violations as of 2026-07-02):** D's network has 18 open class A, B and C violations over 35 lots; the three lots with the most hold 72% of them.
- **Shape:** ranked list with a concentration figure.
- **Audience:** shows which of a landlord's buildings are the worst, for a coordinated campaign.
- **Caveat:** report each class separately and no word "hazardous"; the list changes with the layer used.
- **Sources:** `hpd_violations`, `pluto`, `bor_layers`.

### Q22: Same entity or not
- **Example (G):** HPD spells it `KS Turnpike LLC`; PLUTO, the 2018 deed and DOS spell it `K S TURNPIKE LLC` (DOS id `3574572`, filed 2007-10-01). They differ by a space only; the rule used is stated.
- **Example (B):** `702 54 STREET LLC` and `702 PLAZA LLC` share a lot but no record joins them.
- **Shape:** judgment with evidence for and against.
- **Audience:** keeps an organizer from merging two companies, or splitting one, on spelling alone.
- **Caveat:** a normalization match is derived. A name match is a lead, not a link.
- **Sources:** `acris_parties`, `hpd_contacts`, `nys_corporations`.

### Q23: A managing agent's footprint
- **Example:** **pending.** The agents in A and B are people; an example needs a corporate managing agent. Pick one in week 5 from the HPD contacts.
- **Shape:** list and a comparison.
- **Audience:** a management company is who tenants often deal with.
- **Caveat:** a shared agent is not ownership; a commercial agent links nothing.
- **Sources:** `hpd_contacts`, `bor_layers`, `mail_drop_list`.

### Q24: Start from a name
- **Example:** `5413 PLAZA LLC`: grantee on the 2021 deed, grantor and grantee on the 2025 deed, borrower on the 2021 mortgage, HPD corporate owner of `3008260002`, and a domestic LLC in DOS. These are the records found for the lots examined; the answer must not claim completeness without a full search.
- **Shape:** list of roles by lot.
- **Audience:** an organizer often has a company name from a letter or a lease.
- **Caveat:** return a person only in the recorded role; variants are listed as variants.
- **Sources:** `acris_parties`, `acris_legals`, `hpd_registrations`, `hpd_contacts`, `nys_corporations`.

### Q25: Other jurisdictions
- **Example:** **pending web research.** None of the owners sampled in the neighborhood was registered out of state. Choose one in week 6 with a free registry.
- **Shape:** record or "unresolved lead".
- **Audience:** many owners hold buildings through entities formed elsewhere.
- **Caveat:** a paid step is an unresolved lead.
- **Sources:** `web_research`.

### Q26: What each absence means
- **Example (D):** no DOS record under either spelling of the owner `HP SUNSET PARK I HDFC INC`. **(F):** no HPD registration for a 40-unit building from 2025, so it is in neither layer (`no_registration`, outside source coverage). **(C):** in both layers: the expectation of "excluded by policy (co-op)" did not hold in BOR run 2026-05-29-149e871f.
- **Shape:** list of absences, each with a reason code.
- **Audience:** stops "not found" being read as "nothing there".
- **Caveat:** absence of a link is not evidence of different owners.
- **Sources:** all.

### Q27: Complaints at a building
- **Example (C), snapshot 2026-10-17:** since 2022-01-01, 45 problem records in 30 complaints: 23 EMERGENCY, 2 IMMEDIATE EMERGENCY, 20 NON EMERGENCY, all closed. The latest was received 2026-04-20. About 1.4 problems per unit.
- **Shape:** counts by type, category and status, plus a rate.
- **Audience:** complaints are what tenants actually report, and a pattern can support a repair demand.
- **Caveat:** a complaint is a report, not a finding. Say whether problems or complaints were counted, and that no apartment or complainant detail is returned.
- **Sources:** `hpd_complaints`, `pluto`.

### Q28: Housing Court actions by HPD
- **Example (C):** one HPD case, a Tenant Action opened 2023-05-15, status CLOSED, no harassment finding. The respondents are the owners corporation and an individual (name not repeated), shown with the recorded respondent role and source.
- **Shape:** list of cases.
- **Audience:** shows whether the city has already sued the owner, which organizers can cite.
- **Caveat:** an HPD action is not an eviction and not a finding of liability. Match a respondent to the registered owner only by exact normalized name.
- **Sources:** `hpd_litigations`, `hpd_registrations`.

## Pending summary

| Needs | Questions |
| --- | --- |
| BOR/NLR export (week 5) | Q6, Q7, Q23 (the layers are loaded: Q8 to Q10, Q19, Q21 and Q26 are answered, design note 0024) |
| Web research (week 6) | Q16, Q25 |
| A better-fitting building | Q14 |
| An alternate-address case | Q1 (scenario) |
