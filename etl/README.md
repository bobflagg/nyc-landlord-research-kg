# etl/ (weeks 4–5)

Download and load scripts from the datasets in `data/sources.yaml` into Neo4j.

- Week 4: map ontology classes to labels and relationships; create constraints and indexes; load one borough into the local Neo4j as the development subset; run SHACL validation.
- Week 5: add source, dataset ID, retrieval date and validity windows to every fact; scale the load to all five boroughs. At citywide size, load in batches (or with `neo4j-admin database import` for the initial bulk load) rather than row-by-row Cypher.
- Optional stretch: an export step that writes one community district to AuraDB Free; see `docs/demo-slice.md`.

Raw downloads go in `data/raw/` (gitignored). Scripts must be re-runnable end to end.
