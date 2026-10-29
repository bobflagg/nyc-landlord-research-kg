"""Cut a small, self-consistent piece of a BOR release for the loader tests (design note 0024).

  uv run python scripts/cut_bor_release.py [release dir]

Writes tests/fixtures/bor_cut/: the groups of anchors C and D and a few that show each kind of evidence (a deed-bridged portfolio, a Louvain
community, a link set, a deed bundle, an ambiguous node, a straddling node, a masked address), the rows that explain them, and a sample of absences
(one lot per reason). The run id is renamed to a test run so the cut never collides with the citywide load, node names are replaced with
placeholders (the cut is a test of structure, not a copy of anyone's name), and the checksums are rewritten for the cut's own files."""
import csv
import hashlib
import json
import shutil
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT.parent / "beneficial-ownership-resolution" / "release" / "v0.2.1"
OUT = ROOT / "tests" / "fixtures" / "bor_cut"
TEST_RUN = "2000-01-01-0cafe000"

KEEP = {("owner_portfolio", g) for g in ("OP-98617", "OP-53559", "OP-5346", "OP-25108", "OP-5292", "OP-101271", "OP-31855", "OP-103727")} | \
       {("operational_network", g) for g in ("ON-98617", "ON-18742", "ON-60782", "ON-102796", "ON-103175", "ON-105266", "ON-101079")}
TABLES = ("groups", "group_members", "group_bbls", "group_witness", "network_edges", "network_membership", "node_observations",
          "node_observation_alternatives", "node_names", "node_cluster", "node_cluster_alternatives", "decision_events", "decision_support",
          "evidence_items", "evidence_members", "link_sets", "link_set_members", "masked_addresses", "masked_address_nodes", "method_metrics", "bbl_status")
ANCHORS_UNLINKED = ("A", "B", "E", "F", "G")


def read(t):
    with open(SRC / f"{t}.csv", newline="") as f:
        r = csv.DictReader(f)
        return r.fieldnames, list(r)


def main() -> None:
    data = {t: read(t) for t in TABLES}
    rows = lambda t: data[t][1]
    groups = [r for r in rows("groups") if (r["layer"], r["group_id"]) in KEEP]
    keep = {(r["layer"], r["group_id"]) for r in groups}
    members = [r for r in rows("group_members") if (r["layer"], r["group_id"]) in keep]
    bbls = [r for r in rows("group_bbls") if (r["layer"], r["group_id"]) in keep]
    witness = [r for r in rows("group_witness") if (r["layer"], r["group_id"]) in keep]
    nodes = {r["node_id"] for r in members}
    on_nodes = {r["node_id"] for r in members if r["layer"] == "operational_network"}
    lots = {r["bbl"] for r in bbls}
    # absences: one lot per (layer, reason), then the lots of an unlinked anchor are added by the tests from their own data
    absent, seen = [], set()
    for r in rows("bbl_status"):
        k = (r["layer"], r["reason_code"])
        if r["status"] != "in_group" and k not in seen:
            seen.add(k)
            absent.append(r)
    status = [r for r in rows("bbl_status") if r["bbl"] in lots] + absent
    masked_nodes_all = defaultdict(list)
    for r in rows("masked_address_nodes"):
        masked_nodes_all[r["node_id"]].append(r["address_id"])
    # the node of an absent lot that uses a masked address, so the lot can name it
    obs_by_bbl = {r["bbl"]: r["node_id"] for r in rows("node_observations")}
    absent_nodes = {obs_by_bbl[r["bbl"]] for r in absent if r["bbl"] in obs_by_bbl and obs_by_bbl[r["bbl"]] in masked_nodes_all}
    addr_ids = {a for n in nodes | absent_nodes for a in masked_nodes_all.get(n, [])}
    clusters = {r["cluster_id"] for r in rows("node_cluster") if r["node_id"] in nodes}
    basis = defaultdict(set)
    for r in witness:
        basis[r["basis_type"]].add(r["basis_id"])
    ev_ids = basis["evidence_item"] | {r["evidence_id"] for r in rows("evidence_members") if r["bbl"] in lots}
    evidence = [r for r in rows("evidence_items") if r["evidence_id"] in ev_ids]
    ev_docs = {r["document_id"] for r in evidence}
    set_ids = basis["link_set"]
    cut: dict[str, list] = {
        "groups": groups, "group_members": members, "group_bbls": bbls, "group_witness": witness,
        "network_edges": [r for r in rows("network_edges") if r["node_a"] in on_nodes and r["node_b"] in on_nodes],
        "network_membership": [r for r in rows("network_membership") if r["node_id"] in on_nodes],
        "node_observations": [r for r in rows("node_observations") if r["node_id"] in nodes | absent_nodes],
        "node_observation_alternatives": [r for r in rows("node_observation_alternatives") if r["node_id"] in nodes],
        "node_names": [dict(r, name=f"TEST NAME {r['node_id']}") for r in rows("node_names") if r["node_id"] in nodes],
        "node_cluster": [r for r in rows("node_cluster") if r["node_id"] in nodes],
        "node_cluster_alternatives": [r for r in rows("node_cluster_alternatives") if r["node_id"] in nodes],
        "evidence_items": evidence, "evidence_members": [r for r in rows("evidence_members") if r["evidence_id"] in ev_ids],
        "link_sets": [r for r in rows("link_sets") if r["set_id"] in set_ids], "link_set_members": [r for r in rows("link_set_members") if r["set_id"] in set_ids],
        "masked_addresses": [r for r in rows("masked_addresses") if r["address_id"] in addr_ids],
        "masked_address_nodes": [r for r in rows("masked_address_nodes") if r["address_id"] in addr_ids],
        "method_metrics": rows("method_metrics"), "bbl_status": status,
    }
    ev = []
    for r in rows("decision_events"):
        ids = {r["subject_id"], r["counterpart_id"]}
        if (r["cluster_id"] and r["cluster_id"] in clusters) or ids & lots or (ids & {g for _, g in keep}) or (ids & addr_ids) or (r["subject_type"] == "deed_document" and r["subject_id"] in ev_docs) \
                or (r["counterpart_type"] == "deed_document" and r["counterpart_id"] in ev_docs):
            ev.append(r)
    cut["decision_events"] = ev
    dids = {r["decision_id"] for r in ev}
    cut["decision_support"] = [r for r in rows("decision_support") if r["decision_id"] in dids]

    shutil.rmtree(OUT, ignore_errors=True)
    OUT.mkdir(parents=True)
    old = json.loads((SRC / "manifest.json").read_text())["run_id"]
    for t in TABLES:
        fields = data[t][0]
        with open(OUT / f"{t}.csv", "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
            w.writeheader()
            for r in cut[t]:
                w.writerow({k: (v.replace(old, TEST_RUN) if k == "assertion_key" else v) for k, v in r.items()})
        print(f"{t}: {len(cut[t])}")
    (OUT / "DATA.md").write_text(f"A cut of BOR release {old} for the loader tests (scripts/cut_bor_release.py). The run id is renamed {TEST_RUN}; names are placeholders.\n")
    m = json.loads((SRC / "manifest.json").read_text())
    m["run_id"] = TEST_RUN
    m["output_checksums"] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(OUT.glob("*")) if p.name != "manifest.json"}
    (OUT / "manifest.json").write_text(json.dumps(m, indent=1, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
