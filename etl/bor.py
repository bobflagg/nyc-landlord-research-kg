"""A frozen BOR release: reading, verification before a load, and the pure construction of nodes and edges (design note 0024).

BOR is the sibling project that produces the Owner Portfolio and Operational Network layers. Its release is a directory of
CSV files and a manifest. Nothing here imports BOR: the checks below follow its documented loader contract (docs/kg-mapping.md),
and the fingerprint SQL is copied from its documentation. A group is a lead, not legal ownership; every node built here is
Type II (reliability II, project_derived, unreviewed).
"""
import csv
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Callable, Iterator

from etl.schema import SNAPSHOT_ID
from etl.vocab import bor_term

SUPPORTED_SCHEMA = frozenset({"0.2.1"})
# Tiers of the source-table check (BOR kg-mapping, "What a loader checks"): the tables this graph also loads are required.
REQUIRED_TABLES = ("hpd_contacts", "hpd_registrations", "pluto_latest", "real_property_master", "real_property_legals", "real_property_parties")
WARN_TABLES = ("wow_landlords", "hpd_registrations_grouped_by_bbl_with_contacts")
SKIPPED_TABLES = ("landlords_with_connections",)   # built by BOR; matches only its own build
LAYERS = ("owner_portfolio", "operational_network")
NAME_FILES = ("node_names",)                       # the only name table this graph loads (O1, O5)


@dataclass(frozen=True)
class Check:
    name: str
    ok: bool
    detail: str = ""
    level: str = "error"          # error: refuse the load; warning: report it

    @property
    def refuses(self) -> bool:
        return not self.ok and self.level == "error"


class Release:
    """A release directory. Reads tables lazily; a table is a CSV named for it."""

    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.manifest = json.loads((self.path / "manifest.json").read_text())
        self.run_id: str = self.manifest["run_id"]
        self.name = self.path.name

    def rows(self, table: str) -> Iterator[dict]:
        with open(self.path / f"{table}.csv", newline="", encoding="utf-8") as f:
            yield from csv.DictReader(f)

    def manifest_sha256(self) -> str:
        return hashlib.sha256((self.path / "manifest.json").read_bytes()).hexdigest()


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def verify_release(rel: Release, snapshot_id: str, snapshot_date: date, fingerprint: Callable[[str], tuple[int, str]] | None = None,
                   basis: Callable[[], dict[str, str]] | None = None) -> list[Check]:
    """Every check of note 0024, O4. A check with `refuses` true stops the load. `fingerprint(table)` returns (row count, fingerprint) of
    the graph's own source table and `basis()` the newest value of each column behind the snapshot date; without them the source
    check is reported as not done (a warning), and the run records source_verified false."""
    m, out = rel.manifest, []
    add = lambda name, ok, detail="", level="error": out.append(Check(name, bool(ok), detail, level))
    add("schema version", m.get("schema_version") in SUPPORTED_SCHEMA, f"{m.get('schema_version')!r}, supported {sorted(SUPPORTED_SCHEMA)}")
    add("not synthetic", "synthetic" not in m, "a synthetic release is for tests and is never loaded")
    add("not an excerpt", "excerpt" not in m, "an excerpt leaves rows out")
    dirty = [k for k, v in (m.get("code") or {}).items() if isinstance(v, dict) and v.get("dirty")]
    add("built from clean trees", not dirty, f"dirty: {dirty}")
    sid = m.get("snapshot_id", "")
    add("snapshot id form", SNAPSHOT_ID.match(sid), sid)
    add("snapshot matches the graph", sid == snapshot_id and m.get("snapshot_date") == snapshot_date.isoformat(),
        f"release {sid} {m.get('snapshot_date')}, graph {snapshot_id} {snapshot_date}")
    checks = m.get("output_checksums") or {}
    bad = [f for f, want in checks.items() if not (rel.path / f).exists() or _sha256(rel.path / f) != want]
    add("file checksums", checks and not bad, f"{len(checks)} files; mismatched or missing: {bad}")
    unlisted = [t for t in _TABLES_READ if f"{t}.csv" not in checks]
    add("every table read is checksummed", not unlisted, f"not in output_checksums: {unlisted}")
    for table, col in (("groups", "assertion_key"), ("group_members", "assertion_key"), ("group_witness", "assertion_key")):
        wrong = sum(1 for r in rel.rows(table) if not r[col].startswith(rel.run_id + "/"))
        add(f"{table}: keys begin with the run id", wrong == 0, f"{wrong} rows do not")
    if fingerprint is None:
        add("source tables fingerprinted", False, "not checked: no source connection (source_verified will be false)", "warning")
    else:
        for t, tier in [(t, "error") for t in REQUIRED_TABLES] + [(t, "warning") for t in WARN_TABLES]:
            want = (m.get("source_tables") or {}).get(t)
            if not want:
                add(f"source table {t}", False, "not in the manifest", tier)
                continue
            n, fp = fingerprint(t)
            add(f"source table {t}", (n, str(fp)) == (want["row_count"], str(want["fingerprint"])),
                f"graph source {n} rows {fp}, release {want['row_count']} rows {want['fingerprint']}", tier)
    for key, got in (basis() if basis else {}).items():
        want = ((m.get("snapshot_date_basis") or {}).get(key) or {}).get("newest")
        add(f"snapshot date basis {key}", got == want, f"graph source {got}, release {want}")
    return out


def refusals(checks: list[Check]) -> list[Check]:
    return [c for c in checks if c.refuses]


_TABLES_READ = ("groups", "group_members", "group_bbls", "group_witness", "network_edges", "network_membership", "node_observations",
                "node_observation_alternatives", "node_names", "node_cluster", "node_cluster_alternatives", "decision_events", "decision_support",
                "evidence_items", "evidence_members", "link_sets", "link_set_members", "masked_addresses", "masked_address_nodes",
                "method_metrics", "bbl_status")


# ---- provenance and keys ---------------------------------------------------------------------------------

def node_provenance(run_id: str, snapshot_id: str, record_id: str) -> dict:
    """Type II (note 0005): derived by the project's method, unreviewed. `source` names BOR, `run_id` the frozen run."""
    return {"reliability": "II", "source_category": "project_derived", "review_status": "unreviewed", "source": "bor",
            "source_record_id": record_id, "snapshot_id": snapshot_id, "run_id": run_id}


def edge_provenance(snapshot_id: str, link_id: str) -> dict:
    return {"link_id": link_id, "reliability": "II", "source_category": "project_derived", "review_status": "unreviewed", "snapshot_id": snapshot_id}


def _clean(d: dict) -> dict:
    return {k: v for k, v in d.items() if v is not None and v != ""}


def _int(v) -> int | None:
    return None if v in (None, "") else int(float(v))


def _float(v) -> float | None:
    return None if v in (None, "") else float(v)


def _bool(v) -> bool | None:
    return None if v in (None, "") else str(v).strip().lower() in ("true", "1")


def observation_role_id(observation_id: str) -> str:
    """An observation is registration:contact:k; the graph's role for an HPD contact is hpd:<contact id> (join on ids, never names)."""
    return f"hpd:{observation_id.split(':')[1]}"


# ---- nodes -----------------------------------------------------------------------------------------------

def run_node(rel: Release, snapshot_id: str, source_verified: bool) -> dict:
    m = rel.manifest
    return _clean({
        "run_id": rel.run_id, **node_provenance(rel.run_id, snapshot_id, rel.run_id), "release_name": rel.name,
        "schema_version": m["schema_version"], "snapshot_date": date.fromisoformat(m["snapshot_date"]),
        "built_at": datetime.fromisoformat(m["created_at"]) if m.get("created_at") else None,
        "bor_revision": m["bor_revision"], "nlr_revision": m["nlr_revision"], "manifest_sha256": rel.manifest_sha256(),
        "threshold": float(m["threshold"]), "stage_vocabulary_version": m["stage_vocabulary_version"],
        "reason_vocabulary_version": m["reason_vocabulary_version"],
        "gold_status": bor_term("gold-status", ((m.get("diagnostics") or {}).get("evaluation") or {}).get("gold_status", "none")),
        "source_verified": source_verified})


def group_nodes(rel: Release, snapshot_id: str) -> list[dict]:
    return [_clean({"assertion_key": r["assertion_key"], **node_provenance(rel.run_id, snapshot_id, r["assertion_key"]),
                    "layer": r["layer"], "group_id": r["group_id"], "composition": r["composition"], "split": r["split"],
                    "lot_count": _int(r["lot_count"]), "total_lot_count": _int(r["total_lot_count"]),
                    "witness_pieces": _int(r["witness_pieces"]), "anchor_node_id": r["anchor_node_id"]}) for r in rel.rows("groups")]


def member_nodes(rel: Release, snapshot_id: str) -> list[dict]:
    """The nodes that sit in a group (46,547 of 118,493, O1), with the landlord name as filed (display only), the cluster they were
    assigned and, for a network, the component and community. Straddling nodes keep every cluster they matched, with the votes."""
    wanted = {(r["layer"], r["node_id"]): r for r in rel.rows("group_members")}
    ids = {n for _, n in wanted}
    names = {r["node_id"]: r["name"] for r in rel.rows("node_names") if r["node_id"] in ids}
    cluster = {r["node_id"]: r for r in rel.rows("node_cluster") if r["node_id"] in ids}
    alts: dict[str, list[str]] = {}
    for r in rel.rows("node_cluster_alternatives"):
        if r["node_id"] in ids:
            alts.setdefault(r["node_id"], []).append(f"{r['cluster_id']}:{r['votes']}:{'selected' if _bool(r['selected']) else 'other'}")
    network = {r["node_id"]: r for r in rel.rows("network_membership") if r["node_id"] in ids}
    out = []
    for (layer, node_id), r in wanted.items():
        c, nm = cluster.get(node_id), network.get(node_id) if layer == "operational_network" else None
        out.append(_clean({
            "assertion_key": r["assertion_key"], **node_provenance(rel.run_id, snapshot_id, r["assertion_key"]),
            "layer": layer, "group_id": r["group_id"], "node_id": node_id, "node_name": names.get(node_id),
            "component_id": nm["component_id"] if nm else None, "community_id": nm["community_id"] if nm else None,
            "cluster_id": c["cluster_id"] if c else None, "n_clusters": _int(c["n_clusters"]) if c else None,
            "cluster_tied": _bool(c["tied"]) if c else None,
            "cluster_alternatives": alts.get(node_id) if c and _int(c["n_clusters"]) > 1 else None}))
    return out


def node_keys(rel: Release) -> dict[tuple[str, str], str]:
    """(layer, node id) to the assertion key of the node in that layer."""
    return {(r["layer"], r["node_id"]): r["assertion_key"] for r in rel.rows("group_members")}


def decision_nodes(rel: Release, snapshot_id: str) -> list[dict]:
    out = []
    for r in rel.rows("decision_events"):
        key = f"{rel.run_id}/{r['decision_id']}"
        out.append(_clean({
            "decision_key": key, **node_provenance(rel.run_id, snapshot_id, key), "decision_id": r["decision_id"], "layer": r["layer"],
            "stage": bor_term("link-stage", r["stage"]), "subject_type": r["subject_type"], "subject_id": r["subject_id"],
            "counterpart_type": r["counterpart_type"], "counterpart_id": r["counterpart_id"], "outcome": bor_term("decision-outcome", r["outcome"]),
            "reason_code": bor_term("absence-reason", r["reason_code"]) if r["reason_code"] else None, "rule": r["rule"], "rule_version": r["rule_version"],
            "score": _float(r["score"]), "decision_threshold": _float(r["threshold"]), "cluster_id": r["cluster_id"], "detail": r["detail"]}))
    return out


def evidence_nodes(rel: Release, snapshot_id: str) -> list[dict]:
    out = []
    for r in rel.rows("evidence_items"):
        key = f"{rel.run_id}/{r['evidence_id']}"
        out.append(_clean({"evidence_key": key, **node_provenance(rel.run_id, snapshot_id, key), "evidence_id": r["evidence_id"],
                           "stage": bor_term("link-stage", r["stage"]), "document_id": r["document_id"], "parcel_count": _int(r["parcel_count"]),
                           "rule_version": r["rule_version"]}))
    return out


def link_set_nodes(rel: Release, snapshot_id: str) -> list[dict]:
    out = []
    for r in rel.rows("link_sets"):
        key = f"{rel.run_id}/{r['set_id']}"
        out.append(_clean({"set_key": key, **node_provenance(rel.run_id, snapshot_id, key), "set_id": r["set_id"], "stage": bor_term("link-stage", r["stage"]),
                           "rule": r["rule"], "rule_version": r["rule_version"], "size": _int(r["size"])}))
    return out


def masked_address_nodes(rel: Release, snapshot_id: str) -> list[dict]:
    out = []
    for r in rel.rows("masked_addresses"):
        key = f"{rel.run_id}/{r['address_id']}"
        out.append(_clean({"masked_address_key": key, **node_provenance(rel.run_id, snapshot_id, key), "address_id": r["address_id"], "method": r["method"],
                           "normalizer_version": r["normalizer_version"], "degree": _int(r["degree"]), "degree_unit": r["degree_unit"],
                           "mask_threshold": _int(r["threshold"]), "address_text": r["address"]}))
    return out


def metric_nodes(rel: Release, snapshot_id: str) -> list[dict]:
    out = []
    for r in rel.rows("method_metrics"):
        key = f"{rel.run_id}/{r['stage']}/{r['metric']}"
        out.append(_clean({
            "metric_key": key, **node_provenance(rel.run_id, snapshot_id, key), "stage": bor_term("link-stage", r["stage"]), "metric": r["metric"],
            "unit": r["unit"], "population": r["population"], "sample_n": _int(r["n"]), "numerator": _int(r["numerator"]),
            "denominator": _int(r["denominator"]), "precision": _float(r["precision"]), "ci_lower": _float(r["ci_lower"]),
            "ci_upper": _float(r["ci_upper"]), "confidence_level": _float(r["confidence_level"]), "interval_method": r["interval_method"],
            "estimator": r["estimator"], "strata_ref": r["strata_ref"], "eval_artifact": r["eval_artifact"], "eval_version": r["eval_version"],
            "adjudication_status": bor_term("gold-status", r["adjudication_status"]), "provisional": _bool(r["provisional"]), "metric_note": r["note"]}))
    return out


# ---- edges: each is {"s": source key, "d": target key, "props": {...}} ------------------------------------

def _edge(s: str, d: str, **props) -> dict:
    return {"s": s, "d": d, "props": _clean(props)}


def in_group_edges(rel: Release) -> list[dict]:
    return [_edge(r["assertion_key"], f"{rel.run_id}/{r['layer']}/{r['group_id']}") for r in rel.rows("group_members")]


def member_of_edges(rel: Release, snapshot_id: str) -> list[dict]:
    """A lot's membership of a group (O2). A lot outside the published rental footprint (rental false) keeps its membership and
    carries the reason BOR gives, coop_condo_excluded."""
    out = []
    for r in rel.rows("group_bbls"):
        key = f"{rel.run_id}/{r['layer']}/{r['group_id']}"
        rental = _bool(r["rental"])
        out.append(_edge(r["bbl"], key, **edge_provenance(snapshot_id, f"{key}#{r['bbl']}"), rental=rental,
                         reason_code=None if rental else bor_term("absence-reason", "coop_condo_excluded")))
    return out


def covers_edges(rel: Release) -> tuple[list[dict], list[dict], list[dict]]:
    """COVERS (node to lot), SELECTED_ROLE and CANDIDATE_ROLE, for each layer the node is a member of (O6). An ambiguous (node, lot) row
    has no selected contact (642 rows): it is shown as ambiguous, with every tied candidate, not hidden."""
    keys = node_keys(rel)
    layers: dict[str, list[str]] = {}
    for layer, node_id in keys:
        layers.setdefault(node_id, []).append(layer)
    alt: dict[tuple[str, str], list[str]] = {}
    for r in rel.rows("node_observation_alternatives"):
        if r["node_id"] in layers:
            alt.setdefault((r["node_id"], r["bbl"]), []).append(r["observation_id"])
    covers, selected, candidates = [], [], []
    for r in rel.rows("node_observations"):
        if r["node_id"] not in layers:
            continue
        ambiguous = _bool(r["ambiguous"])
        for layer in layers[r["node_id"]]:
            nk = keys[(layer, r["node_id"])]
            covers.append(_edge(nk, r["bbl"], registration_id=r["registration_id"], n_candidates=_int(r["n_candidates"]), ambiguous=ambiguous))
            if r["selected_observation_id"]:        # an ambiguous row selects none: BOR lists every tied candidate instead
                selected.append(_edge(nk, observation_role_id(r["selected_observation_id"]), bbl=r["bbl"], observation_id=r["selected_observation_id"]))
            for obs in alt.get((r["node_id"], r["bbl"]), []):
                if obs != r["selected_observation_id"]:
                    candidates.append(_edge(nk, observation_role_id(obs), bbl=r["bbl"], observation_id=obs))
    return covers, selected, candidates


def witness_edges(rel: Release, snapshot_id: str) -> list[dict]:
    keys = node_keys(rel)
    return [_edge(keys[(r["layer"], r["node_a"])], keys[(r["layer"], r["node_b"])], **edge_provenance(snapshot_id, r["assertion_key"]), step=_int(r["step"]),
                  stage=bor_term("link-stage", r["stage"]), basis_type=r["basis_type"], basis_id=r["basis_id"]) for r in rel.rows("group_witness")]


def network_edges(rel: Release, snapshot_id: str) -> list[dict]:
    keys = node_keys(rel)
    return [_edge(keys[("operational_network", r["node_a"])], keys[("operational_network", r["node_b"])],
                  **edge_provenance(snapshot_id, f"{rel.run_id}/operational_network/{r['edge_id']}"), edge_id=r["edge_id"], component_id=r["component_id"],
                  name_weight=_float(r["name_weight"]), address_weight=_float(r["address_weight"]), identity_weight=_float(r["identity_weight"]),
                  weight=_float(r["weight"]), crosses_networks=_bool(r["crosses_networks"])) for r in rel.rows("network_edges")]


def masked_address_uses(rel: Release) -> tuple[list[dict], dict[str, str]]:
    """USES_ADDRESS from each loaded network node to its masked address, and the masked address of each lot of a node that uses one
    (so a lot left out of a group can say which address was masked)."""
    keys = node_keys(rel)
    by_node = {r["node_id"]: f"{rel.run_id}/{r['address_id']}" for r in rel.rows("masked_address_nodes")}
    edges = [_edge(keys[("operational_network", n)], a) for n, a in by_node.items() if ("operational_network", n) in keys]
    by_bbl = {r["bbl"]: by_node[r["node_id"]] for r in rel.rows("node_observations") if r["node_id"] in by_node}
    return edges, by_bbl


def decision_edges(rel: Release) -> dict[str, list[dict]]:
    """Edges from decisions to the lots, deeds, groups and addresses they are about, and to the HPD contacts they rest on. Decisions on
    identities and clusters have no edge: their cluster id is a property (identities are not nodes, note 0007)."""
    out: dict[str, list[dict]] = {"ABOUT_LOT": [], "ABOUT_DOCUMENT": [], "ABOUT_GROUP": [], "ABOUT_ADDRESS": [], "SUPPORTED_BY": []}
    for r in rel.rows("decision_events"):
        dk = f"{rel.run_id}/{r['decision_id']}"
        for kind, ident, role in ((r["subject_type"], r["subject_id"], "subject"), (r["counterpart_type"], r["counterpart_id"], "counterpart")):
            if kind == "bbl":
                out["ABOUT_LOT"].append(_edge(dk, ident, role=role))
            elif kind == "deed_document":
                out["ABOUT_DOCUMENT"].append(_edge(dk, ident, role=role))
            elif kind == "group":
                out["ABOUT_GROUP"].append(_edge(dk, f"{rel.run_id}/{r['layer']}/{ident}", role=role))
            elif kind == "parcel":
                out["ABOUT_LOT"].append(_edge(dk, ident, role=role))
            elif kind == "address":
                out["ABOUT_ADDRESS"].append(_edge(dk, f"{rel.run_id}/{ident}", role=role))
    for r in rel.rows("decision_support"):
        dk = f"{rel.run_id}/{r['decision_id']}"
        if r["support_type"] == "observation":
            out["SUPPORTED_BY"].append(_edge(dk, observation_role_id(r["support_id"]), role=r["role"], observation_id=r["support_id"]))
        elif r["support_type"] == "bbl":
            out["ABOUT_LOT"].append(_edge(dk, r["support_id"], role=r["role"]))
        elif r["support_type"] == "document":
            out["ABOUT_DOCUMENT"].append(_edge(dk, r["support_id"], role=r["role"]))
    return out


def evidence_edges(rel: Release) -> tuple[list[dict], list[dict]]:
    for_lot = [_edge(f"{rel.run_id}/{r['evidence_id']}", r["bbl"], role=r["role"], node_id=r["node_id"], original_document_id=r["original_document_id"],
                     latest_document_id=r["latest_document_id"], latest_amount=_float(r["latest_amount"]), excluded_reason=r["excluded_reason"])
               for r in rel.rows("evidence_members")]
    cites = [_edge(f"{rel.run_id}/{r['evidence_id']}", r["document_id"]) for r in rel.rows("evidence_items")]
    return for_lot, cites


def link_set_edges(rel: Release) -> list[dict]:
    keys = node_keys(rel)
    return [_edge(f"{rel.run_id}/{r['set_id']}", keys[("owner_portfolio", r["node_id"])], source_bbl=r["source_bbl"])
            for r in rel.rows("link_set_members") if ("owner_portfolio", r["node_id"]) in keys]


def not_in_group_edges(rel: Release, snapshot_id: str, masked_by_bbl: dict[str, str]) -> Iterator[dict]:
    """A lot with no group in a layer, with BOR's reason (O1). The 1.36M lots HPD does not register (no_registration) are not loaded: the
    graph's own HPD data answers them. An excluded_from_footprint row is a membership (rental false), not an absence."""
    for r in rel.rows("bbl_status"):
        if r["status"] != "not_in_group" or r["reason_code"] == "no_registration":
            continue
        layer = r["layer"]
        yield _edge(r["bbl"], rel.run_id, **edge_provenance(snapshot_id, f"{rel.run_id}/{layer}/absence#{r['bbl']}"), layer=layer,
                    reason_code=bor_term("absence-reason", r["reason_code"]), top_level_reason=bor_term("absence-reason", r["top_level_reason"]),
                    masked_address_key=masked_by_bbl.get(r["bbl"]) if layer == "operational_network" else None)
