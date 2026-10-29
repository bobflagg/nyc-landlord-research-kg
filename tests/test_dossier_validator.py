"""The Q20 validator catches each way a dossier can break the acceptance requirement (design note 0030, I6). Scripted ledgers; no model."""
import copy
import json

from agent.investigator import dossier as D
from agent.investigator.ledger import Ledger
from agent.investigator.validate import check, passed

META = {"snapshot_id": "justfixwow-2026-05-29", "snapshot_date": "2026-05-29", "bor_run": "r", "as_of": {}}


def good():
    led = Ledger("5413 PLAZA LLC", max_calls=40)
    r = led.log("get_hpd_registrations", {"bbl": "3008260002"}, {"status": "found", "owner": "5413 PLAZA LLC", "address": "746 61ST ST 11220"}, "recorded_assertion")
    led.log("find_lot_by_address", {}, {"status": "found"}, "recorded_assertion")
    led.log("get_deed_history", {}, {"status": "found"}, "recorded_assertion")
    led.log("get_dos_record", {}, {"status": "found", "jurisdiction": "New York"}, "recorded_assertion")
    led.log("get_owner_portfolio", {}, {"status": "not_in_group"}, "derived_lead")
    led.log("search_reports", {}, {"status": "no_reports_found"}, "reported_claim")
    led.record_claim("HPD lists 5413 PLAZA LLC as the registered owner.", [r.result_id])
    l = led.add_lead("address", "746 61ST ST 11220", r.result_id)
    led.close_lead(l.lead_id, "resolved")
    led.finish()
    return D.build(led, META)


def failing(d):
    return {n for n, ok, _ in check(d) if not ok}


def test_a_good_dossier_passes_every_check():
    res = check(good(), replay_diffs=[])
    assert passed(res), [r for r in res if not r[1]]


def test_each_violation_is_caught():
    d = good()
    x = copy.deepcopy(d); x["claims"][0]["sources"] = []
    assert "2 claim to source" in failing(x)
    x = copy.deepcopy(d); x["claims"][0]["sources"][0]["result_id"] = "R99"
    assert "2 claim to source" in failing(x)
    x = copy.deepcopy(d); x["claims"][0]["label"] = "derived_lead"
    assert "3 labels" in failing(x)
    x = copy.deepcopy(d); x["claims"][0]["review_status"] = "unreviewed"
    assert "3 labels" in failing(x)
    x = copy.deepcopy(d); x["claims"].append({**x["claims"][0], "claim_id": "C9", "label": "derived_lead", "review_status": "unreviewed", "statement": "The portfolio owns the lot."})
    assert "2 claim to source" in failing(x)
    x = copy.deepcopy(d); x["leads"][0]["value"] = "somewhere else"
    assert "1 lead rule" in failing(x)
    x = copy.deepcopy(d); x["leads"].append({"lead_id": "L9", "kind": "person_name", "value": "x", "key": "X", "found_in": "R1", "disposition": "resolved"})
    assert "1 lead rule" in failing(x)
    x = copy.deepcopy(d); x["leads"][0]["disposition"] = "unresolved"
    assert "4 unresolved leads have reasons" in failing(x)
    x = copy.deepcopy(d); x["finished"]["stop_reason"] = "budget_reached"
    assert "5 stop reason" in failing(x)
    x = copy.deepcopy(d); x["finished"] = None
    assert "5 stop reason" in failing(x)
    x = copy.deepcopy(d); x["retrieval_log"] = [r for r in x["retrieval_log"] if r["tool"] != "search_reports"]
    assert "component Q16 reports" in failing(x)


def test_a_foreign_entity_needs_a_registry_step():
    d = good()
    d["retrieval_log"].append({**d["retrieval_log"][3], "result_id": "R9", "text": json.dumps({"jurisdiction": "Delaware"})})
    assert "6 other jurisdictions" in failing(d)
    d["retrieval_log"].append({**d["retrieval_log"][3], "result_id": "R10", "tool": "lookup_registry", "text": "{}"})
    assert "6 other jurisdictions" not in failing(d)


def test_a_replay_with_differences_fails():
    assert "7 reproducible" in {n for n, ok, _ in check(good(), replay_diffs=[{"x": 1}]) if not ok}


def test_the_stop_reason_is_decided_by_the_leads_and_the_budget():
    from agent.investigator.ledger import LedgerError, compute_stop
    assert compute_stop([], False) == "no_further_recorded_link"
    assert compute_stop([{"lead_id": "L1", "disposition": "queued"}], True) == "budget_reached"
    try:
        compute_stop([{"lead_id": "L1", "disposition": "queued"}], False)
        assert False
    except LedgerError:
        pass
