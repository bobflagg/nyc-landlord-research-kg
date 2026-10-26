"""The Slice 0 agent: one tool (Q1), a prompt that states the answer rules, a model from config.

Model: AGENT_MODEL in .env, a LangChain model string (design note 0012). The judge model for evaluations is
JUDGE_MODEL, kept separate so either can change alone."""
import os

from dotenv import load_dotenv
from langchain.agents import create_agent

from agent.tools.lookup import find_lot_by_address
from etl.config import ROOT

DEFAULT_MODEL = "anthropic:claude-sonnet-5-5"

SYSTEM = """You help tenant organizers find out which lot and buildings sit at a New York City address.

Rules:
- Use find_lot_by_address. Answer only from what it returns.
- Give the lot (BBL) and every building (BIN) returned. Report lots, buildings and units as separate counts and never treat one as another. If units are not available, say so.
- State how the address matched (as typed, or by a variant spelling) and give the source and snapshot id for what you report. The lot and buildings come from the city's address service, confirmed in the graph.
- If status is not_found, say "no lot found", give the reason and the spellings tried. If similar streets are listed, offer them as choices and do not pick one. Never suggest or guess a nearby lot.
- If status is geocoder_unavailable, say the address service could not be reached; that is not "no lot found". If status is geocoded_but_absent, say the city resolves the address to that BBL but the graph holds no such lot.
- Keys are strings. Do not add anything the tool did not return."""


def build_agent():
    load_dotenv(ROOT / ".env")
    return create_agent(model=os.environ.get("AGENT_MODEL", DEFAULT_MODEL), tools=[find_lot_by_address], system_prompt=SYSTEM)


def ask(question: str) -> dict:
    """Returns the answer text and the tool calls made, for evaluators."""
    result = build_agent().invoke({"messages": [{"role": "user", "content": question}]})
    calls = [tc for m in result["messages"] for tc in getattr(m, "tool_calls", [])]
    content = result["messages"][-1].content
    text = content if isinstance(content, str) else "".join(b.get("text", "") for b in content if isinstance(b, dict))
    return {"answer": text, "tool_calls": calls}
