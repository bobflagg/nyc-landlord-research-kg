# vocab/ (weeks 1–2)

Controlled vocabularies and the SKOS thesaurus, in Turtle.

- Week 1: controlled vocabularies for owner and contact roles, violation classes (A/B/C), complaint types and court case types, plus a metadata schema for source records. Start from the values the datasets actually use (HPD contact types, ACRIS document types, violation classes).
- Week 2: encode them as SKOS concept schemes (`*.ttl`) and load them into the graph with the project's own loader (n10s is not used; design note 0011).

Done when: every coded value in the week 4 datasets maps to a concept here.
