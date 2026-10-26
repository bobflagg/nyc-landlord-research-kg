"""Q1 end to end: model, tool and graph. Needs ANTHROPIC_API_KEY and the sample committed in nyclr
(`uv run python -m etl.sample`). Deterministic evaluators: tool trajectory, citations, caveats."""
import os

import pytest
from dotenv import load_dotenv
from langsmith import testing as t

from agent.harness import ask
from etl.config import ROOT
from tests.fakes import FakeGeo

load_dotenv(ROOT / ".env")
TRACING = os.environ.get("LANGSMITH_TRACING", "").lower() == "true"  # off in .env unless you turn it on


def log(inputs=None, outputs=None):
    """Record to LangSmith only when tracing is on; the assertions run either way."""
    if TRACING and inputs:
        t.log_inputs(inputs)
    if TRACING and outputs:
        t.log_outputs(outputs)


@pytest.fixture(autouse=True)
def fake_geocoder(monkeypatch):
    """The sample lots are invented, so the real Geosupport cannot know them; a stub stands in for it."""
    import agent.tools.lookup as lookup_module
    monkeypatch.setattr(lookup_module, "_client", FakeGeo())


pytestmark = [pytest.mark.agent, pytest.mark.skipif(not os.environ.get("ANTHROPIC_API_KEY"), reason="no model key")]


@pytest.mark.langsmith
def test_q1_found():
    q = "What lot and buildings are at 1 Example Street, zip 11201?"
    log(inputs={"question": q})
    out = ask(q)
    log(outputs=out)
    call = out["tool_calls"][0]
    assert call["name"] == "find_lot_by_address" and call["args"]["zip5"] == "11201"
    a = out["answer"]
    assert "3000010001" in a and "3000001" in a                      # correct keys
    assert "sample-2026-01-01" in a                                    # snapshot cited
    assert "3000010002" not in a and "3000002" not in a                # no other property equated


@pytest.mark.langsmith
def test_q1_not_found_does_not_guess():
    q = "What lot is at 99 Nowhere Avenue, zip 11201?"
    log(inputs={"question": q})
    out = ask(q)
    log(outputs=out)
    a = out["answer"].lower()
    assert "no lot found" in a and "99 nowhere avenue" in a           # says why, shows the spelling tried
    assert "3000010" not in a                                          # no nearby lot suggested
