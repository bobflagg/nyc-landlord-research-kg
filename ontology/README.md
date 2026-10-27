# ontology/

OWL modules and SHACL shapes (design note 0010).

| File | What |
| --- | --- |
| `core.ttl` | Core classes and properties: Property, Lot, Building, Party, Role, Snapshot, and the provenance properties |
| `core.shapes.ttl` | What the data must satisfy. Allowed values between `generated` markers are written from `vocab/*.ttl` by `scripts/sync_shape_values.py` |
| `pluto.ttl`, `pluto.shapes.ttl` | PLUTO lot attributes (design note 0014) |
| `hpd.ttl`, `hpd.shapes.ttl` | Registration, HPD party and role (design notes 0006, 0014) |
| `acris.ttl`, `acris.shapes.ttl` | Document, ACRIS party and role: deed family only (design note 0015) |
| `generated/` | Cypher compiled from the shapes by `scripts/compile_shapes.py` (shacl2cypher). Committed; do not edit |

Domain modules are separate pairs of files that import core: PLUTO, HPD and ACRIS now; DOS later in Slice 1, conditions in Slice 2, ownership layers in Slice 4.

Checks that SHACL cannot express are hand-written in `etl/checks/` (snapshot references, role attachment). A violation from any of them fails the build.

After changing a vocabulary or the shapes:

```
uv run python scripts/sync_shape_values.py
uv run --with shacl2cypher python scripts/compile_shapes.py
```

Record each modeling choice in `docs/design-notes/`.
