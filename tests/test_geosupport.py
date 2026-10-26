"""Pure tests of the Geosupport client: interpretation, cleaning, ordinals, retries, outages."""
import httpx
import pytest

from etl.geosupport import Client, Outcome, ReleaseMismatch, clean, interpret, spelled_ordinals_to_digits


def ok(bbl="3008210012", bin_="3324448", billing="0000000000", grc="00"):
    return {"Geosupport Return Code (GRC)": grc, "BOROUGH BLOCK LOT (BBL)": {"BOROUGH BLOCK LOT (BBL)": bbl},
            "Building Identification Number (BIN) of Input Address or NAP": bin_, "Condominium Billing BBL": billing,
            "First Street Name Normalized": "54 STREET   "}


def test_resolved_keeps_bbl_and_bin_as_strings():
    r = interpret(ok())
    assert (r.outcome, r.bbl, r.bin, r.billing_bbl, r.street) == (Outcome.RESOLVED, "3008210012", "3324448", None, "54 STREET")


def test_placeholder_bin_is_not_a_building():
    assert interpret(ok(bin_="3000000")).bin is None


def test_success_with_empty_bbl_is_no_tax_lot_not_resolved():
    assert interpret(ok(bbl="")).outcome is Outcome.NO_TAX_LOT


def test_warning_code_01_is_a_success():
    assert interpret(ok(grc="01")).outcome is Outcome.RESOLVED


def test_condo_billing_bbl_is_kept():
    assert interpret(ok(billing="1001230001")).billing_bbl == "1001230001"


@pytest.mark.parametrize("raw, outcome", [
    ({"Geosupport Return Code (GRC)": "EE", "List of Street Names": ["A", "B", "C", "D", "E", "F"]}, Outcome.STREET_AMBIGUOUS),
    ({"Geosupport Return Code (GRC)": "EE"}, Outcome.STREET_NOT_RECOGNIZED),
    ({"Geosupport Return Code (GRC)": "11"}, Outcome.STREET_NOT_RECOGNIZED),
    ({"Geosupport Return Code (GRC)": "42"}, Outcome.HOUSE_NUMBER_OUT_OF_RANGE),
    ({"Geosupport Return Code (GRC)": "13"}, Outcome.INVALID_INPUT),
    ({"Geosupport Return Code (GRC)": "99"}, Outcome.FAILED),
    ({}, Outcome.FAILED),
])
def test_return_codes(raw, outcome):
    assert interpret(raw).outcome is outcome


def test_candidates_are_capped_and_the_total_reported():
    r = interpret({"Geosupport Return Code (GRC)": "EE", "List of Street Names": list("ABCDEFG")})
    assert len(r.candidates) == 5 and r.candidate_total == 7


@pytest.mark.parametrize("house, street, expect", [
    ("224", "54 STREET APT 3B", ("224", "54 STREET")),
    ("224", "54th St., Apt. 3B", ("224", "54th St")),
    ("224", "54 Street #4", ("224", "54 Street")),
    ("22 REAR", "Mulberry Street", ("22", "Mulberry Street")),
])
def test_clean_removes_unit_text(house, street, expect):
    h, s, removed = clean(house, street)
    assert (h, s) == expect and removed


@pytest.mark.parametrize("street, expect", [
    ("Fifty-fourth Street", "54 STREET"), ("West Tenth Street", "WEST 10 STREET"), ("East Seventh Street", "EAST 7 STREET"),
    ("Twentieth Avenue", "20 AVENUE"), ("Broadway", "BROADWAY"), ("Fifth Avenue", "5 AVENUE"),
])
def test_spelled_ordinals(street, expect):
    assert spelled_ordinals_to_digits(street) == expect


def mock_client(handler):
    return Client("http://sidecar", http=httpx.Client(transport=httpx.MockTransport(handler)))


def test_retries_with_digit_ordinals_and_lists_every_spelling_tried():
    calls = []

    def handler(req):
        body = req.read().decode()
        calls.append(body)
        return httpx.Response(200, json=ok() if "54 STREET" in body else {"Geosupport Return Code (GRC)": "11"})

    r, tried = mock_client(handler).resolve("218", "Fifty-fourth Street", "11220")
    assert r.outcome is Outcome.RESOLVED and tried == ["218 Fifty-fourth Street", "218 54 STREET"] and len(calls) == 2


def test_an_outage_is_unavailable_never_not_found():
    def handler(req):
        raise httpx.ConnectError("refused")

    r, _ = mock_client(handler).resolve("218", "54 Street", "11220")
    assert r.outcome is Outcome.UNAVAILABLE


def test_release_mismatch_fails_loudly():
    with pytest.raises(ReleaseMismatch):
        mock_client(lambda req: httpx.Response(200, json={"release": "24c"})).health()
