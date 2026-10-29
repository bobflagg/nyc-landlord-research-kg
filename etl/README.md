# etl/

Build pipeline: justfixwow snapshot → Neo4j (database `nyclr`, design note 0011).

| Module | What |
| --- | --- |
| `config.py` | Connection from `.env`. Refuses any database other than `nyclr` |
| `schema.py` | Node keys, relationship types, constraints and indexes, read from `ontology/` |
| `load.py` | Snapshot catalog node, batched `MERGE` of nodes on their key, structural edges. Labels and relationship types come from the ontology, never from data |
| `validate.py` | Runs the compiled SHACL checks (`ontology/generated/`) and the hand-written ones (`checks/`). Any row is a violation and fails the build |
| `sample.py` | The Slice 0 sample load (invented records, source `sample`) and a self-test |
| `run_build.py` | The build: `--modules hpd,acris,dos,litigation,violations,complaints,mortgages,references,bor` (see its docstring) |
| `bor.py` | A frozen BOR release: reading, the checks before a load (checksums, snapshot, source-table fingerprints), and the nodes and edges it becomes (design note 0024) |
| `bor_build.py` | Loads a verified BOR release in batches |

```
uv run python -m etl.sample              # load the sample, validate
uv run python -m etl.sample --selftest   # also add bad rows in a rolled-back transaction; each must trip its rule
```

Loads are re-runnable: a second run creates nothing new. Source readers for HPD, PLUTO and ACRIS come with the Slice 1 domain modules. Raw downloads go in `data/raw/` (gitignored).
