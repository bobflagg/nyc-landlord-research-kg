# 0004: Vocabulary conventions, role and entity-kind schemes, and a `project_derived` source category

Date: 2026-10-18

Status: **accepted 2026-10-18.** Amends note 0002 (a fourth `source_category` value). `docs/competency-questions.md` and `data/sources.yaml` updated to match.

## Decision

1. **Roles (D1).** Role concepts are normalized, not a copy of HPD's types. Each source's own code is kept on the concept (as `skos:notation` or an alignment link), so HPD, ACRIS and DOS roles share one scheme. Groupings name what the record says (registered owner, officer, management) and never imply ownership or control. HPD `Agent` is the building's **managing agent**: HPD labels that contact "Managing Agent", and it is the only agent type in the data. The Turtle is written in Slice 1.
2. **Entity kind (D2).** HPD `contactdescription` becomes its own `EntityKind` scheme, not part of the role scheme. It is a property of the registration's owner, not of the person on the contact row (see Context). Read it as "owner type as declared to HPD", not as legal form: DOS is the better source for that (Q5). Normalization: `GEN.PART` maps to a "partnership or LLC" concept; the `TRUST`, `Trust` and `trust` spellings merge; `CO-OP` and `CONDO` stay distinct, since the co-op and condo exclusions depend on them. Free-text values map to no concept and the recorded value is kept. The Turtle is written in Slice 1.
3. **`project_derived` (D3).** `source_category` gains a fourth value, `project_derived`: supplied by this project's pipelines or curation (the BOR/NLR layers as loaded from their release, and the curated mail-drop list). The records behind a derived link keep their own category.
4. **Reliability scheme shape (D4).** Two unordered concepts, I and II, with no hierarchy. "I+II" is an answer-level label, not a fact-level concept. Each concept's `skos:notation` is the exact string stored in the graph (`I`, `II`, `public_record`, `unreviewed`, …); facts store the notation, not the concept URI.
5. **Coverage (D5).** Concepts exist only for coded values that a competency question uses. The recorded raw value is always kept, and an unmapped value is an explicit outcome, not an error. Litigation status gets concepts for its stems, with the original string retained and dates not repaired (Q28). ACRIS document types: the deed variants (`DEED, TS`, `DEED, LE`, `DEEDO`, `DEED COR`) become narrower concepts under a deed family, so Q3, Q12 and Q18 can choose what counts as a deed. The vocabulary carries no "counts as a transfer" flags: that rule lives in the agent's tools and the SHACL shapes, so it can change without changing a concept's meaning. `DEED COR` is its own narrower concept so the tools can exclude it by name. The code list is registered in `data/sources.yaml` as `acris_document_codes`. Their official meanings are confirmed (see Context): `DEED COR` is an index correction and is never counted as a transfer, `DEED, TS` is a timeshare deed, and `DEEDO` is a catch-all that counts as a transfer only after the document is looked at.
6. **Namespace and alignment (D6).** Local namespace `https://bobflagg.github.io/Watchline/vocab/`, one path segment per scheme (`.../reliability/I`). External terms (W3C ORG, PROV-O) are linked with `skos:closeMatch` where close, never adopted in place of local concepts. `Watchline` is the overarching project group; this repo is one project under it.

## Context

- Q2, Q4, Q11, Q22–Q24 need roles from three sources whose codes differ; Q5 and the co-op/condo exclusions need the owner kind.
- Profile of the justfixwow mirror (2026-10-18). HPD contact types: SiteManager 162K, Agent 155K, HeadOfficer 128K, CorporateOwner 122K, Officer 73K, IndividualOwner 48K, JointOwner 45K, Shareholder 41K, Lessee 9K. `contactdescription` carries 300–500 distinct values per type, mostly free-text tail.
- **`contactdescription` is a registration-level owner attribute** (reported 2026-10-18 by the project owner from a profile of the mirror): one value in 182,137 of 182,141 registrations, repeated on every contact row. That is why GEN.PART appears in almost equal counts under owners, agents, head officers and site managers. Of 67,461 corporate owners coded GEN.PART, 88.7% have names ending in LLC, 8.6% look like partnerships and 1.5% like corporations. So GEN.PART abbreviates "general partnership" but in practice means "partnership or LLC", mostly LLC. **This is an inference from names; no HPD codebook confirms it.**
- Note 0002 defines `source_category` as "what kind of source supplied the assertion". The BOR/NLR layers and the mail-drop list (`data/sources.yaml`) are Type II and fit none of its three values.
- ACRIS party types are 1, 2 and 3, with meanings that depend on the document type. For the deed family this is confirmed against ACRIS Document Control Codes (Socrata `7isb-wh4c`, checked 2026-10-18): party 1 is grantor (`GRANTOR/SELLER` on most codes, plain `GRANTOR` on `DEED COR` and `DEEDO`), party 2 is grantee, and party 3 on `DEED, LE` is "life estate retained". Other document types (mortgage, satisfaction, assignment) are not yet confirmed.
- **Deed family, official descriptions and mirror counts** (all class "Deeds and other conveyances"; counts from `real_property_master`, share recorded at $0 in brackets): `DEED` 3,635,052 [74%]; `DEED, TS` timeshare deed 97,274 [27%]; `DEED, LE` life estate deed 32,597 [95%]; `DEEDO` deed, other 30,097 [36%]; `DEED COR` "correct index/deed-office use" 11,256 [100%]; `DEED, RC` deed with restrictive covenant 472 [51%]; `DEEDP` deed, pre RPT tax 2 [100%]. A $0 deed alone is therefore not evidence of anything (Q18). Deed dates run from year 0001 to 2028 and are reported as recorded and flagged, never repaired.
- **The code table in justfixwow is unusable:** `acris_document_control_codes` has 126 rows and every `doctype` is blank, so descriptions come from the Socrata list.

## Alternatives considered

- **D1:** mirroring HPD's nine types (cannot take ACRIS or DOS roles); a flat union of every source's terms (duplicates meanings). A parent "Owner" over Shareholder or Officer was rejected because it implies control, which the specs forbid.
- **D2:** folding `contactdescription` into roles (it is not a role).
- **D3:** (A) give Type II facts the category of their underlying evidence (`public_record`). It needs no change but mislabels the project-curated mail-drop list as a public record. (C) leave it undefined.
- **D5:** a concept for every coded value (over 60 ACRIS types that no question uses; it breaks "nothing no question needs").
- **D6:** local namespace only (no alignment); adopting external terms directly (couples the model to their changes).

## Consequences

- **Agent rule unchanged.** `project_derived` facts are already Type II, so the "interrupt on any non-Type-I link" rule covers them.
- **Edits made with this note:** `docs/competency-questions.md` (the `source_category` line), `data/sources.yaml` (`bor_layers`, `mail_drop_list`), and a pointer in note 0002. `specs/tech-stack.md` names no values, so it needs none.
- **Written now (Slice 0):** `vocab/reliability.ttl`, `vocab/source-category.ttl`, `vocab/review-status.ttl`. The role, entity-kind and coded-value schemes are written in the slices whose questions need them (Slice 1 for roles and entity kind, Slice 2 for violation, complaint and litigation values).
- **Revisit:** the GEN.PART reading once an HPD codebook or a larger name check settles it; ACRIS party-type meanings for the non-deed document types (mortgage, satisfaction, assignment); whether `Watchline` becomes the namespace of a shared core when a second project joins.
