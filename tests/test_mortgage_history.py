"""Q13 tool and the references load, on the anchor lots' mortgage documents loaded into nyclr inside a rolled-back transaction
(design note 0022). Expected edges are worked out from the fixture rows themselves: a reference by CRFN to a document in the fixture."""
import json
from collections import Counter
from datetime import date

import pytest

from agent.tools.mortgages import CAVEATS_Q13, mortgage_history
from etl.build import load_acris, load_hpd, load_pluto, load_references
from etl.config import ROOT
from etl.load import apply_schema, register_snapshot
from tests.scope import SCOPE, tag_acris, tag_hpd

SNAP, SNAP_DATE = "justfixwow-2026-05-29", date(2026, 5, 29)
FX = ROOT / "tests" / "fixtures"
ANCH, MG, REFS = (json.loads((FX / f).read_text()) for f in ("slice1_anchors.json", "slice3_mortgages.json", "slice3_references.json"))
LOTS = frozenset(str(r["bbl"]).strip() for r in ANCH["pluto"])
A, B, C, D, E, F, G = "3008260002", "3008260005", "3008070024", "3008210012", "3008210019", "3008970014", "3008080025"
DOC = {d["documentid"]: d for d in MG["documents"]}
BY_CRFN = {d["crfn"]: d["documentid"] for d in MG["documents"] if d.get("crfn")}
EDGES = {(r["documentid"], BY_CRFN[r["referencebycrfn"]]) for r in REFS["references"] if r["referencebycrfn"] and r["referencebycrfn"] in BY_CRFN and BY_CRFN[r["referencebycrfn"]] != r["documentid"]}
ON = {}
for lg in MG["legals"]:
    if lg["bbl"] in LOTS:
        ON.setdefault(lg["bbl"], set()).add(lg["documentid"])


@pytest.fixture
def graph(session, schema):
    apply_schema(session, schema)
    tx = session.begin_transaction()
    register_snapshot(tx, SNAP, "justfixwow", SNAP_DATE)
    load_pluto(tx, schema, ANCH["pluto"], SNAP)
    load_hpd(tx, schema, ANCH["registrations"], ANCH["contacts"], SNAP)
    load_acris(tx, schema, MG["documents"], MG["parties"], MG["legals"], LOTS, SNAP, SNAP_DATE)
    counts = load_references(tx, REFS["references"])
    tag_acris(tx, MG["documents"], MG["parties"])
    tag_hpd(tx, ANCH["pluto"], ANCH["registrations"], ANCH["contacts"])
    yield tx, counts
    tx.rollback()


def test_the_references_load_links_the_cited_documents_in_the_graph_and_counts_the_rest(graph):
    tx, counts = graph
    got = {(r["a"], r["b"]) for r in tx.run(f"MATCH (a:Document:`{SCOPE}`)-[:REFERENCES]->(b:Document) RETURN a.document_id AS a, b.document_id AS b")}
    assert EDGES <= got and len(EDGES) >= 20
    assert counts["references by reel and page only"] == sum(1 for r in REFS["references"] if not r["referencebycrfn"] and r["referencebydocid"] is None)


def test_loading_the_references_twice_changes_nothing(graph):
    tx, _ = graph
    before = tx.run(f"MATCH (:Document:`{SCOPE}`)-[r:REFERENCES]->() RETURN count(r) AS c").single()["c"]
    assert load_references(tx, REFS["references"])["REFERENCES"] == 0
    assert tx.run(f"MATCH (:Document:`{SCOPE}`)-[r:REFERENCES]->() RETURN count(r) AS c").single()["c"] == before


@pytest.mark.parametrize("lot", [A, B, C, D, E, G])
def test_q13_documents_and_types_on_each_anchor_match_the_source(graph, lot):
    tx, _ = graph
    r = mortgage_history(tx, lot, max_documents=500)
    want = ON.get(lot, set())
    if not want:
        assert r["status"] == "no_document_in_graph"
        return
    assert r["documents"] == len(want) and {t["document_id"] for t in r["timeline"]} == want
    assert r["documents_by_type"] == dict(sorted(Counter({"MTGE": "mortgage", "ASST": "assignment_of_mortgage", "SAT": "satisfaction", "AGMT": "agreement", "AL&R": "assignment_of_leases_rents",
                                                           "TL&R": "termination_lr", "SAGE": "sundry_agreement", "M&CON": "mortgage_consolidation"}[DOC[d]["doctype"]] for d in want).items()))
    recorded = [t["recorded"] for t in r["timeline"]]
    assert recorded == sorted(recorded)


def test_q13_cites_and_cited_by_follow_the_recorded_references(graph):
    tx, _ = graph
    seen = 0
    for lot in (A, B, C, E, G):
        r = mortgage_history(tx, lot, max_documents=500)
        if r["status"] != "found":
            continue
        for t in r["timeline"]:
            want_cites = {b for a, b in EDGES if a == t["document_id"]}
            assert {c["document_id"] for c in t.get("cites", [])} >= want_cites
            seen += len(want_cites)
    assert seen > 0


def test_q13_a_mortgage_with_a_citing_satisfaction_is_not_in_the_no_satisfaction_list(graph):
    tx, _ = graph
    for lot in (A, B, C, E, G):
        r = mortgage_history(tx, lot, max_documents=500)
        if r["status"] != "found":
            continue
        cited = {b for a, b in EDGES if DOC[a]["doctype"] in ("SAT", "PSAT") and DOC[b]["doctype"] in ("MTGE", "M&CON", "CORRM")}
        listed = {m["document_id"] for m in r["mortgages_with_no_satisfaction_citing_them"]}
        assert not (listed & cited), lot
        assert r["mortgages"] == sum(1 for d in ON[lot] if DOC[d]["doctype"] in ("MTGE", "M&CON", "CORRM"))
        assert r["mortgages_cited_by_a_satisfaction"] + len(listed) == r["mortgages"]


def test_q13_parties_carry_the_role_the_document_type_gives(graph):
    tx, _ = graph
    for lot in (A, B, C, E, G):
        r = mortgage_history(tx, lot, max_documents=500)
        for t in r.get("timeline", []):
            keys = set(t["parties"])
            if t["doc_type"] in ("mortgage", "satisfaction"):
                assert keys <= {"borrower", "lender"}
            if t["doc_type"] == "assignment_of_mortgage":
                assert keys <= {"assignor", "assignee"}
            if t["doc_type"] in ("agreement", "sundry_agreement", "termination_lr"):
                assert all(k.startswith("untyped_party_") for k in keys)


def test_q13_since_year_and_truncation_are_reported(graph):
    tx, _ = graph
    full = mortgage_history(tx, G, max_documents=500)
    year = int(full["timeline"][len(full["timeline"]) // 2]["recorded"][:4])
    since = mortgage_history(tx, G, year, max_documents=500)
    assert since["documents"] == sum(1 for t in full["timeline"] if t["recorded"] >= f"{year}-01-01") and 0 < since["documents"] < full["documents"]
    assert since["documents_recorded_before_since_year"] == full["documents"] - since["documents"]
    small = mortgage_history(tx, G, max_documents=2)
    assert small["truncated_to_most_recent"] is True and small["shown"] == 2 and small["documents"] == full["documents"]
    assert [t["document_id"] for t in small["timeline"]] == [t["document_id"] for t in full["timeline"]][-2:]


def test_q13_a_lot_without_documents_does_not_claim_none_was_recorded(graph):
    tx, _ = graph
    tx.run("MERGE (:Lot {bbl: '3099990009'})").consume()
    r = mortgage_history(tx, "3099990009")
    assert r["status"] == "no_document_in_graph" and "not 'no mortgage was ever recorded'" in r["note"] and "only for HPD-registered lots" in r["note"]
    assert mortgage_history(tx, "9999999999")["status"] == "lot_absent"


def test_q13_the_caveats_say_a_missing_satisfaction_proves_nothing(graph):
    text = " ".join(CAVEATS_Q13)
    assert "not proof that the loan is still outstanding" in text and "not proof of how or whether it was paid" in text and "reel and page" in text


# ---- the citywide graph against the source ---------------------------------------------------------------------

EXP3 = json.loads((ROOT / "evals" / "expected" / "slice3.json").read_text())
EXP2 = json.loads((ROOT / "evals" / "expected" / "slice2.json").read_text())
Q13, LETTER_BBL = EXP3["questions"]["Q13"], {k: v["bbl"] for k, v in EXP3["anchors"].items()}


@pytest.fixture(scope="module")
def citywide():
    from agent.db import read_session
    with read_session() as s:
        yield s


@pytest.mark.parametrize("a", list(Q13))
def test_the_citywide_graph_matches_the_source_on_every_anchor(citywide, a):
    e, r = Q13[a], mortgage_history(citywide, LETTER_BBL[a], max_documents=500)
    if not EXP2["questions"]["Q17"][a]["registered"]:      # the mortgage family is loaded for HPD-registered lots only
        assert r["status"] == "no_document_in_graph" and "only for HPD-registered lots" in r["note"]
        return
    assert r["status"] == "found" and r["documents"] == e["documents"]
    TYPE = {"MTGE": "mortgage", "ASST": "assignment_of_mortgage", "SAT": "satisfaction", "AGMT": "agreement", "AL&R": "assignment_of_leases_rents",
            "TL&R": "termination_lr", "SAGE": "sundry_agreement", "M&CON": "mortgage_consolidation", "CORRM": "mortgage_correction", "PSAT": "partial_satisfaction"}
    assert r["documents_by_type"] == {TYPE[k]: v for k, v in sorted(e["by_type"].items(), key=lambda kv: TYPE[kv[0]])}
    got = {t["document_id"]: t for t in r["timeline"]}
    assert set(got) == {t["document_id"] for t in e["timeline"]}
    for t in e["timeline"]:
        g = got[t["document_id"]]
        assert (g["doc_type_raw"], g["recorded"], g.get("amount")) == (t["doc_type"], t["recorded"], t["amount"])
        assert sorted(c["document_id"] for c in g.get("cites", [])) == t["cites"], t["document_id"]
        assert sorted(c["document_id"] for c in g.get("cited_by", []) if c["document_id"] in got) == t["cited_by"], t["document_id"]
    assert (r["mortgages"], r["mortgages_cited_by_a_satisfaction"]) == (e["mortgages"], e["mortgages_cited_by_a_satisfaction"])
    assert sorted(m["document_id"] for m in r["mortgages_with_no_satisfaction_citing_them"]) == sorted(e["mortgages_with_no_satisfaction_citing_them"])
