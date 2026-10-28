"""Q17 tool against the anchor lots, loaded into nyclr inside a rolled-back transaction (design note 0020). Expected values are
the ones in docs/competency-questions-detail.md (anchors E, F and A) re-read from the snapshot."""
import json
from datetime import date

import pytest

from agent.tools.conditions import registration_status
from etl.build import load_acris, load_hpd, load_pluto
from etl.config import ROOT
from etl.load import apply_schema, register_snapshot

SNAP, SNAP_DATE = "justfixwow-2026-05-29", date(2026, 5, 29)
FX = ROOT / "tests" / "fixtures"
ANCH, AC = (json.loads((FX / f).read_text()) for f in ("slice1_anchors.json", "slice1_acris.json"))
LOTS = frozenset(str(r["bbl"]).strip() for r in ANCH["pluto"])
A, B, C, D, E, F, G = "3008260002", "3008260005", "3008070024", "3008210012", "3008210019", "3008970014", "3008080025"


@pytest.fixture
def graph(session, schema):
    apply_schema(session, schema)
    tx = session.begin_transaction()
    register_snapshot(tx, SNAP, "justfixwow", SNAP_DATE)
    load_pluto(tx, schema, ANCH["pluto"], SNAP)
    load_hpd(tx, schema, ANCH["registrations"], ANCH["contacts"], SNAP)
    load_acris(tx, schema, AC["documents"], AC["parties"], AC["legals"], LOTS, SNAP, SNAP_DATE)
    yield tx
    tx.rollback()


def test_anchor_e_lapsed_and_older_than_the_latest_deed(graph):
    r = registration_status(graph, E)
    assert r["status"] == "found" and r["registration"] == "present" and r["no_registration"] is False
    assert (r["latest_registration_date"], r["latest_registration_end_date"]) == ("2020-08-31", "2021-09-01")
    assert r["lapsed"] is True and r["registration_older_than_latest_deed"] is True and r["latest_deed"]["recorded"] == "2026-04-21"
    assert r["units"]["residential"] == 6 and r["units"]["at_or_above_threshold"] is True


def test_anchor_f_has_no_registration_and_is_new_construction(graph):
    r = registration_status(graph, F)
    assert r["registration"] == "none_in_dataset" and r["no_registration"] is True and r["lapsed"] is None
    assert r["units"]["residential"] == 40 and r["year_built"] == 2025 and "legitimate reason" in r["recently_built"]
    assert "not 'the owner failed to register'" in r["note"]


def test_anchor_a_current_registration_period_ends_after_the_snapshot(graph):
    r = registration_status(graph, A)
    assert r["latest_registration_end_date"] == "2026-09-01" and r["lapsed"] is False and r["registration_older_than_latest_deed"] is False


@pytest.mark.parametrize("lot", [A, B, C, D, E, G])
def test_every_registered_anchor_reports_dates_and_both_conditions(graph, lot):
    r = registration_status(graph, lot)
    assert r["registration"] == "present" and r["registrations"] and isinstance(r["lapsed"], bool)
    assert r["registration_data_as_of"] == "2026-05-29"


def test_the_threshold_is_reported_and_no_ruling_is_made(graph):
    r = registration_status(graph, E)
    assert r["units"]["threshold_in_dataset"] == "3 or more units"
    assert "not decide whether registration was legally required" in " ".join(r["caveats"])


def test_an_unknown_lot_is_lot_absent(graph):
    assert registration_status(graph, "9999999999")["status"] == "lot_absent"
