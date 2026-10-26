# NYC Landlord Research KG

This repo holds my coursework and capstone for learning to build an ontology-first knowledge graph, following Jessica Talisman’s Ontology Pipeline and Jesús Barrasa’s knowledge-layer approach. The capstone automates the Private Equity Stakeholder Project’s *How to Research Your Landlord* method for New York City. It loads PLUTO, ACRIS, HPD registrations and NY State corporation records into a validated Neo4j graph, resolves owners into portfolios, and keeps recorded facts (Type I) separate from inferred links (Type II). A Deep Agents investigator then starts from a tenant’s address and produces an evidence-backed dossier for tenant organizers.

## Course map

Eight weeks at about 12 hours a week. Full plan with readings: [docs/curriculum.md](docs/curriculum.md).

| Week | Topic | Lands in |
| --- | --- | --- |
| 1 | Foundations, vocabularies, metadata | `docs/competency-questions.md`, `vocab/` |
| 2 | Thesauri (SKOS) and ontology design | `vocab/`, `ontology/` |
| 3 | OWL, n-ary relations, SHACL validation | `ontology/` |
| 4 | Ontology to Neo4j, loading NYC data | `etl/` |
| 5 | Entity resolution, provenance, time | `resolution/`, `etl/` |
| 6 | Grounding an LLM, LangGraph control flow | `agent/` |
| 7 | Deep Agents investigator and MCP | `agent/` |
| 8 | Evaluation and capstone | `evals/` |

## Repository layout

```
docs/          curriculum, competency questions, demo-slice plan, design notes
vocab/         controlled vocabularies and SKOS thesaurus (Turtle)
ontology/      OWL ontology and SHACL shapes
data/          sources.yaml (dataset IDs and retrieval dates); raw/ is gitignored
etl/           download and load scripts into Neo4j
resolution/    entity resolution (Splink) and the mail-drop address list
agent/         LangGraph agent and Deep Agents investigator
evals/         LangSmith datasets and evaluators
```

## Setup

1. Copy `.env.example` to `.env` and fill in the Neo4j connection.
2. In Neo4j Desktop, create a DBMS (5.26 or later, with APOC) and a database named `nyclr`:

   ```cypher
   CREATE DATABASE nyclr IF NOT EXISTS
   ```

   Bolt: `bolt://localhost:7687`. The server may host other projects' databases; this project uses only `nyclr` (design note 0011). For the citywide graph, raise the DBMS heap and page cache in Desktop's settings.
3. Start the address service (NYC DCP Geosupport, release 25b; the first build downloads about 2 GB):

   ```bash
   docker build --platform=linux/amd64 -t nyclr-geosupport geosupport/
   docker run -d --platform=linux/amd64 -p 8081:8080 --name nyclr-geosupport nyclr-geosupport
   curl -s localhost:8081/health      # {"release":"25b"}
   ```

   It runs under emulation on Apple Silicon. Port 8081 leaves 8080 free for other projects.
4. Add Python dependencies as each week needs them, for example:

   ```bash
   uv add rdflib pyshacl neo4j            # weeks 1–4
   uv add splink pandas                   # week 5
   uv add langchain langgraph deepagents langsmith neo4j-graphrag   # weeks 6–8
   ```

## Scope

The capstone is the **full citywide graph and agent**, running locally: all five boroughs of the sources in `data/sources.yaml`. Development starts on one borough (week 4) and scales to the whole city (week 5 onward).

A hosted demo on Neo4j AuraDB Free, using one community district, is an **optional stretch goal**. It comes only after the full version works. See [docs/demo-slice.md](docs/demo-slice.md).

## Data and attribution

Data comes from [NYC Open Data](https://opendata.cityofnewyork.us/) and [data.ny.gov](https://data.ny.gov/); see `data/sources.yaml`. Method adapted from the Private Equity Stakeholder Project and Tenant Union Federation’s [How to Research Your Landlord](https://pestakeholder.org/wp-content/uploads/2026/06/PESP_Landlord_ResearchGuide_2026.pdf) (2026).

Inferred ownership links are leads, not findings. Every Type II claim the agent makes is labeled as inferred and cites its evidence.
