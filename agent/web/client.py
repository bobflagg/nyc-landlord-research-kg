"""Search and fetch through our own interface over Tavily (design note 0028, W1). Every call is logged, budgeted, cached and time-stamped.

Modes (WEB_MODE or the argument): live (cache first, then the network), replay (cache only, ignoring time to live; a miss is an error, so tests never touch the network),
offline (same as replay). The API key is read from TAVILY_API_KEY in .env and never printed or logged. Fetched text is untrusted data: nothing here interprets it."""
import os

import httpx
from dotenv import load_dotenv

from agent.web.cache import Cache
from agent.web.evidence import Budget, BudgetExhausted, now_iso
from etl.config import ROOT

API = "https://api.tavily.com"
PROVIDER = "tavily"


class WebError(Exception):
    def __init__(self, kind: str, detail: str):
        super().__init__(detail)
        self.kind, self.detail = kind, detail     # kind is a lead-reason: inaccessible, unreadable, ...


class ReplayMiss(WebError):
    def __init__(self, what: str):
        super().__init__("inaccessible", f"replay mode and no recorded response for {what}")


class WebClient:
    def __init__(self, cache: Cache | None = None, mode: str | None = None, budget: Budget | None = None, transport: httpx.BaseTransport | None = None):
        load_dotenv(ROOT / ".env")
        self.mode = mode or os.environ.get("WEB_MODE", "live")
        self.cache = cache or Cache()
        self.budget = budget or Budget()
        self.log: list[dict] = []
        self._transport = transport

    # ---- one request, cached ----
    def _call(self, kind: str, endpoint: str, params: dict, timeout: float = 30.0) -> tuple[dict, str, bool]:
        hit = self.cache.get(kind, {"provider": PROVIDER, "endpoint": endpoint, **params}, ignore_ttl=self.mode in ("replay", "offline"))
        if hit:
            return hit["response"], hit["retrieved_at"], True
        if self.mode in ("replay", "offline"):
            raise ReplayMiss(f"{endpoint} {params}")
        key = os.environ.get("TAVILY_API_KEY")
        if not key:
            raise WebError("inaccessible", "TAVILY_API_KEY is not set")
        try:
            with httpx.Client(transport=self._transport, timeout=timeout) as c:
                r = c.post(f"{API}/{endpoint}", json=params, headers={"Authorization": f"Bearer {key}"})
        except httpx.HTTPError as e:
            raise WebError("inaccessible", f"{type(e).__name__} reaching the search provider") from None
        if r.status_code != 200:
            raise WebError("inaccessible", f"the search provider answered {r.status_code}")
        at = now_iso()
        data = r.json()
        self.cache.put(kind, {"provider": PROVIDER, "endpoint": endpoint, **params}, data, at)
        return data, at, False

    def search(self, query: str, news: bool = False, max_results: int = 8, start_date: str | None = None, end_date: str | None = None) -> dict:
        self.budget.use("search")
        params = {"query": query, "topic": "news" if news else "general", "max_results": max_results, "search_depth": "basic", "include_published_date": True, "exact_match": True}
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date
        data, at, cached = self._call("search", "search", params)
        self.log.append({"kind": "search", "provider": PROVIDER, "query": query, "topic": params["topic"], "retrieved_at": at, "cached": cached, "results": len(data.get("results", []))})
        return {"query": query, "retrieved_at": at, "cached": cached, "results": data.get("results", [])}

    def fetch(self, url: str, query: str | None = None) -> dict:
        self.budget.use("fetch")
        params = {"urls": [url], "format": "text", "extract_depth": "basic"}
        if query:
            params |= {"query": query, "chunks_per_source": 3}
        data, at, cached = self._call("extract", "extract", params, timeout=65.0)
        failed = data.get("failed_results") or []
        self.log.append({"kind": "fetch", "provider": PROVIDER, "url": url, "retrieved_at": at, "cached": cached, "ok": bool(data.get("results")), "failed": [f.get("error") for f in failed]})
        if not data.get("results"):
            raise WebError("unreadable", (failed[0].get("error") if failed else "no text was extracted"))
        return {"url": url, "retrieved_at": at, "cached": cached, "text": data["results"][0].get("raw_content") or ""}
