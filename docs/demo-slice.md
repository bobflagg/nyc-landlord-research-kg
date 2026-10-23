# Optional: a public demo on AuraDB Free

> **Stretch goal.** The capstone is the full citywide graph and agent running locally. Start this only after that works; the full version always takes priority.

The demo is one community district of NYC, exported from the full local graph into Neo4j AuraDB Free, with the investigator agent pointed at it read-only. Because it's derived from the full graph, it adds an export step, not a second pipeline.

## The constraint

AuraDB Free is one database with caps on node and relationship counts, reported as about **200,000 nodes and 400,000 relationships**. Neo4j's pricing page confirms caps exist but doesn't list them, so check the console when creating the instance and update this line.

Target **150,000 nodes and 300,000 relationships** so there is 25% headroom for growth and for reloads.

## Budget per building (rough; replace with measured numbers in week 4)

| Element | Nodes per building | Notes |
| --- | --- | --- |
| Lot and building | 2 | From PLUTO; could merge into one node for the demo |
| HPD registration | 1 | |
| Registration roles (owner, head officer, officer, agent) | ~4 | Role nodes, per the week 3 design |
| People and organizations | ~2 new | Shared across a portfolio, so the per-building cost is low |
| Addresses | ~2 new | Also shared |
| ACRIS documents since 2000 (deeds, mortgages) | ~3 | Plus ~3 new parties |
| HPD violations | ~15 | Biggest and most variable cost; see trims below |
| **Total** | **~30** | Relationships run about 2× nodes, so ~60 |

At ~30 nodes and ~60 relationships per building, the budget fits about **4,000–5,000 HPD-registered buildings**, roughly one community district.

## Trims if the slice runs over

1. **Violations:** keep only open violations plus those issued in the last three years, and store older history as counts per class and year on the building.
2. **ACRIS:** keep deeds and mortgages only, not satisfactions, assignments or other document types.
3. **Provenance:** store source, dataset ID and retrieval date as properties on facts, with a handful of shared `Source` nodes rather than one per fact.
4. **Geography:** drop to 3–5 zip codes inside the district.

## Avoiding truncated portfolios

A geographic slice cuts portfolios at the district line, which would understate a landlord's size, a core output.

1. Resolve portfolios on the full local graph (citywide or borough-wide).
2. Export every building in the slice in full.
3. For portfolios that touch the slice, export the other buildings as skeleton nodes: BBL, address, units and open-violation counts as properties, linked to the portfolio, with no violations or documents.

The demo then reports correct portfolio sizes while staying in budget. Mark skeleton buildings (for example `:Building {detail: "summary"}`) so the agent says when details are outside the demo.

## Build and publish

- Export from the full graph: an `etl/` export step selects the district (plus portfolio summary nodes) from the local citywide graph and writes it to Aura.
- Keep the ontology and SHACL in the repo. n10s and Graph Data Science aren't available on Aura as far as I know (check), so run SHACL validation and any graph algorithms locally before publishing.
- Publish by uploading a database dump or by running the load scripts against the Aura URI.
- Point the agent's MCP server at Aura in read-only mode (`NEO4J_READ_ONLY=true` in mcp-neo4j-cypher) and keep credentials server-side.
- Free instances pause when idle and can be removed after long inactivity; check the current rules and keep the publish step scripted so the demo can be rebuilt in one command.

## Choosing the district

Pick a district where:

- organizers you know are active, so the demo is useful as well as illustrative;
- several large portfolios operate, so entity resolution and the ownership pyramid have something to show;
- the HPD-registered building count fits the budget (check with PLUTO and HPD registrations in week 4).

## Publishing responsibly

Officer and agent names are public records, but a public demo concentrates them. In the demo:

- show people only in roles recorded in HPD, ACRIS or DOS filings (Type I);
- show inferred links (Type II) between companies and buildings with their evidence and a clear "inferred" label, never as findings;
- don't follow inferred links to individuals' personal addresses or non-business information.
