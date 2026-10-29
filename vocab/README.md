# vocab/

Controlled vocabularies as SKOS concept schemes, in Turtle (design note 0004). The namespace is `https://bobflagg.github.io/Watchline/vocab/`, one path segment per scheme. A concept's `skos:notation` is the exact string stored in the graph.

| File | Scheme | Used for |
| --- | --- | --- |
| `reliability.ttl` | Reliability (I, II) | `reliability` on every fact |
| `source-category.ttl` | Source category | `source_category` on every fact |
| `review-status.ttl` | Review status | `review_status` |
| `role-type.ttl` | Role type | `role_type` on roles (HPD, ACRIS deed and mortgage-class parties) |
| `document-type.ttl` | Document type | `doc_type` on ACRIS documents (deed family and mortgage family) |
| `entity-kind.ttl` | Entity kind | `owner_kind` on registrations |
| `violation-class.ttl` | Violation class (A, B, C, I) | `violation_class` on violations |
| `violation-status-group.ttl` | Violation status group | `status_group` (open, closed) |
| `complaint-type.ttl` | Complaint type | `group_value` on type summaries |
| `litigation-case-type.ttl` | Litigation case type | `case_type` on litigation |
| `absence-reason.ttl` | Absence reason (five top-level reasons and BOR's detailed codes) | `reason_code`, `top_level_reason` on `NOT_IN_GROUP`, decisions (note 0024) |
| `link-stage.ttl` | Link stage | `stage` on witness steps, decisions, evidence and metrics (note 0024) |
| `decision-outcome.ttl` | Decision outcome | `outcome` on BOR decisions (note 0024) |
| `gold-status.ttl` | Gold status | `adjudication_status` on method metrics (note 0024) |
| `address-kind.ttl` | Address kind | `kind` on mail-drop-list addresses (note 0026) |
| `deed-pattern.ttl` | Deed pattern | the patterns `classify_deeds` reports (note 0026) |
| `affiliation-type.ttl` | Affiliation type | the relationship types `get_affiliations` reports (note 0026) |
| `evidence-relation.ttl`, `match-basis.ttl`, `extraction-method.ttl`, `lead-reason.ttl` | Session evidence | the coded values of Slice 6 evidence items and unresolved leads (notes 0028, 0030) |
| `claim-label.ttl`, `stop-reason.ttl`, `lead-disposition.ttl`, `lead-kind.ttl` | Dossier | the labels, stop reasons and lead dispositions of the investigator (note 0030) |

`skos:hiddenLabel` with the language tag `x-hpd` carries the HPD code a concept maps from; `x-bor` carries BOR's own code for the four BOR schemes, whose notation is that code as the release writes it. The loader and the shapes read the vocabulary: `etl/vocab.py` for the mappings and `scripts/sync_shape_values.py` for the allowed values in `ontology/*.shapes.ttl`.

Coded values are added only when a competency question uses them (design note 0004, D5); the recorded raw value is always kept.
