from agent.tools.lookup import lookup
from tests.fakes import FakeGeo


def test_found_lists_every_building_on_the_lot(tx):
    r = lookup(tx, "1", "Example Street", "11201", geo=FakeGeo())
    assert r["status"] == "found" and r["match"]["inferred"] is False and r["match"]["kind"] == "as_typed"
    assert [l["bbl"] for l in r["lots"]] == ["3000010001"] and [b["bin"] for b in r["buildings"]] == ["3000001"]
    assert r["address_building_bin"] == "3000001"
    assert r["counts"] == {"lots": 1, "buildings": 1, "units_residential": 0, "units_total": 0}
    assert r["lots"][0]["snapshot_id"] == "sample-2026-01-01"


def test_unit_text_is_ignored(tx):
    assert lookup(tx, "1", "Example Street Apt 3B", "11201", geo=FakeGeo())["status"] == "found"


def test_not_found_says_why_and_guesses_nothing(tx):
    r = lookup(tx, "99", "Nowhere Avenue", "11201", geo=FakeGeo())
    assert r["status"] == "not_found" and r["reason"] == "street_not_recognized" and "lots" not in r
    assert r["spellings_tried"] == ["99 NOWHERE AVENUE"]


def test_no_tax_lot_is_its_own_reason(tx):
    assert lookup(tx, "5", "Example Street", "11201", geo=FakeGeo())["reason"] == "no_tax_lot"


def test_similar_streets_are_offered(tx):
    r = lookup(tx, "9", "Examplr Street", "11201", geo=FakeGeo())
    assert r["similar_streets"] == ["EXAMPLE STREET", "EXAMPLER PLACE"]


def test_geocoded_but_absent_is_not_no_such_address(tx):
    r = lookup(tx, "7", "Example Street", "11201", geo=FakeGeo())
    assert r["status"] == "geocoded_but_absent" and r["bbl"] == "3999999999"


def test_outage_is_not_not_found(tx):
    assert lookup(tx, "1", "Example Street", "11201", geo=FakeGeo(down=True))["status"] == "geocoder_unavailable"


def test_found_returns_the_lots_characteristics_with_their_source(tx):
    tx.run("MATCH (l:Lot {bbl: '3000010001'}) SET l.building_class = 'C1', l.units_residential = 12, l.units_total = 13, l.year_built = 1925, l.assessed_total = 500000, l.buildings_count = 1")
    r = lookup(tx, "1", "Example Street", "11201", geo=FakeGeo())
    lot = r["lots"][0]
    assert (lot["building_class"], lot["units_residential"], lot["units_total"], lot["year_built"], lot["assessed_total"]) == ("C1", 12, 13, 1925, 500000)
    assert lot["snapshot_id"] == "sample-2026-01-01" and "source" in lot
    assert r["counts"]["units_residential"] == 12 and r["counts"]["buildings"] == 1
    assert "year_built_raw" not in lot and "owner_name_pluto" not in lot
