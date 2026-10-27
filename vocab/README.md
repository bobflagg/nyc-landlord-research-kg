# vocab/

Controlled vocabularies as SKOS concept schemes, in Turtle (design note 0004). The namespace is `https://bobflagg.github.io/Watchline/vocab/`, one path segment per scheme. A concept's `skos:notation` is the exact string stored in the graph.

| File | Scheme | Used for |
| --- | --- | --- |
| `reliability.ttl` | Reliability (I, II) | `reliability` on every fact |
| `source-category.ttl` | Source category | `source_category` on every fact |
| `review-status.ttl` | Review status | `review_status` |
| `role-type.ttl` | Role type | `role_type` on roles (HPD now; ACRIS and DOS with their modules) |
| `entity-kind.ttl` | Entity kind | `owner_kind` on registrations |

`skos:hiddenLabel` with the language tag `x-hpd` carries the HPD code a concept maps from. The loader and the shapes read the vocabulary: `etl/vocab.py` for the mappings and `scripts/sync_shape_values.py` for the allowed values in `ontology/*.shapes.ttl`.

Coded values are added only when a competency question uses them (design note 0004, D5); the recorded raw value is always kept.
