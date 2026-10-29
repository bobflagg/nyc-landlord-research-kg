"""Q11 and Q23: a lot's affiliations by relationship type, and a managing agent's footprint (design note 0026). Read-only, parameterized.

Each relationship is reported as the kind it is: a lender is a financing relationship, a joint borrower a shared borrower record, a managing agent a management relationship,
a registered principal a person or company in an HPD role, a process agent where the state forwards papers. None of them is a parent relationship, and no loaded source
documents one. A commercial managing agent, or one at a mail-drop-list address, links nothing."""
from langchain.tools import tool

from agent.db import read_session
from agent.tools.layers import WHAT_IT_IS
from agent.tools.linkrules import COMMERCIAL_AGENT_LOTS, dos_process_key, mail_drop
from agent.tools.records import PROV, _clean, _plain, snapshot
from etl.names import n1
from etl.vocab import mortgage_family_types

BOROUGH = {"1": "Manhattan", "2": "Bronx", "3": "Brooklyn", "4": "Queens", "5": "Staten Island"}
CAVEATS_Q11 = [
    "Each relationship is reported as its own type and only as far as the record goes: a lender is a financing relationship; joint borrowers are a shared borrower record, not common control; "
    "a managing agent is a management relationship, not ownership; a registered principal is a person or company in an HPD role; a process agent is where the state forwards papers.",
    "No loaded source records a parent company, so no relationship here is a parent relationship and none may be called one. A reported claim of a parent is not a documented affiliation.",
    "Mortgage-family documents are loaded for HPD-registered lots only, and a lender is the lender named on that document, not the current lender. A name is shown only in the role the record gives it, with its source.",
]
CAVEATS_Q23 = [
    "A managing agent is a management relationship, not ownership, and a shared agent says nothing about whether the owners are related. An agent registered for many unrelated owners, or at an address on the mail-drop list, links nothing.",
    "The agent is identified by exact normalized name (rule N1) across HPD parties; a company that appears at several addresses is shown as one name with each address, and a name match is a lead, not a finding that the parties are one company.",
    "The footprint is the lots where the agent is registered in the snapshot. Lots are counted apart from buildings (the buildings the graph holds on them) and residential units (PLUTO), with the lots missing a unit count.",
]
ROLES = f"""
MATCH (l:Lot {{bbl: $bbl}})<-[:ON_LOT]-(reg:Registration)<-[:IN_REGISTRATION]-(o:HpdRole)-[:HELD_BY]->(p:HpdParty)
RETURN reg.registration_id AS reg, o.role_type AS role, o.source_role_code AS code, p {{.party_id, .organization_name, .person_name, .name_n1, .person_name_n1, .business_address_key}} AS p
ORDER BY reg, role
"""
MORTGAGE_ROLES = """
MATCH (l:Lot {bbl: $bbl})<-[:ON_LOT]-(d:Document) WHERE d.doc_type IN $types
MATCH (d)<-[:IN_DOCUMENT]-(r:AcrisRole)-[:HELD_BY]->(p:AcrisParty) WHERE r.role_type IN ['lender', 'borrower']
RETURN d {.document_id, .doc_type, .recorded, .amount} AS d, r.role_type AS role, p {.party_name, .name_n1} AS p
ORDER BY d.recorded, d.document_id
"""
DOS = "MATCH (e:DosEntity {name_n1: $n}) RETURN e {.dos_id, .entity_name, .process_name, .process_address_line1, .process_zip, .registered_agent_name} AS e"
FOOT = """
MATCH (p:HpdParty {%s: $n})<-[:HELD_BY]-(o:HpdRole {role_type: 'managing_agent'})-[:IN_REGISTRATION]->(reg:Registration)-[:ON_LOT]->(l:Lot)
OPTIONAL MATCH (reg)<-[:IN_REGISTRATION]-(:HpdRole {role_type: 'registered_owner'})-[:HELD_BY]->(own:HpdParty)
RETURN p.party_id AS party_id, p.business_address_key AS addr, coalesce(p.organization_name, p.person_name) AS name, l.bbl AS bbl, l.address_text AS address, l.units_residential AS units,
       reg.registration_id AS reg, collect(DISTINCT coalesce(own.organization_name, own.person_name)) AS owners
"""
BLDGS = "UNWIND $lots AS b MATCH (x:Building)-[:ON_LOT]->(:Lot {bbl: b}) RETURN count(DISTINCT x) AS n"
LAYERS = """
UNWIND $lots AS b OPTIONAL MATCH (:Lot {bbl: b})-[:MEMBER_OF]->(g:BorGroup {layer: $layer})
RETURN g.group_id AS group_id, g.lot_count AS size, count(b) AS lots, collect(b)[0..3] AS sample
ORDER BY lots DESC
"""


def affiliations(runner, bbl: str) -> dict:
    base = {"bbl": bbl, **snapshot(runner)}
    if runner.run("MATCH (l:Lot {bbl: $bbl}) RETURN l.bbl", bbl=bbl).single() is None:
        return {**base, "status": "lot_absent", "note": "The graph holds no such lot."}
    base |= {"caveats": CAVEATS_Q11, "documented_parent": "none: no loaded source records a parent company, so no relationship below is a parent relationship"}
    registered = runner.run("MATCH (:Lot {bbl: $bbl})<-[:ON_LOT]-(r:Registration) RETURN count(r) AS c", bbl=bbl).single()["c"] > 0
    roles = runner.run(ROLES, bbl=bbl).data()
    mgmt, principals, owners = {}, {}, set()
    for r in roles:
        p = r["p"]
        name = p.get("organization_name") or p.get("person_name")
        entry = {"name": name, "role": r["role"], "contact_type": r["code"], "registration_id": r["reg"], "business_address_key": p.get("business_address_key"), "source": "hpd_contacts", "reliability": "I"}
        if r["role"] in ("managing_agent", "site_manager"):
            entry["mail_drop_list"] = (mail_drop(runner, p.get("business_address_key")) or {}).get("kind")
            mgmt[(name, r["role"], r["reg"])] = entry
        elif r["role"] in ("registered_owner", "head_officer", "officer", "shareholder", "lessee"):
            principals[(name, r["role"], r["reg"])] = entry
            if r["role"] == "registered_owner" and p.get("name_n1"):
                owners.add(p["name_n1"])
    rows = runner.run(MORTGAGE_ROLES, bbl=bbl, types=mortgage_family_types()).data()
    lenders: dict[str, dict] = {}
    docs: dict[str, dict] = {}
    for r in rows:
        d = docs.setdefault(r["d"]["document_id"], {"d": r["d"], "borrowers": set(), "lenders": set()})
        (d["lenders"] if r["role"] == "lender" else d["borrowers"]).add(r["p"]["party_name"])
    for d in docs.values():
        for name in d["lenders"]:
            e = lenders.setdefault(name, {"name": name, "documents": 0, "first_recorded": None, "last_recorded": None, "document_types": set()})
            e["documents"] += 1
            e["document_types"].add(d["d"]["doc_type"])
            rec = _plain(d["d"].get("recorded"))
            e["first_recorded"] = min(filter(None, [e["first_recorded"], rec]), default=None)
            e["last_recorded"] = max(filter(None, [e["last_recorded"], rec]), default=None)
    joint = [{"document_id": k, "doc_type": d["d"]["doc_type"], "recorded": _plain(d["d"].get("recorded")), "amount": d["d"].get("amount"), "borrowers": sorted(d["borrowers"]), "lenders": sorted(d["lenders"])}
             for k, d in docs.items() if len(d["borrowers"]) >= 2]
    process = []
    for key in sorted(owners):
        for e in runner.run(DOS, n=key).data():
            e = e["e"]
            pk = dos_process_key(e)
            process.append(_clean({"entity": e["entity_name"], "dos_id": e["dos_id"], "process_name": e.get("process_name"), "process_address_key": pk, "registered_agent": e.get("registered_agent_name"),
                                   "mail_drop_list": (mail_drop(runner, pk) or {}).get("kind"), "source": "nys_corporations", "reliability": "I"}))
    out = {**base, "status": "found" if (roles or rows) else "no_relationships_found", "lot_has_hpd_registration": registered,
           "by_type": {
               "lender": {"relationship": "financing", "count": len(lenders), "parties": [_clean({**e, "document_types": sorted(e["document_types"])}) for e in sorted(lenders.values(), key=lambda e: -e["documents"])]},
               "joint_borrower": {"relationship": "a shared borrower record on one document, not common control", "documents": len(joint), "examples": sorted(joint, key=lambda j: j["recorded"] or "")[:10]},
               "managing_agent": {"relationship": "management, not ownership", "parties": sorted(mgmt.values(), key=lambda e: (e["role"], e["name"]))},
               "registered_principal": {"relationship": "a person or company in an HPD role, as recorded", "parties": sorted(principals.values(), key=lambda e: (e["role"], e["name"]))},
               "process_agent": {"relationship": "where the state forwards papers", "entities": process}}}
    if not registered:
        out["note"] = "The lot has no HPD registration, so no HPD role is here and the mortgage family is not loaded for it; nothing here says it has no affiliations."
    return out


def agent_footprint(runner, name_or_bbl: str, max_lots: int = 40) -> dict:
    """The lots where a managing agent is registered. Starts from a name, or from a lot (the agents registered on it)."""
    base = {**snapshot(runner), "caveats": CAVEATS_Q23}
    names = []
    if name_or_bbl.isdigit() and len(name_or_bbl) == 10:
        base["bbl"] = name_or_bbl
        for r in runner.run(ROLES, bbl=name_or_bbl).data():
            if r["role"] == "managing_agent":
                p = r["p"]
                names.append(p.get("organization_name") or p.get("person_name"))
        names = sorted(set(names))
        if not names:
            return {**base, "status": "no_managing_agent", "note": "No managing agent is registered on this lot in the snapshot."}
    else:
        names = [name_or_bbl]
    results = []
    for name in names:
        key = n1(name)
        rows = []
        for field in ("name_n1", "person_name_n1"):
            rows += runner.run(FOOT % field, n=key).data()
        if not rows:
            results.append({"agent": name, "normalized_name": key, "status": "no_registration_as_managing_agent", "note": "No HPD registration lists this normalized name as managing agent."})
            continue
        lots: dict[str, dict] = {}
        parties: dict[str, dict] = {}
        for r in rows:
            lots.setdefault(r["bbl"], {"bbl": r["bbl"], "address": r["address"], "units": r["units"], "registrations": set(), "owners": set()})
            lots[r["bbl"]]["registrations"].add(r["reg"]); lots[r["bbl"]]["owners"] |= {o for o in r["owners"] if o}
            pr = parties.setdefault((r["name"], r["addr"]), {"name": r["name"], "business_address_key": r["addr"], "lots": set()})
            pr["lots"].add(r["bbl"])
        owners = {o for v in lots.values() for o in v["owners"]}
        md = {k: mail_drop(runner, v["business_address_key"]) for k, v in parties.items()}
        commercial = len(lots) >= COMMERCIAL_AGENT_LOTS or len(owners) >= COMMERCIAL_AGENT_LOTS or any(md.values())
        bl = sorted(lots)
        units = [v["units"] for v in lots.values() if v["units"] is not None]
        by_borough: dict[str, int] = {}
        for b in bl:
            by_borough[BOROUGH.get(b[0], b[0])] = by_borough.get(BOROUGH.get(b[0], b[0]), 0) + 1
        layers = {}
        for layer in ("owner_portfolio", "operational_network"):
            g = runner.run(LAYERS, lots=bl, layer=layer).data()
            in_none = sum(x["lots"] for x in g if x["group_id"] is None)
            layers[layer] = {"what_this_layer_is": WHAT_IT_IS[layer], "lots_in_a_group": len(bl) - in_none, "lots_in_no_group": in_none, "distinct_groups": sum(1 for x in g if x["group_id"]),
                             "largest_shares": [{"group_id": x["group_id"], "lots_of_the_footprint": x["lots"], "group_lots": x["size"]} for x in g if x["group_id"]][:5]}
        results.append({"agent": name, "normalized_name": key, "status": "found", "parties": [_clean({"name": v["name"], "business_address_key": v["business_address_key"], "lots": len(v["lots"]),
                                                                                                    "mail_drop_list": (md[k] or {}).get("kind")}) for k, v in sorted(parties.items(), key=lambda kv: -len(kv[1]["lots"]))],
                        "footprint": {"lots": len(bl), "registrations": len({r for v in lots.values() for r in v["registrations"]}), "buildings": runner.run(BLDGS, lots=bl).single()["n"],
                                      "residential_units": sum(units), "lots_missing_a_unit_count": len(bl) - len(units), "lots_by_borough": dict(sorted(by_borough.items())),
                                      "distinct_registered_owners": len(owners)},
                        "commercial_agent": commercial, "commercial_reading": ("registered for many lots or many different owners, or at a mail-drop-list address: treated here as a commercial agent, so the registration alone ties none of the owners; "
                                                                                  "the layers below group the lots on their own evidence" if commercial
                                                                                 else "registered for few lots and owners; still a management relationship, not ownership"),
                        "comparison_with_the_layers": layers, "lots_shown": min(max_lots, len(bl)),
                        "lots": [_clean({"bbl": b, "address": lots[b]["address"], "owners": sorted(lots[b]["owners"])[:3]}) for b in bl[:max_lots]]})
    return {**base, "status": "found", "agents": results}


@tool
def get_affiliations(bbl: str) -> dict:
    """List the relationships recorded around a tax lot (BBL, a 10-digit string), each as its own type: lenders on recorded mortgage-family documents (financing),
    documents naming two or more borrowers (a shared borrower record), HPD managing agents and site managers (management), registered owners, officers and
    shareholders (registered principals), and the DOS process agent of each organization owner. None is a parent relationship: no loaded source records a parent, and
    a lender is the lender named on that document. Mortgage documents are loaded for HPD-registered lots only."""
    with read_session() as session:
        return affiliations(session, bbl)


@tool
def get_agent_footprint(name_or_bbl: str) -> dict:
    """Give a managing agent's footprint: pass the agent's name exactly as HPD spells it, or a tax lot (BBL, 10 digits) to take the agents registered on it. Reports
    the lots where the agent is registered (counts of lots, buildings, residential units, boroughs, distinct registered owners, a bounded list), the agent's addresses,
    whether it looks like a commercial agent (many lots or owners, or a mail-drop-list address, which links nothing), and how the lots fall in the Owner Portfolio and
    Operational Network. A managing agent is a management relationship, not ownership; a shared agent says nothing about common ownership."""
    with read_session() as session:
        return agent_footprint(session, name_or_bbl)
