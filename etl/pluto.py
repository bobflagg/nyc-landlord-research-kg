"""PLUTO row to a Lot node (design note 0014). Pure; no database."""
import re

from etl.address import a2_key

SOURCE = "pluto"


def provenance(source: str, snapshot_id: str, record_id: str | None = None) -> dict:
    p = {"reliability": "I", "source_category": "public_record", "source": source, "snapshot_id": snapshot_id}
    if record_id:
        p["source_record_id"] = record_id
    return p


def _int(v) -> int | None:
    try:
        return None if v is None or str(v).strip() == "" else int(float(v))
    except ValueError:
        return None


def lot_node(row: dict, snapshot_id: str) -> dict:
    """A Lot with PLUTO's attributes. Empty values and PLUTO's year 0 (unknown) are left off, not stored as 0."""
    bbl = str(row["bbl"]).strip()
    address = (row.get("address") or "").strip() or None
    zip5 = re.sub(r"\D", "", str(row.get("zipcode") or ""))[:5] or None
    node = {"bbl": bbl, **provenance(SOURCE, snapshot_id, bbl), "address_text": address, "zip5": zip5,
            "building_class": (row.get("bldgclass") or "").strip() or None,
            "units_residential": _int(row.get("unitsres")), "units_total": _int(row.get("unitstotal")),
            "buildings_count": _int(row.get("numbldgs")), "assessed_total": _int(row.get("assesstot")),
            "owner_name_pluto": (row.get("ownername") or "").strip() or None,
            "community_district": f"{_int(row.get('cd')):03d}" if _int(row.get("cd")) else None}
    year = _int(row.get("yearbuilt"))
    node["year_built"] = year if year else None
    if address and zip5 and re.match(r"\d", address):
        house, street = address.split(" ", 1) if " " in address else (address, "")
        if street:
            node["address_key"] = a2_key(house, street, zip5)
    return {k: v for k, v in node.items() if v is not None}
