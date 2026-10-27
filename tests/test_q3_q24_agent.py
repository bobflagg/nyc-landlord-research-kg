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
