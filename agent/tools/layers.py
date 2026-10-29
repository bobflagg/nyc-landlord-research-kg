"""Q8, Q9, Q10 and Q19: the Owner Portfolio and Operational Network layers of a BOR run (design note 0024). Read-only, parameterized.

Everything here is Type II: derived by the project's method, a lead and not legal ownership. The counting unit is the tax lot. A name is the
landlord name as filed, display only, and a group's anchor is the member with the most lots, not an owner. A precision belongs to a stage of the
method on a sample, with its interval and the status of the gold behind it; it is never the chance that a link is right. An absence describes
what the method did or did not use; it is never evidence that no relationship exists or that the owners differ."""
from langchain.tools import tool

from agent.db import read_session
from agent.tools.records import _clean, _plain, snapshot
from etl.vocab import bor_meaning

LAYERS = {"owner_portfolio": "Owner Portfolio", "operational_network": "Operational Network"}
OTHER = {"owner_portfolio": "operational_network", "operational_network": "owner_portfolio"}
WHAT_IT_IS = {
    "owner_portfolio": "An Owner Portfolio links landlord records that BOR judges to be one resolved owner, by identity matches between HPD owner contacts and by multi-parcel deeds. It is the stricter layer.",
    "operational_network": "An Operational Network links landlord records by accepted edges: a shared business address (unless the address is shared by too many records and is masked), a shared name, or an identity link. It is looser by design than an Owner Portfolio.",
}
BOROUGH = {"1": "Manhattan", "2": "Bronx", "3": "Brooklyn", "4": "Queens", "5": "Staten Island"}

CAVEATS = [
    "A group is a lead, not a determination of legal ownership. It is derived by the project's method (reliability II) from HPD registrations, deeds and addresses, and has not been reviewed by a person.",
    "The counting unit is the tax lot (BBL). Buildings are the buildings the graph holds on those lots and units are PLUTO's residential units, with the lots that have no unit count reported; "
    "a lot count is never a building count.",
    "A name is the landlord name as filed, shown for display with its source. It does not assert a role. The group's anchor is the member with the most lots, a label for the group and not an owner.",
    "A published precision is a property of one stage of the method on a sample, with its interval and the status of the gold behind it (provisional unless blind human adjudication). "
    "It is not the chance that a particular link is right, and a group's path chains several links.",
    "Being left out of a group, or in a different group, is not evidence that the owners differ. An absence says what the method used or did not use.",
]
COUNT_NOTE = ("lots counts the tax lots in the published rental footprint; lots_outside_rental_footprint are co-op or condo lots BOR leaves out of it and are counted apart. "
              "A lot can hold several buildings and a lot HPD does not register has none, so buildings is not lots.")

RUN = """
MATCH (r:BorRun) WHERE $run IS NULL OR r.run_id = $run
RETURN r {.run_id, .release_name, .schema_version, .snapshot_id, .snapshot_date, .built_at, .bor_revision, .threshold, .gold_status, .source_verified} AS r
ORDER BY r.built_at DESC, r.run_id DESC LIMIT 1
"""
METRICS = """
MATCH (m:BorMetric {run_id: $run}) WHERE m.stage IN $stages
RETURN m {.stage, .metric, .population, .sample_n, .precision, .ci_lower, .ci_upper, .confidence_level, .interval_method, .adjudication_status, .provisional, .metric_note} AS m
ORDER BY m.stage, m.metric
"""
LOT = "MATCH (l:Lot {bbl: $bbl}) RETURN l {.bbl, .address_text, .building_class, .units_residential} AS l"
MEMBERSHIP = """
MATCH (l:Lot {bbl: $bbl})-[m:MEMBER_OF]->(g:BorGroup {run_id: $run, layer: $layer})
RETURN g {.assertion_key, .group_id, .layer, .composition, .split, .lot_count, .total_lot_count, .witness_pieces, .anchor_node_id} AS g, m {.rental, .reason_code, .link_id} AS m
"""
GROUP_LOTS = """
MATCH (g:BorGroup {assertion_key: $key})<-[m:MEMBER_OF]-(l:Lot)
OPTIONAL MATCH (b:Building)-[:ON_LOT]->(l)
WITH l, m, count(b) AS buildings
RETURN l.bbl AS bbl, l.address_text AS address, l.building_class AS building_class, l.units_residential AS units, m.rental AS rental, buildings
ORDER BY bbl
"""
GROUP_NODES = """
MATCH (g:BorGroup {assertion_key: $key})<-[:IN_GROUP]-(n:BorNode)
OPTIONAL MATCH (n)-[c:COVERS]->(:Lot)
WITH n, count(c) AS lots, sum(CASE WHEN c.ambiguous THEN 1 ELSE 0 END) AS ambiguous_lots
RETURN n {.node_id, .node_name, .component_id, .community_id, .cluster_id, .n_clusters, .cluster_tied, .cluster_alternatives} AS n, lots, ambiguous_lots
ORDER BY lots DESC, n.node_id
"""
SIGNALS = """
MATCH (a:BorNode {run_id: $run, layer: $layer, group_id: $gid})-[w:WITNESS_STEP]->(:BorNode)
RETURN w.stage AS stage, w.basis_type AS basis_type, count(w) AS steps
ORDER BY steps DESC, stage
"""
NETWORK_EDGES_WITHIN = """
MATCH (a:BorNode {run_id: $run, layer: 'operational_network', group_id: $gid})-[e:NETWORK_EDGE]-(b:BorNode)
WITH e, a, b WHERE b.group_id = $gid AND a.node_id < b.node_id
RETURN e {.edge_id, .name_weight, .address_weight, .identity_weight, .weight, .crosses_networks, .component_id} AS e,
       a {.node_id, .node_name} AS a, b {.node_id, .node_name} AS b
ORDER BY e.weight DESC, e.edge_id
"""
NETWORK_EDGES_CROSSING = """
MATCH (a:BorNode {run_id: $run, layer: 'operational_network', group_id: $gid})-[e:NETWORK_EDGE]-(b:BorNode)
WHERE b.group_id <> $gid
RETURN e.edge_id AS edge_id, b.group_id AS other_group, e.crosses_networks AS crosses_networks, e.weight AS weight
ORDER BY other_group, edge_id
"""
OTHER_LAYER_LOTS = """
MATCH (:Lot {bbl: $bbl})-[:MEMBER_OF]->(g:BorGroup {run_id: $run, layer: $layer})
MATCH (g)<-[:MEMBER_OF]-(l:Lot)
RETURN g.group_id AS group_id, g.assertion_key AS key, g.lot_count AS lot_count, g.composition AS composition, g.split AS split, collect(l.bbl) AS bbls
"""
ABSENCES = """
MATCH (:Lot {bbl: $bbl})-[n:NOT_IN_GROUP]->(:BorRun {run_id: $run})
RETURN n {.layer, .reason_code, .top_level_reason, .masked_address_key, .link_id} AS n ORDER BY n.layer
"""
MASKED = "MATCH (a:BorMaskedAddress {masked_address_key: $key}) RETURN a {.address_id, .address_text, .degree, .degree_unit, .mask_threshold, .method} AS a"
REGISTERED = "MATCH (:Lot {bbl: $bbl})<-[:ON_LOT]-(r:Registration) RETURN count(r) AS n"
CROSSING_NOTE = "crosses_networks marks an accepted edge whose ends ended up in different Operational Networks after a split."


def active_run(runner, run_id: str | None = None) -> dict | None:
    r = runner.run(RUN, run=run_id).single()
    return _clean(r["r"]) if r else None


def precision_notes(runner, run_id: str, stages: list[str]) -> list[dict]:
    """The published precision of each stage a result used, as stored, with its interval and the status of the gold. A stage with no estimate says
    so and why. The long notes of the release are not repeated per row: how_to_read says it once."""
    out, seen_none, rows = [], set(), runner.run(METRICS, run=run_id, stages=sorted(set(stages))).data()
    by_stage: dict[str, dict] = {}
    for r in rows:
        by_stage.setdefault(r["m"]["stage"], {})[r["m"]["metric"]] = r["m"]
    for stage, ms in by_stage.items():
        have = {k: m for k, m in ms.items() if m.get("precision") is not None}
        if not have:
            first = next(iter(ms.values()))
            out.append(_clean({"stage": stage, "estimate": "none: this stage was not evaluated, which is not the same as no problem", "why": first.get("metric_note"),
                               "adjudication_status": first["adjudication_status"]}))
            continue
        vals = {(round(m["precision"], 3), round(m["ci_lower"], 3), round(m["ci_upper"], 3)) for m in have.values()}
        for name, m in ([("precision_strict and precision_inclusive", next(iter(have.values())))] if len(vals) == 1 and len(have) == 2 else have.items()):
            out.append(_clean({"stage": stage, "metric": name, "precision": round(m["precision"], 3), "interval_95": [round(m["ci_lower"], 3), round(m["ci_upper"], 3)],
                               "pairs_sampled": m.get("sample_n"), "population": m.get("population"), "adjudication_status": m["adjudication_status"], "provisional": m["provisional"]}))
    return out


HOW_TO_READ_PRECISION = ("A published precision is the share of sampled pairs judged the same owner in one stratum, on one snapshot, with a Wilson 95% interval. precision_strict counts pairs "
                         "corroborated across sources; precision_inclusive adds same-source pairs that were verified. The gold is human_llm_provisional (one human annotator, an LLM second "
                         "reader and an LLM-run resolution of their disagreements; blind human re-adjudication is pending). It is not the chance that any one link is right, and a group's "
                         "path chains several pairs.")


def lot_absence(runner, bbl: str, run_id: str, layer: str | None = None) -> list[dict]:
    """Why a lot is in no group, from the rows BOR wrote for it (and, for a lot HPD does not register, from the graph's own HPD data, which BOR's
    contract allows). Each absence names the layer, BOR's reason code and its top-level reason with their meanings."""
    rows = [r["n"] for r in runner.run(ABSENCES, bbl=bbl, run=run_id).data()]
    out = []
    for n in rows:
        if layer and n["layer"] != layer:
            continue
        item = {"layer": n["layer"], "reason": bor_meaning("absence-reason", n["reason_code"]), "top_level_reason": bor_meaning("absence-reason", n["top_level_reason"])}
        if n.get("masked_address_key"):
            a = runner.run(MASKED, key=n["masked_address_key"]).single()
            if a:
                a = _clean(a["a"])
                item["masked_address"] = {"address": a.get("address_text"), "shared_by": a.get("degree"), "unit": a.get("degree_unit"), "threshold": a.get("mask_threshold"),
                                          "note": "the Operational Network layer does not link landlord records on an address shared by more records than the threshold"}
        out.append(item)
    if not out and runner.run(REGISTERED, bbl=bbl).single()["n"] == 0:
        for lay in ([layer] if layer else list(LAYERS)):
            out.append({"layer": lay, "reason": bor_meaning("absence-reason", "no_registration"), "top_level_reason": bor_meaning("absence-reason", "outside_source_coverage"),
                        "evidence": "the graph holds no HPD registration on this lot (BOR does not list these lots; the graph's own HPD data answers it)"})
    return out


def _footprint(rows: list[dict]) -> dict:
    rental = [r for r in rows if r["rental"]]
    units = [r["units"] for r in rental if r["units"] is not None]
    by_borough: dict[str, int] = {}
    for r in rental:
        by_borough[BOROUGH.get(r["bbl"][0], r["bbl"][0])] = by_borough.get(BOROUGH.get(r["bbl"][0], r["bbl"][0]), 0) + 1
    return {"lots": len(rental), "lots_outside_rental_footprint": len(rows) - len(rental), "buildings": sum(r["buildings"] for r in rental),
            "lots_with_no_building_in_graph": sum(1 for r in rental if r["buildings"] == 0), "residential_units": sum(units),
            "lots_missing_a_unit_count": len(rental) - len(units), "lots_by_borough": dict(sorted(by_borough.items())), "note": COUNT_NOTE}


def _lot_row(r: dict) -> dict:
    return _clean({"bbl": r["bbl"], "address": r["address"], "building_class": r["building_class"], "residential_units": r["units"], "buildings": r["buildings"],
                   "rental_footprint": r["rental"]})


def _group_summary(g: dict, layer: str) -> dict:
    out = {"group_id": g["group_id"], "layer": LAYERS[layer], "what_this_layer_is": WHAT_IT_IS[layer], "lots_in_published_footprint": g["lot_count"],
           "lots_including_outside_footprint": g["total_lot_count"]}
    if layer == "owner_portfolio":
        out["composition"] = {"identity": "linked by resolved identities of HPD owner contacts", "deed_only": "linked only by a multi-parcel deed",
                              "deed_bridged": "identity links joined by deed evidence"}.get(g.get("composition"), g.get("composition"))
    else:
        out["split"] = ("a whole weakly connected component of accepted edges: it was not split into communities, and no Louvain split was applied to it" if g.get("split") == "wcc" else
                        "a community split (Louvain) from a larger connected component, so some members are connected to buildings outside this network" if g.get("split") == "louvain" else g.get("split"))
    return out


def layer_view(runner, bbl: str, layer: str, run_id: str | None = None, max_lots: int = 60, max_nodes: int = 25, max_links: int = 25) -> dict:
    """One lot's group in one layer: the run, the counts, the members, the signals behind the group, and how it differs from the other layer."""
    base = {"bbl": bbl, "layer": LAYERS[layer], **snapshot(runner), "caveats": CAVEATS}
    run = active_run(runner, run_id)
    if run is None:
        return {**base, "status": "no_run_loaded", "note": "The graph holds no BOR run, so no group can be reported."}
    base["bor_run"] = run
    lot = runner.run(LOT, bbl=bbl).single()
    if lot is None:
        return {**base, "status": "lot_absent", "note": "The graph holds no such lot."}
    m = runner.run(MEMBERSHIP, bbl=bbl, run=run["run_id"], layer=layer).single()
    if m is None:
        absences = lot_absence(runner, bbl, run["run_id"], layer)
        return {**base, "status": "not_in_group", "absences": absences,
                "note": ("This lot is in no " + LAYERS[layer] + " in this run. " + ("" if absences else "The release has no row for it, and a missing row means nothing. ")
                         + "That is not evidence that no relationship exists or that its owners differ.")}
    g, link = m["g"], m["m"]
    key, gid = g["assertion_key"], g["group_id"]
    rows = runner.run(GROUP_LOTS, key=key).data()
    nodes = runner.run(GROUP_NODES, key=key).data()
    signals = runner.run(SIGNALS, run=run["run_id"], layer=layer, gid=gid).data()
    out = {**base, "status": "found", "group": _group_summary(g, layer), "this_lot": {"rental_footprint": link["rental"], "link_id": link["link_id"],
                                                                                      **({"left_out_reason": bor_meaning("absence-reason", link["reason_code"])} if link.get("reason_code") else {})},
           "footprint": _footprint(rows), "lots_shown": min(len(rows), max_lots), "lots_total": len(rows)}
    out["lots"] = [_lot_row(r) for r in rows[:max_lots]]
    if len(rows) > max_lots:
        out["lots_truncated"] = f"{len(rows) - max_lots} more lots not listed; the counts above are for all {len(rows)}"
    anchor = next((n for n in nodes if n["n"]["node_id"] == g.get("anchor_node_id")), None)
    if anchor:
        out["group"]["anchor"] = {"node_id": g["anchor_node_id"], "name": anchor["n"].get("node_name"), "lots": anchor["lots"],
                                  "label": "the member with the most lots, ties to the smallest node id; a label for the group, not an owner and not evidence of ownership",
                                  "name_source": "node_names (the landlord name as filed), display only"}
    out["landlord_records"] = {"count": len(nodes), "shown": min(len(nodes), max_nodes),
                               "members": [_clean({"node_id": n["n"]["node_id"], "name": n["n"].get("node_name"), "lots": n["lots"],
                                                   "ambiguous_lots": n["ambiguous_lots"] or None, "straddles_clusters": (n["n"].get("n_clusters") or 0) > 1 or None,
                                                   "cluster_alternatives": n["n"].get("cluster_alternatives")}) for n in nodes[:max_nodes]],
                               "note": "A landlord record is a BOR node: a landlord name with its business address as WoW builds it, covering one or more lots. The name is display only. "
                                       "An ambiguous lot has tied HPD contacts BOR could not choose between; a straddling record matched more than one identity cluster, and the alternatives are listed."}
    stages = sorted({s["stage"] for s in signals})
    out["signals"] = {"path_steps": sum(s["steps"] for s in signals), "by_stage": [{"stage": s["stage"], **bor_meaning("link-stage", s["stage"]), "basis": s["basis_type"], "steps": s["steps"]} for s in signals],
                      "note": "The steps are a representative spanning path of the group, not the only or the strongest evidence."}
    if layer == "operational_network":
        within = runner.run(NETWORK_EDGES_WITHIN, run=run["run_id"], gid=gid).data()
        crossing = runner.run(NETWORK_EDGES_CROSSING, run=run["run_id"], gid=gid).data()
        kinds = {"address": sum(1 for r in within if r["e"].get("address_weight")), "name": sum(1 for r in within if r["e"].get("name_weight")),
                 "identity": sum(1 for r in within if r["e"].get("identity_weight"))}
        out["links"] = {"accepted_edges_within_the_network": len(within), "edges_by_kind": kinds, "shown": min(len(within), max_links),
                        "edges": [_clean({"edge_id": r["e"]["edge_id"], "between": [r["a"], r["b"]], "address_weight": r["e"].get("address_weight"),
                                          "name_weight": r["e"].get("name_weight"), "identity_weight": r["e"].get("identity_weight"), "weight": r["e"].get("weight")}) for r in within[:max_links]],
                        "edges_to_other_networks": len(crossing), "edges_to_other_networks_by_group": _count(crossing, "other_group"), "note": CROSSING_NOTE + " An edge's kind is the signal that carried it: a shared business address, a shared name, or an accepted identity link."}
    pr = precision_notes(runner, run["run_id"], stages)
    out["method_precision"] = {"entries": pr, "how_to_read": HOW_TO_READ_PRECISION}
    other = OTHER[layer]
    ol = runner.run(OTHER_LAYER_LOTS, bbl=bbl, run=run["run_id"], layer=other).data()
    mine = {r["bbl"] for r in rows}
    if ol:
        o = ol[0]
        theirs = set(o["bbls"])
        out["other_layer"] = {"layer": LAYERS[other], "group_id": o["group_id"], "lots": o["lot_count"], "lots_in_both": len(mine & theirs),
                              "lots_only_in_this_layer": sorted(mine - theirs)[:max_lots], "lots_only_in_this_layer_count": len(mine - theirs),
                              "lots_only_in_the_other_layer": sorted(theirs - mine)[:max_lots], "lots_only_in_the_other_layer_count": len(theirs - mine),
                              "next_step": "compare_layers explains each difference."}
    else:
        out["other_layer"] = {"layer": LAYERS[other], "status": "this lot is in no " + LAYERS[other], "absences": lot_absence(runner, bbl, run["run_id"], other)}
    return out


def _count(rows: list[dict], key: str) -> dict:
    out: dict[str, int] = {}
    for r in rows:
        out[r[key]] = out.get(r[key], 0) + 1
    return out


@tool
def get_owner_portfolio(bbl: str) -> dict:
    """The Owner Portfolio containing a tax lot (BBL, a 10-digit string) in the BOR run the graph holds: a lead for the buildings one resolved owner may hold,
    from identity links of HPD owner contacts and multi-parcel deeds. Gives the run, the counts of lots, buildings and residential units (lots and units are
    counted apart, with the lots missing a unit count), the lots, the landlord records and the signals behind the group, the published precision of those
    stages with its interval and gold status, and how the group differs from the lot's Operational Network. Not legal ownership. If the lot is in no
    portfolio it gives the reason, which is not evidence that no relationship exists."""
    with read_session() as session:
        return layer_view(session, bbl, "owner_portfolio")


@tool
def get_operational_network(bbl: str) -> dict:
    """The Operational Network containing a tax lot (BBL, a 10-digit string) in the BOR run the graph holds: a looser lead for buildings that share an operation
    by shared business address, shared name or identity. Gives the run, whether the network is a whole connected component or a Louvain community split from a
    larger one, the counts of lots, buildings and residential units, the lots, the accepted links that connect them with their kinds, the published precision
    of the stages used, and how the network differs from the lot's Owner Portfolio. Not legal ownership. If the lot is in no network it gives the reason."""
    with read_session() as session:
        return layer_view(session, bbl, "operational_network")


# ---- Q19: why two lots are grouped, or not ---------------------------------------------------------------------

COVERING_NODE = """
MATCH (l:Lot {bbl: $bbl})<-[c:COVERS]-(n:BorNode {run_id: $run, layer: $layer})
OPTIONAL MATCH (n)-[s:SELECTED_ROLE {bbl: $bbl}]->(role:Role)
OPTIONAL MATCH (role)-[:IN_REGISTRATION]->(reg:Registration)
OPTIONAL MATCH (role)-[:HELD_BY]->(p:HpdParty)
OPTIONAL MATCH (n)-[k:CANDIDATE_ROLE {bbl: $bbl}]->(cand:Role)
RETURN n {.assertion_key, .node_id, .node_name, .group_id, .component_id, .community_id, .cluster_id} AS n, c.ambiguous AS ambiguous, c.registration_id AS registration_id,
       role {.role_id, .role_type, .source_role_code} AS role, reg.registration_id AS role_registration, coalesce(p.organization_name, p.person_name) AS party_name,
       count(DISTINCT cand) AS tied_candidates
"""
WITNESS_PATH = """
MATCH (a:BorNode {assertion_key: $ka}), (b:BorNode {assertion_key: $kb})
MATCH p = shortestPath((a)-[:WITNESS_STEP*..400]-(b))
RETURN [x IN nodes(p) | x {.assertion_key, .node_id, .node_name}] AS ns, [r IN relationships(p) | r {.step, .stage, .basis_type, .basis_id, .link_id}] AS rs
"""
NETWORK_PATH = """
MATCH (a:BorNode {assertion_key: $ka}), (b:BorNode {assertion_key: $kb})
MATCH p = shortestPath((a)-[:NETWORK_EDGE*..200]-(b))
RETURN [x IN nodes(p) | x {.assertion_key, .node_id, .node_name, .group_id}] AS ns,
       [r IN relationships(p) | r {.edge_id, .name_weight, .address_weight, .identity_weight, .weight, .crosses_networks}] AS rs
"""
CLUSTER_DECISIONS = """
MATCH (d:BorDecision {cluster_id: $cid, run_id: $run})
RETURN d.stage AS stage, d.outcome AS outcome, d.rule AS rule, d.rule_version AS rule_version, count(d) AS decisions, min(d.score) AS min_score,
       max(d.decision_threshold) AS threshold
ORDER BY stage, outcome
"""
LINK_SET = """
MATCH (s:BorLinkSet {set_key: $key})
OPTIONAL MATCH (s)-[:HAS_MEMBER]->(n:BorNode)
RETURN s {.set_id, .stage, .rule, .rule_version, .size} AS s, count(n) AS members_in_groups
"""
EVIDENCE = """
MATCH (e:BorEvidence {evidence_key: $key})
OPTIONAL MATCH (e)-[:CITES_DOCUMENT]->(d:Document)
OPTIONAL MATCH (e)-[f:EVIDENCE_FOR]->(l:Lot)
WITH e, d, collect({bbl: l.bbl, role: f.role, latest_document_id: f.latest_document_id, latest_amount: f.latest_amount, excluded_reason: f.excluded_reason}) AS lots
RETURN e {.evidence_id, .stage, .document_id, .parcel_count} AS e, d {.document_id, .doc_type, .recorded, .doc_date, .amount} AS d, lots
"""
STEP_EDGE = """
MATCH (a:BorNode {assertion_key: $ka})-[x:NETWORK_EDGE {edge_id: $eid}]-(b:BorNode {assertion_key: $kb})
RETURN x {.edge_id, .name_weight, .address_weight, .identity_weight, .weight, .crosses_networks} AS x LIMIT 1
"""


def _step_evidence(runner, run_id: str, step: dict, ka: str, kb: str) -> dict:
    """What the step cites, from the release and from the recorded facts it points to. The ids are run-local."""
    kind, bid = step["basis_type"], step["basis_id"]
    out = {"step": step["step"], "stage": bor_meaning("link-stage", step["stage"]), "cites": f"{kind} {bid} (run-local id)"}
    if kind == "identity_cluster":
        out["decisions"] = [_clean({"stage": d["stage"], "outcome": d["outcome"], "rule": d["rule"], "rule_version": d["rule_version"], "decisions": d["decisions"],
                                    "lowest_score": d["min_score"], "threshold": d["threshold"]}) for d in runner.run(CLUSTER_DECISIONS, cid=bid, run=run_id).data()]
        out["reading"] = "the two landlord records sit in one resolved identity cluster; the decisions are the identity matches inside it"
    elif kind == "link_set":
        r = runner.run(LINK_SET, key=f"{run_id}/{bid}").single()
        if r:
            out["link_set"] = _clean(r["s"]) | {"members_in_groups": r["members_in_groups"]}
            out["reading"] = ("nodes tied by a curated owner list" if r["s"]["stage"] == "identity.curated" else
                              "nodes tied because one owner-of-record entity in the tax records is matched to their registered LLC owners")
    elif kind == "evidence_item":
        r = runner.run(EVIDENCE, key=f"{run_id}/{bid}").single()
        if r:
            out["deed_bundle"] = _clean(r["e"]) | {"deed": _clean(r["d"]) if r["d"] else None, "lots": [_clean(x) for x in r["lots"]][:12]}
            out["reading"] = "lots held under one multi-parcel deed (a recorded ACRIS fact) or moved onward from a shell holder; BOR's rules decide that the bundle links them"
    elif kind == "network_edge":
        r = runner.run(STEP_EDGE, ka=ka, kb=kb, eid=bid).single()
        if r:
            out["edge"] = _clean(r["x"])
            out["reading"] = "an accepted Operational Network edge: the signals with a non-zero weight (address, name, identity) carried it"
    return out


def _end(runner, bbl: str, layer: str, run_id: str) -> dict | None:
    r = runner.run(COVERING_NODE, bbl=bbl, run=run_id, layer=layer).single()
    if r is None:
        return None
    return {"landlord_record": _clean(r["n"]), "hpd_contact": _clean({"role_id": (r["role"] or {}).get("role_id"), "role_type": (r["role"] or {}).get("role_type"),
                                                                      "registration_id": r["role_registration"] or r["registration_id"], "name": r["party_name"], "source": "HPD registration contact"}),
            "ambiguous": bool(r["ambiguous"]) or None, "tied_candidate_contacts": r["tied_candidates"] or None}


def _pair_layer(runner, a: str, b: str, layer: str, run: dict) -> dict:
    rid = run["run_id"]
    ma, mb = runner.run(MEMBERSHIP, bbl=a, run=rid, layer=layer).single(), runner.run(MEMBERSHIP, bbl=b, run=rid, layer=layer).single()
    out = {"layer": LAYERS[layer]}
    if ma is None or mb is None:
        absent = {x: lot_absence(runner, x, rid, layer) for x, m in ((a, ma), (b, mb)) if m is None}
        out |= {"verdict": "neither_in_a_group" if ma is None and mb is None else "only_one_in_a_group",
                "groups": {x: m["g"]["group_id"] for x, m in ((a, ma), (b, mb)) if m is not None}, "absences": absent,
                "statement": ("In this run the method did not place " + ("either lot" if ma is None and mb is None else "one of the lots") + " in an " + LAYERS[layer] + "; "
                              "the reasons are listed. That is not evidence that the two lots are or are not related."),
                "method_precision": {"note": "No path is reported for this layer, so no stage precision applies."}}
        return out
    ga, gb = ma["g"], mb["g"]
    if ga["assertion_key"] != gb["assertion_key"]:
        out |= {"verdict": "different_groups", "groups": {a: ga["group_id"], b: gb["group_id"]},
                "statement": "In this run the method placed the two lots in different groups. That is not evidence that their owners differ.",
                "method_precision": {"note": "No path is reported for this layer, so no stage precision applies."}}
        if layer == "operational_network":
            na, nb = _end(runner, a, layer, rid), _end(runner, b, layer, rid)
            if na and nb:
                ca, cb = na["landlord_record"].get("component_id"), nb["landlord_record"].get("component_id")
                out["original_component"] = {"lot_a": ca, "lot_b": cb, "community_a": na["landlord_record"].get("community_id"), "community_b": nb["landlord_record"].get("community_id")}
                if ca and ca == cb:
                    p = runner.run(NETWORK_PATH, ka=na["landlord_record"]["assertion_key"], kb=nb["landlord_record"]["assertion_key"]).single()
                    out["connected_before_the_split"] = ("The two lots were in one connected component of accepted edges and a Louvain split put them in different communities, "
                                                         "so they are connected by accepted edges but not in the same Operational Network.")
                    if p:
                        out["connecting_edges"] = [_clean(x) for x in p["rs"]]
        return out
    na, nb = _end(runner, a, layer, rid), _end(runner, b, layer, rid)
    out |= {"verdict": "same_group", "group": _group_summary(ga, layer), "from": {"bbl": a, **(na or {})}, "to": {"bbl": b, **(nb or {})}}
    ka, kb = na["landlord_record"]["assertion_key"], nb["landlord_record"]["assertion_key"]
    if ka == kb:
        out["path"] = {"landlord_records": [na["landlord_record"]], "steps": [], "reading": "both lots are covered by one landlord record, so no link between records is needed; the release's paths are representative, not the only or the strongest evidence"}
        stages = []
    else:
        p = runner.run(WITNESS_PATH, ka=ka, kb=kb).single()
        if p is None:
            out["path"] = None
            out["note"] = "The release's representative path does not connect these two records, though they share a group; the path is representative, not the only evidence."
            stages = []
        else:
            steps = [_step_evidence(runner, rid, r, p["ns"][i]["assertion_key"], p["ns"][i + 1]["assertion_key"]) for i, r in enumerate(p["rs"])]
            out["path"] = {"landlord_records": [_clean(n) for n in p["ns"]], "steps": steps,
                           "reading": "lot, HPD contact, landlord record, then each step to the next landlord record, then the contact and lot at the other end; the path is representative, not the only or the strongest"}
            stages = [r["stage"] for r in p["rs"]]
    out["statement"] = ("In this run the method placed both lots in " + LAYERS[layer] + " " + ga["group_id"] + ". This is a lead derived from the records cited, not a finding that one owner holds both.")
    out["method_precision"] = precision_notes(runner, rid, stages) if stages else \
        {"note": "No link stage is cited, so there is no precision to report: the path has no step (both lots are covered by one landlord record, or the release's path does not join them)."}
    return out


def explain_membership(runner, bbl_a: str, bbl_b: str, run_id: str | None = None) -> dict:
    """Why two lots are grouped, or not, in each layer: the groups, the representative path of recorded and derived steps between them, and the reasons for
    any absence. A path is evidence for the grouping, never proof of common ownership; the lack of one is not evidence the owners differ."""
    base = {"bbl_a": bbl_a, "bbl_b": bbl_b, **snapshot(runner), "caveats": CAVEATS}
    run = active_run(runner, run_id)
    if run is None:
        return {**base, "status": "no_run_loaded"}
    missing = [x for x in (bbl_a, bbl_b) if runner.run(LOT, bbl=x).single() is None]
    if missing:
        return {**base, "bor_run": run, "status": "lot_absent", "lots_not_in_graph": missing}
    out = {**base, "bor_run": run, "status": "found"}
    for layer in LAYERS:
        out[layer] = _pair_layer(runner, bbl_a, bbl_b, layer, run)
    out["how_to_read"] = HOW_TO_READ_PRECISION
    return out


@tool
def explain_why_grouped(bbl_a: str, bbl_b: str) -> dict:
    """Explain why two tax lots (BBLs, 10-digit strings) are grouped together, or not, in each layer of the BOR run: the Owner Portfolio and the Operational
    Network. For each layer it says whether the lots share a group, and if they do gives the representative path between them (the HPD contact at each end,
    each landlord record, and each step with the recorded evidence it cites: identity matches with their rule and scores, a curated or owner-of-record link
    set, a multi-parcel deed, or a shared address or name edge) and the published precision of the stages used. If a lot is in no group it gives BOR's
    reason; in a network split by community it says whether the lots were connected before the split. A path is evidence for a grouping, not proof of common
    ownership, and not being grouped is not evidence that the owners differ."""
    with read_session() as session:
        return explain_membership(session, bbl_a, bbl_b)


# ---- Q10: where the layers disagree ----------------------------------------------------------------------------

OVERLAP = """
MATCH (:Lot {bbl: $bbl})-[:MEMBER_OF]->(g:BorGroup {run_id: $run, layer: $layer})
MATCH (g)<-[:MEMBER_OF]-(l:Lot)
OPTIONAL MATCH (l)-[:MEMBER_OF]->(o:BorGroup {run_id: $run, layer: $other})
RETURN l.bbl AS bbl, o.group_id AS other_group, o.lot_count AS other_lot_count, o.split AS other_split, o.composition AS other_composition
ORDER BY bbl
"""
LOT_STATUS = """
UNWIND $bbls AS b
MATCH (l:Lot {bbl: b})
OPTIONAL MATCH (l)-[n:NOT_IN_GROUP {layer: $layer}]->(:BorRun {run_id: $run})
OPTIONAL MATCH (l)<-[:ON_LOT]-(r:Registration)
RETURN b AS bbl, n.reason_code AS code, n.top_level_reason AS top, n.masked_address_key AS masked, count(r) AS registrations
"""
GROUP_ADDRESSES = """
MATCH (a:BorNode {run_id: $run, layer: 'operational_network', group_id: $gid})-[:USES_ADDRESS]->(m:BorMaskedAddress)
RETURN m.address_text AS address, m.degree AS shared_by, m.mask_threshold AS threshold, count(a) AS landlord_records
ORDER BY shared_by DESC
"""
NODE_EDGE_KINDS = """
UNWIND $bbls AS b
MATCH (:Lot {bbl: b})<-[:COVERS]-(n:BorNode {run_id: $run, layer: 'operational_network'})
OPTIONAL MATCH (n)-[e:NETWORK_EDGE]-(:BorNode)
RETURN b AS bbl, count(e) AS edges, sum(CASE WHEN e.address_weight > 0 THEN 1 ELSE 0 END) AS address, sum(CASE WHEN e.name_weight > 0 THEN 1 ELSE 0 END) AS name,
       sum(CASE WHEN e.identity_weight > 0 THEN 1 ELSE 0 END) AS identity
"""
CROSSING_BETWEEN = """
MATCH (a:BorNode {run_id: $run, layer: 'operational_network'})-[e:NETWORK_EDGE {crosses_networks: true}]-(b:BorNode)
WHERE a.group_id IN $gids AND b.group_id IN $gids AND a.group_id < b.group_id
RETURN a.group_id AS network_a, b.group_id AS network_b, count(e) AS edges
"""


def _reason(runner, row: dict) -> dict:
    if row["code"]:
        out = {"reason": bor_meaning("absence-reason", row["code"]), "top_level_reason": bor_meaning("absence-reason", row["top"])}
        if row.get("masked"):
            a = runner.run(MASKED, key=row["masked"]).single()
            if a:
                out["masked_address"] = {"address": a["a"].get("address_text"), "shared_by": a["a"].get("degree"), "threshold": a["a"].get("mask_threshold")}
        return out
    if row["registrations"] == 0:
        return {"reason": bor_meaning("absence-reason", "no_registration"), "top_level_reason": bor_meaning("absence-reason", "outside_source_coverage")}
    return {"reason": None, "note": "BOR wrote no row for this lot in this layer, and a missing row means nothing"}


def compare_layers(runner, bbl: str, run_id: str | None = None, max_lots: int = 30) -> dict:
    """The two layers for one lot side by side, and where and why they differ. Each lot in one layer but not the other is explained by the other layer's
    group for it or by BOR's reason for leaving it out. Both lists are derived; neither is the true list of the landlord's buildings."""
    base = {"bbl": bbl, **snapshot(runner), "caveats": CAVEATS}
    run = active_run(runner, run_id)
    if run is None:
        return {**base, "status": "no_run_loaded"}
    base["bor_run"] = run
    if runner.run(LOT, bbl=bbl).single() is None:
        return {**base, "status": "lot_absent"}
    rid = run["run_id"]
    groups = {lay: runner.run(MEMBERSHIP, bbl=bbl, run=rid, layer=lay).single() for lay in LAYERS}
    if not any(groups.values()):
        return {**base, "status": "in_neither_layer", "absences": lot_absence(runner, bbl, rid),
                "note": "The lot is in no group of either layer. That is not evidence that no relationship exists or that its owners differ."}
    out = {**base, "status": "found", "layers": {lay: (_group_summary(m["g"], lay) if m else {"layer": LAYERS[lay], "status": "this lot is in no group", "absences": lot_absence(runner, bbl, rid, lay)})
                                                  for lay, m in groups.items()}}
    if not all(groups.values()):
        out["note"] = "The lot is in a group in one layer only, so there is no second list to compare; the reason for the other layer is above."
        return out
    lots = {}
    for lay in LAYERS:
        lots[lay] = runner.run(OVERLAP, bbl=bbl, run=rid, layer=lay, other=OTHER[lay]).data()
    sets = {lay: {r["bbl"] for r in rows} for lay, rows in lots.items()}
    both = sets["owner_portfolio"] & sets["operational_network"]
    out["comparison"] = {"lots_in_both": len(both), "only_in_owner_portfolio": len(sets["owner_portfolio"] - sets["operational_network"]),
                         "only_in_operational_network": len(sets["operational_network"] - sets["owner_portfolio"]), "identical": sets["owner_portfolio"] == sets["operational_network"]}
    diffs = {}
    for lay in LAYERS:
        other = OTHER[lay]
        only = sorted(sets[lay] - sets[other])
        if not only:
            continue
        status = {r["bbl"]: r for r in runner.run(LOT_STATUS, bbls=only, run=rid, layer=other).data()}
        in_other = {r["bbl"]: r for r in lots[lay] if r["other_group"]}
        shown = []
        for b in only[:max_lots]:
            if b in in_other:
                o = in_other[b]
                shown.append({"bbl": b, "in_other_layer": f"a different {LAYERS[other]} ({o['other_group']}, {o['other_lot_count']} lots)"})
            else:
                shown.append({"bbl": b, **_reason(runner, status[b])})
        if lay == "operational_network":     # what linked a lot the portfolio layer did not: the signals on its landlord record's accepted edges
            kinds = {r["bbl"]: r for r in runner.run(NODE_EDGE_KINDS, bbls=[s["bbl"] for s in shown], run=rid).data()}
            for s in shown:
                k = kinds.get(s["bbl"])
                if k:
                    s["linked_in_the_network_by"] = {"accepted_edges": k["edges"], "of_which_with_address": k["address"], "with_name": k["name"], "with_identity": k["identity"]}
        by_reason: dict[str, int] = {}
        for b in only:
            key = (f"in a different {LAYERS[other]}" if b in in_other else (status[b]["code"] or ("no_registration" if status[b]["registrations"] == 0 else "no row")))
            by_reason[key] = by_reason.get(key, 0) + 1
        diffs[f"only_in_{lay}"] = {"count": len(only), "shown": len(shown), "lots": shown, "by_explanation": dict(sorted(by_reason.items(), key=lambda kv: -kv[1]))}
    out["differences"] = diffs
    # how the groups nest: a network that holds several portfolios, a portfolio that spans several networks
    nest = {}
    for lay in LAYERS:
        c: dict[str, int] = {}
        for r in lots[lay]:
            c[r["other_group"] or "(none)"] = c.get(r["other_group"] or "(none)", 0) + 1
        nest[lay] = {"distinct_groups_in_other_layer": len([k for k in c if k != "(none)"]), "lots_by_other_layer_group": dict(sorted(c.items(), key=lambda kv: -kv[1])[:15]),
                     "lots_in_no_group_of_the_other_layer": c.get("(none)", 0)}
    out["nesting"] = {"owner_portfolio": {**nest["owner_portfolio"], "reading": "the networks this portfolio's lots fall in"},
                      "operational_network": {**nest["operational_network"], "reading": "the portfolios this network's lots fall in"}}
    on_gid = groups["operational_network"]["g"]["group_id"]
    out["evidence"] = {
        "owner_portfolio_signals": [{"stage": s["stage"], "steps": s["steps"]} for s in runner.run(SIGNALS, run=rid, layer="owner_portfolio", gid=groups["owner_portfolio"]["g"]["group_id"]).data()],
        "operational_network_signals": [{"stage": s["stage"], "steps": s["steps"]} for s in runner.run(SIGNALS, run=rid, layer="operational_network", gid=on_gid).data()],
        "masked_addresses_used_by_the_network": [_clean(a) for a in runner.run(GROUP_ADDRESSES, run=rid, gid=on_gid).data()],
        "note": "The two layers use different evidence. A portfolio links records by resolved identity of owner contacts and by multi-parcel deeds; a network also links records that share a business address or a name, "
                "so it is looser by design, and it does not link on a business address shared by more records than the threshold (a masked address)."}
    nets = sorted({r["other_group"] for r in lots["owner_portfolio"] if r["other_group"]})
    if len(nets) > 1:
        out["evidence"]["accepted_edges_between_these_networks"] = [_clean(r) for r in runner.run(CROSSING_BETWEEN, run=rid, gids=nets).data()]
    stages = [s["stage"] for k in ("owner_portfolio_signals", "operational_network_signals") for s in out["evidence"][k]]
    out["method_precision"] = precision_notes(runner, rid, stages)
    out["how_to_read"] = ("Both layers are derived leads. The difference between them is a difference in method, not a finding about who owns what. " + HOW_TO_READ_PRECISION)
    return out


@tool
def compare_ownership_layers(bbl: str) -> dict:
    """Compare the Owner Portfolio and the Operational Network that contain a tax lot (BBL, a 10-digit string) in the BOR run, and explain where they
    disagree: the lots in each layer and not the other, each with the other layer's group for it or BOR's reason for leaving it out (a masked address, a
    name or first-name veto, a co-op or condo screen, no linkage), how many portfolios a network holds or how many networks a portfolio spans, and the
    evidence each layer uses. Both are derived leads; neither is the true list of the landlord's buildings, and a difference is not a finding about ownership."""
    with read_session() as session:
        return compare_layers(session, bbl)
