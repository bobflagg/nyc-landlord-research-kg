"""The investigation ledger (design note 0030): the dossier rules on scripted tool sequences. No model, no database, no network."""
import pytest

from agent.investigator.ledger import Ledger, LedgerError


def ledger(**kw):
    return Ledger("5413 PLAZA LLC", **kw)


def rec(led, tool="get_hpd_registrations", label="recorded_assertion", **result):
    return led.log(tool, {"bbl": "3008260002"}, result or {"status": "found", "owner": "5413 PLAZA LLC", "agent": "JAY WONG", "address": "746 61ST ST 11220"}, label).result_id


# ---- the log ------------------------------------------------------------------------------------------------

def test_every_result_gets_an_id_a_time_a_category_and_a_hash():
    led = ledger()
    r = led.record(rec(led))
    assert r.result_id == "R1" and r.called_at and r.source_category == "public_record" and len(r.result_hash) == 16
    r2 = led.record(rec(led, "get_owner_portfolio", "derived_lead"))
    assert r2.source_category == "project_derived" and r2.result_id == "R2"


def test_an_unknown_result_id_is_refused():
    with pytest.raises(LedgerError):
        ledger().record("R9")


# ---- claims -------------------------------------------------------------------------------------------------

def test_a_claim_needs_cited_sources_and_takes_the_weakest_label():
    led = ledger()
    a, b = rec(led), rec(led, "get_owner_portfolio", "derived_lead", status="found", group="OP-1")
    with pytest.raises(LedgerError):
        led.record_claim("x", [])
    c1 = led.record_claim("HPD registers 5413 PLAZA LLC as owner.", [a])
    assert c1.label == "recorded_assertion" and c1.review_status is None and c1.sources[0].tool == "get_hpd_registrations"
    c2 = led.record_claim("The run places the lot in a group.", [a, b])
    assert c2.label == "derived_lead" and c2.review_status == "unreviewed" and c2.source_category == "project_derived"


def test_a_reported_claim_needs_a_verbatim_quote_from_its_source():
    led = ledger()
    r = rec(led, "search_reports", "reported_claim", status="found", items=[{"quote": "The owner skipped the tenant meeting."}])
    with pytest.raises(LedgerError, match="verbatim quote"):
        led.record_claim("A report says the owner skipped a meeting.", [r])
    with pytest.raises(LedgerError, match="does not appear verbatim"):
        led.record_claim("A report says so.", [r], quote="The owner attended the tenant meeting.")
    c = led.record_claim("A report says the owner skipped a meeting.", [r], quote="the owner skipped   the tenant meeting.")
    assert c.label == "reported_claim" and c.quote


@pytest.mark.parametrize("label", ["derived_lead", "reported_claim"])
def test_ownership_cannot_rest_on_a_derived_or_reported_source(label):
    led = ledger()
    r = rec(led, "x", label, status="found", text="Harbor Fund controls it")
    for stmt in ("Harbor Fund owns 5413 Plaza LLC.", "The lot is owned by the portfolio's anchor.", "X controls the building."):
        with pytest.raises(LedgerError, match="cannot state ownership"):
            led.record_claim(stmt, [r], quote="Harbor Fund controls it")
    led.record_claim("The run does not show who owns the lot; it places it in a group.", [r], quote="Harbor Fund controls it")      # a denial is allowed


def test_a_recorded_assertion_may_state_a_recorded_ownership_role():
    led = ledger()
    c = led.record_claim("HPD lists 5413 PLAZA LLC as the registered owner.", [rec(led)])
    assert c.label == "recorded_assertion"


# ---- leads --------------------------------------------------------------------------------------------------

def test_a_lead_must_appear_in_a_retrieved_source():
    led = ledger()
    r = rec(led)
    with pytest.raises(LedgerError, match="does not appear"):
        led.add_lead("entity_name", "Invented Holdings LLC", r)
    assert led.add_lead("entity_name", "jay wong", r).disposition in ("queued", "set_aside")


def test_a_person_is_logged_and_not_followed():
    led = ledger()
    l = led.add_lead("person_name", "JAY WONG", rec(led))
    assert l.disposition == "set_aside" and l.reason == "person_not_followed"


def test_a_masked_or_mail_drop_address_is_set_aside_with_its_reason():
    led = ledger(address_checker=lambda a: {"reason": "mail_drop_address", "note": "on the list"} if "BROADWAY" in a.upper() else None)
    r = rec(led, address="418 BROADWAY 12207", other="746 61ST ST 11220")
    a = led.add_lead("address", "418 BROADWAY 12207", r)
    b = led.add_lead("address", "746 61ST ST 11220", r)
    assert (a.disposition, a.reason) == ("set_aside", "mail_drop_address") and b.disposition == "queued"


def test_a_duplicate_and_the_subject_itself_are_not_followed_twice():
    led = ledger()
    r = rec(led)
    assert led.add_lead("address", "746 61ST ST 11220", r).disposition == "queued"
    assert led.add_lead("address", "746 61st st 11220", r).reason == "already_followed"
    assert led.add_lead("entity_name", "5413 Plaza LLC", r).reason == "already_followed"


def test_leads_past_the_budget_are_set_aside_with_that_reason():
    led = ledger(max_leads=1)
    r = rec(led, a="Alpha Realty LLC", b="Beta Realty LLC")
    assert led.add_lead("entity_name", "Alpha Realty LLC", r).disposition == "queued"
    assert led.add_lead("entity_name", "Beta Realty LLC", r).reason == "budget_exhausted"


def test_closing_a_lead_needs_a_reason_when_unresolved():
    led = ledger()
    r = rec(led)
    l = led.add_lead("address", "746 61ST ST 11220", r)
    with pytest.raises(LedgerError):
        led.close_lead(l.lead_id, "unresolved")
    with pytest.raises(LedgerError):
        led.close_lead(l.lead_id, "unresolved", "made_up")
    assert led.close_lead(l.lead_id, "unresolved", "inaccessible").reason == "inaccessible"
    with pytest.raises(LedgerError, match="only a queued lead"):
        led.close_lead(l.lead_id, "resolved")


# ---- the stop reason ----------------------------------------------------------------------------------------

def finished(led):
    led.record_claim("HPD lists an owner.", [rec(led)])
    return led.finish()["stop_reason"]


def test_open_leads_block_finishing_unless_the_budget_is_spent():
    led = ledger(max_calls=3)
    r = rec(led)
    led.add_lead("address", "746 61ST ST 11220", r)
    led.record_claim("HPD lists an owner.", [r])
    with pytest.raises(LedgerError, match="still open"):
        led.finish()
    rec(led); rec(led)                                     # three calls: the budget is spent
    assert led.finish()["stop_reason"] == "budget_reached"


def test_no_open_lead_and_nothing_unresolved_is_no_further_recorded_link():
    led = ledger()
    l = led.add_lead("address", "746 61ST ST 11220", rec(led))
    led.close_lead(l.lead_id, "resolved")
    assert finished(led) == "no_further_recorded_link"


def test_a_trail_that_reached_a_mail_drop_address_says_so():
    led = ledger(address_checker=lambda a: {"reason": "masked_address"})
    led.add_lead("address", "746 61ST ST 11220", rec(led))
    assert finished(led) == "reached_registered_agent_mail_drop_or_masked_address"


@pytest.mark.parametrize("reason,stop", [("needs_payment", "needs_payment_or_inaccessible"), ("inaccessible", "needs_payment_or_inaccessible"), ("conflicting_records", "conflicting_records_unresolved")])
def test_an_unresolved_lead_decides_the_stop(reason, stop):
    led = ledger()
    l = led.add_lead("address", "746 61ST ST 11220", rec(led))
    led.close_lead(l.lead_id, "unresolved", reason)
    assert finished(led) == stop


def test_a_mail_drop_set_aside_does_not_hide_an_unresolved_lead():
    led = ledger(address_checker=lambda a: {"reason": "mail_drop_address"} if a.startswith("418") else None)
    r = rec(led, a="418 BROADWAY 12207", b="746 61ST ST 11220")
    led.add_lead("address", "418 BROADWAY 12207", r)
    l = led.add_lead("address", "746 61ST ST 11220", r)
    led.close_lead(l.lead_id, "unresolved", "inaccessible")
    assert finished(led) == "needs_payment_or_inaccessible"


def test_finishing_needs_a_claim_and_happens_once():
    led = ledger()
    with pytest.raises(LedgerError, match="at least one claim"):
        led.finish()
    finished(led)
    with pytest.raises(LedgerError, match="already finished"):
        led.finish()


def test_parallel_tool_calls_get_distinct_ids_and_never_exceed_the_budget():
    import threading
    led = ledger(max_calls=20)
    ran = []
    def call():
        if led.reserve():
            ran.append(led.log("t", {}, {"status": "found"}, "recorded_assertion").result_id)
    ts = [threading.Thread(target=call) for _ in range(40)]
    [t.start() for t in ts]; [t.join() for t in ts]
    assert len(ran) == 20 and len(set(ran)) == 20
    ids = []
    def lead(i):
        ids.append(led.add_lead("entity_name", f"Co {i} LLC", led.log("t", {}, {"n": f"Co {i} LLC"}, "recorded_assertion").result_id).lead_id)
    ts = [threading.Thread(target=lead, args=(i,)) for i in range(10)]
    [t.start() for t in ts]; [t.join() for t in ts]
    assert len(set(ids)) == 10


def test_finish_is_refused_until_a_required_tool_was_called_unless_the_budget_is_spent():
    led = Ledger("x", max_calls=3, required_tools=("search_reports",))
    r = rec(led)
    led.record_claim("HPD lists an owner.", [r])
    with pytest.raises(LedgerError, match="search_reports has not been called"):
        led.finish()
    led.log("search_reports", {}, {"status": "no_reports_found"}, "reported_claim")
    assert led.finish()["stop_reason"] in ("no_further_recorded_link", "budget_reached")
    led2 = Ledger("x", max_calls=1, required_tools=("search_reports",))
    led2.record_claim("HPD lists an owner.", [rec(led2)])
    assert led2.finish()["stop_reason"]          # the budget is spent: finishing is allowed without the search


def test_finish_is_refused_while_a_foreign_dos_entity_has_no_registry_step():
    led = ledger()
    r = rec(led)
    led.log("get_dos_record", {}, {"status": "found", "records": [{"jurisdiction": "Wyoming"}]}, "recorded_assertion")
    led.record_claim("HPD lists an owner.", [r])
    with pytest.raises(LedgerError, match="registered in Wyoming"):
        led.finish()
    led.log("lookup_registry", {}, {"status": "unresolved"}, "recorded_assertion")
    assert led.finish()["stop_reason"] == "no_further_recorded_link"


def test_a_claim_cannot_use_an_id_or_date_that_is_not_in_its_cited_results():
    led = ledger()
    a = rec(led, status="found", doc="2021031601183001", recorded="2021-03-22")
    b = rec(led, status="found", other="2023061200959001")
    with pytest.raises(LedgerError, match="not in the cited results: 2023061200959001"):
        led.record_claim("Mortgage 2021031601183001 and termination 2023061200959001 are recorded.", [a])
    with pytest.raises(LedgerError, match="2024-01-01"):
        led.record_claim("Mortgage 2021031601183001 was recorded 2024-01-01.", [a])
    assert led.record_claim("Mortgage 2021031601183001 was recorded 2021-03-22.", [a]).claim_id == "C1"
    assert led.record_claim("Termination 2023061200959001 is recorded; mortgage 2021031601183001 is also.", [a, b]).claim_id == "C2"
