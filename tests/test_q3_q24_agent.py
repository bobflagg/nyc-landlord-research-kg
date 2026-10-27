"""Q3 and Q24 end to end on the real graph: model, tools, nyclr. Needs ANTHROPIC_API_KEY and the Slice 1 data loaded
(HPD, ACRIS, DOS). Deterministic evaluators: tool trajectory, keys, caveats, no overreach."""
import os

import pytest
from dotenv import load_dotenv

from agent.harness import ask
from etl.config import ROOT
from tests.test_q1_agent import log

load_dotenv(ROOT / ".env")
pytestmark = [pytest.mark.agent, pytest.mark.skipif(not os.environ.get("ANTHROPIC_API_KEY"), reason="no model key")]


@pytest.mark.langsmith
def test_q3_a_deed_and_the_hpd_owner():
    q = "For lot 3008260002, who is the grantee on the most recent deed and is it the same name as the HPD owner?"
    log(inputs={"question": q})
    out = ask(q)
    log(outputs=out)
    assert any(c["name"] == "compare_deed_grantee_with_hpd_owner" and c["args"]["bbl"] == "3008260002" for c in out["tool_calls"])
    a = out["answer"]
    assert "2025032100031001" in a and "5413 PLAZA LLC" in a and "316103" in a
    assert "2021022201130003" in a                                      # the last deed for value
    assert "justfixwow-2026-05-29" in a
    low = a.lower()
    assert "lead" in low                                                # a name match is called a lead
    assert not any(p in low for p in (" owns ", "is the owner of", "proves ownership", "confirmed owner"))   # no ownership claim


@pytest.mark.langsmith
def test_q24_start_from_a_name_states_its_limits():
    q = "I have a letter from 5413 PLAZA LLC. What do the records show for that name?"
    log(inputs={"question": q})
    out = ask(q)
    log(outputs=out)
    assert any(c["name"] == "find_records_by_name" for c in out["tool_calls"])
    a = out["answer"]
    assert "5857246" in a and "316103" in a and "2021022201130003" in a   # DOS id, HPD registration, a deed
    low = a.lower()
    assert "deed" in low and ("only" in low or "not loaded" in low or "not searched" in low)   # coverage limit
    assert "mortgage" not in low or "not" in low


@pytest.mark.langsmith
def test_q2_registered_owner_with_dates_and_snapshot():
    q = "Who is the HPD registered owner of lot 3008260002 and when does the registration period end?"
    log(inputs={"question": q})
    out = ask(q)
    log(outputs=out)
    assert any(c["name"] == "get_hpd_registrations" and c["args"]["bbl"] == "3008260002" for c in out["tool_calls"])
    a = out["answer"]
    assert "316103" in a and "5413 PLAZA LLC" in a and "2026-09-01" in a and "2026-05-29" in a
    assert "title" in a.lower()                                          # says a registration is not proof of title


@pytest.mark.langsmith
def test_q4_managing_agent_is_management_not_ownership():
    q = "Who is the managing agent and who is the head officer listed for lot 3008260002?"
    log(inputs={"question": q})
    out = ask(q)
    log(outputs=out)
    assert any(c["name"] == "get_hpd_contacts" for c in out["tool_calls"])
    a = out["answer"]
    assert "JAY WONG" in a.upper() and "BAOZHEN CHEN" in a.upper() and "PRESIDENT" in a.upper()
    low = a.lower()
    assert "management" in low and "not ownership" in low or "does not" in low
    assert not any(p in low for p in (" owns ", "is the owner of", "controls the building"))


@pytest.mark.langsmith
def test_q5_dos_record_and_its_limits():
    q = "What does the New York Department of State record say about 5413 PLAZA LLC?"
    log(inputs={"question": q})
    out = ask(q)
    log(outputs=out)
    assert any(c["name"] == "get_dos_record" for c in out["tool_calls"])
    a = out["answer"]
    assert "5857246" in a and "2020-10-14" in a and "5 CROMWELL CIRCLE" in a.upper()
    low = a.lower()
    assert "active" in low                                              # active entities only
    assert "run" in low or "who runs" in low or "does not say" in low   # process address is not who runs the entity


@pytest.mark.langsmith
def test_q5_the_hpd_spelling_finds_no_record_and_the_agent_tries_the_other_spelling():
    q = "Is there a Department of State record for the owner 438 52 ST OWNERS CORP, which is how HPD spells it?"
    log(inputs={"question": q})
    out = ask(q)
    log(outputs=out)
    names = [c["args"].get("name", "") for c in out["tool_calls"] if c["name"] == "get_dos_record"]
    assert names and names[0].upper() == "438 52 ST OWNERS CORP"
    low = out["answer"].lower()
    assert "no record" in low or "no dos record" in low or "no match" in low or "did not find" in low
    assert "not" in low and "exist" in low                              # no record is not 'does not exist'
