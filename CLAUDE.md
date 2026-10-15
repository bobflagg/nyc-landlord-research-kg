# CLAUDE.md

Guidance for Claude Code in this repository.

## What this project is

A self-directed 8-week course in ontology-first knowledge graphs (Talisman's Ontology Pipeline, Barrasa's knowledge layer) and its capstone: an NYC landlord research agent. The capstone automates the PESP *How to Research Your Landlord* method for New York City: from a tenant's address, it traces the building to its LLC, the people and addresses behind it, related LLCs and any parent company, citing a public record for every step.

- Plan and progress: `docs/curriculum.md` (full curriculum doc linked there).
- What the graph must answer: `docs/competency-questions.md`. Check new modeling or agent work against it.
- Modeling decisions: `docs/design-notes/`. Read them before changing the ontology or graph schema, and add a note when a decision is made.

## Priorities

1. **The full citywide graph and agent, running locally**, is the deliverable. Develop on one borough, then scale to all five.
2. The hosted demo on AuraDB Free (`docs/demo-slice.md`) is an optional stretch goal. Don't trade away anything in the full version to make the demo fit.

## How to work with me

This is a learning project; I'm building the skills, not just the artifact.

- Explain the reasoning behind non-obvious choices (modeling, Cypher patterns, agent design) briefly as you go.
- For **ontology and schema decisions**, propose options with trade-offs and let me choose. Don't settle them silently in code.
- Work in the current week's folder unless I ask otherwise; don't build ahead into later weeks.
- Don't commit or push unless I ask.

## Layout

```
docs/        curriculum, competency questions, demo plan, design notes
vocab/       controlled vocabularies, SKOS thesaurus (Turtle)        weeks 1–2
ontology/    OWL ontology, SHACL shapes                              weeks 2–3
data/        sources.yaml (dataset IDs); raw/ and interim/ gitignored
etl/         download and load scripts into Neo4j                    weeks 4–5
resolution/  load BOR/NLR derived layers, mail-drop address list     week 5
agent/       LangGraph agent, Deep Agents investigator               weeks 6–7
evals/       LangSmith datasets and evaluators                       week 8
```

## Environment and commands

- Python 3.13, managed with **uv**. Add packages with `uv add <pkg>`; run with `uv run <cmd>`. Don't use pip.
- Local Neo4j 5.26 (APOC + n10s) via Docker: `docker compose up -d`.
  - Bolt `bolt://localhost:7688`, Browser http://localhost:7475. Credentials and memory settings are in `.env` (copy `.env.example`).
  - **Only ever connect to this database.** Other Neo4j instances on this machine (default ports 7687/7474, e.g. the Watchline discovery graph) belong to other projects. Never read from or write to them from this repo.
- Secrets live in `.env`, which is gitignored. Never print, log or commit their values.

## Data

- Sources and dataset IDs are in `data/sources.yaml`: PLUTO, ACRIS (master, parties, legals), HPD registrations and contacts, HPD violations, NY DOS corporations. All are Socrata portals (`https://<domain>/resource/<id>.json`).
- Downloads go to `data/raw/` and are never committed. Record `retrieved_at` in `sources.yaml` when data is fetched.
- Several tables have millions of rows citywide. Page through the API (or use bulk CSV export), cache to disk, and load in batches. Never load row-by-row Cypher at citywide scale.
- Primary keys: BBL for lots (10-digit string: borough + block + lot), BIN for buildings, ACRIS `document_id`, HPD `registrationid`. Keep them as strings; don't let leading zeros be lost.

## Graph conventions

These are the current conventions; update this section when a design note changes them.

- **Reliability on every fact.** `reliability: "I"` for recorded assertions (a public record states it, or it follows from joining records on an official identifier), `"II"` for derived conclusions (entity-resolution matches, group membership, links drawn from reported claims). It describes how the assertion was obtained, not how far to trust it. Never mix them: an inferred link is a separate relationship, not a property on a recorded one (design note 0002).
- **Source category and review status on every fact:** `source_category` is `public_record`, `published_reporting` or `web_content`; `review_status` is `unreviewed`, `confirmed`, `refuted`, `inconclusive` or `contested`. Web search is a retrieval channel, not a category: a primary record found by search is `public_record`. A third party's claim is its own relationship type (Type I only as to the fact that it was published), never a property on a recorded relationship.
- **Provenance on every fact:** `source` (key from `sources.yaml`), `source_record_id`, `retrieved_at`. Type II links also carry the evidence (`match_score`, matched fields, linkage stage and run, or claim URLs).
- **Time:** ownership and role facts carry `valid_from` / `valid_to` where the source supports it.
- **Ownership and control are role nodes** (who, what role, which building, when, per which source), not direct Person→Building edges.
- **Mail-drop addresses** (registered-agent services, virtual offices, mail-drop stores, listed in `resolution/`) must never on their own link two entities.
- Cypher: parameterized queries only; `MERGE` only on properties backed by a uniqueness constraint; create constraints and indexes before loading.
- The ontology (OWL/SHACL) in `ontology/` is the source of truth for the schema. When labels or relationship types change, update the ontology and shapes in the same change, and re-run SHACL validation.

## Agent conventions (weeks 6–8)

- Stack: LangChain v1 (`create_agent`), LangGraph, Deep Agents, LangSmith. These libraries change quickly, so check the live docs at https://docs.langchain.com before relying on remembered APIs.
- The agent's graph access is **read-only**: templated Cypher tools first, text-to-Cypher only as a validated fallback, mcp-neo4j-cypher with `NEO4J_READ_ONLY=true`.
- Every claim in an answer or dossier cites its source. Any answer that depends on a Type II link says so and shows the evidence.
- Trace runs to LangSmith (`LANGSMITH_PROJECT=nyc-landlord-research-kg`).

## Publishing responsibly

The graph names real people from public filings. In agent output, demos and docs:

- show people only in roles recorded in HPD, ACRIS or DOS filings (Type I);
- label inferred links (Type II) as leads with their evidence, never as findings;
- don't follow links to individuals' personal addresses or non-business information.
