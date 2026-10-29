"""The graph agrees with the expected Slice 5 answers, derived from the source database, the mail-drop CSV and the earlier expected files without the graph
(evals/expected/derive_slice5.py). Read-only. Design note 0026."""
import json

import pytest

from agent.db import read_session
from agent.tools.addresses import check_address
from agent.tools.affiliations import affiliations, agent_footprint
from agent.tools.evidence import compare_entity_names, shared_evidence
from agent.tools.restructuring import classify
from etl.config import ROOT

EXP = json.loads((ROOT / "evals" / "expected" / "slice5.json").read_text())
Q, BBL = EXP["questions"], {k: v["bbl"] for k, v in EXP["anchors"].items()}


@pytest.fixture(scope="module")
def runner():
    with read_session() as s:
        yield s


@pytest.mark.parametrize("key", list(Q["Q6"]))
def test_q6_each_method_answers_for_the_address(runner, key):
    e, r = Q["Q6"][key], check_address(runner, address_key=key)
    m = {x["method"]: x for x in r["methods"]}
    assert m["the project's mail-drop list"]["flagged"] == e["on_mail_drop_list"] and m["the project's mail-drop list"].get("kind") == e["list_kind"]
    assert m["BOR's masking of aggregator addresses"]["flagged"] == e["bor_masked_on_list"]
    deg = m["parties at the address in the graph"]
    assert (deg["hpd_parties"], deg["hpd_roles"]) == (e["hpd_parties"], e["hpd_contact_rows"]) and deg["flagged"] == (e["hpd_parties"] >= 25)
    assert "unreviewed" in " ".join(r["caveats"])


def test_q6_a_typed_address_finds_the_key_with_an_ordinal_street(runner):
    r = check_address(runner, "746", "61 Street", "11220")
    assert r["address_key"] == "746 61ST ST 11220" and r["keys_tried"][0] == "746 61 ST 11220"


@pytest.mark.parametrize("pair", list(Q["Q22"]))
def test_q22_the_relation_and_the_dos_records(runner, pair):
    a, b = pair.split(" | ")
    e, r = Q["Q22"][pair], compare_entity_names(runner, a, b)
    assert r["status"] == "found"
    if e["relation"]:
        assert r["relation"]["relation"] == e["relation"]
    else:
        assert r["relation"]["relation"] in ("different", "differs_by_one_token")
    got = {x: sorted(d["dos_id"] for d in r["holdings"][x]["dos_entities"]) for x in "ab"}
    assert (got["a"], got["b"]) == (e["dos_ids_a"], e["dos_ids_b"])
    assert "not a link" in r["caveats"][-1] or "lead" in r["caveats"][-1]


def test_q22_g_spelling_pair_is_a_spacing_match_with_no_record_beyond_the_names(runner):
    r = compare_entity_names(runner, "KS Turnpike LLC", "K S TURNPIKE LLC")
    assert r["relation"]["relation"] == "spacing_match" and not r["evidence_for"] and "No record other than the names" in r["judgment"]


def test_q22_the_two_702_names_are_different_entities_with_distinct_dos_records(runner):
    r = compare_entity_names(runner, "702 54 STREET LLC", "702 PLAZA LLC")
    assert r["relation"]["relation"] == "different" and any(x["type"] == "distinct_dos_records" for x in r["evidence_against"])


def test_q7_a_and_b_share_evidence_each_marked_used_or_set_aside(runner):
    e, r = Q["Q7"]["A|B"], shared_evidence(runner, BBL["A"], BBL["B"])
    by = {}
    for i in r["evidence"]:
        by.setdefault(i["type"], []).append(i)
    assert [i["address_key"] for i in by["shared_hpd_business_address"]] == e["shared_hpd_addresses"] and all(i["status"] == "used" for i in by["shared_hpd_business_address"])
    assert {i["person_name"].upper() for i in by["same_person_name_in_a_principal_role"]} == set(e["same_person_names"])
    assert {i["name_a"] for i in by["person_name_differing_by_spacing"]} | {i["name_b"] for i in by["person_name_differing_by_spacing"]} == {e["spacing_only_person_names"][0][1], e["spacing_only_person_names"][0][2]}
    assert {i["agent"].upper() for i in by["shared_managing_agent"]} == set(e["shared_managing_agents"])
    docs = {i["document"]["document_id"] for i in by["shared_acris_document"]}
    assert "2021031601183001" in docs and docs <= set(e["documents_on_both_lots"])
    assert by["same_dos_process_address"][0]["address_key"] == "5 CROMWELL CIRCLE 10304"
    assert all(i["status"] in ("used", "set_aside") and i["source"] and i["reliability"] for i in r["evidence"]) and r["used"] + r["set_aside"] == len(r["evidence"])
    assert "searched_and_not_found" in r and "score" not in json.dumps(r["how_to_read"]).lower().replace("not scored", "")


def test_q7_an_address_on_the_mail_drop_list_is_set_aside_with_its_reason(runner):
    from agent.tools.evidence import pair_evidence
    pa = {"n1": "X", "hpd_parties": [{"organization_name": "X LLC", "business_address_key": "418 BROADWAY 12207"}], "others": [], "dos": [], "lots": []}
    pb = {"n1": "Y", "hpd_parties": [{"organization_name": "Y LLC", "business_address_key": "418 BROADWAY 12207"}], "others": [], "dos": [], "lots": []}
    items, _ = pair_evidence(runner, pa, pb)
    assert items[0]["status"] == "set_aside" and "mail-drop list" in items[0]["reason"]


@pytest.mark.parametrize("letter", ["A", "C"])
def test_q11_lenders_and_joint_borrowers(runner, letter):
    e, r = Q["Q11"][letter], affiliations(runner, BBL[letter])
    lenders = {p["name"] for p in r["by_type"]["lender"]["parties"]}
    assert lenders == {" ".join(x.split()) for x in e["lenders_named"]}
    assert {j["document_id"] for j in r["by_type"]["joint_borrower"]["examples"]} == set(e["documents_with_several_borrowers"])
    assert "no loaded source records a parent" in r["documented_parent"]


def test_q11_a_and_b_joint_mortgage_is_a_shared_borrower_record_not_control(runner):
    r = affiliations(runner, BBL["A"])
    j = r["by_type"]["joint_borrower"]
    assert "not common control" in j["relationship"] and "CONNECTONE BANK" in j["examples"][0]["lenders"] and set(j["examples"][0]["borrowers"]) == {"5413 PLAZA LLC", "702 PLAZA LLC"}
    assert r["by_type"]["managing_agent"]["relationship"].startswith("management")


def test_q18_b_deeds_are_classified_by_pattern(runner):
    e, r = Q["Q18"]["B"]["deeds"], classify(runner, BBL["B"], max_deeds=50)
    got = {d["document_id"]: sorted(d["patterns"]) for d in r["deeds"]}
    for d in e:
        assert got[d["document_id"]] == d["patterns"], d["document_id"]


def test_q18_the_pair_of_2021_deeds_and_the_buyer_with_no_established_relationship(runner):
    r = classify(runner, BBL["B"])
    by = {d["document_id"]: d for d in r["deeds"]}
    last = by["2021022201130002"]
    assert last["amount"] == 6800000 and last["grantees"] == ["702 PLAZA LLC"] and last["buyer_relationship"] == "no relationship established"
    assert "paired_with_sale" in by["2021022201130001"]["patterns"] and "a hint" in " ".join(r["caveats"])


def test_q18_a_deed_naming_both_parties_is_not_independent_support(runner):
    r = classify(runner, BBL["B"], max_deeds=50)
    for d in r["deeds"]:
        for s in d.get("independent_support") or []:
            assert not str((s.get("document") or {}).get("doc_type", "")).startswith("deed")


@pytest.mark.parametrize("agent", list(Q["Q23"]))
def test_q23_a_managing_agents_footprint(runner, agent):
    e = Q["Q23"][agent]
    r = agent_footprint(runner, agent)["agents"][0]
    f = r["footprint"]
    assert (f["lots"], f["registrations"], f["residential_units"], f["lots_missing_a_unit_count"]) == (e["lots"], e["registrations"], e["residential_units"], e["lots_missing_a_unit_count"])
    assert set(r["comparison_with_the_layers"]) == {"owner_portfolio", "operational_network"}


def test_q23_a_commercial_agent_is_flagged_and_a_small_one_is_not(runner):
    big, small = agent_footprint(runner, "BRIGHTON MANAGEMENT")["agents"][0], agent_footprint(runner, "BIG BROOKLYN REHAB INC")["agents"][0]
    assert big["commercial_agent"] and not small["commercial_agent"]


def test_q23_from_a_lot_takes_the_agents_registered_on_it(runner):
    r = agent_footprint(runner, BBL["A"])
    assert [a["agent"] for a in r["agents"]] == ["JAY WONG"] and r["agents"][0]["footprint"]["lots"] >= 2
