"""Live smoke test for the search provider and one registry (design note 0028, W6). Off by default: it spends search credits and needs the network.

  WEB_LIVE_TESTS=1 uv run pytest tests/test_web_live.py"""
import os

import pytest

from agent.web.cache import Cache
from agent.web.client import WebClient
from agent.web import registries

pytestmark = pytest.mark.skipif(os.environ.get("WEB_LIVE_TESTS") != "1", reason="live web tests are off by default (set WEB_LIVE_TESTS=1)")


def test_the_search_provider_answers_with_results_and_a_retrieval_time():
    r = WebClient(cache=Cache(":memory:"), mode="live").search('"New York City Housing Preservation and Development"', news=False, max_results=2)
    assert r["results"] and r["retrieved_at"] and not r["cached"]


def test_the_connecticut_registry_answers():
    out = registries.lookup("CT", "Points North Realty Inc", Cache(":memory:"), "live")
    assert out["status"] in ("found", "not_found") and "email" not in str(out).lower().replace("e-mail", "")
