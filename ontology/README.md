# ontology/

OWL modules and SHACL shapes (design note 0010).

| File | What |
| --- | --- |
| `core.ttl` | Core classes and properties: Property, Lot, Building, Party, Role, Snapshot, and the provenance properties |
| `core.shapes.ttl` | What the data must satisfy. Allowed values between `generated` markers are written from `vocab/*.ttl` by `scripts/sync_shape_values.py` |
| `generated/` | Cypher compiled from the shapes by `scripts/compile_shapes.py` (shacl2cypher). Committed; do not edit |

Domain modules (HPD and ACRIS in Slice 1, conditions in Slice 2, ownership layers in Slice 4) are separate pairs of files that import core.

Checks that SHACL cannot express are hand-written in `etl/checks/` (snapshot references, role attachment). A violation from any of them fails the build.

After changing a vocabulary or the shapes:

```
uv run python scripts/sync_shape_values.py
uv run --with shacl2cypher python scripts/compile_shapes.py
```

Record each modeling choice in `docs/design-notes/`.
