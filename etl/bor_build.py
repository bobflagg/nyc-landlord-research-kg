"""Load a verified BOR release into the graph (design note 0024). Batched; labels and relationship types come only from the ontology.

Order: run, groups, nodes, then the edges that need both ends, then decisions, evidence, link sets, masked addresses, metrics and
absences. Every edge is matched on keys; one whose end is not in the graph is counted, not made (the counts are the load report)."""
from collections import defaultdict
from datetime import date
from typing import Callable, Iterable

from etl import bor
from etl.load import _batches, apply_schema, load_nodes, register_snapshot
from etl.schema import Schema

BATCH = 5000


def load_edges_with(tx, schema: Schema, rel: str, src_label: str, dst_label: str, edges: Iterable[dict], merge_on: str | None = None) -> dict[str, int]:
    """MERGE edges between existing nodes, matched on their keys, with properties. `merge_on` names the property that tells two edges between the
    same pair apart (a link id, a role); with none, a pair has one edge. Returns the edges matched, created, and not made (an end missing)."""
    if rel not in schema.relationships:
        raise ValueError(f"unknown relationship type {rel}")
    sk, dk = schema.keys[src_label], schema.keys[dst_label]
    pattern = f"(a)-[r:`{rel}` {{`{merge_on}`: row.props.`{merge_on}`}}]->(b)" if merge_on else f"(a)-[r:`{rel}`]->(b)"
    q = (f"UNWIND $rows AS row MATCH (a:`{src_label}` {{`{sk}`: row.s}}) MATCH (b:`{dst_label}` {{`{dk}`: row.d}}) "
         f"MERGE {pattern} SET r += row.props RETURN count(r) AS matched")
    total = made = 0
    for chunk in _batches(edges, BATCH):
        res = tx.run(q, rows=chunk)
        matched = res.single()["matched"]
        made += res.consume().counters.relationships_created
        total += len(chunk) - matched
    return {"created": made, "not made (an end is not in the graph)": total}


def _write(session, fn: Callable, *args):
    return session.execute_write(fn, *args)


def _nodes(session, schema: Schema, label: str, rows: list[dict]) -> int:
    n = 0
    for chunk in _batches(rows, BATCH):
        n += session.execute_write(load_nodes, schema, label, chunk)
    return n


def _edges(session, schema: Schema, totals: dict, name: str, rel: str, src: str, dst: str, edges: Iterable[dict], merge_on: str | None = None) -> None:
    """One write transaction per batch (a citywide edge set is too big for one)."""
    made = missing = 0
    for chunk in _batches(edges, BATCH):
        r = session.execute_write(load_edges_with, schema, rel, src, dst, chunk, merge_on)
        made += r["created"]
        missing += r["not made (an end is not in the graph)"]
    totals[f"{name}"] = made
    if missing:
        totals[f"{name}: not made, an end is not in the graph"] = missing


def build_bor(session, schema: Schema, rel: "bor.Release", snapshot_id: str, snapshot_date: date, source_verified: bool, ensure_schema: bool = True) -> dict:
    """Idempotent: a second run creates nothing new. The Snapshot node is registered first (every fact names it). A test inside a
    transaction has applied the schema already (DDL cannot share a transaction with writes) and passes ensure_schema False."""
    if ensure_schema:
        apply_schema(session, schema)
    session.execute_write(register_snapshot, snapshot_id, "justfixwow", snapshot_date)
    totals: dict[str, int] = defaultdict(int)
    session.execute_write(load_nodes, schema, "BorRun", [bor.run_node(rel, snapshot_id, source_verified)])
    totals["BorRun"] = 1
    totals["BorGroup"] = _nodes(session, schema, "BorGroup", bor.group_nodes(rel, snapshot_id))
    totals["BorNode"] = _nodes(session, schema, "BorNode", bor.member_nodes(rel, snapshot_id))
    _edges(session, schema, totals, "IN_GROUP", "IN_GROUP", "BorNode", "BorGroup", bor.in_group_edges(rel))
    _edges(session, schema, totals, "MEMBER_OF", "MEMBER_OF", "Lot", "BorGroup", bor.member_of_edges(rel, snapshot_id), "link_id")
    covers, selected, candidates = bor.covers_edges(rel)
    _edges(session, schema, totals, "COVERS", "COVERS", "BorNode", "Lot", covers)
    _edges(session, schema, totals, "SELECTED_ROLE", "SELECTED_ROLE", "BorNode", "Role", selected, "bbl")
    _edges(session, schema, totals, "CANDIDATE_ROLE", "CANDIDATE_ROLE", "BorNode", "Role", candidates, "bbl")
    _edges(session, schema, totals, "WITNESS_STEP", "WITNESS_STEP", "BorNode", "BorNode", bor.witness_edges(rel, snapshot_id), "link_id")
    _edges(session, schema, totals, "NETWORK_EDGE", "NETWORK_EDGE", "BorNode", "BorNode", bor.network_edges(rel, snapshot_id), "link_id")
    totals["BorMaskedAddress"] = _nodes(session, schema, "BorMaskedAddress", bor.masked_address_nodes(rel, snapshot_id))
    uses, masked_by_bbl = bor.masked_address_uses(rel)
    _edges(session, schema, totals, "USES_ADDRESS", "USES_ADDRESS", "BorNode", "BorMaskedAddress", uses)
    totals["BorDecision"] = _nodes(session, schema, "BorDecision", bor.decision_nodes(rel, snapshot_id))
    d = bor.decision_edges(rel)
    _edges(session, schema, totals, "ABOUT_LOT", "ABOUT_LOT", "BorDecision", "Lot", d["ABOUT_LOT"], "role")
    _edges(session, schema, totals, "ABOUT_DOCUMENT", "ABOUT_DOCUMENT", "BorDecision", "Document", d["ABOUT_DOCUMENT"], "role")
    _edges(session, schema, totals, "ABOUT_GROUP", "ABOUT_GROUP", "BorDecision", "BorGroup", d["ABOUT_GROUP"], "role")
    _edges(session, schema, totals, "ABOUT_ADDRESS", "ABOUT_ADDRESS", "BorDecision", "BorMaskedAddress", d["ABOUT_ADDRESS"], "role")
    _edges(session, schema, totals, "SUPPORTED_BY", "SUPPORTED_BY", "BorDecision", "Role", d["SUPPORTED_BY"], "observation_id")
    totals["BorEvidence"] = _nodes(session, schema, "BorEvidence", bor.evidence_nodes(rel, snapshot_id))
    for_lot, cites = bor.evidence_edges(rel)
    _edges(session, schema, totals, "EVIDENCE_FOR", "EVIDENCE_FOR", "BorEvidence", "Lot", for_lot, "role")
    _edges(session, schema, totals, "CITES_DOCUMENT", "CITES_DOCUMENT", "BorEvidence", "Document", cites)
    totals["BorLinkSet"] = _nodes(session, schema, "BorLinkSet", bor.link_set_nodes(rel, snapshot_id))
    _edges(session, schema, totals, "HAS_MEMBER", "HAS_MEMBER", "BorLinkSet", "BorNode", bor.link_set_edges(rel))
    totals["BorMetric"] = _nodes(session, schema, "BorMetric", bor.metric_nodes(rel, snapshot_id))
    _edges(session, schema, totals, "NOT_IN_GROUP", "NOT_IN_GROUP", "Lot", "BorRun", bor.not_in_group_edges(rel, snapshot_id, masked_by_bbl), "layer")
    return dict(totals)
