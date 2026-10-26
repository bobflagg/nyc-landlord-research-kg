"""Snapshot-tagged, batched loading. Cypher is parameterized; labels and relationship types come only from the
ontology (Schema), never from data. MERGE only on the constrained key property."""
from datetime import date
from itertools import islice
from typing import Iterable, Iterator

from etl.schema import SNAPSHOT_ID, Schema

BATCH = 1000


def _batches(rows: Iterable[dict], size: int = BATCH) -> Iterator[list[dict]]:
    it = iter(rows)
    while chunk := list(islice(it, size)):
        yield chunk


def apply_schema(tx_or_session, schema: Schema) -> None:
    for stmt in [*schema.constraints(), *schema.indexes()]:
        tx_or_session.run(stmt).consume()


def register_snapshot(tx, snapshot_id: str, source: str, snapshot_date: date) -> None:
    """Create the catalog node every fact's snapshot_id must refer to (note 0008)."""
    if not SNAPSHOT_ID.match(snapshot_id):
        raise ValueError(f"bad snapshot id: {snapshot_id!r}")
    base = f"{source}-{snapshot_date.isoformat()}"
    if snapshot_id != base and not snapshot_id.startswith(base + "-r"):
        raise ValueError(f"snapshot id {snapshot_id!r} does not match source {source!r} and date {snapshot_date}")
    tx.run(
        "MERGE (s:Snapshot {snapshot_id: $id}) SET s.source = $source, s.snapshot_date = $date",
        id=snapshot_id, source=source, date=snapshot_date,
    ).consume()


def load_nodes(tx, schema: Schema, label: str, rows: Iterable[dict]) -> int:
    """MERGE nodes on the label's key. Each row is a flat dict that includes the key and the provenance properties."""
    key = schema.keys[label]
    n = 0
    for chunk in _batches(rows):
        tx.run(
            f"UNWIND $rows AS row MERGE (n:`{label}` {{`{key}`: row.`{key}`}}) SET n += row",
            rows=chunk,
        ).consume()
        n += len(chunk)
    return n


def load_edges(tx, schema: Schema, rel: str, src_label: str, dst_label: str, pairs: Iterable[tuple[str, str]]) -> int:
    """MERGE structural edges (no provenance, note 0010 item 4) between existing nodes, matched on their keys."""
    if rel not in schema.relationships:
        raise ValueError(f"unknown relationship type {rel}")
    sk, dk = schema.keys[src_label], schema.keys[dst_label]
    n = 0
    for chunk in _batches({"s": s, "d": d} for s, d in pairs):
        res = tx.run(
            f"UNWIND $rows AS row MATCH (a:`{src_label}` {{`{sk}`: row.s}}) MATCH (b:`{dst_label}` {{`{dk}`: row.d}}) "
            f"MERGE (a)-[:`{rel}`]->(b)",
            rows=chunk,
        )
        n += res.consume().counters.relationships_created
    return n
