from agent.tools.lookup import lookup


def test_found_by_building_address_lists_all_buildings_on_lot(tx):
    r = lookup(tx, "1", "Example Street", "11201")
    assert r["status"] == "found" and r["match"]["inferred"] is False
    assert [l["bbl"] for l in r["lots"]] == ["3000010001"]
    assert [b["bin"] for b in r["buildings"]] == ["3000001"]
    assert r["counts"] == {"lots": 1, "buildings": 1, "units": None}
    assert r["lots"][0]["snapshot_id"] == "sample-2026-01-01"


def test_not_found_reports_key_and_guesses_nothing(tx):
    r = lookup(tx, "99", "Nowhere Ave", "11201")
    assert r == {"status": "not_found", "variants_tried": ["99 NOWHERE AVE 11201"], "note": r["note"]}
    assert "lots" not in r
