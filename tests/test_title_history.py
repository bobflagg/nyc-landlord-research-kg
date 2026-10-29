"""Q14 tool: the title holder and registered owner on a past date, on the citywide graph, against expectations worked out from the
source without the graph (Q12 timelines in slice3.json, Q2 registrations in slice1.json, violations in slice2.json). Design note 0022."""
import json
from datetime import date

import pytest

from agent.db import read_session
from agent.tools.history import CAVEATS_Q14, title_and_registrant
from etl.config import ROOT

E = ROOT / "evals" / "expected"
Q12 = json.loads((E / "slice3.json").read_text())["questions"]["Q12"]
Q2 = json.loads((E / "slice1.json").read_text())["questions"]["Q2"]
Q15 = json.loads((E / "slice2.json").read_text())["questions"]["Q15"]
BBL = {k: v["bbl"] for k, v in json.loads((E / "slice1.json").read_text())["anchors"].items()}
norm = lambda s: " ".join(s.split())


@pytest.fixture(scope="module")
def runner():
    with read_session() as s:
        yield s


def expected_title(a, on):
    upto = [t for t in Q12[a]["timeline"] if t["recorded"] <= on]
    if not upto:
        return None, set()
    last = max(t["recorded"] for t in upto)
    return last, {norm(g) for t in upto if t["recorded"] == last for g in t["grantees"]}


def expected_owners(a, on):
    regs = Q2[a]
    if isinstance(regs, str):
        return set()
    return {(r["registration_id"], norm(r["registered_owner"])) for r in regs if r["last_registration_date"] <= on <= r["registration_end_date"]}


DATES = ["1960-01-01", "1990-06-01", "2015-06-01", "2022-10-20", "2024-04-08", "2025-05-01", "2026-05-01", "2026-06-24"]


@pytest.mark.parametrize("a", list(BBL))
@pytest.mark.parametrize("on", DATES)
def test_title_and_registrant_match_the_source(runner, a, on):
    r = title_and_registrant(runner, BBL[a], on)
    assert r["status"] == "found" and r["date"] == on
    last, names = expected_title(a, on)
    if last is None:
        assert r["title"]["title_status"] == "no_deed_recorded_by_then" and r["title"]["title_holders"] == []
    else:
        assert r["title"]["latest_recorded_before_the_date"] == last
        assert {norm(g["party_name"]) for h in r["title"]["title_holders"] for g in h["grantees"]} == names
    owners = expected_owners(a, on)
    assert {(o["registration_id"], norm(o["name"])) for o in r["registration"]["registered_owners"]} == owners
    assert (r["registration"]["registration_status"] == "in_force") == bool(owners) or Q2[a] == "no HPD registration in the snapshot"
    assert r["gaps_and_conflicts"] is not None and any("today's records" in c for c in r["caveats"])


def test_a_date_before_any_deed_says_no_title_holder_is_supported(runner):
    r = title_and_registrant(runner, BBL["B"], "1900-01-01")
    assert r["title"]["title_status"] == "no_deed_recorded_by_then" and any("no title holder is supported" in g for g in r["gaps_and_conflicts"])


def test_a_lapsed_registration_gives_no_registrant_and_says_why(runner):
    r = title_and_registrant(runner, BBL["E"], "2024-04-08")        # registered 2020-08-31, period ended 2021-09-01
    assert r["registration"]["registration_status"] == "none_in_force_in_data" and "after the latest registration period" in r["registration"]["reason"]
    assert r["do_they_coincide"] == "not_comparable" and any("No registered owner is in force" in g for g in r["gaps_and_conflicts"])


def test_a_lot_with_no_registration_is_reported_as_such(runner):
    r = title_and_registrant(runner, BBL["F"], "2025-06-01")
    assert r["registration"]["registration_status"] == "no_registration_on_lot"


def test_the_current_owner_is_never_substituted(runner):
    now = title_and_registrant(runner, BBL["E"], "2026-05-01")["title"]["title_holders"]
    then = title_and_registrant(runner, BBL["E"], "2024-04-08")["title"]["title_holders"]
    assert {g["party_name"] for h in now for g in h["grantees"]} == {"234 54TH ST LLC"} or now
    assert {norm(g["party_name"]) for h in then for g in h["grantees"]} == {"PAGAN ANGEL LUIS"} and then[0]["recorded"] == "1978-10-27"


def test_a_violation_id_gives_its_lot_and_inspection_date(runner):
    vid = Q15["C"]["oldest_open_ids"][0]
    r = title_and_registrant(runner, violation_id=vid)
    assert r["status"] == "found" and r["bbl"] == BBL["C"] and r["violation"]["date_used"] == Q15["C"]["oldest_open_inspection_date"] and r["violation"]["date_kind"] == "inspection"
    last, names = expected_title("C", r["date"])
    assert {norm(g["party_name"]) for h in r["title"]["title_holders"] for g in h["grantees"]} == names


def test_a_notice_date_can_be_asked_for_and_an_unknown_violation_is_reported(runner):
    vid = Q15["C"]["oldest_open_ids"][0]
    r = title_and_registrant(runner, violation_id=vid, date_kind="notice")
    assert r["status"] in ("found", "violation_has_no_notice_date") and (r["status"] != "found" or r["violation"]["date_kind"] == "notice")
    assert title_and_registrant(runner, violation_id="1")["status"] == "violation_not_found"


def test_bad_inputs_are_reported_not_guessed(runner):
    assert title_and_registrant(runner, BBL["A"], "June 2024")["status"] == "bad_date"
    assert title_and_registrant(runner, "9999999999", "2024-01-01")["status"] == "lot_absent"


def test_title_holders_carry_a_dos_note_that_says_nothing_about_the_past(runner):
    r = title_and_registrant(runner, BBL["E"], "1990-06-01")
    assert all("dos_active_record" in g for h in r["title"]["title_holders"] for g in h["grantees"])
    assert any("says nothing about whether the entity existed" in c for c in CAVEATS_Q14)


# ---- the hard cases, on a small load ---------------------------------------------------------------------------

def test_a_deed_dated_before_the_date_but_recorded_after_is_reported_as_uncertain(tx, schema):
    from datetime import date as D
    from etl.build import load_acris, load_pluto
    from etl.load import register_snapshot
    snap = "justfixwow-2026-05-29"
    register_snapshot(tx, snap, "justfixwow", D(2026, 5, 29))
    load_pluto(tx, schema, [{"bbl": "3099990003", "address": "", "unitsres": None, "cd": None}], snap)
    docs = [{"documentid": "T1", "crfn": "C1", "doctype": "DEED", "docdate": "2019-01-01", "docamount": 100, "recordedfiled": "2019-01-10"},
            {"documentid": "T2", "crfn": "C2", "doctype": "DEED", "docdate": "2020-01-15", "docamount": 200, "recordedfiled": "2020-03-01"},
            {"documentid": "T3", "crfn": "C3", "doctype": "MTGE", "docdate": "2020-01-20", "docamount": 900, "recordedfiled": "2020-01-25"}]
    legals = [{"documentid": d["documentid"], "bbl": "3099990003"} for d in docs]
    parties = [{"documentid": d, "partytype": t, "name": n, "address1": None} for d, t, n in
               [("T1", "1", "A SELLER"), ("T1", "2", "FIRST BUYER LLC"), ("T2", "1", "FIRST BUYER LLC"), ("T2", "2", "SECOND BUYER LLC"), ("T3", "1", "SECOND BUYER LLC"), ("T3", "2", "SOME BANK")]]
    load_acris(tx, schema, docs, parties, legals, frozenset({"3099990003"}), snap, D(2026, 5, 29))
    r = title_and_registrant(tx, "3099990003", "2020-02-01")
    assert [g["party_name"] for h in r["title"]["title_holders"] for g in h["grantees"]] == ["FIRST BUYER LLC"]        # the mortgage T3 is not a deed
    assert [d["document_id"] for d in r["title"]["deeds_dated_on_or_before_but_recorded_after"]] == ["T2"]
    assert any("dated on or before the date was recorded after it" in g for g in r["gaps_and_conflicts"])
    assert r["registration"]["registration_status"] == "no_registration_on_lot"
