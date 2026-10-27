"""Q5: the NY Department of State record for an owner entity (design notes 0009, 0016, 0017). Read-only, parameterized.

Matches the exact normalized name (rule N1). Active entities only: no record is not 'does not exist'."""
from langchain.tools import tool

from agent.db import read_session
from agent.tools.records import PROV, _clean, _mail_drop
from etl.address import a2_key
from etl.names import n1

CAVEATS_Q5 = [
    "DOS holds active entities only, as of the snapshot: no record is not 'does not exist', and a dissolved, renamed or foreign entity may not appear.",
    "The process name and address are where the state forwards legal papers. They do not say who runs the entity. The CEO and officer fields are not "
    "carried for LLCs, so their absence does not mean there are none.",
    "A record found by name is a lead: the name matches after punctuation and case are removed (rule N1), and nothing fuzzy is tried.",
]
STATUTORY_DEFAULT = {"THE COMPANY", "THE LIMITED LIABILITY COMPANY", "THE CORPORATION", "THE LLC"}
ENTITY = f"""
MATCH (e:DosEntity {{name_n1: $n}})
RETURN e {{.*}} AS e ORDER BY e.dos_id
"""


def _process_kind(e: dict) -> str:
    name = n1(e.get("process_name") or "")
    if not name:
        return "none"
    if name in STATUTORY_DEFAULT:
        return "statutory_default"
    return "entitys_own_name" if name == e.get("name_n1") else "other_name"


def _record(e: dict) -> dict:
    addr = ", ".join(x for x in (e.get("process_address_line1"), e.get("process_city"), e.get("process_zip")) if x) or None
    key = a2_key(*e["process_address_line1"].split(" ", 1), e["process_zip"]) if e.get("process_address_line1") and e.get("process_zip") and e["process_address_line1"][0].isdigit() and " " in e["process_address_line1"] else None
    return _clean({k: e.get(k) for k in ("dos_id", "entity_name", "entity_type", "initial_filing_date", "county", "jurisdiction", "process_name",
                                         "registered_agent_name", "ceo_name", "location_name", "source", "reliability", "source_category", "snapshot_id")}) | {
        "process_address": addr, "process_name_kind": _process_kind(e), "process_address_mail_drop": _mail_drop(key),
        "registered_agent": e.get("registered_agent_name"), "ceo_fields_present": bool(e.get("ceo_name"))}


def dos_record(runner, name: str) -> dict:
    n = n1(name)
    if not n:
        return {"status": "no_name_given"}
    rows = [r["e"] for r in runner.run(ENTITY, n=n)]
    base = {"searched_name": name, "normalized_name": n, "rule": "N1 (uppercase, punctuation deleted, whitespace collapsed); nothing fuzzy", "caveats": CAVEATS_Q5}
    if not rows:
        return {**base, "status": "no_record", "reason": "no active DOS entity has this normalized name", "variants_tried": [n]}
    return {**base, "status": "found" if len(rows) == 1 else "several_entities", "records": [_record(e) for e in rows]}


@tool
def get_dos_record(name: str) -> dict:
    """Look up the New York Department of State record for an owner entity by name (for example the HPD registered owner, or a deed
    grantee). The name is matched after punctuation and case are removed (rule N1); a different spelling is a different name, so try
    each spelling the records give. Returns the entity, its type, initial filing date, county, process name and address (and whether
    that is the statutory default or the entity's own name), and registered agent if listed. Several entities with one name are all
    returned. No record means none among active entities, not that the entity does not exist."""
    with read_session() as session:
        return dos_record(session, name)
