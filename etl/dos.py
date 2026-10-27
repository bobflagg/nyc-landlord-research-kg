"""NY DOS active-entity row to a DosEntity node (design notes 0006, 0016). Pure; no database."""
import re
from datetime import date, datetime

from etl.names import n1
from etl.pluto import provenance

SOURCE = "dos_active_corporations"

# (property, source column) in the order the source lists them; the people and addresses stay properties of the record
FIELDS = [("entity_type", "entitytype"), ("county", "county"), ("jurisdiction", "jurisdiction"), ("process_name", "dosprocessname"),
          ("registered_agent_name", "registeredagentname"), ("ceo_name", "ceoname"), ("location_name", "locationname")]
for _group, _col in (("process", "dosprocess"), ("registered_agent", "registeredagent"), ("ceo", "ceo"), ("location", "location")):
    FIELDS += [(f"{_group}_address_line1", f"{_col}address1"), (f"{_group}_address_line2", f"{_col}address2"),
               (f"{_group}_city", f"{_col}city"), (f"{_group}_state", f"{_col}state"), (f"{_group}_zip", f"{_col}zip")]


def _s(v) -> str | None:
    v = re.sub(r"\s+", " ", str(v)).strip() if v is not None else ""
    return v or None


def _day(v) -> date | None:
    if v is None:
        return None
    return v.date() if isinstance(v, datetime) else v if isinstance(v, date) else date.fromisoformat(str(v)[:10])


def dos_entity_node(row: dict, snapshot_id: str) -> dict:
    """One row to a DosEntity. Empty fields are left off. The name is the current entity name; `name_n1` is its
    rule N1 form, an index key and not a stored match (note 0009)."""
    dos_id, name = str(row["dosid"]).strip(), _s(row["currententityname"])
    node = {"party_id": f"dos:{dos_id}", **provenance(SOURCE, snapshot_id, dos_id), "dos_id": dos_id,
            "entity_name": name, "name_n1": n1(name), "initial_filing_date": _day(row.get("initialdosfilingdate"))}
    for prop, col in FIELDS:
        node[prop] = _s(row.get(col))
    return {k: v for k, v in node.items() if v is not None}
