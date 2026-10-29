"""Q16 and Q25: reports and filing documents, and out-of-state registries (design note 0028). Findings are session evidence, never graph facts.

The graph is read-only here; the web is reached only through agent.web (logged, budgeted, cached, time-stamped). The search subject is a recorded entity's exact name
or a recorded lot's address; individuals are not searched. A report is a claim that was published, not a fact."""
from datetime import date

from langchain.tools import tool

from agent.db import read_session
from agent.tools.evidence import profile
from agent.tools.records import snapshot
from agent.web import registries
from agent.web.cache import Cache
from agent.web.client import WebClient
from agent.web.evidence import Budget, Lead
from agent.web.reports import LLMExtractor, is_entity_name, search_reports_about
from etl.names import n1

BOROUGH = {"1": "Manhattan", "2": "Bronx", "3": "Brooklyn", "4": "Queens", "5": "Staten Island"}
CAVEATS_Q16 = [
    "A report is a claim that was published, not a fact. Every item is unreviewed, kept apart from the recorded facts, and shown with its publisher, date, quote and retrieval time.",
    "An item is about this entity only where its exact normalized name or address appears in the quoted text; a similar name is a lead about a different entity and is not attached. "
    "A person named in a report is an attributed claim, never a role or an owner, and a signatory is not an owner.",
    "'No reports found' means none within the queries, sources and budget listed: the search index is not published and is not complete. It never means nothing has happened.",
    "Retrieval times are when the page or search was read ('cached' shows an earlier read). They are separate from the snapshot date, which is when the recorded facts were taken.",
]
CAVEATS_Q25 = [
    "A registry record is that registry's assertion about the entity under that name. It does not say who owns or controls the entity, and a record under a similar name is a lead about a different entity.",
    "A registry that needs a login, a CAPTCHA or payment, or that blocks a plain request, is an unresolved lead with the reason; it is not bypassed, and a lead is not a finding.",
]
OWNER_NAMES = """
MATCH (l:Lot {bbl: $bbl})
OPTIONAL MATCH (l)<-[:ON_LOT]-(:Registration)<-[:IN_REGISTRATION]-(:HpdRole {role_type: 'registered_owner'})-[:HELD_BY]->(p:HpdParty)
RETURN l.address_text AS address, collect(DISTINCT p.organization_name) AS owners
"""
RECORDED_NAME = """
CALL { MATCH (p:HpdParty {name_n1: $n}) RETURN count(p) AS hpd }
CALL { MATCH (e:DosEntity {name_n1: $n}) RETURN count(e) AS dos }
CALL { MATCH (p:AcrisParty {name_n1: $n}) RETURN count(p) AS acris }
RETURN hpd, dos, acris
"""


def _recorded_text(runner, names: list[str]) -> str:
    lines = []
    for n in names[:2]:
        p = profile(runner, n)
        people = {}
        for r in p["others"]:
            q = r["q"]
            nm = q.get("organization_name") or q.get("person_name")
            if nm and nm.upper() != n.upper():
                people.setdefault(nm, set()).add(r["role"])
        lines.append(f"{n}: HPD roles on its registrations: " + "; ".join(f"{k} ({', '.join(sorted(v))})" for k, v in sorted(people.items())[:12]) if people else f"{n}: no other HPD roles on file")
        for e in p["dos"][:2]:
            lines.append(f"{n}: DOS entity {e['dos_id']}, filed {e.get('initial_filing_date')}, process name {e.get('process_name')}, registered agent {e.get('registered_agent_name')}")
        lines.append(f"{n}: registered with HPD on {len(p['lots'])} lots")
    return "\n".join(lines)[:2500]


def reports_about(runner, subject: str, client: WebClient, extractor, as_of: date | None = None) -> dict:
    snap = snapshot(runner)
    snap_date = date.fromisoformat(snap["snapshot_date"]) if snap.get("snapshot_date") else date.today()
    base = {"subject": subject, **snap, "caveats": CAVEATS_Q16, "as_of_date": (as_of or snap_date).isoformat(), "search_provider": "Tavily (web and news search; index not published)"}
    names, address, suffix = [], None, ""
    if subject.isdigit() and len(subject) == 10:
        r = runner.run(OWNER_NAMES, bbl=subject).single()
        if r is None or r["address"] is None and not r["owners"]:
            return {**base, "status": "lot_absent", "note": "The graph holds no such lot."}
        names = sorted({o for o in r["owners"] if o and is_entity_name(o)})
        address, suffix = (r["address"], BOROUGH.get(subject[0], "")) if r["address"] else (None, "")
    else:
        key = n1(subject)
        c = runner.run(RECORDED_NAME, n=key).single()
        if not key or not (c["hpd"] or c["dos"] or c["acris"]):
            return {**base, "status": "not_searched", "note": "The name is not a party recorded in the graph (HPD, ACRIS or DOS), so it is not searched: queries are made only for recorded entities and addresses."}
        if not is_entity_name(subject) and not c["dos"]:
            return {**base, "status": "not_searched", "note": "The name looks like an individual's. A person's name is not searched; search the recorded entity or the address instead."}
        names = [subject]
    if not names and not address:
        return {**base, "status": "not_searched", "note": "The lot has no registered organization owner and no address to search."}
    out = search_reports_about(names, address, _recorded_text(runner, names) if names else "", client, extractor, as_of or snap_date, snap_date, address_query_suffix=suffix)
    items = out["items"]
    about = [i for i in items if i.match_basis != "lead_only"]
    res = {**base, **({"names_note": "the lot has no registered organization owner in the graph, so only its address was searched"} if subject.isdigit() and not names else {}), "names_searched": names, "address_searched": address, "queries": out["queries"], "budget": out["budget"],
           "items": [i.out() for i in items], "unresolved_leads": [l.out() for l in out["leads"]]}
    ran = sum(1 for q in out["queries"] if q["kind"] == "search")
    if ran == 0:
        res |= {"status": "search_unavailable", "statement": "no search could be run, so nothing can be said about reports: this is not 'no reports found'. The reasons are in unresolved_leads."}
    elif not about:
        res |= {"status": "no_reports_found", "statement": ("no reports or documents found in the sources searched, with the queries and dates listed" + ("; similar names appear as leads" if items else "")
                                                             + f"; the budget used is shown ({ran} searches completed, {out['budget']['fetches_used']} fetches)")
                                                             + ("; some searches failed (see unresolved_leads)" if out["leads"] else "")}
    else:
        res |= {"status": "found", "items_about_the_subject": len(about), "items_that_are_leads_only": len(items) - len(about)}
    return res


def registry_lookup(name: str, jurisdiction: str, cache: Cache | None = None, mode: str | None = None, runner=None) -> dict:
    import os
    out = registries.lookup(jurisdiction, name, cache or Cache(), mode or os.environ.get("WEB_MODE", "live"))
    out["caveats"] = CAVEATS_Q25
    if runner is not None:
        out |= snapshot(runner)
    return out


@tool
def search_reports(subject: str) -> dict:
    """Search the web and news for reports and documents about a recorded entity or lot. subject is an entity name exactly as the records spell it (it must be a
    party recorded in the graph; an individual's name is not searched) or a tax lot (BBL, 10 digits), in which case the lot's registered organization owners and its
    address are searched. Each item has the publisher, date, URL, a verbatim quote, the basis for treating it as about the entity (exact name or address, or lead only
    for a similar name), how it relates to the recorded facts (agrees, adds, conflicts, unrelated), retrieval time and flags. A report is a published claim, not a fact.
    If nothing is found it says so with the queries, dates and budget, never 'no news'."""
    with read_session() as session:
        return reports_about(session, subject, WebClient(budget=Budget()), LLMExtractor())


@tool
def lookup_registry(name: str, jurisdiction: str) -> dict:
    """Look up an entity formed outside New York in another state's free business registry: give the name exactly as the records spell it and the state (Connecticut,
    Delaware, Florida, New Jersey). Returns the registry's record (status, type, formation, registration and dissolution dates) as that registry's assertion, or an
    unresolved lead with the reason (needs payment, inaccessible, not found). A registry that needs a login, CAPTCHA or payment is reported, not bypassed."""
    with read_session() as session:
        return registry_lookup(name, jurisdiction, runner=session)
