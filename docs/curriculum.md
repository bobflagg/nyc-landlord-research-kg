# Curriculum: 8 weeks

The full plan, with readings and links, is the curriculum doc:
https://claude.ai/code/artifact/06c10c80-29ed-4f04-8138-7507c0a5ec50

This file tracks progress. Tick a box when that week's build is committed.

## Weeks

- [ ] **Week 1: Foundations, vocabularies and metadata.** Repo set up; 20 competency questions; controlled vocabularies for owner roles, violation classes, complaint and case types; metadata schema for source records.
- [ ] **Week 2: Thesauri and ontology design.** SKOS thesaurus imported with n10s; core classes drafted in Protégé, including the PESP guide's roles (officer, registered agent, corporate servicer, managing agent).
- [ ] **Week 3: OWL, n-ary relations and validation.** Ownership and control modeled as role nodes; fund → portfolio company → LLC pyramid; SHACL shapes; OOPS! scan.
- [ ] **Week 4: Ontology to Neo4j, loading NYC data.** Labels, relationships and constraints; one borough (the development subset) of PLUTO, ACRIS, HPD registrations and contacts, HPD violations and NY DOS corporations loaded; SHACL passing.
- [ ] **Week 5: Derived layers, provenance and time.** BOR/NLR Owner Portfolio and Operational Network memberships loaded as Type II, each tied to a build and pipeline run with its supporting records as Type I evidence (design note 0001); mail-drop addresses reconciled with BOR's aggregator masking; sources, retrieval dates and validity windows on every fact; load scaled to all five boroughs.
- [ ] **Week 6: Grounding an LLM and LangGraph control flow.** Templated Cypher tools for guide steps 1–2, text-to-Cypher fallback, Cypher validation, interrupt on Type II-only answers, LangSmith tracing.
- [ ] **Week 7: Deep Agents and MCP.** Investigator with graph and web-research subagents, read-only mcp-neo4j-cypher, ontology and caveat rules as a skill, dossier with the inference → source table.
- [ ] **Week 8: Evaluation and capstone.** Competency questions as a LangSmith dataset; answers, trajectories, citations and caveats scored on the citywide graph.
- [ ] **Optional stretch: public demo.** One community district published to AuraDB Free (`docs/demo-slice.md`). Only after every week above is done.
