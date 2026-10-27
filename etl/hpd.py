"""HPD registrations and contacts to nodes and edges (design notes 0006, 0014). Pure; no database."""
import hashlib
import re
from datetime import date

from etl.address import a2_key
from etl.pluto import provenance
from etl.vocab import hpd_owner_kind, hpd_role_type

REGISTRATIONS = "hpd_registrations"
CONTACTS = "hpd_contacts"
_PLACEHOLDER_BIN = re.compile(r"[1-5]0{6}")


def _s(v) -> str | None:
    v = re.sub(r"\s+", " ", str(v)).strip() if v is not None else ""
    return v or None


def _date(v) -> date | None:
    """A Neo4j DATE, so range questions work. Sentinel and malformed dates are not stored."""
    try:
        return None if v is None else date.fromisoformat(str(v)[:10])
    except ValueError:
        return None


def real_bin(v) -> str | None:
    """A BIN with seven digits that is not a placeholder (1000000 style). Padded values are trimmed."""
    b = _s(v)
    return b if b and re.fullmatch(r"\d{7}", b) and not _PLACEHOLDER_BIN.fullmatch(b) else None


def registration_nodes(row: dict, owner_description: str | None, snapshot_id: str) -> dict:
    """One registration row to {registration, building (or None), lot}. The lot carries only what HPD says, and is
    created only if PLUTO did not load it."""
    rid, bbl, bin_ = str(row["registrationid"]), str(row["bbl"]).strip(), real_bin(row.get("bin"))
    raw = _s(owner_description)
    reg = {"registration_id": rid, **provenance(REGISTRATIONS, snapshot_id, rid),
           "hpd_building_id": _s(row.get("buildingid")), "last_registration_date": _date(row.get("lastregistrationdate")),
           "registration_end_date": _date(row.get("registrationenddate")), "owner_kind": hpd_owner_kind(raw), "owner_kind_raw": raw}
    building = None
    if bin_:
        house, street, zip5 = _s(row.get("housenumber")), _s(row.get("streetname")), _s(row.get("zip"))
        building = {"bin": bin_, **provenance(REGISTRATIONS, snapshot_id, _s(row.get("buildingid"))),
                    "address_text": " ".join(x for x in (house, street) if x) or None, "zip5": zip5}
        if house and street and zip5 and house[0].isdigit():
            building["address_key"] = a2_key(house, street, zip5)
        building = {k: v for k, v in building.items() if v is not None}
    return {"registration": {k: v for k, v in reg.items() if v is not None}, "building": building,
            "lot": {"bbl": bbl, **provenance(REGISTRATIONS, snapshot_id)}}


def _person(c: dict) -> str | None:
    return _s(" ".join(x for x in (_s(c.get("firstname")), _s(c.get("middleinitial")), _s(c.get("lastname"))) if x))


def party_id(c: dict) -> str:
    """md5 over HPD contact type, organization, person and business address, upper-cased and trimmed (note 0006)."""
    parts = [c.get("type"), c.get("corporationname"), c.get("firstname"), c.get("middleinitial"), c.get("lastname"),
             c.get("businesshousenumber"), c.get("businessstreetname"), c.get("businessapartment"), c.get("businesscity"),
             c.get("businessstate"), c.get("businesszip")]
    return hashlib.md5("|".join((_s(p) or "").upper() for p in parts).encode()).hexdigest()


def contact_nodes(c: dict, snapshot_id: str) -> dict:
    """One contact row to {party, role}. The party is the (type, name, address) identity; the role is this row."""
    house, street, zip5 = _s(c.get("businesshousenumber")), _s(c.get("businessstreetname")), _s(c.get("businesszip"))
    party = {"party_id": party_id(c), **provenance(CONTACTS, snapshot_id), "hpd_type": _s(c["type"]),
             "organization_name": _s(c.get("corporationname")), "person_name": _person(c),
             "business_house": house, "business_street": street, "business_apartment": _s(c.get("businessapartment")),
             "business_city": _s(c.get("businesscity")), "business_state": _s(c.get("businessstate")), "business_zip": zip5}
    if house and street and zip5 and house[0].isdigit():
        party["business_address_key"] = a2_key(house, street, zip5)
    cid = str(c["registrationcontactid"])
    role = {"role_id": f"hpd:{cid}", **provenance(CONTACTS, snapshot_id, cid), "role_type": hpd_role_type(c["type"]),
            "source_role_code": _s(c["type"]), "title": _s(c.get("title"))}
    return {"party": {k: v for k, v in party.items() if v is not None},
            "role": {k: v for k, v in role.items() if v is not None},
            "registration_id": str(c["registrationid"])}
