"""Record the replay fixtures for the Slice 6 evaluation (design note 0028, W6) from SYNTHETIC pages and a mock provider.

  uv run python -m scripts.make_web_fixtures

The articles below are invented and deliberately bland (a tenant meeting, a scaffolding notice, a unit count): they exercise the contract's cases without putting an invented allegation
about a real company in the repository. Subjects are real recorded entities because the tool searches only recorded names. The Connecticut records are a modelled public-domain
registry row. The output, tests/fixtures/web/replay.json, is loaded into the cache in replay mode."""
import json
from pathlib import Path

import httpx

from agent.db import read_session
from agent.tools.reports import registry_lookup, reports_about
from agent.web.cache import Cache
from agent.web.client import WebClient
from agent.web.evidence import Budget
from agent.web.reports import Reading
from etl.config import ROOT

OUT = ROOT / "tests" / "fixtures" / "web" / "replay.json"
PAGES = {
    "https://tenantnews.example/plaza-meeting": {"title": "Tenants meet at Seventh Avenue building", "published": "2026-04-12",
        "text": "Tenants of the Sunset Park building met on Saturday. 5413 Plaza LLC, the registered owner named in city records, did not send a representative to the tenant meeting. Organizers said they would write to the owner."},
    "https://tenantnews.example/plaza-ii": {"title": "Notice posted", "published": "2026-03-02",
        "text": "A notice about scaffolding was posted at a different address. 5413 Plaza II LLC was named on the notice. The notice gave no other detail."},
    "https://citywatch.example/702-plaza-ii": {"title": "A scaffolding notice", "published": "2026-02-02",
        "text": "Officials listed 702 Plaza II LLC on a scaffolding notice. The company is not otherwise described in the notice."},
    "https://local.example/turnpike-one": {"title": "Building profile", "published": "2025-09-01",
        "text": "KS Turnpike LLC is listed as the owner of a 22-unit building on 52nd Street, according to this profile."},
    "https://block.example/turnpike-two": {"title": "Block association newsletter", "published": "2026-01-15",
        "text": "KS Turnpike LLC is listed as the owner of a 24-unit building on 52nd Street, the newsletter says."},
}
READINGS = {
    "tenant meeting": Reading(claim="the article says the registered owner sent no representative to a tenant meeting", relation="agrees", relation_note="5413 Plaza LLC is the registered owner in HPD records", persons=[]),
    "22-unit": Reading(claim="the profile says the building has 22 units", relation="adds", relation_note="the records give PLUTO units, not this profile's count", claim_subject="ks turnpike llc building", claim_predicate="has units", claim_object="22"),
    "24-unit": Reading(claim="the newsletter says the building has 24 units", relation="adds", relation_note="the records give PLUTO units, not this newsletter's count", claim_subject="ks turnpike llc building", claim_predicate="has units", claim_object="24"),
}


class Fake:
    def read(self, entity, quote, recorded):
        for k, v in READINGS.items():
            if k in quote:
                return v
        return Reading(claim="the passage mentions the entity", relation="unrelated", relation_note="nothing the records speak to")


def provider(req: httpx.Request) -> httpx.Response:
    import os
    body = json.loads(req.content)
    if req.url.path.endswith("search"):
        phrase = " ".join(body["query"].strip('"').split('" ')[0].lower().split()[:2])
        res = [{"title": p["title"], "url": u, "content": p["text"], "score": 0.9, "published_date": p["published"]} for u, p in PAGES.items() if phrase in p["text"].lower()]
        return httpx.Response(200, json={"query": body["query"], "results": res})
    u = body["urls"][0]
    return httpx.Response(200, json={"results": [{"url": u, "raw_content": PAGES[u]["text"]}], "failed_results": []})


def ct(req: httpx.Request) -> httpx.Response:
    w = req.url.params["$where"].lower()
    rec = {"id": "0018y000008lkmcAAA", "name": "POINTS NORTH REALTY INC", "business_type": "Stock", "status": "Forfeited", "sub_status": "Administrative", "accountnumber": "2757063",
           "citizenship": "Domestic", "formation_place": "Connecticut", "date_registration": "2023-03-28T00:00:00.000"}
    return httpx.Response(200, json=[rec] if "points north realty inc'" in w else [])


def main() -> None:
    cache = Cache(":memory:")
    with read_session() as s:
        for subject in ("5413 PLAZA LLC", "702 PLAZA LLC", "3008970014", "KS Turnpike LLC"):
            reports_about(s, subject, WebClient(cache=cache, mode="live", budget=Budget(), transport=httpx.MockTransport(provider)), Fake())
    import os
    os.environ["TAVILY_API_KEY"] = os.environ.get("TAVILY_API_KEY", "x")
    registries_cache = cache
    from agent.web import registries
    registries.lookup("CT", "Points North Realty Inc", registries_cache, "live", httpx.MockTransport(ct))
    registries.lookup("DE", "Acme Realty LLC", registries_cache, "live", httpx.MockTransport(lambda r: httpx.Response(200, text="<html>Please complete the CAPTCHA to continue</html>")))
    registries.lookup("FL", "Acme Realty LLC", registries_cache, "live", httpx.MockTransport(lambda r: httpx.Response(403, text="<title>Just a moment...</title>")))
    n = cache.dump(OUT)
    print("fixtures:", n)


if __name__ == "__main__":
    main()
