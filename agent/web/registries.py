"""Out-of-state business registries for Q25 (design note 0028, W4). One adapter per registry behind lookup().

An adapter reads only what the registry shows free to a plain request. It never signs in, solves a CAPTCHA, pays or disguises itself; a registry that blocks a plain request
or has no free search is an unresolved lead with the reason inaccessible. A registry's record is a recorded assertion of that registry (reliability I, public_record).
Connecticut's open-data Business Registry works today; Delaware, Florida and New Jersey were probed on 2026-10-29 and are inaccessible to a plain request (adapters re-probe and
report what they see). The business e-mail field of the Connecticut dataset is personal data and is never read into a result."""
import re

import httpx

from agent.web.cache import Cache
from agent.web.client import ReplayMiss, WebError
from agent.web.evidence import EvidenceItem, Lead, now_iso
from etl.names import n1

UA = "nyc-landlord-research-kg/0.1 (public-records research; contact via repository)"
JURISDICTIONS = {"CT": "Connecticut", "CONNECTICUT": "Connecticut", "DE": "Delaware", "DELAWARE": "Delaware", "FL": "Florida", "FLORIDA": "Florida", "NJ": "New Jersey", "NEW JERSEY": "New Jersey"}
CT_URL = "https://data.ct.gov/resource/n7gp-d28j.json"
CT_BODY = "Connecticut Secretary of the State, Business Registry (data.ct.gov, public domain)"
PROBES = {
    "Delaware": ("https://icis.corp.delaware.gov/Ecorp/EntitySearch/NameSearch.aspx", "Delaware Division of Corporations, entity search",
                 "Delaware's free entity name search is behind a CAPTCHA and a browser challenge; formation documents and status certificates are paid. Not attempted past a plain request."),
    "Florida": ("https://search.sunbiz.org/Inquiry/CorporationSearch/ByName", "Florida Division of Corporations (Sunbiz)", "Florida's search answers a plain request with a browser challenge."),
    "New Jersey": ("https://www.njportal.com/DOR/BusinessNameSearch/Search/BusinessName", "New Jersey Division of Revenue, business name search",
                   "New Jersey's free search is a browser form that a plain request cannot submit."),
}
CHALLENGE = re.compile(r"captcha|just a moment|enable javascript|cf-chl|access denied", re.I)


def normalize_jurisdiction(j: str) -> str | None:
    return JURISDICTIONS.get(j.strip().upper())


def _get(cache: Cache, mode: str, url: str, params: dict | None, kind_key: dict, transport=None, sanitize=None) -> tuple[int, str, str, bool]:
    hit = cache.get("registry", kind_key, ignore_ttl=mode in ("replay", "offline"))
    if hit:
        r = hit["response"]
        return r["status"], r["body"], hit["retrieved_at"], True
    if mode in ("replay", "offline"):
        raise ReplayMiss(f"registry {kind_key}")
    try:
        with httpx.Client(transport=transport, timeout=25.0, headers={"User-Agent": UA}, follow_redirects=True) as c:
            r = c.get(url, params=params)
    except httpx.HTTPError as e:
        raise WebError("inaccessible", f"{type(e).__name__} reaching the registry") from None
    at = now_iso()
    body = sanitize(r.text) if sanitize and r.status_code == 200 else r.text[:200000]    # personal fields are dropped before anything is cached
    cache.put("registry", kind_key, {"status": r.status_code, "body": body}, at)
    return r.status_code, body, at, False


def _ct_item(rec: dict, query: str, exact: bool, at: str, cached: bool, url: str) -> EvidenceItem:
    bits = [rec.get("name"), f"status {rec.get('status')}" + (f" ({rec['sub_status']})" if rec.get("sub_status") else ""), rec.get("business_type"),
            f"formed in {rec.get('formation_place')}" if rec.get("formation_place") else None, f"registered {rec['date_registration'][:10]}" if rec.get("date_registration") else None,
            f"dissolved {rec['dissolution_date'][:10]}" if rec.get("dissolution_date") else None, f"account {rec.get('accountnumber')}" if rec.get("accountnumber") else None]
    quote = " | ".join(b for b in bits if b)
    flags = [] if exact else ["a similar name: a lead about a different entity, not attached to the name searched"]
    return EvidenceItem(item_id=f"ct-{rec.get('accountnumber') or rec.get('id')}", publisher_or_body=CT_BODY, retrieved_at=at, cached=cached, url=url, document_id=rec.get("accountnumber"),
                        quote=quote, extraction_method="registry_field", source_category="public_record", match_basis="exact_name" if exact else "lead_only", matched_text=rec.get("name"),
                        relation_to_records="adds", relation_note="a registry record in another jurisdiction; the graph holds no record from it", flags=flags)


def _drop_personal(text: str) -> str:
    import json
    try:
        recs = json.loads(text)
    except ValueError:
        return text[:200000]
    return json.dumps([{k: v for k, v in r.items() if "email" not in k} for r in recs])


def lookup(jurisdiction: str, name: str, cache: Cache, mode: str = "live", transport=None) -> dict:
    j = normalize_jurisdiction(jurisdiction)
    if j is None:
        return {"status": "unsupported_jurisdiction", "jurisdiction": jurisdiction, "supported": sorted(set(JURISDICTIONS.values())),
                "leads": [Lead(step=f"registry of {jurisdiction}", reason="inaccessible", detail="no adapter for this jurisdiction yet; a person can search its free registry directly").out()], "items": []}
    base = {"jurisdiction": j, "searched_name": name, "normalized_name": n1(name)}
    if j == "Connecticut":
        q = name.upper().replace("'", "''")
        try:
            status, body, at, cached = _get(cache, mode, CT_URL, {"$where": f"upper(name)='{q}'", "$limit": "10"}, {"registry": "CT", "mode": "exact", "name": q}, transport, _drop_personal)
            if status == 402:
                raise WebError("needs_payment", "the registry asks for payment for this record")
            if status != 200:
                raise WebError("inaccessible", f"the registry answered {status}")
            import json
            recs = json.loads(body)
            exact = [r for r in recs if n1(r.get("name", "")) == n1(name)]
            items = [_ct_item(r, name, True, at, cached, f"{CT_URL}?$where=upper(name)='{q}'") for r in exact]
            leads = []
            if not exact:
                first = " ".join(n1(name).split()[:2]).replace("'", "''")
                st2, body2, at2, c2 = _get(cache, mode, CT_URL, {"$where": f"upper(name) like '{first}%'", "$limit": "5"}, {"registry": "CT", "mode": "similar", "name": first}, transport, _drop_personal)
                similar = json.loads(body2) if st2 == 200 else []
                items = [_ct_item(r, name, False, at2, c2, CT_URL) for r in similar]
                leads.append(Lead(step="Connecticut Business Registry", reason="not_found", detail=f"no registry entry has the exact normalized name {n1(name)!r}; "
                                                                                                 + (f"{len(items)} similar names are listed as leads about different entities" if items else "no similar names either"), retrieved_at=at).out())
            return {**base, "status": "found" if exact else "not_found", "registry": CT_BODY, "retrieved_at": at, "cached": cached, "items": [i.out() for i in items], "leads": leads,
                    "note": "The registry's e-mail field is personal data and is not read. A record here says the entity is registered in Connecticut under that name, nothing about its owners."}
        except WebError as e:
            return {**base, "status": "unresolved", "items": [], "leads": [Lead(step="Connecticut Business Registry", reason=e.kind, detail=e.detail).out()]}
    url, body_name, why = PROBES[j]
    try:
        status, body, at, cached = _get(cache, mode, url, None, {"registry": j, "probe": url}, transport)
    except WebError as e:
        return {**base, "status": "unresolved", "items": [], "leads": [Lead(step=body_name, reason=e.kind, detail=e.detail, url=url).out()]}
    lead = Lead(step=body_name, reason="inaccessible", detail=f"{why} (plain request answered {status}); not bypassed", url=url, retrieved_at=at)
    return {**base, "status": "unresolved", "retrieved_at": at, "cached": cached, "items": [], "leads": [lead.out()],
            "next_step": f"a person can search the {j} registry's free search directly for {name!r}; formation documents may need payment"}
