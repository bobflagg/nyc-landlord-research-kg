"""Q1: address to lot and buildings. Geosupport turns the typed address into the city's BBL and BIN; the graph
confirms them. A templated, parameterized, read-only query."""
from langchain.tools import tool

from agent.db import read_session
from etl.geosupport import Client, Outcome

LOT = """
MATCH (l:Lot {bbl: $bbl})
OPTIONAL MATCH (b:Building)-[:ON_LOT]->(l)
WITH l, b ORDER BY b.bin
RETURN l {.bbl, .reliability, .source_category, .source, .snapshot_id} AS lot,
       [x IN collect(b {.bin, .reliability, .source_category, .source, .snapshot_id}) WHERE x.bin IS NOT NULL] AS buildings
"""

_client: Client | None = None


def client() -> Client:
    global _client
    _client = _client or Client()
    return _client


def lookup(runner, house_number: str, street: str, zip5: str | None = None, borough: str | None = None, geo: Client | None = None) -> dict:
    """`runner` is a neo4j Session or Transaction. A miss says what was tried and never guesses a nearby lot."""
    geo = geo or client()
    result, tried = geo.resolve(house_number, street, zip5, borough)
    base = {"spellings_tried": tried, "geocoder": "NYC DCP Geosupport"}
    if result.outcome is Outcome.UNAVAILABLE:
        return {**base, "status": "geocoder_unavailable", "note": "The address service could not be reached. This is not 'no lot found'."}
    if result.outcome is not Outcome.RESOLVED:
        out = {**base, "status": "not_found", "reason": result.outcome.value, "city_message": result.message}
        if result.candidates:
            out["similar_streets"] = list(result.candidates)
            out["similar_streets_total"] = result.candidate_total
        out["note"] = "No lot was resolved. No nearby lot was guessed."
        return out
    rec = runner.run(LOT, bbl=result.bbl).single()
    if rec is None:
        return {**base, "status": "geocoded_but_absent", "bbl": result.bbl,
                "note": "The city resolves this address to a lot the graph does not hold. This is not 'no such address'."}
    typed_as = tried[0]
    return {
        **base,
        "status": "found",
        "match": {"kind": "as_typed" if result.typed == typed_as else "variant", "typed": result.typed,
                  "canonical_street": result.street, "inferred": False},
        "address_building_bin": result.bin,
        "lots": [rec["lot"]],
        "buildings": rec["buildings"],
        "counts": {"lots": 1, "buildings": len(rec["buildings"]), "units": None},
        "note": "Units are not in the graph yet; lots, buildings and units are counted separately.",
    }


@tool
def find_lot_by_address(house_number: str, street: str, zip5: str = "", borough: str = "") -> dict:
    """Find the tax lot (BBL) and the buildings (BIN) at a New York City street address.

    Pass the house number, the street as typed (for example "54 Street", "7th Avenue", "Seventh Ave") and the
    5-digit zip code, or the borough name or code (1 Manhattan, 2 Bronx, 3 Brooklyn, 4 Queens, 5 Staten Island).
    The city's address service standardizes the address; the result lists every building on the lot, each with its
    source and snapshot, and says which spellings were tried. If the street is unknown it lists similar street names."""
    with read_session() as session:
        return lookup(session, house_number, street, zip5 or None, borough or None)
