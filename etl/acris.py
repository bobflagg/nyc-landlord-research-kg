"""ACRIS documents, parties and roles to nodes and edges (design notes 0006, 0015). Pure; no database."""
import hashlib
import re
from datetime import date, datetime

from etl.address import a2_key
from etl.names import n1
from etl.pluto import provenance
from etl.vocab import acris_doc_type, acris_role_type

MASTER = "acris_master"
PARTIES = "acris_parties"
EARLIEST = date(1900, 1, 1)  # ACRIS holds dates from year 0001; earlier ones are typing errors, flagged not repaired


def _s(v) -> str | None:
    v = re.sub(r"\s+", " ", str(v)).strip() if v is not None else ""
    return v or None


def _day(v) -> date | None:
    if v is None:
        return None
    return v.date() if isinstance(v, datetime) else v if isinstance(v, date) else date.fromisoformat(str(v)[:10])


def document_node(row: dict, snapshot_id: str, snapshot_date: date) -> dict:
    """One master row to a Document. A document date outside 1900..snapshot date is not stored as a date; the
    recorded value is kept as text in doc_date_raw."""
    did, raw_type = str(row["documentid"]).strip(), _s(row["doctype"])
    doc_date = _day(row.get("docdate"))
    node = {"document_id": did, **provenance(MASTER, snapshot_id, did), "crfn": _s(row.get("crfn")),
            "doc_type": acris_doc_type(raw_type), "doc_type_raw": raw_type,
            "recorded": _day(row.get("recordedfiled")),
            "amount": None if row.get("docamount") is None else int(row["docamount"])}
    if doc_date and EARLIEST <= doc_date <= snapshot_date:
        node["doc_date"] = doc_date
    elif doc_date:
        node["doc_date_raw"] = doc_date.isoformat()
    return {k: v for k, v in node.items() if v is not None}


def party_id(p: dict) -> str:
    """md5 over name and address, upper-cased and trimmed, prefixed so it cannot meet an HPD party id."""
    parts = [p.get(k) for k in ("name", "address1", "address2", "city", "state", "zip", "country")]
    return "acris:" + hashlib.md5("|".join((_s(x) or "").upper() for x in parts).encode()).hexdigest()


def party_nodes(p: dict, doc_type: str | None, snapshot_id: str) -> dict:
    """One party row to {party, role}. The party is the (name, address) identity; the role is this row in its document."""
    name, a1, zip5 = _s(p.get("name")), _s(p.get("address1")), re.sub(r"\D", "", str(p.get("zip") or ""))[:5] or None
    party = {"party_id": party_id(p), **provenance(PARTIES, snapshot_id), "party_name": name,
             "name_n1": n1(name) if name else None, "address_line1": a1, "address_line2": _s(p.get("address2")),
             "city": _s(p.get("city")), "state": _s(p.get("state")), "zip": _s(p.get("zip")), "country": _s(p.get("country"))}
    if a1 and zip5 and a1[0].isdigit() and " " in a1:
        house, street = a1.split(" ", 1)
        party["address_key"] = a2_key(house, street, zip5)
    did, ptype = str(p["documentid"]).strip(), str(p["partytype"]).strip()
    digest = hashlib.md5("|".join((_s(x) or "").upper() for x in (did, ptype, p.get("name"), p.get("address1"), p.get("address2"),
                                                                    p.get("city"), p.get("state"), p.get("zip"), p.get("country"))).encode()).hexdigest()
    role = {"role_id": f"acris:{digest}", **provenance(PARTIES, snapshot_id, did), "source_role_code": ptype,
            "role_type": acris_role_type(doc_type, ptype)}
    return {"party": {k: v for k, v in party.items() if v is not None},
            "role": {k: v for k, v in role.items() if v is not None}, "document_id": did}
