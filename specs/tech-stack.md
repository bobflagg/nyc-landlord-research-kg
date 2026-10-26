# Tech stack

Status: draft for review, 2026-10-18. Each constraint has a reason. Change one by writing a design note in `docs/design-notes/` and updating this file in the same change.

## Architecture

```
justfixwow PostgreSQL snapshot ─┐
BOR/NLR derived layers ─────────┼─► build pipeline ─► Neo4j knowledge graph ◄─ agent / app ─► web, Socrata API
ontology + vocabulary ──────────┘   (re-runnable)      (system of record)        (runtime)
```

| Constraint | Reason |
| --- | --- |
| The **knowledge graph is the system of record** for every application | One shared model of the evidence; applications differ, the evidence does not |
| The **justfixwow PostgreSQL database is a build-time input only.** Applications never query it | It is a source snapshot, refreshed before production; the graph is what we curate and validate |
| **Every graph fact names the snapshot it was built from**, by id in the form `<source>-<YYYY-MM-DD>[-rN]` (design note 0008) | Snapshots will be refreshed, and an answer must say what date it reflects |
| **Rebuilding the graph from a new snapshot is routine and scripted** | The production version starts with a current snapshot. BOR/NLR run once on it and the result is frozen; a graph build loads that release and never re-runs BOR (design note 0007) |
| The **graph and its BOR/NLR layers come from the same snapshot** | BOR group ids are stable only within a build; mixing snapshots breaks membership claims |
| At runtime, **live Socrata and web results are labeled with their retrieval time** and kept apart from graph facts | Two kinds of time: "as of the snapshot" and "retrieved just now" must never blur |

## Data

| Constraint | Reason |
| --- | --- |
| Source tables in justfixwow: `pluto_latest`, `real_property_master` / `_parties` / `_legals`, `hpd_registrations`, `hpd_contacts`, `hpd_violations`, `hpd_complaints_and_problems`, `hpd_litigations`, `dos_active_corporations` | These cover the Stage 1 questions. The `acris_real_property_*` and `hpd_complaints` copies are stale (2025-01 and 2023-11) and are not used |
| `data/sources.yaml` maps each source key to its justfixwow table and its Socrata dataset id | One registry for build-time loading and runtime freshness checks |
| A **new source enters only with a competency question that needs it** | The database holds many more tables; scope grows with questions, not with availability |
| Known limit: `hpd_violations` holds about 2M of about 11M violations; open violations are present, closed history is partial | Historical questions (Q14) must report the gap or backfill from Socrata |
| Keys stay strings: BBL (10 digits), BIN, ACRIS `document_id`, HPD `registrationid` | Leading zeros carry meaning |

## Knowledge graph

| Constraint | Reason |
| --- | --- |
| **Neo4j 5.26** with APOC and n10s; local in Docker for development (ports 7688/7475) | Property graph for agent queries; n10s bridges the RDF ontology. Ports avoid other local instances |
| Production hosting: **not yet decided** | Decided when the live app is planned (roadmap, later horizons) |
| **Reliability, source category and review status on every fact**; provenance (source, record id, snapshot) on every fact; validity dates where the source gives them | Outcomes 1 and 2 of the mission; design notes 0002 and 0003 |
| **Inferred links and reported claims are their own relationships**, never properties on recorded ones | Recorded and derived must stay separable in every query |
| **Ownership and control are role nodes** (who, what role, which building, when, per which source) | Roles change over time and come from different sources |
| **Mail-drop addresses never link two entities on their own** | Registered-agent and virtual-office addresses join unrelated owners |
| Cypher is parameterized; `MERGE` only on constrained properties; constraints before loading; batch loading at citywide scale | Correctness and load time on tens of millions of rows |

## Ontology and vocabulary

| Constraint | Reason |
| --- | --- |
| The **OWL/SKOS/SHACL files in `ontology/` and `vocab/` are the source of truth** for the graph schema | The graph is ontology-first; the schema is reviewed as a model, not inferred from code |
| **Modular ontology:** a core module (property, lot, building, entity, role, provenance, reliability) imported by domain modules added per stage, each with its own SHACL shapes | Later stages add modules without rewriting the core |
| **Vocabularies are SKOS concept schemes.** A stage may add schemes and concepts; it never changes an existing concept's meaning | Earlier answers and data keep their meaning |
| Schema changes are **versioned and come with a migration**; SHACL validation (shacl2cypher, plus a snapshot-reference check) runs on every build, and a violation fails it (design note 0010) | Several applications will read the graph |

## Agent and runtime

| Constraint | Reason |
| --- | --- |
| **Python 3.13 with uv** | One toolchain for pipeline, agent and evaluation |
| **LangChain v1, LangGraph, Deep Agents, LangSmith** | Existing stack; LangGraph for controlled flows, Deep Agents for multi-step investigation, LangSmith for traces and evaluation |
| **Graph access is read-only**: templated Cypher tools first, validated text-to-Cypher as fallback, mcp-neo4j-cypher in read-only mode | Applications never change recorded evidence |
| **Web and document findings are session evidence**, not graph facts | A finding enters the graph only through a later, reviewed process (mission, not yet in scope) |
| **Tools and skills are grouped by question family** | A stage adds a family without changing the others |
| Model provider, web search tool and retrieval cache: **not yet decided** | Needed before the slices that use them (roadmap) |

## Extension pattern and evaluation

| Constraint | Reason |
| --- | --- |
| Every stage, and every slice within it, runs: **questions → vocabulary → ontology → ingestion → agent → evaluation** | The pattern of Stage 1, repeated |
| **Competency question ids are stable and never renumbered**; each belongs to one stage | Ids key the evaluation datasets, the review page and traceability |
| **Every addition traces to a competency question**: question → vocabulary terms → ontology classes → loader → agent tool → evaluation case | Nothing is built that no question needs |
| **Prefer the simplest model that keeps every answer citable and its reliability visible.** Add structure only when a competency question, or a requirement the specs now defer, forces it. Provenance is flat properties on each fact (design note 0005) | The agent's accuracy and citations are the product; extra structure adds load, query and validation cost |
| **An evaluation dataset per stage, with expected answers from the build snapshot**; earlier stages' evaluations must keep passing | Regression protection as stages accumulate |
| Test framework: **not yet decided** | Needed by Slice 0 |

## Open decisions

Model provider · web search tool · retrieval cache design · test framework · production hosting · the form of BOR/NLR's edge-level evidence export (design notes 0001 and 0007).
