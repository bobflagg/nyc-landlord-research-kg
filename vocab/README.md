# vocab/

Controlled vocabularies as SKOS concept schemes, in Turtle (design note 0004). The namespace is `https://bobflagg.github.io/Watchline/vocab/`, one path segment per scheme. A concept's `skos:notation` is the exact string stored in the graph.

| File | Scheme | Used for |
| --- | --- | --- |
| `reliability.ttl` | Reliability (I, II) | `reliability` on every fact |
| `source-category.ttl` | Source category | `source_category` on every fact |
| `review-status.ttl` | Review status | `review_status` |
| `role-type.ttl` | Role type | `role_type` on roles (HPD and ACRIS deed parties now; DOS with its module) |
| `document-type.ttl` | Document type | `doc_type` on ACRIS documents (deed family only) |
| `entity-kind.ttl` | Entity kind | `owner_kind` on registrations |
| `violation-class.ttl` | Violation class (A, B, C, I) | `violation_class` on violations |
| `violation-status-group.ttl` | Violation status group | `status_group` (open, closed) |
| `complaint-type.ttl` | Complaint type | `group_value` on type summaries |
| `litigation-case-type.ttl` | Litigation case type | `case_type` on litigation |

`skos:hiddenLabel` with the language tag `x-hpd` carries the HPD code a concept maps from. The loader and the shapes read the vocabulary: `etl/vocab.py` for the mappings and `scripts/sync_shape_values.py` for the allowed values in `ontology/*.shapes.ttl`.

Coded values are added only when a competency question uses them (design note 0004, D5); the recorded raw value is always kept.
