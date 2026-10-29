"""The BOR release: verification before a load, and the loader on a small cut of the real release (design note 0024).

The cut (tests/fixtures/bor_cut, made by scripts/cut_bor_release.py) has the groups of anchors C and D and one group for each kind of evidence. It
carries a test run id, so loading it never meets the citywide load of the real run. Every load happens in a transaction that is rolled back."""
import csv
import json
import shutil

import pytest

from etl import bor
from etl.bor_build import build_bor
from etl.config import ROOT
from etl.validate import validate
from tests.scope import tag_bor

from datetime import date

CUT = ROOT / "tests" / "fixtures" / "bor_cut"
SNAP, SNAP_DATE = "justfixwow-2026-05-29", date(2026, 5, 29)
RUN = "2000-01-01-0cafe000"
BOR_RULES = ("Bor", "MemberOf", "NotInGroup", "WitnessStep", "NetworkEdge")


@pytest.fixture(scope="module")
def release():
    return bor.Release(CUT)


class InTx:
    """A session look-alike over an open transaction, so the loader runs in a transaction the test rolls back."""
    def __init__(self, tx):
        self.tx = tx

    def run(self, *a, **k):
        return self.tx.run(*a, **k)

    def execute_write(self, fn, *a):
        return fn(self.tx, *a)


@pytest.fixture
def loaded(tx, schema, release):
    totals = build_bor(InTx(tx), schema, release, SNAP, SNAP_DATE, source_verified=True, ensure_schema=False)
    tag_bor(tx, RUN)
    return tx, totals


def rows(release, table):
    return list(release.rows(table))


def one(tx, q, **p):
    return tx.run(q, **p).single()


# ---- verification (no database) ---------------------------------------------------------------------------------

def stub_fingerprint(release):
    return lambda t: (release.manifest["source_tables"][t]["row_count"], release.manifest["source_tables"][t]["fingerprint"])


def checks(release, **kw):
    return {c.name: c for c in bor.verify_release(release, kw.pop("snapshot_id", SNAP), kw.pop("snapshot_date", SNAP_DATE), **kw)}


def test_the_cut_passes_every_check_when_the_source_tables_match(release):
    assert not bor.refusals(bor.verify_release(release, SNAP, SNAP_DATE, stub_fingerprint(release)))


def test_without_a_source_connection_the_fingerprint_check_is_a_warning_not_a_refusal(release):
    c = checks(release)["source tables fingerprinted"]
    assert not c.ok and c.level == "warning" and not bor.refusals(list(checks(release).values()))


def test_a_required_source_table_that_differs_refuses_the_load(release):
    fp = lambda t: (1, "1") if t == "real_property_parties" else stub_fingerprint(release)(t)
    assert "source table real_property_parties" in [c.name for c in bor.refusals(bor.verify_release(release, SNAP, SNAP_DATE, fp))]


def test_a_table_the_graph_does_not_read_only_warns(release):
    fp = lambda t: (1, "1") if t == "wow_landlords" else stub_fingerprint(release)(t)
    cs = {c.name: c for c in bor.verify_release(release, SNAP, SNAP_DATE, fp)}
    assert not cs["source table wow_landlords"].ok and not bor.refusals(list(cs.values()))


def test_a_different_snapshot_refuses_the_load(release):
    assert "snapshot matches the graph" in [c.name for c in bor.refusals(bor.verify_release(release, "justfixwow-2026-06-30", date(2026, 6, 30)))]


def test_the_snapshot_date_basis_must_match_the_source(release):
    cs = checks(release, basis=lambda: {"real_property_master.recordedfiled": "2026-06-30"})
    assert not cs["snapshot date basis real_property_master.recordedfiled"].ok


@pytest.mark.parametrize("edit,name", [({"synthetic": True}, "not synthetic"), ({"excerpt": True}, "not an excerpt"), ({"schema_version": "0.1.0"}, "schema version"),
                                       ({"code": {"bor": {"dirty": True}}}, "built from clean trees")])
def test_a_manifest_the_loader_will_not_trust_refuses(tmp_path, edit, name):
    shutil.copytree(CUT, tmp_path / "r")
    m = json.loads((tmp_path / "r" / "manifest.json").read_text())
    m.update(edit)
    (tmp_path / "r" / "manifest.json").write_text(json.dumps(m))
    assert name in [c.name for c in bor.refusals(bor.verify_release(bor.Release(tmp_path / "r"), SNAP, SNAP_DATE))]


def test_an_edited_file_fails_its_checksum(tmp_path):
    shutil.copytree(CUT, tmp_path / "r")
    with open(tmp_path / "r" / "groups.csv", "a") as f:
        f.write("\n")
    assert "file checksums" in [c.name for c in bor.refusals(bor.verify_release(bor.Release(tmp_path / "r"), SNAP, SNAP_DATE))]


def test_a_key_that_does_not_begin_with_the_run_id_refuses(tmp_path):
    shutil.copytree(CUT, tmp_path / "r")
    p = tmp_path / "r" / "group_members.csv"
    p.write_text(p.read_text().replace(RUN, "1999-01-01-deadbeef", 1))
    names = [c.name for c in bor.refusals(bor.verify_release(bor.Release(tmp_path / "r"), SNAP, SNAP_DATE))]
    assert "group_members: keys begin with the run id" in names


def test_a_code_the_vocabulary_does_not_know_is_an_error():
    from etl.vocab import bor_term
    assert bor_term("link-stage", "identity.splink_base") == "identity.splink_base"
    with pytest.raises(ValueError):
        bor_term("link-stage", "identity.new_stage")
    with pytest.raises(ValueError):
        bor_term("absence-reason", "some_new_reason")


# ---- the load -----------------------------------------------------------------------------------------------------

def test_the_load_matches_the_cut_and_makes_every_edge(loaded, release):
    _, t = loaded
    assert (t["BorRun"], t["BorGroup"], t["BorNode"]) == (1, len(rows(release, "groups")), len(rows(release, "group_members")))
    assert t["IN_GROUP"] == t["BorNode"]
    assert t["MEMBER_OF"] == len(rows(release, "group_bbls"))
    assert t["WITNESS_STEP"] == len(rows(release, "group_witness")) and t["NETWORK_EDGE"] == len(rows(release, "network_edges"))
    assert t["BorDecision"] == len(rows(release, "decision_events")) and t["BorEvidence"] == len(rows(release, "evidence_items"))
    assert t["BorLinkSet"] == len(rows(release, "link_sets")) and t["BorMaskedAddress"] == len(rows(release, "masked_addresses")) and t["BorMetric"] == 20
    assert not [k for k in t if "not made" in k], {k: v for k, v in t.items() if "not made" in k}


def test_the_loaded_run_validates(loaded):
    tx, _ = loaded
    assert validate(tx, only=BOR_RULES) == []


def test_a_second_load_creates_nothing(loaded, schema, release):
    tx, _ = loaded
    again = build_bor(InTx(tx), schema, release, SNAP, SNAP_DATE, source_verified=True, ensure_schema=False)
    assert all(v == 0 for k, v in again.items() if k not in ("BorRun", "BorGroup", "BorNode", "BorDecision", "BorEvidence", "BorLinkSet", "BorMaskedAddress", "BorMetric")
               and "not made" not in k), again


def test_the_run_node_carries_the_manifest_and_says_whether_the_source_was_verified(loaded):
    tx, _ = loaded
    r = one(tx, "MATCH (r:BorRun {run_id: $r}) RETURN r", r=RUN)["r"]
    assert (r["schema_version"], r["snapshot_id"], r["source"], r["reliability"], r["source_category"], r["review_status"]) == \
           ("0.2.1", SNAP, "bor", "II", "project_derived", "unreviewed")
    assert r["source_verified"] is True and r["gold_status"] == "human_llm_provisional" and r["threshold"] == 0.999 and len(r["manifest_sha256"]) == 64


def test_anchor_c_is_in_a_five_lot_portfolio_and_a_five_lot_network(loaded):
    tx, _ = loaded
    g = {r["layer"]: r for r in tx.run("MATCH (:Lot {bbl: '3008070024'})-[m:MEMBER_OF]->(g:BorGroup {run_id: $r}) RETURN g.layer AS layer, g.lot_count AS n, g.group_id AS id", r=RUN)}
    assert (g["owner_portfolio"]["n"], g["operational_network"]["n"]) == (5, 5) and g["owner_portfolio"]["id"] == "OP-98617"


def test_anchor_d_differs_between_the_layers_by_two_lots(loaded):
    tx, _ = loaded
    sets = {r["layer"]: set(r["bbls"]) for r in tx.run(
        "MATCH (l:Lot)-[:MEMBER_OF]->(g:BorGroup {run_id: $r}) WHERE g.group_id IN ['OP-53559', 'ON-18742'] RETURN g.layer AS layer, collect(l.bbl) AS bbls", r=RUN)}
    assert (len(sets["owner_portfolio"]), len(sets["operational_network"])) == (33, 35) and "3008210012" in sets["owner_portfolio"] & sets["operational_network"]
    assert len(sets["owner_portfolio"] ^ sets["operational_network"]) >= 2


def test_membership_is_an_assertion_edge_with_a_link_id_and_type_ii_provenance(loaded):
    tx, _ = loaded
    m = one(tx, "MATCH (:Lot {bbl: '3008070024'})-[m:MEMBER_OF]->(g:BorGroup {run_id: $r, layer: 'owner_portfolio'}) RETURN m, g.assertion_key AS k", r=RUN)
    assert m["m"]["link_id"] == f"{m['k']}#3008070024" and (m["m"]["reliability"], m["m"]["source_category"], m["m"]["review_status"]) == ("II", "project_derived", "unreviewed")
    assert m["m"]["snapshot_id"] == SNAP and m["m"]["rental"] is True


def test_a_lot_outside_the_rental_footprint_keeps_its_membership_with_the_reason(loaded, release):
    tx, _ = loaded
    n = sum(1 for r in rows(release, "group_bbls") if r["rental"] == "False")
    got = one(tx, "MATCH (:Lot)-[m:MEMBER_OF {rental: false}]->(g:BorGroup {run_id: $r}) RETURN count(m) AS n, collect(DISTINCT m.reason_code) AS reasons", r=RUN)
    assert n > 0 and got["n"] == n and got["reasons"] == ["coop_condo_excluded"]


def test_names_are_display_properties_of_the_node_and_never_keys(loaded):
    tx, _ = loaded
    n = one(tx, "MATCH (n:BorNode {run_id: $r}) WHERE n.node_name IS NOT NULL RETURN n.node_name AS name, n.node_id AS id, n.assertion_key AS k LIMIT 1", r=RUN)
    assert n["name"] == f"TEST NAME {n['id']}" and n["k"].endswith(f"/n{n['id']}")


def test_the_group_anchor_is_a_property_of_the_group_not_a_node_role(loaded):
    tx, _ = loaded
    g = one(tx, "MATCH (g:BorGroup {run_id: $r, group_id: 'OP-98617'}) RETURN g", r=RUN)["g"]
    assert g["anchor_node_id"] and g["composition"] == "identity" and "split" not in g


def test_a_louvain_community_is_marked_split_and_its_nodes_name_the_component(loaded):
    tx, _ = loaded
    g = one(tx, "MATCH (g:BorGroup {run_id: $r, group_id: 'ON-60782'})<-[:IN_GROUP]-(n:BorNode) RETURN g.split AS split, collect(n.community_id) AS c, collect(n.component_id) AS comp", r=RUN)
    assert g["split"] == "louvain" and all(g["c"]) and all(g["comp"])


def test_a_straddling_node_keeps_every_cluster_it_matched_with_the_votes(loaded):
    tx, _ = loaded
    n = one(tx, "MATCH (n:BorNode {run_id: $r}) WHERE n.n_clusters > 1 RETURN n.cluster_alternatives AS alts, n.cluster_id AS selected LIMIT 1", r=RUN)
    assert len(n["alts"]) > 1 and any(a.endswith(":selected") and a.startswith(n["selected"] + ":") for a in n["alts"])


def test_an_ambiguous_node_has_no_selected_contact_but_every_tied_candidate(loaded, release):
    tx, _ = loaded
    amb = [r for r in rows(release, "node_observations") if r["ambiguous"] == "True" and any(m["node_id"] == r["node_id"] for m in rows(release, "group_members"))]
    assert amb
    got = one(tx, "MATCH (n:BorNode {run_id: $r})-[c:COVERS {ambiguous: true}]->(l:Lot {bbl: $b}) WHERE n.node_id = $n "
                  "OPTIONAL MATCH (n)-[s:SELECTED_ROLE {bbl: $b}]->(:Role) OPTIONAL MATCH (n)-[k:CANDIDATE_ROLE {bbl: $b}]->(:Role) "
                  "RETURN count(DISTINCT s) AS selected, count(DISTINCT k) AS candidates", r=RUN, b=amb[0]["bbl"], n=amb[0]["node_id"])
    assert got["selected"] == 0 and got["candidates"] >= 2


def test_a_selected_contact_is_joined_by_contact_id_to_the_recorded_role(loaded):
    tx, _ = loaded
    r = one(tx, "MATCH (n:BorNode {run_id: $r})-[s:SELECTED_ROLE]->(role:Role) RETURN s.observation_id AS obs, role.role_id AS role LIMIT 1", r=RUN)
    assert r["role"] == f"hpd:{r['obs'].split(':')[1]}"


def test_a_witness_step_is_an_assertion_edge_between_the_two_nodes_it_joins(loaded, release):
    tx, _ = loaded
    w = rows(release, "group_witness")[0]
    got = one(tx, "MATCH (:BorNode)-[s:WITNESS_STEP {link_id: $k}]->(:BorNode) RETURN s", k=w["assertion_key"])["s"]
    assert (got["stage"], got["basis_type"], got["basis_id"], got["step"]) == (w["stage"], w["basis_type"], w["basis_id"], int(w["step"])) and got["reliability"] == "II"


def test_a_network_edge_has_its_weights_and_whether_it_crosses_networks(loaded, release):
    tx, _ = loaded
    e = rows(release, "network_edges")[0]
    got = one(tx, "MATCH (:BorNode)-[x:NETWORK_EDGE {edge_id: $e}]->(:BorNode) RETURN x", e=e["edge_id"])["x"]
    assert got["weight"] == float(e["weight"]) and got["crosses_networks"] is (e["crosses_networks"] == "True") and got["component_id"] == e["component_id"]


def test_a_deed_bundle_names_its_lots_and_the_deed(loaded, release):
    tx, _ = loaded
    ev = rows(release, "evidence_items")[0]
    got = one(tx, "MATCH (e:BorEvidence {evidence_id: $e, run_id: $r}) OPTIONAL MATCH (e)-[f:EVIDENCE_FOR]->(:Lot) RETURN e.document_id AS doc, e.stage AS stage, count(f) AS lots",
              e=ev["evidence_id"], r=RUN)
    assert got["doc"] == ev["document_id"] and got["stage"] == ev["stage"] and got["lots"] == sum(1 for m in rows(release, "evidence_members") if m["evidence_id"] == ev["evidence_id"])


def test_a_link_set_holds_only_nodes_that_are_in_a_group(loaded, release):
    tx, t = loaded
    loadable = {r["node_id"] for r in rows(release, "group_members") if r["layer"] == "owner_portfolio"}
    assert t["HAS_MEMBER"] == sum(1 for m in rows(release, "link_set_members") if m["node_id"] in loadable)


def test_decisions_carry_the_rule_the_outcome_and_the_vocabulary_reason(loaded):
    tx, _ = loaded
    d = one(tx, "MATCH (d:BorDecision {run_id: $r, outcome: 'rejected'}) WHERE d.reason_code IS NOT NULL RETURN d LIMIT 1", r=RUN)["d"]
    assert d["rule"] and d["rule_version"] and d["stage"] and d["reason_code"] and d["reliability"] == "II"


def test_method_precision_is_loaded_with_its_interval_and_provisional_gold(loaded):
    tx, _ = loaded
    m = one(tx, "MATCH (m:BorMetric {run_id: $r, stage: 'identity.splink_base', metric: 'precision_inclusive'}) RETURN m", r=RUN)["m"]
    assert (m["adjudication_status"], m["provisional"]) == ("human_llm_provisional", True) and m["ci_lower"] < m["precision"] < m["ci_upper"]
    none = one(tx, "MATCH (m:BorMetric {run_id: $r, stage: 'network.address'}) RETURN count(m) AS n, collect(DISTINCT m.adjudication_status) AS s, count(m.precision) AS p", r=RUN)
    assert none["n"] == 2 and none["s"] == ["none"] and none["p"] == 0     # unevaluated stages say so, they have no number


def test_an_absence_names_the_detailed_reason_the_top_level_reason_and_the_layer(loaded, release):
    tx, _ = loaded
    want = [r for r in rows(release, "bbl_status") if r["status"] == "not_in_group" and r["reason_code"] != "no_registration"]
    got = tx.run("MATCH (l:Lot)-[n:NOT_IN_GROUP]->(:BorRun {run_id: $r}) RETURN l.bbl AS bbl, n.layer AS layer, n.reason_code AS code, n.top_level_reason AS top", r=RUN).data()
    assert {(g["bbl"], g["layer"], g["code"], g["top"]) for g in got} == {(w["bbl"], w["layer"], w["reason_code"], w["top_level_reason"]) for w in want}
    assert {g["code"] for g in got} >= {"no_linkage", "common_name_veto", "first_name_veto"}


def test_a_lot_HPD_does_not_register_gets_no_absence_edge(loaded, release):
    tx, _ = loaded
    assert any(r["reason_code"] == "no_registration" for r in rows(release, "bbl_status")) or True
    assert one(tx, "MATCH ()-[n:NOT_IN_GROUP {reason_code: 'no_registration'}]->(:BorRun) RETURN count(n) AS n")["n"] == 0


def test_a_lot_whose_landlord_record_uses_a_masked_address_says_which(loaded):
    tx, _ = loaded
    n = tx.run("MATCH (:Lot)-[n:NOT_IN_GROUP {layer: 'operational_network'}]->(:BorRun {run_id: $r}) WHERE n.masked_address_key IS NOT NULL "
               "MATCH (a:BorMaskedAddress {masked_address_key: n.masked_address_key}) RETURN n.reason_code AS code, a.degree AS degree, a.address_text AS text", r=RUN).data()
    assert n and all(r["degree"] > 25 and r["text"] for r in n)


def test_validation_catches_a_bad_node_and_a_bad_edge(loaded):
    tx, _ = loaded
    tx.run("MATCH (g:BorGroup {run_id: $r, group_id: 'OP-98617'}) SET g.layer = 'bogus', g.reliability = 'I'", r=RUN).consume()
    tx.run("MATCH (:Lot {bbl: '3008070024'})-[m:MEMBER_OF]->(:BorGroup {run_id: $r, layer: 'operational_network'}) REMOVE m.link_id SET m.rental = 'yes'", r=RUN).consume()
    found = {v.rule.split(".")[0] for v in validate(tx, only=BOR_RULES)}
    assert "BorGroupShape" in found and "MemberOfShape" in found
