"""Q1: address to lot and buildings. A templated, parameterized, read-only query."""
from langchain.tools import tool

from agent.db import read_session
from etl.address import a2_key

FIND = """
CALL () {
  MATCH (l:Lot {address_key: $key}) RETURN l
  UNION
  MATCH (:Building {address_key: $key})-[:ON_LOT]->(l:Lot) RETURN l
}
WITH DISTINCT l
OPTIONAL MATCH (b:Building)-[:ON_LOT]->(l)
WITH l, b ORDER BY b.bin
RETURN l {.bbl, .address_key, .reliability, .source_category, .source, .snapshot_id} AS lot,
       [x IN collect(b {.bin, .address_key, .reliability, .source_category, .source, .snapshot_id}) WHERE x.bin IS NOT NULL] AS buildings
ORDER BY lot.bbl
"""


def lookup(runner, house_number: str, street: str, zip5: str) -> dict:
    """`runner` is a neo4j Session or Transaction. A miss says what was tried and never guesses a nearby lot."""
    key = a2_key(house_number, street, zip5)
    rows = [dict(r) for r in runner.run(FIND, key=key)]
    lots = [r["lot"] for r in rows]
    buildings = [b for r in rows for b in r["buildings"]]
    if not lots:
        return {"status": "not_found", "variants_tried": [key],
                "note": "No lot found under this address key. No nearby lot was guessed."}
    return {
        "status": "found",
        "match": {"kind": "exact_a2_key", "key": key, "inferred": False},
        "lots": lots,
        "buildings": buildings,
        "counts": {"lots": len(lots), "buildings": len(buildings), "units": None},
        "note": "Units are not in the graph yet; lots, buildings and units are counted separately.",
    }


@tool
def find_lot_by_address(house_number: str, street: str, zip5: str) -> dict:
    """Find the tax lot (BBL) and the buildings (BIN) at a New York City street address.

    Pass the house number, the street name with its type (for example "54 Street" or "7th Avenue") and the
    5-digit zip code. The result lists every lot and building found, each with its source and snapshot, or
    says that no lot was found and which address key was tried. Spellings such as ST/STREET are treated alike."""
    with read_session() as session:
        return lookup(session, house_number, street, zip5)
