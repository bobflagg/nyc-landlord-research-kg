# 0005: Prefer the simplest model; provenance as flat properties

Date: 2026-10-19

Status: **accepted 2026-10-19.** The new row in `specs/tech-stack.md` stands. Builds on notes 0002 to 0004.

## Decision

1. **Principle.** Prefer the simplest model that keeps every answer citable and its reliability visible. Add structure only when a competency question, or a requirement the specs currently defer, forces it.
2. **Facts and provenance.** Every asserted fact carries its provenance as flat properties on the node or relationship that holds it. No reified fact nodes, and no edge from each fact to a shared source or snapshot node.
   - **Properties on every fact:** `reliability`, `source_category`, `source`, `source_record_id`, `snapshot_id`, `retrieved_at`, and `valid_from` / `valid_to` where the source gives them. Values are the `skos:notation` strings of the schemes in `vocab/` (note 0004).
   - **`review_status`** is written only where note 0003 requires it, and never on Type I rows.
   - **`snapshot_id`** is a property, not an edge, so no snapshot node becomes a supernode. A small catalog of snapshot and run nodes (date, source tables, BOR/NLR run) is joined by key.
   - **Type II links** (BOR/NLR memberships, the mail-drop list) additionally carry a stable `link_id`. A later review record points to a link by this key, so links need not be reified now and need no migration when reviews arrive.
   - **Evidence for a Type II link** is held as list properties on the link (record ids, stage, method, run), or as one relationship per supporting edge, whichever the BOR edge-level export (note 0001) turns out to need.
3. **Promotion rule.** Promote a relationship to a node only when something forces it. Expected triggers are listed under Consequences.

## Context

- Mission outcomes 1 and 2 and the `CLAUDE.md` citation rule define what an answer must show: its source, its snapshot and how the fact was obtained. Flat properties return all of that in the same row as the fact, so the agent's tools can cite without extra joins.
- The only existing rule about restraint is `specs/tech-stack.md`: "Every addition traces to a competency question". There was no general statement of the principle.
- The requirements that seemed to need reified facts are deferred or out of the graph in Stage 1:
  - the review store, the reviewer interface and any promotion process are deferred past week 8 (note 0003);
  - web and document findings and reported claims are session evidence, not graph facts (tech stack);
  - so the only Type II facts loaded are the BOR/NLR layers and the mail-drop list.
- Scale: Type I rows number in the tens of millions (about 11.7M ACRIS deed-party rows in the mirror alone), which makes per-fact nodes and edges expensive.

## Alternatives considered

- **B. Reify every assertion** as a fact node with edges to subject, object, source record and snapshot. Uniform, reviewable and close to PROV-O, but it adds a node and several edges per fact at citywide scale, makes every query multi-hop, and turns shared source and snapshot nodes into supernodes.
- **C. Hybrid:** flat properties for Type I, fact nodes for Type II links, reported claims and web findings. This was the first recommendation. It was set aside because the facts it protects (reviewable links, claims as evidence) are not loaded in Stage 1. It costs a second pattern with its own shapes and queries.

## Consequences

- **Validation:** SHACL shapes are property shapes on the node and relationship types; one shape set covers the provenance properties.
- **Agent tools:** every templated query returns the provenance properties with the fact. A citation is a projection of the result row.
- **Names are proposed here:** `snapshot_id` and `link_id` are new. The other names come from notes 0002 and 0003.
- **Revisit, and promote to nodes if:**
  - the BOR edge-level evidence export (open, note 0001) is richer than lists and per-edge relationships can hold, such as several stages each with its own records, which Q19 would then need;
  - the review process is designed, if keyed references prove insufficient;
  - reported claims or web findings are allowed into the graph (they become fact nodes with evidence edges, as in option C);
  - measured query cost or row size under the flat model becomes a problem at citywide scale.
- **Not decided here:** whether a role node's "who" is a shared entity node or a per-source name occurrence. That is the next decision, with Q3, Q22 and Q24 as the questions it serves.
