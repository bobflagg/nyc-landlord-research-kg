# 0010: Structure of the core ontology module

Date: 2026-10-26

Status: **accepted 2026-10-26.** Items 1–6 were accepted first; items 7 and 8 were accepted the same day after the spike. Amends `specs/roadmap.md` (Slice 0 row) and `specs/tech-stack.md` (modular ontology and schema rows) as listed under Consequences. Builds on notes 0004, 0005, 0006 and 0007.

## Decision

1. **Layout.** One core OWL file, `ontology/core.ttl`, and one shapes file, `ontology/core.shapes.ttl`. Each domain module is a separate pair that imports core: HPD and ACRIS records in Slice 1, conditions in Slice 2, ownership layers in Slice 4. OWL declares classes and properties; SHACL carries what the data must satisfy (required properties, allowed values, key patterns, references).
2. **The property spine.**
   - `Lot` is the base node, keyed by BBL (string, 10 digits). `Building` is a node keyed by BIN that exists only where a source gives a real BIN, linked to its lot.
   - `Property` is an abstract OWL superclass of `Lot` and `Building` for shared characteristics. It has no label in the graph.
   - **Addresses are properties,** not nodes. The A2 key (note 0006) is stored and indexed, so "who else uses this address" is an index lookup, not a traversal. An address becomes a node only if Q6 or Q7 turns out to need traversal.
3. **Parties and roles.**
   - `Party` is a superclass with source subclasses: HPD identity nodes (note 0006), DOS entities, and ACRIS parties (still open in note 0006).
   - One `Role` class holds the normalized role type (note 0004), the source's own code, the source record ids and valid dates. A role attaches to a building or a lot.
   - `Registration` and `Deed` are defined by the first domain module (Slice 1), not by core. Source-specific shapes say which role properties each source requires.
4. **Provenance.**
   - The flat provenance of note 0005 is carried by record-like nodes (roles, registrations, deeds, identity nodes) and by entity nodes as loaded from their source.
   - **Structural edges** (a building on a lot, a role in a registration) carry none, because they restate a column of the record node. **Assertion edges** (a Type II membership from BOR) carry their own provenance and a `link_id`, because they assert something the source record does not.
   - The provenance properties are enforced by **one reusable SHACL shape,** applied to each class that needs it. There is no `Fact` class in OWL.
   - `Lot` and `Building` properties are taken from one source and tagged with it (PLUTO for lots). If a second source later adds properties to the same node, the model changes then, by a new note. The alternative, separate record nodes per source, was not adopted.
5. **Validation fails the build.** Any SHACL violation fails a build. A report-only tier is not used.
6. **`ReviewRecord` is deferred.** It is not part of the core module. The class and its shape are defined with the review process (roadmap, cross-cutting work), together with the reviewer interface. Every fact still has a key a review can point at: a node key for records and a `link_id` for assertion edges (note 0005).

7. **shacl2cypher runs the shapes (accepted).** shacl2cypher checks the shapes, plus one hand-written Cypher check for snapshot references. The generated Cypher is kept in the repo, and the allowed values in the shapes are generated from the `.ttl` vocabulary files, not typed twice. Basis: the spike below. Candidates were n10s inside Neo4j, shacl2cypher (https://github.com/Volland/shacl2cypher, MIT, v0.3.0 from PyPI), pySHACL on an RDF export, and hand-written Cypher. The spike (2026-10-26) ran the same sample shapes over the same sample graph on Neo4j 5.26 in a throwaway container: 5 lots, 4 buildings, 4 roles, 2 `MEMBER_OF` edges, with 9 deliberately bad rows that should produce 11 violations.
   - **shacl2cypher** compiled all 31 rules (none unsupported) and found all 11 violations with no false positives on the good rows. That includes the `sh:not` placeholder-BIN pattern, `sh:maxCount` on a relationship (a role on two buildings), and every property rule on a `MEMBER_OF` edge through `s2c:targetRelationship`. Shapes keep our own namespace. Weaker points: a violation of the shared provenance shape (applied with `sh:node`) is reported against the node as "violates sh:node", without naming the property; and an edge violation is reported as "MEMBER_OF ->" without identifying the edge. At 600,000 lots, 300,000 buildings and 300,000 edges (1 GB heap, synthetic data) it took 14.7 seconds.
   - **n10s** found 5 of the 11, and ran without an error that told us about the other 6. It silently dropped the `sh:not` rule and did not check the relationship rules or a role on two buildings. It also needed the shapes in the `neo4j://graph.schema#` namespace (our namespace was rejected in its default mode). A tool that skips rules without saying so is a poor fit for "a violation fails the build".
   - **Neither tool** can check that a fact's `snapshot_id` exists in the catalog. One hand-written Cypher query does it and found the test case. It runs beside the generated checks.
   - **Not tested:** whether n10s can be configured to cover the missed rules; shacl2cypher on the full citywide graph; how its project health looks over time (single author, a young project); and "a role is on a building or a lot" (`sh:or`), which the sample shapes did not include.
   - **Found while writing the shapes (2026-10-26):** a relationship path inside `sh:xone` (or `sh:or`) is read as a property, so "a role is on a building or a lot" flagged every role. That closes the `sh:or` question above: it does not work for relationships. The rule is a hand-written check, `etl/checks/role_attachment.cypher`, tested on a throwaway database (it flagged the role on both and the role on neither, and passed the two valid roles). The other rules in `core.shapes.ttl` (43 compiled) behaved as expected on the same fixture.
   - **Open risks, to watch:** the three untested points above, and the weak diagnostics. If shacl2cypher is abandoned or fails at citywide scale, the kept Cypher still runs and pySHACL on an export is the fallback.
8. **Naming (accepted).** snake_case property names, as in notes 0002 to 0008 and BOR's release; PascalCase labels; SCREAMING_SNAKE_CASE relationship types.

## Context

- Data checked 2026-10-26 on the justfixwow database: PLUTO has no BIN and gives lot-level facts only. HPD registrations carry 200,417 BINs on 181,863 lots. 3,989 lots have more than one real BIN. 363 registrations have a placeholder BIN of the `1000000` kind and 33 have none. So a lot exists everywhere, and a building only where HPD registers it.
- The mission counts in lots, buildings or units, so the building level has to exist. Q2, Q4 and violations are at building level; Q1 is at lot level and must work for lots HPD does not register.
- Note 0005 sets the principle that the model stays as simple as the competency questions allow. Decisions 2, 3 and 4 follow it: no address nodes, one role class, one shape instead of a `Fact` class.

## Alternatives considered

- **Several small core files from the start.** Easier to review in pieces, but adds imports before any module needs them.
- **SHACL only, with no OWL.** The smallest, but `tech-stack.md` makes OWL, SKOS and SHACL the source of truth.
- **`Building` as the base node.** Breaks Q1 for lots HPD does not register.
- **One node per BBL with BINs as a list property.** Loses the anchor for building-level facts.
- **Address nodes.** One DOS address holds about 93,000 entities, so a node there becomes a supernode. An indexed property gives the same lookup.
- **A role subclass per source.** More precise shapes, more classes.
- **A role as a relationship with properties.** Contradicts the tech-stack rule that ownership and control are role nodes.
- **Per-source record nodes for lot attributes** (about 860,000 more nodes). Provenance would always be exact, but it adds structure no question needs yet.
- **An abstract `Fact` class in OWL.** Documentation that adds nothing the shared shape does not.

## Consequences

- **Edits made with this note:**
  - `specs/roadmap.md`: "review record" is removed from the Slice 0 core module, and the review-records bullet in cross-cutting work now says the class is defined there.
  - `specs/tech-stack.md`: "review record" is removed from the core module list, and the schema row says a violation fails the build.
- **A registration without a real BIN** (396 of 203,236) has no building node, so its roles attach to the lot. This follows from decision 2 and should be confirmed when the HPD module is written in Slice 1.
- **Slice 0 exit test** is unchanged: a sample load validates under SHACL, and the harness runs one question end to end. The validation step is now shacl2cypher plus the snapshot-reference check (item 7).
- **READMEs:** `ontology/README.md` and `vocab/README.md` still describe the old "weeks 2–3" course plan. They are rewritten with the first ontology files.
- **Revisit:** per-source attributes on `Lot` once a second source needs them; address nodes if Q6 or Q7 needs traversal; the review class with the review process.
