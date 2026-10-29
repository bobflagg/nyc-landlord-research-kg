"""Q12: the deed-history tool against the expected timelines (derived from the source without the graph, evals/expected/derive_slice3.py)
on the citywide graph, and its counting rules on small loads in a rolled-back transaction (design note 0022)."""
import json
from datetime import date

import pytest

from agent.db import read_session
from agent.tools.transfers import deed_history
from etl.build import load_acris, load_pluto
from etl.config import ROOT
from etl.load import register_snapshot

EXP = json.loads((ROOT / "evals" / "expected" / "slice3.json").read_text())
Q12, BBL = EXP["questions"]["Q12"], {k: v["bbl"] for k, v in EXP["anchors"].items()}
SNAP, SNAP_DATE = "justfixwow-2026-05-29", date(2026, 5, 29)


@pytest.fixture(scope="module")
def runner():
    with read_session() as s:
        yield s


# ---- the citywide graph against the source ---------------------------------------------------------------------

@pytest.mark.parametrize("a", list(Q12))
def test_every_anchor_timeline_matches_the_source(runner, a):
    e, r = Q12[a], deed_history(runner, BBL[a])
    assert r["status"] == "found" and (r["deeds"], r["deeds_for_value"], r["deeds_for_zero_dollars"], r["corrections_not_counted"]) == (e["deeds"], e["deeds_for_value"], e["deeds_for_zero_dollars"], e["corrections"])
    assert [(t["document_id"], t["doc_type_raw"], t.get("doc_date"), t["recorded"], t.get("amount")) for t in r["timeline"]] == \
           [(t["document_id"], t["doc_type"], t["doc_date"], t["recorded"], t["amount"]) for t in e["timeline"]]
    for got, want in zip(r["timeline"], e["timeline"]):
        assert sorted(got["lots_on_document"]) == want["lots"]
        norm = lambda names: sorted(" ".join(n.split()) for n in names)
        assert norm(g["name"] for g in got["grantors"]) == norm(want["grantors"]) and norm(g["name"] for g in got["grantees"]) == norm(want["grantees"])


def test_anchor_a_two_deeds_since_2015_one_a_sale_and_one_for_zero_dollars(runner):
    r = deed_history(runner, BBL["A"], 2015)
    assert [t["recorded"] for t in r["timeline"]] == ["2021-02-26", "2025-04-02"] and r["deeds"] == 2
    assert [t["amount"] for t in r["timeline"]] == [5000000, 0] and (r["deeds_for_value"], r["deeds_for_zero_dollars"]) == (1, 1)
    assert r["timeline"][1]["grantor_and_grantee_share_a_normalized_name"] == ["5413 PLAZA LLC"] and r["last_deed_for_value"]["document_id"] == "2021022201130003"


def test_since_year_reports_how_many_earlier_deeds_were_left_out(runner):
    r = deed_history(runner, BBL["C"], 2015)
    assert r["status"] == "no_deed_in_graph" and r["deeds_recorded_before_since_year"] == 3


def test_since_year_keeps_deeds_recorded_from_that_year(runner):
    all_ = deed_history(runner, BBL["B"])
    since = deed_history(runner, BBL["B"], 2015)
    assert since["deeds"] == sum(1 for t in all_["timeline"] if t["recorded"] >= "2015-01-01") and since["since_year"] == 2015


def test_the_caveats_say_what_is_not_attributed(runner):
    text = " ".join(deed_history(runner, BBL["A"])["caveats"])
    assert "not a sale" in text and "does not attribute" in text and "not proof of who owns" in text


def test_an_unknown_lot_is_lot_absent_and_a_lot_with_no_deed_does_not_claim_none_happened(runner):
    assert deed_history(runner, "9999999999")["status"] == "lot_absent"
    r = deed_history(runner, BBL["F"], 2030)
    assert r["status"] == "no_deed_in_graph" and "not 'no transfer happened'" in r["note"]


# ---- the counting rules, on small loads ------------------------------------------------------------------------

def _doc(i, doctype="DEED", amount=100, recorded="2020-01-01"):
    return {"documentid": i, "crfn": f"C{i}", "doctype": doctype, "docdate": recorded, "docamount": amount, "recordedfiled": recorded}


@pytest.fixture
def small(tx, schema):
    """Two lots, one deed on both, one correction, one DEEDO, one $0 deed."""
    lots = [{"bbl": "3099990001", "address": "", "unitsres": None, "cd": None}, {"bbl": "3099990002", "address": "", "unitsres": None, "cd": None}]
    docs = [_doc("D1", amount=500, recorded="2019-05-05"), _doc("D2", "DEED COR", 0, "2019-06-06"), _doc("D3", "DEEDO", 0, "2021-01-01"), _doc("D4", amount=0, recorded="2022-02-02")]
    legals = [{"documentid": "D1", "bbl": "3099990001"}, {"documentid": "D1", "bbl": "3099990002"}, {"documentid": "D2", "bbl": "3099990001"},
              {"documentid": "D3", "bbl": "3099990001"}, {"documentid": "D4", "bbl": "3099990001"}]
    parties = [{"documentid": d, "partytype": t, "name": n, "address1": None} for d, t, n in
               [("D1", "1", "SELLER ONE LLC"), ("D1", "2", "BUYER ONE LLC"), ("D3", "1", "A B"), ("D3", "2", "A. B."), ("D4", "1", "BUYER ONE LLC"), ("D4", "2", "NEW OWNER INC")]]
    register_snapshot(tx, SNAP, "justfixwow", SNAP_DATE)
    load_pluto(tx, schema, lots, SNAP)
    load_acris(tx, schema, docs, parties, legals, frozenset(r["bbl"] for r in lots), SNAP, SNAP_DATE)
    return tx


def test_a_deed_on_two_lots_counts_once_on_each_lot_and_names_both(small):
    for lot in ("3099990001", "3099990002"):
        r = deed_history(small, lot)
        assert any(t["document_id"] == "D1" and t["lots_on_document"] == ["3099990001", "3099990002"] for t in r["timeline"])
    assert deed_history(small, "3099990002")["deeds"] == 1


def test_corrections_are_counted_apart_and_not_as_transfers(small):
    r = deed_history(small, "3099990001")
    assert r["deeds"] == 3 and r["corrections_not_counted"] == 1 and "D2" not in [t["document_id"] for t in r["timeline"]]


def test_zero_dollar_deeds_are_not_for_value_and_deedo_is_noted(small):
    r = deed_history(small, "3099990001")
    by = {t["document_id"]: t for t in r["timeline"]}
    assert (r["deeds_for_value"], r["deeds_for_zero_dollars"]) == (1, 2) and by["D4"]["for_value"] is False
    assert "catch-all" in by["D3"]["note"] and by["D3"]["grantor_and_grantee_share_a_normalized_name"] == ["A B"]
    assert r["last_deed_for_value"]["document_id"] == "D1"


def test_the_timeline_is_oldest_first(small):
    assert [t["document_id"] for t in deed_history(small, "3099990001")["timeline"]] == ["D1", "D3", "D4"]
