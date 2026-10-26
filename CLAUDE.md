# CLAUDE.md

Guidance for Claude Code in this repository.

## What this project is

The first stage of public accountability infrastructure for NYC housing: a knowledge graph of properties, owners and the public record, and an investigator agent built on it. Read these before starting work. They are the project's agreements, and this file does not repeat them:

- `specs/mission.md`: users, outcomes, boundaries, non-goals.
- `specs/tech-stack.md`: architecture, data sources, graph, ontology and agent constraints, each with its reason.
- `specs/roadmap.md`: Stage 1 slices and the competency questions each must pass.
- `docs/competency-questions.md` and `-detail.md`: what the graph and agent must answer.
- `docs/design-notes/`: decisions behind the constraints. Exact property names and values (reliability, `source_category`, `review_status`) are in notes 0002 and 0003.

## How to work with me

- Work in the current roadmap slice. Trace each change to the competency questions it serves; if a change serves none, ask first.
- For ontology, vocabulary and schema decisions, propose options with trade-offs and let me choose. Don't settle them silently in code.
- A change that contradicts `specs/` needs a design note and a matching edit to the spec, in the same change. Point it out rather than working around it.
- Explain the reasoning behind non-obvious choices briefly as you go.
- Don't commit or push unless I ask.

## Layout

```
docs/        competency questions, design notes, demo plan
specs/       mission, tech stack, roadmap
vocab/       SKOS concept schemes (Turtle)
ontology/    OWL modules and SHACL shapes
data/        sources.yaml (source keys → justfixwow tables and Socrata ids)
etl/         build pipeline: justfixwow snapshot → Neo4j
resolution/  BOR/NLR derived layers, mail-drop address list
agent/       LangGraph tools and Deep Agents investigator
evals/       evaluation datasets and evaluators, per stage
scripts/     utilities (competency question review page)
```

## Environment

- Python 3.13 with **uv**: `uv add <pkg>`, `uv run <cmd>`. Never pip.
- **Source data:** the local justfixwow PostgreSQL database (`postgres-justfix` MCP server in `.mcp.json`, port 5434). Read-only; it is a build input, never queried by the agent. Use the tables named in `specs/tech-stack.md`; the stale `acris_real_property_*` and `hpd_complaints` copies are not used.
- **Graph:** Neo4j 5.26 (APOC, n10s) via `docker compose up -d`. Bolt `bolt://localhost:7688`, Browser http://localhost:7475; credentials and memory in `.env` (copy `.env.example`).
- **Only ever connect to this repo's Neo4j.** Other instances on this machine (ports 7687/7474, such as the Watchline discovery graph) belong to other projects. Never read from or write to them.
- Secrets live in `.env` and `.mcp.json`. Never print, log or commit their values.

## Quick rules (full set in `specs/tech-stack.md`)

- Every fact carries reliability, source category and provenance including its snapshot. Inferred links and reported claims are separate relationships, never properties on recorded ones.
- Ownership and control are role nodes. Mail-drop addresses never link two entities on their own.
- Keys (BBL, BIN, document_id, registrationid) stay strings.
- Cypher is parameterized; `MERGE` only on constrained properties; load in batches.
- The agent's graph access is read-only. Every claim cites its source; any answer resting on a Type II link or a reported claim says so.
- LangChain, LangGraph and Deep Agents change quickly: check https://docs.langchain.com before relying on remembered APIs.
- Names are shown with their source and reliability; a name never asserts a role, and a name match is a lead, computed at query time (`specs/mission.md`, Boundaries; design note 0009).
