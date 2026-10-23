# Ontology-First Knowledge Graph Curriculum

Oct 15, 2026 · @Robert Flagg

## Overview

Eight weeks at about 12 hours a week takes you from semantic basics to a provenance-aware landlord accountability graph in Neo4j, investigated by an agent you build with LangGraph and Deep Agents. Course notes and capstone code live in the `nyc-landlord-research-kg` GitHub repo.

The sequence follows Talisman's Ontology Pipeline (vocabulary → taxonomy → ontology → graph), then adds what a public-records domain demands: entity resolution, time and provenance, then building and evaluating an agent with LangChain, LangGraph and Deep Agents. Each week pairs about 4 hours of reading with 8 hours of building on NYC data, and each week's build is a piece of the capstone.

- **Weeks 1–3, model:** vocabularies, ontology and validation.
- **Weeks 4–5, build:** load NYC records into Neo4j, resolve owners, add provenance and time.
- **Weeks 6–8, agent:** ground an LLM, build the LangGraph and Deep Agents investigator, evaluate it and finish the capstone.

Weeks 3, 5 and 7 are the heaviest; if one runs long, borrow from week 8's buffer rather than skipping its exercise.

## Core references

These fourteen resources carry most of the curriculum; buy or bookmark them first.

| Resource | Author | Type | Why it matters for you |
| --- | --- | --- | --- |
| [Ontology Pipeline](https://technicspub.com/ontology-pipeline/) (Technics Publications, fall 2026; preorder) | Jessica Talisman | Book | The method behind weeks 1–7: controlled vocabulary → metadata → taxonomy → thesaurus → ontology → knowledge graph. Until it ships, use her newsletter tutorials |
| [How to Research Your Landlord](https://pestakeholder.org/wp-content/uploads/2026/06/PESP_Landlord_ResearchGuide_2026.pdf) (May 2026) | Private Equity Stakeholder Project & Tenant Union Federation | Guide | The manual ownership-research method your capstone automates for NYC; also a source of competency questions and a worked test case |
| [Building Knowledge Graphs](https://www.oreilly.com/library/view/building-knowledge-graphs/9781098127091) (2023) | Barrasa & Webber | Book | Barrasa's own playbook for Neo4j knowledge graphs; your primary build guide |
| [Semantic Web for the Working Ontologist](https://dl.acm.org/doi/book/10.1145/3382097), 3rd ed. | Allemang, Hendler & Gandon | Book | The standard practitioner's text on RDF, RDFS, SKOS and OWL |
| [The Accidental Taxonomist](https://www.hedden-information.com/accidental-taxonomist/) | Heather Hedden | Book | Deeper practice on controlled vocabularies and taxonomies |
| [Knowledge Graphs](https://kgbook.org/) (free online) | Hogan et al. | Book / survey | Rigorous overview of graph models, schemas, identity, quality and refinement |
| [Intentional Arrangement](https://jessicatalisman.substack.com/) | Jessica Talisman | Newsletter | Weekly Ontology Pipeline tutorials, many of them early drafts of the book |
| [Ontology Development 101](https://protege.stanford.edu/publications/ontology_development/ontology101.pdf) | Noy & McGuinness | Paper | The classic 25-page method for scoping and building a first ontology |
| [RDF 1.1 Primer](https://www.w3.org/TR/rdf11-primer/) | W3C | Spec | The triple model underneath everything |
| [SKOS Primer](https://www.w3.org/TR/skos-primer/) | W3C | Spec | Standard for vocabularies, thesauri and taxonomies |
| [OWL 2 Primer](https://www.w3.org/TR/owl2-primer/) | W3C | Spec | Classes, properties and logical rules |
| [SHACL](https://www.w3.org/TR/shacl/) | W3C | Spec | Validating graph data against your model |
| [PROV-O](https://www.w3.org/TR/prov-o/) | W3C | Spec | Recording where every fact came from |
| [Neosemantics (n10s) guide](https://neo4j.com/labs/neosemantics/4.2) | Neo4j Labs | Docs | Bridges RDF/OWL/SHACL and your Neo4j graph |

Tools: [Protégé](https://protege.stanford.edu/) for ontology editing and [Neo4j GraphAcademy](https://graphacademy.neo4j.com/courses/) (free) for Cypher and modeling.

## 8-week schedule

Each week ends with a commit to the repo, so the capstone is mostly assembled by week 7.

### Week 1: Foundations, vocabularies and metadata

- **Read:** *Ontology Pipeline* overview and vocabulary, metadata and taxonomy stages; [Building Knowledge Graphs](https://www.oreilly.com/library/view/building-knowledge-graphs/9781098127091) ch. 1–3; [Knowledge Graphs](https://kgbook.org/) ch. 1–2; [The Accidental Taxonomist](https://www.hedden-information.com/accidental-taxonomist/) ch. 1–5; [PESP guide](https://pestakeholder.org/wp-content/uploads/2026/06/PESP_Landlord_ResearchGuide_2026.pdf)
- **Build:** set up the repo; write 20 competency questions, starting from the guide's list; build controlled vocabularies for owner roles, violation classes, complaint and case types; define a metadata schema for source records

### Week 2: Thesauri and ontology design

- **Read:** *Ontology Pipeline* thesaurus and ontology stages; [RDF 1.1 Primer](https://www.w3.org/TR/rdf11-primer/); [SKOS Primer](https://www.w3.org/TR/skos-primer/); Working Ontologist ch. 1–5; [Ontology Development 101](https://protege.stanford.edu/publications/ontology_development/ontology101.pdf); [Protégé](https://protege.stanford.edu/) tutorial
- **Build:** encode the vocabularies as a SKOS thesaurus and import with [n10s](https://neo4j.com/labs/neosemantics/4.2); draft core classes in Protégé (Building, Lot (BBL), Person, Organization, Registration, Deed, Violation, CourtCase) plus the guide's roles (officer, registered agent, corporate servicer, managing agent)

### Week 3: OWL, n-ary relations and validation

- **Read:** [OWL 2 Primer](https://www.w3.org/TR/owl2-primer/); [W3C Organization Ontology](https://www.w3.org/TR/vocab-org/); [N-ary Relations note](https://www.w3.org/TR/swbp-n-aryRelations/); [SHACL](https://www.w3.org/TR/shacl/); n10s SHACL chapter; [OOPS!](https://oops.linkeddata.es/)
- **Build:** model ownership and control as role nodes (who, what role, which building, when, per which source) and the fund → portfolio company → LLC pyramid; write SHACL shapes; run OOPS! on the ontology

### Week 4: Ontology to Neo4j, loading NYC data

- **Read:** *Ontology Pipeline* knowledge graph stage; [GraphAcademy](https://graphacademy.neo4j.com/courses/): Graph Data Modeling Fundamentals, Cypher Indexes and Constraints
- **Build:** map the ontology to labels and relationships with constraints; load one borough (the development subset) of [PLUTO](https://data.cityofnewyork.us/d/64uk-42ks), [ACRIS](https://data.cityofnewyork.us/d/bnx9-e6tj), [HPD registrations](https://data.cityofnewyork.us/d/tesw-yqqr) and [contacts](https://data.cityofnewyork.us/d/feu5-w2e2), HPD violations and [NY DOS corporations](https://data.ny.gov/d/n9v6-gdp6); pass SHACL

### Week 5: Entity resolution, provenance and time

- **Read:** [Splink docs](https://moj-analytical-services.github.io/splink/); [Who Owns What methodology](https://whoownswhat.justfix.org/en/about); PESP guide section 2; [PROV-O](https://www.w3.org/TR/prov-o/); [Zep temporal KG paper](https://arxiv.org/abs/2501.13956)
- **Build:** resolve owners into portfolios as Type II links with match scores, down-weighting registered-agent and mail-drop addresses; add source, retrieval date and validity windows; answer “who owned it when the violation was issued?”; then scale the load to all five boroughs

### Week 6: Grounding an LLM and LangGraph control flow

- **Read:** [Sequeda et al. benchmark](https://arxiv.org/abs/2311.07509); [LangChain tools](https://docs.langchain.com/oss/python/langchain/tools); [neo4j-graphrag-python](https://neo4j.com/docs/neo4j-graphrag-python/current/) Text2Cypher; [LangSmith tracing](https://docs.langchain.com/langsmith/observability-quickstart); [Thinking in LangGraph](https://docs.langchain.com/oss/python/langgraph/thinking-in-langgraph); [Interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts); [Custom SQL agent](https://docs.langchain.com/oss/python/langgraph/sql-agent) (adapt to Cypher)
- **Build:** a LangGraph agent with templated Cypher tools for guide steps 1–2, a text-to-Cypher fallback, schema validation of generated Cypher, and an interrupt when an answer rests only on Type II links; trace in LangSmith

### Week 7: Deep Agents and MCP

- **Read:** [Deep Agents overview](https://docs.langchain.com/oss/python/deepagents/overview); [Subagents](https://docs.langchain.com/oss/python/deepagents/subagents); [Skills](https://docs.langchain.com/oss/python/deepagents/skills); [Tools and MCP](https://docs.langchain.com/oss/python/deepagents/tools); [mcp-neo4j](https://github.com/neo4j-contrib/mcp-neo4j)
- **Build:** the investigator: week 6 graph as a subagent, a web-research subagent for Type II leads, read-only mcp-neo4j-cypher access, ontology and caveat rules as a skill, and a dossier step that writes the guide's inference → source table

### Week 8: Evaluation and capstone

- **Read:** [Agent evals](https://docs.langchain.com/oss/python/langchain/test/evals); [LLM-as-judge evaluators](https://docs.langchain.com/langsmith/online-evaluations-llm-as-judge); [Knowledge Graphs](https://kgbook.org/) ch. on quality
- **Build:** load competency questions as a LangSmith dataset; score answers, trajectories, citations and caveats; finish the capstone checklist on the citywide graph and write up the repo README; publish the optional demo only if time remains

## Capstone

The capstone is an NYC version of the PESP landlord research pipeline: a Deep Agents investigator that starts from a tenant's address and climbs from the building to its LLC, the people and addresses behind it, and any parent company, citing a public record for every step. The deliverable is the full citywide graph and agent running locally; a hosted demo is optional and comes only after the full version works.

### Pipeline: guide steps mapped to NYC sources

NYC can automate most of the guide because HPD requires buildings with 3+ units to register their owner, head officer and managing agent, information the guide has to dig out of state filings by hand.

| Guide step | NYC source | Graph output | Reliability |
| --- | --- | --- | --- |
| 1. Find the property record | [PLUTO](https://data.cityofnewyork.us/d/64uk-42ks) (BBL, units, year built, owner name) | Building, Lot (BBL) | Type I |
| 1. Sales history and legal owner | [ACRIS Master](https://data.cityofnewyork.us/d/bnx9-e6tj) and [ACRIS Parties](https://data.cityofnewyork.us/d/636b-3b5g) (deeds, mortgages, party names and addresses) | Deed, Mortgage, Party; recorded ownership with dates | Type I |
| 2. Officers and agents behind the LLC | [HPD Multiple Dwelling Registrations](https://data.cityofnewyork.us/d/tesw-yqqr) and [Registration Contacts](https://data.cityofnewyork.us/d/feu5-w2e2) (head officer, officer, managing agent, corporation, business addresses) | Person, Organization, role nodes with dates | Type I |
| 2. State and Delaware filings | [NY DOS Active Corporations](https://data.ny.gov/d/n9v6-gdp6); OpenCorporates for out-of-state parents | Registration, registered agent, process address | Type I |
| 2. Corporate servicers and mail drops | Curated list of registered-agent, virtual-office and mail-drop addresses | Address flagged as non-identifying | Modeling rule |
| 2. Related LLCs | Shared officers, addresses and ACRIS signatories, scored with Splink | Possible-same-controller links with match scores | Type II |
| 2. Web search, LinkedIn, news, IRS filings | Agent web-search tool | Claim nodes with URL and retrieval date | Type II |
| 3. Bring it together | The agent's dossier | Inference → source table, plus the ownership pyramid (fund → portfolio company → LLCs) | Each row labeled |

Two limits to plan around: HPD registration covers only 3+ unit buildings, and New York's LLC Transparency Act (effective January 2026) keeps its beneficial-owner filings confidential, so it can't serve as a source ([ABA](https://www.americanbar.org/groups/business_law/resources/business-law-today/2025-december/beneficial-ownership-new-york-llc-transparency)).

- [ ] Scope: all five boroughs, loading PLUTO, ACRIS, HPD registrations and contacts, HPD violations and NY DOS corporations (develop on one borough first, then scale citywide)
- [ ] Ontology published as OWL/SKOS with a design note, including the guide's roles (officer, registered agent, corporate servicer, managing agent) and the ownership pyramid
- [ ] Neo4j graph loaded, with constraints in place and SHACL shapes passing
- [ ] Ownership resolved into portfolios, with Type I (recorded) and Type II (inferred) links kept distinct and mail-drop addresses down-weighted
- [ ] Every fact carries its source and validity dates
- [ ] Deep agent runs the pipeline from an address: graph subagent for steps 1–2, web-research subagent for Type II leads, and a dossier step that writes the inference → source table
- [ ] Dossiers are action-oriented, as the guide asks: who controls the building, how big the portfolio is, conditions across it, and who to pressure
- [ ] Agent answers at least 15 of your 20 competency questions correctly in a LangSmith evaluation, citing sources and stating caveats on inferred links
- [ ] Use the guide's Grandview walkthrough as the model trajectory: hand-research one NYC building the same way, check the agent reaches the same chain, then compare three NYC portfolios against [Who Owns What](https://whoownswhat.justfix.org/en/about) and explain the differences

### Optional: public demo on AuraDB Free

Do this only once every item above is checked. The demo is one community district (about 4,000–5,000 HPD-registered buildings) loaded into Neo4j AuraDB Free, which caps a database at roughly 200,000 nodes and 400,000 relationships. Development uses a fresh local Neo4j in Docker with no size limit.

- [ ] Measure nodes and relationships per building in week 4; budget the demo at 150,000 nodes and 300,000 relationships
- [ ] Trim to fit: open and recent violations only, deeds and mortgages only, provenance as properties
- [ ] Resolve portfolios on the full local graph, and export out-of-slice portfolio buildings as summary nodes so portfolio sizes stay correct
- [ ] Validate with SHACL locally before publishing, since n10s isn't available on Aura
- [ ] Point the investigator at Aura through mcp-neo4j-cypher in read-only mode, and script the publish so the demo rebuilds in one command

The plan is in the repo's `docs/demo-slice.md`.

## Ongoing learning

After week 8, stay current through practitioners and the semantic web community.

- **Jessica Talisman:** [Intentional Arrangement](https://jessicatalisman.substack.com/) and her Knowledge Graph Academy cohorts.
- **Jesús Barrasa and Neo4j:** the [Neo4j blog](https://neo4j.com/blog/) and [GraphAcademy](https://graphacademy.neo4j.com/courses/) for new courses on context graphs and GraphRAG.
- **Juan Sequeda:** the Catalog & Cocktails podcast and his research on knowledge graphs and LLM accuracy.
- **Communities:** the [Knowledge Graph Conference](https://www.knowledgegraph.tech/) and W3C community groups for SKOS, SHACL and RDF.
- **Domain:** JustFix, ANHD and tenant organizing groups, who define what accountability means in practice and can review your ontology.

For the agent side, follow the [Deep Agents tutorials](https://docs.langchain.com/oss/python/deepagents/deep-research) and the [LangChain changelog](https://docs.langchain.com/oss/python/releases/changelog); these libraries change quickly, so check the live docs before relying on older examples.
