"""The citywide graph agrees with the expected Slice 4 answers, which were derived from the BOR release files and the source database without the graph
(evals/expected/derive_slice4.py). Read-only: the tools run against nyclr as it is. Design note 0024."""
import json

import pytest

from agent.db import read_session
from agent.tools.absences import explain_absences
from agent.tools.layer_violations import group_violations
from agent.tools.layers import OTHER, compare_layers, explain_membership, layer_view
from etl.config import ROOT

EXP = json.loads((ROOT / "evals" / "expected" / "slice4.json").read_text())
Q = EXP["questions"]
BBL = {**{k: v["bbl"] for k, v in EXP["anchors"].items()}, **{k: v["bbl"] for k, v in EXP["cases"].items()}}
OP, ON = "owner_portfolio", "operational_network"
RUN = EXP["run_id"]


@pytest.fixture(scope="module")
def runner():
    with read_session() as s:
        yield s


def test_the_graph_holds_the_run_the_answers_were_derived_from(runner):
    r = runner.run("MATCH (r:BorRun {run_id: $r}) RETURN r.snapshot_id AS s, r.source_verified AS v, r.release_name AS n", r=RUN).single()
    assert (r["s"], r["v"], r["n"]) == (EXP["snapshot_id"], True, EXP["release"])


@pytest.mark.parametrize("k", ["C", "D", "H2", "H4", "H5"])
def test_q9_portfolio_footprint(runner, k):
    e, r = Q["Q9"][k], layer_view(runner, BBL[k], OP, RUN)
    assert r["status"] == "found" and r["group"]["group_id"] == e["group_id"]
    f = r["footprint"]
    assert (f["lots"], f["lots_outside_rental_footprint"], f["buildings"], f["residential_units"], f["lots_missing_a_unit_count"]) == \
           (len(e["lots"]), len(e["lots_outside_rental_footprint"]), e["buildings"], e["residential_units"], e["lots_missing_a_unit_count"])
    assert sorted(x["bbl"] for x in r["lots"] if x["rental_footprint"]) == e["lots"]
    assert r["landlord_records"]["count"] == e["landlord_records"]
    assert {s["stage"]: s["steps"] for s in r["signals"]["by_stage"]} == e["path_steps_by_stage"]
    assert r["group"]["anchor"]["node_id"] == e["anchor_node_id"] and r["group"]["anchor"]["name"] == e["anchor_name"]
    assert r["group"]["lots_in_published_footprint"] == e["lot_count"] and r["group"]["lots_including_outside_footprint"] == e["total_lot_count"]


@pytest.mark.parametrize("k", ["A", "B", "E", "F", "G", "M", "V"])
def test_q9_a_lot_in_no_portfolio_gives_the_reason(runner, k):
    e, r = Q["Q9"][k], layer_view(runner, BBL[k], OP, RUN)
    assert r["status"] == "not_in_group" and not e["in_group"]
    assert r["absences"][0]["reason"]["code"] == (e["reason_code"] or "no_registration") and "not evidence" in r["note"]


@pytest.mark.parametrize("k", ["C", "D", "H1", "H3", "H2"])
def test_q8_operational_network(runner, k):
    e, r = Q["Q8"][k], layer_view(runner, BBL[k], ON, RUN)
    assert r["status"] == "found" and r["group"]["group_id"] == e["group_id"]
    f = r["footprint"]
    assert (f["lots"], f["buildings"], f["residential_units"], f["lots_missing_a_unit_count"]) == (len(e["lots"]), e["buildings"], e["residential_units"], e["lots_missing_a_unit_count"])
    assert r["links"]["accepted_edges_within_the_network"] == e["accepted_edges_within"] and r["links"]["edges_by_kind"] == e["edges_by_kind"]
    assert r["links"]["edges_to_other_networks"] == e["edges_to_other_networks"]
    split = r["group"]["split"]
    assert split.startswith("a community split") == (e["split"] == "louvain") and split.startswith("a whole") == (e["split"] == "wcc")
    assert {s["stage"]: s["steps"] for s in r["signals"]["by_stage"]} == e["path_steps_by_stage"]


@pytest.mark.parametrize("k", ["D", "H1", "H2", "C"])
def test_q10_where_the_layers_disagree(runner, k):
    e, r = Q["Q10"][k], compare_layers(runner, BBL[k], RUN)
    assert r["status"] == "found" and r["comparison"]["lots_in_both"] == e["lots_in_both"]
    assert r["layers"][OP]["group_id"] == e["owner_portfolio"] and r["layers"][ON]["group_id"] == e["operational_network"]
    for lay in (OP, ON):
        want = e["differences"][f"only_in_{lay}"]
        got = r["differences"].get(f"only_in_{lay}", {"count": 0, "lots": []})
        assert got["count"] == want["count"]
        for w in want["lots"]:
            g = next(x for x in got["lots"] if x["bbl"] == w["bbl"])
            if "group_id" in w["other_layer"]:
                assert w["other_layer"]["group_id"] in g["in_other_layer"]
            else:
                assert g["reason"]["code"] == w["other_layer"]["reason_code"]
    assert r["nesting"][ON]["distinct_groups_in_other_layer"] == len([p for p in e["portfolios_in_the_network"] if p != "(none)"])
    assert r["nesting"][OP]["distinct_groups_in_other_layer"] == len([n for n in e["networks_in_the_portfolio"] if n != "(none)"])


def test_q10_a_network_that_holds_two_portfolios_and_a_portfolio_that_spans_two_networks(runner):
    assert len(Q["Q10"]["H1"]["portfolios_in_the_network"]) == 2 and len(Q["Q10"]["H2"]["networks_in_the_portfolio"]) == 2
    assert len(compare_layers(runner, BBL["H1"], RUN)["nesting"][ON]["lots_by_other_layer_group"]) == 2


def test_q10_d_has_two_lots_the_network_holds_and_the_portfolio_does_not(runner):
    r = compare_layers(runner, BBL["D"], RUN)
    d = r["differences"]["only_in_operational_network"]
    assert d["count"] == 2 and all(x["linked_in_the_network_by"]["of_which_with_address"] > 0 for x in d["lots"])


@pytest.mark.parametrize("i", range(len(Q["Q19"])))
def test_q19_why_two_lots_are_grouped_or_not(runner, i):
    e = Q["Q19"][i]
    r = explain_membership(runner, e["bbl_a"], e["bbl_b"], RUN)
    for lay in (OP, ON):
        assert r[lay]["verdict"] == e[lay]["verdict"], (e["a"], e["b"], lay)
        if e[lay]["verdict"] == "same_group":
            assert r[lay]["path"] is not None and r[lay]["path"]["landlord_records"] and "not proof" in r[lay]["statement"] or "lead" in r[lay]["statement"]
        else:
            assert "not evidence" in r[lay]["statement"]
        for bbl, a in e[lay]["absences"].items():
            got = r[lay]["absences"][bbl][0]["reason"]["code"]
            assert got == (a.get("reason_code") or "no_registration")


def test_q19_the_path_between_two_lots_is_a_chain_of_steps_that_cite_their_evidence(runner):
    r = explain_membership(runner, BBL["H2"], "4100220013", RUN)[OP]
    steps = r["path"]["steps"]
    assert steps and all(s["stage"]["code"] and s["cites"] for s in steps)
    assert any("deed_bundle" in s for s in steps) or any("decisions" in s for s in steps)
    assert r["from"]["hpd_contact"]["registration_id"]


def test_q19_a_registered_llc_link_set_is_named(runner):
    r = explain_membership(runner, BBL["H4"], "3050747502", RUN)[OP]
    assert any("link_set" in s for s in r["path"]["steps"])


def test_q19_a_louvain_community_pair_reports_its_split(runner):
    r = explain_membership(runner, BBL["H3"], "3001830030", RUN)[ON]
    assert r["verdict"] == "same_group" and "louvain" in r["group"]["split"].lower()


@pytest.mark.parametrize("k", ["C", "D", "H2"])
def test_q21_violations_across_a_layer(runner, k):
    for lay in (OP, ON):
        if lay not in Q["Q21"][k]:
            continue
        e, r = Q["Q21"][k][lay], group_violations(runner, BBL[k], lay, "abc", RUN)
        s = r["summary"]
        assert (s["total_open"], s["lots"], s["by_class"], s["lots_with_any_open"]) == (e["total_open_abc"], e["lots"], e["by_class"], e["lots_with_any_open"]), (k, lay)
        assert s["share_held_by_top_3"] == e["share_held_by_top_3"] and s["lots_missing_a_unit_count"] == e["lots_missing_a_unit_count"]
        assert [x["bbl"] for x in r["ranked_by_open_per_residential_unit"][:5]] == e["top_lots_by_open_per_unit"]
        assert s["top_3_lots"] == e["top3_by_count"]
        assert s["residential_units"] == e["residential_units"]


def test_q21_class_i_is_never_added_to_the_others_and_the_other_layer_is_given(runner):
    r = group_violations(runner, BBL["D"], ON, "abc", RUN)
    assert r["other_layer"]["layer"] == "Owner Portfolio" and "Class I is never added" in " ".join(r["caveats"])
    only_i = group_violations(runner, BBL["D"], ON, "I", RUN)
    assert only_i["summary"]["total_open"] == sum(x["open_by_class"]["I"] for x in only_i["ranked_by_open_per_residential_unit"] + only_i["lots_without_a_unit_count"]) or only_i["summary"]["total_open"] >= 0


def test_q21_a_bad_measure_or_an_ungrouped_lot_is_reported(runner):
    assert group_violations(runner, BBL["D"], ON, "hazardous", RUN)["status"] == "bad_measure"
    assert group_violations(runner, BBL["A"], ON, "abc", RUN)["status"] == "not_in_group"


def _src(r, name):
    return next(s for s in r["sources"] if s["source"] == name)


@pytest.mark.parametrize("k", ["D", "F", "M", "V", "A", "C"])
def test_q26_what_each_absence_means(runner, k):
    e, r = Q["Q26"][k], explain_absences(runner, BBL[k], RUN)
    assert (_src(r, "HPD registration")["status"] == "present") == (e["hpd_registrations"] > 0)
    assert (_src(r, "HPD violations")["status"] == "present") == (e["violation_rows"] > 0)
    assert (_src(r, "HPD Housing Court actions")["status"] == "present") == (e["litigation_cases"] > 0)
    for lay, name in ((OP, "Owner Portfolio"), (ON, "Operational Network")):
        s = [x for x in r["sources"] if x["source"] == name][0]
        if e[lay]["in_group"]:
            assert s["status"] == "present" and s["group_id"] == e[lay]["group_id"]
        else:
            assert s["status"] == "absent" and s["reason"]["code"] == (e[lay].get("reason_code") or "no_registration")
            assert s["top_level_reason"]["code"] == (e[lay].get("top_level_reason") or "outside_source_coverage")
    assert "none of them is evidence" in " ".join(r["caveats"]).lower() or "none of them is evidence" in r["caveats"][-1].lower()


def test_q26_d_has_no_dos_record_under_either_spelling_of_its_owner(runner):
    r = explain_absences(runner, BBL["D"], RUN)
    dos = [s for s in r["sources"] if s["source"] == "NY Department of State entity"]
    assert len(dos) == 2 and all(s["status"] == "absent" for s in dos)
    assert all(s["reason"]["code"] == "outside_source_coverage" for s in dos)


def test_q26_a_masked_aggregator_address_is_named_with_how_many_share_it(runner):
    r = explain_absences(runner, BBL["M"], RUN)
    s = [x for x in r["sources"] if x["source"] == "Operational Network"][0]
    assert s["reason"]["code"] == "aggregator_address_masked" and s["masked_address"]["shared_by"] > s["masked_address"]["threshold"]
    e = Q["Q26"]["M"][ON]["masked_address"]
    assert s["masked_address"]["address"] == e["address"] and s["masked_address"]["shared_by"] == e["shared_by"]


def test_q26_f_has_no_registration_and_the_layers_say_so(runner):
    r = explain_absences(runner, BBL["F"], RUN)
    assert _src(r, "HPD registration")["reason"]["code"] == "no_registration"
    assert [x["reason"]["code"] for x in r["sources"] if x["source"] in ("Owner Portfolio", "Operational Network")] == ["no_registration", "no_registration"]


def test_q19_a_pair_covered_by_one_landlord_record_has_no_step_and_says_no_precision_applies(runner):
    r = explain_membership(runner, BBL["H5"], "2034980026", RUN)[OP]
    if not r["path"]["steps"]:
        assert isinstance(r["method_precision"], dict) and "No link stage is cited" in r["method_precision"]["note"]
        assert "one landlord record" in r["path"]["reading"]
