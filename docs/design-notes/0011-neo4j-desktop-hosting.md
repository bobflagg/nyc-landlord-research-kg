# 0011: Host the graph in Neo4j Desktop, without n10s

Date: 2026-10-26

Status: **accepted 2026-10-26.** Amends `specs/tech-stack.md` (the Neo4j row), `CLAUDE.md` (Environment), `README.md` (Setup) and `.env.example`; removes `docker-compose.yml`. Builds on note 0010.

## Decision

1. **The graph lives in Neo4j Desktop,** database `nyclr`, on `bolt://localhost:7687`. Connection values are in `.env`: `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`, `NEO4J_DATABASE`.
2. **No n10s.** Shapes run as Cypher compiled by shacl2cypher (note 0010), so nothing needs n10s. Vocabularies are loaded by the project's own loader.
3. **One database, named every time.** The Desktop server also hosts other projects' databases. Every connection passes `NEO4J_DATABASE` explicitly. The rule "only ever connect to this repo's Neo4j" becomes "only ever use the `nyclr` database": nothing reads, writes or alters any other database.
4. **`docker-compose.yml` is removed.** It started a separate container on shifted ports with n10s. Throwaway containers are still fine for tests that must not touch `nyclr`.

## Consequences

- Named databases need Neo4j Enterprise or Desktop's developer license; Community has one database. Neo4j Desktop covers that, but a later production host must support what the build uses (property-type constraints are also Enterprise).
- `.env.example` and the README follow the new variable names (`NEO4J_USER`, not `NEO4J_USERNAME`).
- The old heap and page-cache variables are dropped; memory is set in Desktop.
- Open: how the SKOS vocabularies enter the graph (a small loader of concepts as nodes, or not at all, since the shapes already carry the allowed values).
