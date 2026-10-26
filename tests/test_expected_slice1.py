"""The expected-answers file must agree with itself: comparisons recomputed by the project's rules N1 and A2."""
import json
import re

import pytest

from etl.address import a2_key
from etl.config import ROOT
from etl.names import n1
from etl.schema import SNAPSHOT_ID

DOC = json.loads((ROOT / "evals" / "expected" / "slice1.json").read_text())
Q = DOC["questions"]


def test_snapshot_id_form():
    assert SNAPSHOT_ID.match(DOC["snapshot_id"])


def test_keys_are_strings_of_the_right_shape():
    for a in DOC["anchors"].values():
        assert re.fullmatch(r"\d{10}", a["bbl"])
    for q in Q["Q1"].values():
        for b in q["buildings"]:
            assert re.fullmatch(r"\d{7}", b["bin"])


@pytest.mark.parametrize("anchor", list(Q["Q1"]))
def test_q1_counts_match_listed_buildings(anchor):
    q = Q["Q1"][anchor]
    assert q["counts"]["buildings"] == len(q["buildings"])
    assert q["counts"]["lots"] == 1


def test_q1_a2_keys_are_recomputable():
    for q in Q["Q1"].values():
        for b in q["buildings"]:
            house, street = b["hpd_address"].split(" ", 1)
            assert b["hpd_a2_key"].startswith(a2_key(house, street, ""))


@pytest.mark.parametrize("anchor", list(Q["Q3"]))
def test_q3_name_agreement_follows_n1(anchor):
    for g in Q["Q3"][anchor]["grantees"]:
        assert g["grantee_n1"] == n1(g["grantee"])
        if isinstance(g["vs_hpd"], str):
            continue
        for c in g["vs_hpd"]:
            if c["name_agreement"] == "not_comparable":
                continue
            same = n1(g["grantee"]) == n1(c["hpd_owner"])
            assert c["name_agreement"] == ("exact_normalized" if same else "different")


def test_q2_registration_ids_are_strings():
    for v in Q["Q2"].values():
        for r in ([] if isinstance(v, str) else v):
            assert isinstance(r["registration_id"], str)


def test_q4_every_contact_has_a_role_source_and_id():
    for regs in Q["Q4"].values():
        for contacts in ([] if isinstance(regs, str) else regs.values()):
            for c in contacts:
                assert c["type"] and c["source"] == "hpd_contacts" and c["reliability"] == "I"
                assert re.fullmatch(r"\d+", c["contact_id"])
                assert c["person_name"] or c["organization_name"]


def test_q5_hpd_spelling_of_g_does_not_match_dos_under_n1():
    assert n1("KS Turnpike LLC") != n1(Q["Q5"]["G"]["record"]["entity_name"])
