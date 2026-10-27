"""Q3 and Q24 tools against the anchor lots, loaded into nyclr inside a rolled-back transaction and checked against
the expected answers (evals/expected/slice1.json). Design notes 0009, 0015, 0016."""
import json
from datetime import date

import pytest

from agent.tools.records import CAVEATS_Q24, compare_deed_and_owner, find_by_name, mail_drops
from etl.build import load_acris, load_hpd, load_nodes, load_pluto
from etl.config import ROOT
from etl.dos import dos_entity_node
from etl.load import apply_schema, register_snapshot

SNAP, SNAP_DATE = "justfixwow-2026-05-29", date(2026, 5, 29)
FX = ROOT / "tests" / "fixtures"
ANCH, AC, DOS = (json.loads((FX / f).read_text()) for f in ("slice1_anchors.json", "slice1_acris.json", "slice1_dos.json"))
EXPECTED = json.loads((ROOT / "evals" / "expected" / "slice1.json").read_text())
Q3, Q24, BBL = EXPECTED["questions"]["Q3"], EXPECTED["questions"]["Q24"], {k: v["bbl"] for k, v in EXPECTED["anchors"].items()}
LOTS = frozenset(str(r["bbl"]).strip() for r in ANCH["pluto"])


@pytest.fixture
def graph(session, schema):
    apply_schema(session, schema)
    tx = session.begin_transaction()
    register_snapshot(tx, SNAP, "justfixwow", SNAP_DATE)
    load_pluto(tx, schema, ANCH["pluto"], SNAP)
    load_hpd(tx, schema, ANCH["registrations"], ANCH["contacts"], SNAP)
    load_acris(tx, schema, AC["documents"], AC["parties"], AC["legals"], LOTS, SNAP, SNAP_DATE)
    load_nodes(tx, schema, "Party", (dos_entity_node(r, SNAP) for r in DOS), also=("DosEntity",))
    yield tx
    tx.rollback()


# ---- Q3 -----------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("anchor", list(Q3))
def test_q3_latest_deeds_grantees_and_comparisons_match(graph, anchor):
    exp, got = Q3[anchor], compare_deed_and_owner(graph, BBL[anchor])
    assert got["status"] == "found"
    assert sorted(d["document_id"] for d in got["latest_deeds"]) == sorted(d["document_id"] for d in exp["deeds"])
    by_name = {g["party_name"]: g for d in got["latest_deeds"] for g in d["grantees"]}
    for eg in exp["grantees"]:
        g = by_name[eg["grantee"]]
        assert (g["name_n1"], g["address_line1"].split()[0]) == (eg["grantee_n1"], eg["address"].split()[0])
        if isinstance(eg["vs_hpd"], str):                      # F: no HPD registration
            assert g["vs_hpd_owners"] == [] and "no comparison" in got["hpd_note"]
            continue
        want = {(c["registration_id"], c["name_agreement"], c["address_agreement"]) for c in eg["vs_hpd"]}
        have = {(c["registration_id"], c["name_agreement"], c["address_agreement"]) for c in g["vs_hpd_owners"]}
        assert have == want


def test_q3_last_deed_for_value_is_found_when_the_latest_deed_is_not_a_sale(graph):
    r = compare_deed_and_owner(graph, BBL["A"])
    assert r["latest_deeds"][0]["amount"] == 0
    v = r["last_deed_for_value"]
    assert (v["document_id"], v["amount"], v["is_latest"]) == (Q3["A"]["last_deed_for_value"]["document_id"], 5000000, False)
    # the 2021 deed's grantee address agreement is reported for that deed, not carried over from the latest one
    assert v["grantees"][0]["vs_hpd_owners"][0]["address_agreement"] in {"same", "differs", "absent"}


def test_q3_tied_latest_deeds_are_all_reported(graph):
    r = compare_deed_and_owner(graph, BBL["D"])
    assert sorted(d["document_id"] for d in r["latest_deeds"]) == ["2017061600025001", "2017061600025002"]


def test_q3_hpd_individual_owner_is_not_compared_with_an_entity(graph):
    g = compare_deed_and_owner(graph, BBL["E"])["latest_deeds"][0]["grantees"][0]
    c = g["vs_hpd_owners"][0]
    assert (c["name_agreement"], c["address_agreement"]) == ("not_comparable", "not_comparable") and c["hpd_type"] == "IndividualOwner"


def test_q3_the_hpd_spelling_of_k_s_turnpike_is_a_different_name(graph):
    for g in compare_deed_and_owner(graph, BBL["G"])["latest_deeds"][0]["grantees"]:
        assert {c["name_agreement"] for c in g["vs_hpd_owners"]} == {"different"}


def test_q3_every_record_carries_source_and_snapshot_and_the_caveats_are_there(graph):
    r = compare_deed_and_owner(graph, BBL["A"])
    d = r["latest_deeds"][0]
    assert (d["source"], d["snapshot_id"], d["reliability"]) == ("acris_master", SNAP, "I")
    assert r["latest_deeds"][0]["grantees"][0]["vs_hpd_owners"][0]["snapshot_id"] == SNAP
    assert any("lead" in c for c in r["caveats"]) and any("$0 deed is not a sale" in c for c in r["caveats"])


def test_q3_unknown_lot_and_lot_without_deeds_say_so(graph):
    assert compare_deed_and_owner(graph, "3999999999")["status"] == "lot_absent"
    graph.run("MATCH (l:Lot {bbl: $b})<-[x:ON_LOT]-(d:Document) DELETE x", b=BBL["A"]).consume()   # rolled back
    r = compare_deed_and_owner(graph, BBL["A"])
    assert r["status"] == "no_deed_in_graph" and "not 'no deed exists'" in r["note"]


def test_mail_drop_list_loads_and_is_keyed_like_the_graph():
    assert "418 BROADWAY 12207" in mail_drops()


# ---- Q24 ----------------------------------------------------------------------------------------------------

def test_q24_5413_plaza_deed_rows_hpd_role_and_dos_record(graph):
    r = find_by_name(graph, "5413 PLAZA LLC")
    assert r["status"] == "found" and r["normalized_name"] == "5413 PLAZA LLC"
    want = {(d["document_id"], str(d["party_type"]), tuple(d["bbls"])) for d in Q24["acris_documents"]}
    assert {(d["document_id"], d["party_type"], tuple(d["bbls"])) for d in r["acris_documents"]} == want
    assert {(d["document_id"], d["role_type"]) for d in r["acris_documents"] if d["party_type"] == "2"} >= {("2021022201130003", "grantee")}
    hpd = Q24["hpd"][0]
    assert any((h["registration_id"], h["contact_id"], h["hpd_type"], hpd["bbl"] in h["bbls"], hpd["bin"] in h["bins"]) ==
               (hpd["registration_id"], hpd["contact_id"], hpd["type"], True, True) for h in r["hpd"])
    assert [e["dos_id"] for e in r["dos"]] == [Q24["dos"]["dos_id"]]
    assert r["dos"][0]["entity_type"] == Q24["dos"]["entity_type"]


def test_q24_says_deed_documents_only_and_a_match_is_a_lead(graph):
    r = find_by_name(graph, "5413 PLAZA LLC")
    assert r["caveats"] == CAVEATS_Q24 and any("deed family" in c for c in r["caveats"]) and any("lead" in c for c in r["caveats"])
    assert all(d["doc_type"].startswith("deed") for d in r["acris_documents"])


def test_q24_finds_the_name_through_punctuation_and_case_but_not_a_different_spelling(graph):
    assert find_by_name(graph, "5413 plaza llc.")["status"] == "found"
    assert find_by_name(graph, "5413 Plaza L.L.C.")["status"] == "found"           # N1 deletes the periods
    r = find_by_name(graph, "KS Turnpike LLC")      # the HPD spelling (anchor G): HPD has it, ACRIS and DOS spell it K S TURNPIKE LLC
    assert r["status"] == "found" and r["hpd"] and r["acris_documents"] == [] and r["dos"] == []
    assert find_by_name(graph, "K S Turnpike LLC")["dos"][0]["dos_id"] == "3574572"


def test_q24_no_record_says_what_was_tried(graph):
    r = find_by_name(graph, "Zzyzx Holdings LLC")
    assert r["status"] == "no_record" and r["variants_tried"] == ["ZZYZX HOLDINGS LLC"] and "reason" in r


def test_q24_a_person_appears_only_in_the_role_the_record_gives(graph):
    person = next(c for c in ANCH["contacts"] if c["type"] == "HeadOfficer" and c.get("firstname"))
    name = " ".join(x for x in (person["firstname"], person.get("middleinitial"), person["lastname"]) if x)
    r = find_by_name(graph, name)
    assert r["status"] == "found" and r["hpd"] and all(row["hpd_type"] and row["role_type"] for row in r["hpd"])
    assert "dos" in r   # DOS entities are returned only when a DOS name equals the person's name


def test_q24_limit_truncates_and_says_so(graph):
    r = find_by_name(graph, "5413 PLAZA LLC", limit=1)
    assert r["truncated"] is True and len(r["acris_documents"]) == 1
