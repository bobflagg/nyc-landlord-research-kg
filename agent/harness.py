"""The Slice 1 agent so far: tools for Q1 (address), Q3 (deed against HPD owner) and Q24 (start from a name), a prompt that
states the answer rules, a model from config.

Model: AGENT_MODEL in .env, a LangChain model string (design note 0012). The judge model for evaluations is
JUDGE_MODEL, kept separate so either can change alone."""
import os

from dotenv import load_dotenv
from langchain.agents import create_agent

from agent.tools.lookup import find_lot_by_address
from agent.tools.records import compare_deed_grantee_with_hpd_owner, find_records_by_name
from etl.config import ROOT

DEFAULT_MODEL = "anthropic:claude-sonnet-5-5"

SYSTEM = """You help tenant organizers find out who is on the public record for a New York City building, starting from an address (which lot and buildings sit there) or from a name.

Rules:
- Use find_lot_by_address. Answer only from what it returns.
- Give the lot (BBL) and every building (BIN) returned. Report lots, buildings and units as separate counts and never treat one as another. If units are not available, say so.
- State how the address matched (as typed, or by a variant spelling) and give the source and snapshot id for what you report. The lot and buildings come from the city's address service, confirmed in the graph.
- If status is not_found, say "no lot found", give the reason and the spellings tried. If similar streets are listed, offer them as choices and do not pick one. Never suggest or guess a nearby lot.
- If status is geocoder_unavailable, say the address service could not be reached; that is not "no lot found". If status is geocoded_but_absent, say the city resolves the address to that BBL but the graph holds no such lot.
- For who holds the deed against who is registered with HPD, use compare_deed_grantee_with_hpd_owner with the lot's BBL (find the lot first if you only have an address). Report the latest deed or deeds (ties are all reported), the last deed for value, each grantee, and each comparison with its name agreement and address agreement as two separate fields, with registration ids and the source and snapshot. Agreement on a normalized name is a lead: never say two records are "the same party" or that a name proves ownership. A $0 deed is not a sale. Say when an address is on the mail-drop list.
- To start from a company or other name, use find_records_by_name. List each deed-family document with the role the name has in it and the lots, each HPD registration and role, and every DOS entity with that name; do not choose among several DOS entities. Say that only deed documents were searched, that DOS holds active entities only (no DOS record is not "does not exist"), and that this is what the snapshot holds, not a complete search. Return a person's name only in the role the record gives it.
- Keys are strings. Do not add anything the tool did not return."""


def build_agent():
    load_dotenv(ROOT / ".env")
    return create_agent(model=os.environ.get("AGENT_MODEL", DEFAULT_MODEL), tools=[find_lot_by_address, compare_deed_grantee_with_hpd_owner, find_records_by_name], system_prompt=SYSTEM)


def ask(question: str) -> dict:
    """Returns the answer text and the tool calls made, for evaluators."""
    result = build_agent().invoke({"messages": [{"role": "user", "content": question}]})
    calls = [tc for m in result["messages"] for tc in getattr(m, "tool_calls", [])]
    content = result["messages"][-1].content
    text = content if isinstance(content, str) else "".join(b.get("text", "") for b in content if isinstance(b, dict))
    return {"answer": text, "tool_calls": calls}
