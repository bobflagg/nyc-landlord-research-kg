"""The investigator's wrapped tools, dossier and replay, driven by a scripted sequence against the real graph (design note 0030). No model."""
import json

import pytest

from agent.db import read_session
from agent.investigator import dossier as D
from agent.investigator.agent import Investigation, replay_tools
from agent.investigator.ledger import Ledger
from agent.investigator.tools import graph_tools, ledger_tools, web_tools

A = "3008260002"


@pytest.fixture(scope="module")
def session():
    with read_session() as s:
        yield s


def toolmap(tools):
    return {t.name: t for t in tools}


def scripted(session, subject="5413 7 AVENUE", max_calls=40):
    inv = Investigation(subject)
    addr, ent = inv._checkers(session)
    led = Ledger(subject, max_calls=max_calls, address_checker=addr, entity_checker=ent)
    return led, toolmap(graph_tools(led)), toolmap(ledger_tools(led))


def test_a_wrapped_tool_returns_a_result_id_a_label_and_logs_the_call(session):
    led, g, _ = scripted(session)
    r = g["get_hpd_registrations"].invoke({"bbl": A})
    assert r["result_id"] == "R1" and r["label"] == "recorded_assertion" and r["source_category"] == "public_record" and "registration_id" in json.dumps(r)
    assert led.records[0].tool == "get_hpd_registrations" and led.records[0].args == {"bbl": A}
    assert g["get_owner_portfolio"].invoke({"bbl": A})["label"] == "derived_lead"


def test_a_scripted_investigation_builds_a_dossier_that_replays(session, tmp_path):
    led, g, l = scripted(session)
    contacts = g["get_hpd_contacts"].invoke({"bbl": A})
    regs = g["get_hpd_registrations"].invoke({"bbl": A})
    layer = g["get_owner_portfolio"].invoke({"bbl": A})
    c1 = l["record_claim"].invoke({"statement": "HPD lists 5413 PLAZA LLC as the registered owner of the lot.", "source_ids": [regs["result_id"]]})
    c2 = l["record_claim"].invoke({"statement": "In the BOR run the lot is in no Owner Portfolio.", "source_ids": [layer["result_id"]]})
    assert c1["label"] == "recorded_assertion" and c2["label"] == "derived_lead"
    refused = l["record_claim"].invoke({"statement": "5413 PLAZA LLC owns the lot.", "source_ids": [layer["result_id"], regs["result_id"]]})
    assert refused["status"] == "refused" and "cannot state ownership" in refused["reason"]
    lead = l["add_lead"].invoke({"kind": "address", "value": "746 61ST ST 11220", "found_in": contacts["result_id"]})
    person = l["add_lead"].invoke({"kind": "person_name", "value": "JAY WONG", "found_in": contacts["result_id"]})
    assert lead["disposition"] == "queued" and person["reason"] == "person_not_followed"
    assert l["finish"].invoke({})["status"] == "refused"                       # a lead is still open
    l["close_lead"].invoke({"lead_id": lead["lead_id"], "outcome": "resolved"})
    done = l["finish"].invoke({})
    assert done["stop_reason"] == "no_further_recorded_link"
    d = D.build(led, D.meta(session))
    folder = D.save(d, "test-scripted", tmp_path)
    md = (folder / "dossier.md").read_text()
    assert "Claims: inference to source" in md and "recorded assertion (Type I)" in md and "derived lead (Type II)" in md and "no_further_recorded_link" in md and "person_not_followed" in md
    assert D.replay(d, replay_tools()) == []                                   # the evidence is reproducible
    d["retrieval_log"][0]["result_hash"] = "0" * 16
    assert D.replay(d, replay_tools())[0]["problem"] == "result differs from the one logged"


def test_a_mail_drop_address_found_in_a_result_is_set_aside_by_the_ledger(session):
    led, g, l = scripted(session)
    r = led.log("get_hpd_contacts", {}, {"status": "found", "address": "418 BROADWAY 12207"}, "recorded_assertion")
    lead = l["add_lead"].invoke({"kind": "address", "value": "418 BROADWAY 12207", "found_in": r.result_id})
    assert (lead["disposition"], lead["reason"]) == ("set_aside", "mail_drop_address")


def test_a_person_given_as_an_entity_name_is_set_aside(session):
    led, g, l = scripted(session)
    r = led.log("x", {}, {"status": "found", "name": "JAY WONG"}, "recorded_assertion")
    assert l["add_lead"].invoke({"kind": "entity_name", "value": "JAY WONG", "found_in": r.result_id})["reason"] == "person_not_followed"


def test_past_the_budget_a_tool_does_not_run(session):
    led, g, l = scripted(session, max_calls=1)
    g["get_hpd_registrations"].invoke({"bbl": A})
    r = g["get_hpd_contacts"].invoke({"bbl": A})
    assert r["status"] == "budget_reached" and len(led.records) == 1


def test_no_tool_after_finishing_and_the_tool_sets_are_the_expected_ones(session):
    led, g, l = scripted(session)
    assert len(g) == 25 and set(toolmap(web_tools(led))) == {"search_reports", "lookup_registry"} and set(l) == {"add_lead", "record_claim", "close_lead", "get_ledger", "finish"}


def test_a_bad_vocabulary_value_is_a_refusal_not_a_crash(session):
    led, g, l = scripted(session)
    r = led.log("get_hpd_contacts", {}, {"status": "found", "address": "746 61ST ST 11220"}, "recorded_assertion")
    lead = l["add_lead"].invoke({"kind": "address", "value": "746 61ST ST 11220", "found_in": r.result_id})
    out = l["close_lead"].invoke({"lead_id": lead["lead_id"], "outcome": "partial"})
    assert out["status"] == "refused"
    assert l["add_lead"].invoke({"kind": "company", "value": "x", "found_in": r.result_id})["status"] == "refused"
