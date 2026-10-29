"""Model construction with usage tracking, and what the usage cost (design note 0030, cost controls).

Every chat model the project builds goes through chat_model(): it attaches one process-wide usage handler, so a run can be priced afterwards
(snapshot() before, report(delta(...)) after). Prices are Anthropic's first-party list prices per million tokens as cached in the claude-api skill on 2026-10-06
(Sonnet 5.5 $2 in / $10 out, Haiku 5.5 $0.10 / $0.50 for prompts up to 100K tokens); a cache read costs 0.1x the input price and a 5-minute cache write 1.25x.
The figures are estimates from token counts, not an invoice."""
import copy
import os

from langchain.chat_models import init_chat_model
from langchain_core.callbacks import UsageMetadataCallbackHandler

TRACKER = UsageMetadataCallbackHandler()
PRICES = {   # model substring -> (input, output) dollars per million tokens
    "haiku-5-5": (0.10, 0.50), "sonnet-5-5": (2.00, 10.00), "sonnet-5": (2.00, 10.00), "opus-5-5": (4.00, 20.00), "fable": (10.00, 50.00),
}
CHEAP = "anthropic:claude-haiku-5-5"        # reading a quote, judging an answer, searching the web: mechanical steps
MAIN = "anthropic:claude-sonnet-5-5"


def model_for(role: str) -> str:
    """The model string for a role. AGENT_MODEL (or MODEL) for the agents; JUDGE_MODEL, READER_MODEL and WEB_MODEL default to the cheap model."""
    if role == "agent":
        return os.environ.get("AGENT_MODEL") or os.environ.get("MODEL") or MAIN
    return os.environ.get(f"{role.upper()}_MODEL") or CHEAP


def chat_model(name: str, **kw):
    return init_chat_model(name, callbacks=[TRACKER], **kw)


def snapshot() -> dict:
    return copy.deepcopy(TRACKER.usage_metadata)


def delta(before: dict, after: dict) -> dict:
    out = {}
    for model, u in after.items():
        b = before.get(model, {})
        d = {"input_tokens": u.get("input_tokens", 0) - b.get("input_tokens", 0), "output_tokens": u.get("output_tokens", 0) - b.get("output_tokens", 0)}
        ib, ia = b.get("input_token_details", {}), u.get("input_token_details", {})
        d["cache_read"] = ia.get("cache_read", 0) - ib.get("cache_read", 0)
        d["cache_creation"] = ia.get("cache_creation", 0) - ib.get("cache_creation", 0)
        if any(d.values()):
            out[model] = d
    return out


def _price(model: str) -> tuple[float, float]:
    for key, p in PRICES.items():
        if key in model:
            return p
    return PRICES["sonnet-5-5"]


def report(usage: dict) -> dict:
    """Tokens and estimated dollars per model and in total. input_tokens already includes the cache tokens (LangChain's convention)."""
    rows, total = {}, 0.0
    for model, u in usage.items():
        pin, pout = _price(model)
        fresh = u["input_tokens"] - u["cache_read"] - u["cache_creation"]
        dollars = (fresh * pin + u["cache_read"] * pin * 0.1 + u["cache_creation"] * pin * 1.25 + u["output_tokens"] * pout) / 1e6
        rows[model] = {**u, "uncached_input": fresh, "dollars": round(dollars, 4)}
        total += dollars
    return {"models": rows, "total_dollars": round(total, 4), "total_input_tokens": sum(u["input_tokens"] for u in usage.values()),
            "total_output_tokens": sum(u["output_tokens"] for u in usage.values()), "cache_read_tokens": sum(u["cache_read"] for u in usage.values())}
