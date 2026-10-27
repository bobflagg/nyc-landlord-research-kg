"""Q2 and Q4: HPD registrations and contacts at a lot (design notes 0009, 0014, 0017). Read-only, parameterized.

A registration says who registered, not who holds title. A person's name is shown only in the role HPD records, and a
managing agent is a management relationship, not ownership."""
from langchain.tools import tool

from agent.db import read_session
from agent.tools.records import PROV, _clean

CAVEATS_Q2 = [
    "An HPD registration says who registered with HPD, not who holds title (see the deed comparison).",
    "The registration period and the snapshot date are reported; whether a registration has lapsed is for the reader to judge from them. "
    "A newer registration may exist outside the snapshot.",
]
CAVEATS_Q4 = [
    "A person is shown only in the HPD role recorded for them, with the source. A name does not make an ownership claim.",
    "A managing agent or site manager is a management relationship, not ownership. Contacts at a shared business address are not linked by that address.",
]

REGISTRATIONS = f"""
MATCH (l:Lot {{bbl: $bbl}})<-[:ON_LOT]-(reg:Registration)
OPTIONAL MATCH (reg)-[:ON_BUILDING]->(b:Building)-[:ON_LOT]->(l)
WITH reg, collect(b {{.bin, .address_text, .zip5}}) AS buildings
OPTIONAL MATCH (reg)<-[:IN_REGISTRATION]-(o:HpdRole {{role_type: 'registered_owner'}})-[:HELD_BY]->(p:HpdParty)
WITH reg, buildings, collect(o {{.source_record_id, .source_role_code, name: coalesce(p.organization_name, p.person_name)}}) AS owners
OPTIONAL MATCH (s:Snapshot {{snapshot_id: reg.snapshot_id}})
RETURN reg {{.registration_id, .hpd_building_id, .last_registration_date, .registration_end_date, .owner_kind, .owner_kind_raw, {PROV}}} AS reg,
       [x IN buildings WHERE x.bin IS NOT NULL] AS buildings, owners, s.snapshot_date AS snapshot_date
ORDER BY reg.registration_id
"""
CONTACTS = f"""
MATCH (l:Lot {{bbl: $bbl}})<-[:ON_LOT]-(reg:Registration)<-[:IN_REGISTRATION]-(role:HpdRole)-[:HELD_BY]->(p:HpdParty)
RETURN reg.registration_id AS registration_id,
       role {{.source_record_id, .source_role_code, .role_type, .title, {PROV}}} AS role,
       p {{.organization_name, .person_name, .business_house, .business_street, .business_apartment, .business_city,
          .business_state, .business_zip, .business_address_key}} AS p
ORDER BY registration_id, role.source_record_id
"""
GROUPING = {"registered_owner": "registered principal", "head_officer": "registered principal", "officer": "registered principal",
            "shareholder": "registered principal", "lessee": "registered principal", "managing_agent": "management", "site_manager": "management"}


def registrations(runner, bbl: str) -> dict:
    """Every HPD registration on a lot, with its buildings, registered owner(s) and registration period."""
    if runner.run("MATCH (l:Lot {bbl: $bbl}) RETURN l.bbl", bbl=bbl).single() is None:
        return {"status": "lot_absent", "bbl": bbl, "note": "The graph holds no such lot."}
    rows = runner.run(REGISTRATIONS, bbl=bbl).data()
    if not rows:
        return {"status": "no_registration", "bbl": bbl, "caveats": CAVEATS_Q2,
                "note": "No HPD registration on this lot in the snapshot. That is not 'the building is exempt': buildings with fewer than three units "
                        "and others need not register."}
    out = []
    for r in rows:
        reg = r["reg"]
        item = _clean(reg) | {"buildings": r["buildings"],
                              "registered_owners": [{"name": o["name"], "contact_type": o["source_role_code"], "contact_id": o["source_record_id"]} for o in r["owners"]]}
        end, snap = reg.get("registration_end_date"), r["snapshot_date"]
        if end is not None and snap is not None:
            item["registration_end_date_before_snapshot"] = end.to_native() < snap.to_native()
        item["snapshot_date"] = snap.iso_format() if snap else None
        out.append(item)
    return {"status": "found", "bbl": bbl, "registrations": out, "caveats": CAVEATS_Q2}


def contacts(runner, bbl: str) -> dict:
    """Every contact HPD records for the registrations on a lot, by registration, with role, title, name and business address."""
    if runner.run("MATCH (l:Lot {bbl: $bbl}) RETURN l.bbl", bbl=bbl).single() is None:
        return {"status": "lot_absent", "bbl": bbl, "note": "The graph holds no such lot."}
    by_reg: dict[str, list] = {}
    for r in runner.run(CONTACTS, bbl=bbl):
        p, role = r["p"], r["role"]
        addr = _clean({"house": p.get("business_house"), "street": p.get("business_street"), "apartment": p.get("business_apartment"),
                       "city": p.get("business_city"), "state": p.get("business_state"), "zip": p.get("business_zip"),
                       "a2_key": p.get("business_address_key")})
        by_reg.setdefault(r["registration_id"], []).append(_clean({
            "contact_id": role["source_record_id"], "hpd_type": role["source_role_code"], "role_type": role.get("role_type"),
            "grouping": GROUPING.get(role.get("role_type")), "title": role.get("title"),
            "organization_name": p.get("organization_name"), "person_name": p.get("person_name"), "business_address": addr,
            "source": role["source"], "reliability": role["reliability"], "snapshot_id": role["snapshot_id"]}))
    if not by_reg:
        return {"status": "no_registration", "bbl": bbl, "caveats": CAVEATS_Q4, "note": "No HPD contacts on this lot in the snapshot."}
    return {"status": "found", "bbl": bbl, "registrations": [{"registration_id": k, "contacts": v} for k, v in by_reg.items()], "caveats": CAVEATS_Q4}


@tool
def get_hpd_registrations(bbl: str) -> dict:
    """For one tax lot (10-digit BBL string, from find_lot_by_address), return every HPD registration on it: the registration id,
    its buildings (BIN, address), the registered owner(s), the last registration date and the end of the registration period,
    with the snapshot date so the reader can see whether the period had ended. A registration is who registered, not proof of title."""
    with read_session() as session:
        return registrations(session, bbl)


@tool
def get_hpd_contacts(bbl: str) -> dict:
    """For one tax lot (10-digit BBL string), return the contacts HPD records on each registration there: the corporate or individual
    owner, managing agent, head officer, officers, shareholders, site manager and lessee, each with the title as recorded, the name,
    the business address, and the source and snapshot. A person appears only in the role HPD records. A managing agent is a
    management relationship, not ownership."""
    with read_session() as session:
        return contacts(session, bbl)
