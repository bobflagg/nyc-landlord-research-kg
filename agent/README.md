# agent/

Tools and the agent harness. Slice 1 so far: `tools/lookup.py` (Q1, address to lot and buildings through Geosupport) and `tools/records.py` (Q3, deed grantee against HPD owner; Q24, start from a name). All graph access is read-only (`db.py`). `harness.py` builds the agent and states the answer rules. Design notes 0012, 0013 and 0017.

Planned (the original course plan):

The investigator.

- Week 6 (LangGraph): templated Cypher tools for PESP guide steps 1–2, a text-to-Cypher fallback, schema validation of generated Cypher, and an interrupt when an answer rests only on Type II links. Trace everything in LangSmith.
- Week 7 (Deep Agents): the week 6 graph as a subagent, a web-research subagent for Type II leads, read-only access through mcp-neo4j-cypher, the ontology and caveat rules as a skill, and a dossier step that writes the guide's inference → source table.

The dossier is action-oriented: who controls the building, how big the portfolio is, conditions across it, and who to pressure.
