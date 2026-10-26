"""The expected Q1 answers (evals/expected/slice1.json) against the real Geosupport sidecar.
Needs the sidecar: docker run -d --platform=linux/amd64 -p 8081:8080 --name nyclr-geosupport nyclr-geosupport"""
import json

import pytest

from etl.config import ROOT
from etl.geosupport import Client, Outcome

EXPECTED = json.loads((ROOT / "evals" / "expected" / "slice1.json").read_text())["questions"]["Q1"]


def sidecar():
    try:
        Client().health()
        return True
    except Exception:
        return False


pytestmark = [pytest.mark.geosupport, pytest.mark.skipif(not sidecar(), reason="Geosupport sidecar not running")]

CASES = [(k, b) for k, q in EXPECTED.items() for b in q["buildings"]]


@pytest.mark.parametrize("anchor, building", CASES, ids=[f'{k}-{b["bin"]}' for k, b in CASES])
def test_hpd_spelling_reaches_the_expected_lot_and_building(anchor, building):
    house, street = building["hpd_address"].split(" ", 1)
    r, _ = Client().resolve(house, street, "11220")
    assert r.outcome is Outcome.RESOLVED
    assert (r.bbl, r.bin) == (EXPECTED[anchor]["lot"]["bbl"], building["bin"])


@pytest.mark.parametrize("anchor", list(EXPECTED))
def test_pluto_spelling_reaches_the_expected_lot(anchor):
    lot = EXPECTED[anchor]["lot"]
    house, street = lot["address"].split(" ", 1)
    r, _ = Client().resolve(house, street, lot["zip5"])
    assert (r.outcome, r.bbl) == (Outcome.RESOLVED, lot["bbl"])


@pytest.mark.parametrize("house, street, bbl, bin_", [
    ("218", "54 St", "3008210012", "3324448"),
    ("218", "Fifty-fourth Street", "3008210012", "3324448"),
    ("224", "54 STREET APT 3B", "3008210012", "3324451"),
    ("5413", "7th Ave", "3008260002", "3014788"),
    ("5413", "Seventh Ave.", "3008260002", "3014788"),
    ("214", "St Nicholas Ave", "3032910032", "3075210"),
    ("214", "Saint Nicholas Avenue", "3032910032", "3075210"),
    ("218-224", "54 Street", "3008210012", "3324448"),
])
def test_typed_variants_resolve(house, street, bbl, bin_):
    r, _ = Client().resolve(house, street, "11237" if "Nicholas" in street else "11220")
    assert (r.outcome, r.bbl, r.bin) == (Outcome.RESOLVED, bbl, bin_)


def test_a_typo_offers_similar_streets_and_a_gap_has_no_lot():
    r, _ = Client().resolve("5413", "Seventh Avnue", "11220")
    assert r.outcome is Outcome.STREET_AMBIGUOUS and any("SEVENTH AVENUE" in c for c in r.candidates)
    assert Client().resolve("222", "54 Street", "11220")[0].outcome is Outcome.NO_TAX_LOT
