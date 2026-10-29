"""Q13: mortgages, assignments and satisfactions recorded against a lot (design notes 0015, 0022). Read-only, parameterized.

The mortgage family is loaded for HPD-registered lots only. A document cites other documents in its recorded references (matched by
CRFN or document id when the cited document is in the graph); a citation is the filer's record, not proof of what happened to a loan.
No satisfaction recorded, or none citing a mortgage, is not proof that the loan is outstanding, and a termination is not proof it was paid."""
from langchain.tools import tool

from agent.db import read_session
from agent.tools.records import PARTIES, PROV, _clean, snapshot
from etl.vocab import mortgage_family_types

CAVEATS_Q13 = [
    "No satisfaction recorded, or none that cites a mortgage, is not proof that the loan is still outstanding; a satisfaction or termination that is recorded is not proof of how or whether it was paid. "
    "This tool reports documents and does not say which loan is outstanding.",
    "A citation (cites, cited_by) is what the filer wrote in the document's recorded references, matched by CRFN or document id to a document in the graph. A reference by reel and page, to a document "
    "recorded before CRFNs or on a lot outside the registered lots, or to a document type not loaded, makes no link, so a missing citation is not evidence that none exists.",
    "The mortgage family is loaded for HPD-registered lots only, and only these document types: mortgage, consolidation, correction, assignment of mortgage, satisfaction and partial satisfaction, agreement, "
    "assignment of leases and rents (and of an assignment), termination of leases and rents, and sundry agreement. Other recorded instruments are not here.",
    "Parties are shown in the role the document type gives them (borrower and lender on a mortgage or satisfaction, assignor and assignee on an assignment). An agreement, termination or sundry agreement "
    "names its parties only as party 1 and party 2, so they carry no role. A party name is a lead, not a finding about who owns or controls the building.",
    "An amount of $0 on a mortgage-class document is the amount the document records; many of these instruments (agreements, assignments, terminations) record none, and the amount is not a measure of a loan.",
]
MORTGAGE_KINDS = {"mortgage", "mortgage_consolidation", "mortgage_correction"}
SATISFACTION_KINDS = {"satisfaction", "partial_satisfaction"}
DOCS = f"""
MATCH (l:Lot {{bbl: $bbl}})<-[:ON_LOT]-(d:Document) WHERE d.doc_type IN $types
OPTIONAL MATCH (d)-[:ON_LOT]->(other:Lot)
WITH d, collect(DISTINCT other.bbl) AS lots
OPTIONAL MATCH (d)-[:REFERENCES]->(c:Document)
WITH d, lots, collect(DISTINCT c {{.document_id, .doc_type, .recorded, .amount}}) AS cites
OPTIONAL MATCH (b:Document)-[:REFERENCES]->(d)
WITH d, lots, cites, collect(DISTINCT b {{.document_id, .doc_type, .recorded, .amount}}) AS cited_by
RETURN d {{.document_id, .doc_type, .doc_type_raw, .doc_date, .doc_date_raw, .recorded, .amount, .crfn, {PROV}}} AS d, lots, cites, cited_by
ORDER BY d.recorded, d.doc_date, d.document_id
"""


def _p(p: dict) -> dict:
    return _clean({"name": p.get("party_name"), "address": ", ".join(x for x in (p.get("address_line1"), p.get("city"), p.get("state"), p.get("zip")) if x) or None})


def _ref(c: dict) -> dict:
    return _clean({"document_id": c["document_id"], "doc_type": c["doc_type"], "recorded": c.get("recorded"), "amount": c.get("amount")})


def mortgage_history(runner, bbl: str, since_year: int | None = None, max_documents: int = 60) -> dict:
    """Mortgage-family documents on a lot, oldest first, with parties by role and the documents each cites and is cited by."""
    base = {"bbl": bbl, **snapshot(runner)}
    if runner.run("MATCH (l:Lot {bbl: $bbl}) RETURN l.bbl", bbl=bbl).single() is None:
        return {**base, "status": "lot_absent", "note": "The graph holds no such lot."}
    base |= {"caveats": CAVEATS_Q13, "since_year": since_year, "ordering": "oldest first by recording date, then document date"}
    registered = runner.run("MATCH (l:Lot {bbl: $bbl})<-[:ON_LOT]-(:Registration) RETURN count(*) AS c", bbl=bbl).single()["c"] > 0
    rows = runner.run(DOCS, bbl=bbl, types=mortgage_family_types()).data()
    if since_year is not None:
        earlier = sum(1 for r in rows if r["d"].get("recorded") is None or r["d"]["recorded"].year < since_year)
        rows = [r for r in rows if r["d"].get("recorded") is not None and r["d"]["recorded"].year >= since_year]
        base["documents_recorded_before_since_year"] = earlier
    if not rows:
        return {**base, "status": "no_document_in_graph", "lot_has_hpd_registration": registered,
                "note": ("No mortgage-family document is in the graph for this lot. " + ("" if registered else
                         "The lot has no HPD registration, and the mortgage family is loaded only for HPD-registered lots, so this says nothing about whether any exist. ")
                         + "It is not 'no mortgage was ever recorded'.")}
    truncated = len(rows) > max_documents
    shown = rows[-max_documents:] if truncated else rows
    docs = []
    for r in shown:
        d = r["d"]
        roles: dict[str, list] = {}
        for x in runner.run(PARTIES, id=d["document_id"]).data():
            roles.setdefault(x["role_type"] or "untyped_party_" + str(x["party_type"]), []).append(_p(x["p"]))
        entry = _clean(d) | {"lots_on_document": sorted(r["lots"]), "parties": roles}
        if r["cites"]:
            entry["cites"] = [_ref(c) for c in sorted(r["cites"], key=lambda c: (str(c.get("recorded")), c["document_id"]))]
        if r["cited_by"]:
            entry["cited_by"] = [_ref(c) for c in sorted(r["cited_by"], key=lambda c: (str(c.get("recorded")), c["document_id"]))]
        docs.append(entry)
    by_type: dict[str, int] = {}
    for r in rows:
        by_type[r["d"]["doc_type"]] = by_type.get(r["d"]["doc_type"], 0) + 1
    mortgages = [r for r in rows if r["d"]["doc_type"] in MORTGAGE_KINDS]
    cited_by_satisfaction = lambda r: any(c["doc_type"] in SATISFACTION_KINDS for c in r["cited_by"])
    return {**base, "status": "found", "documents": len(rows), "documents_by_type": dict(sorted(by_type.items())), "shown": len(shown), "truncated_to_most_recent": truncated,
            "mortgages": len(mortgages), "mortgages_cited_by_a_satisfaction": sum(1 for r in mortgages if cited_by_satisfaction(r)),
            "mortgages_with_no_satisfaction_citing_them": [{"document_id": r["d"]["document_id"], "recorded": r["d"].get("recorded"), "amount": r["d"].get("amount")}
                                                            for r in mortgages if not cited_by_satisfaction(r)],
            "satisfactions": sum(1 for r in rows if r["d"]["doc_type"] in SATISFACTION_KINDS),
            "satisfactions_that_cite_no_document_in_the_graph": sum(1 for r in rows if r["d"]["doc_type"] in SATISFACTION_KINDS and not r["cites"]),
            "timeline": docs}


@tool
def get_mortgage_history(bbl: str, since_year: int = 0) -> dict:
    """List the mortgages, assignments of mortgage, satisfactions, agreements and related instruments recorded against a tax lot (BBL, a
    10-digit string), oldest first: document id, type, recorded date, amount, parties in the role the document type gives them (borrower
    and lender, assignor and assignee), and the documents each cites and is cited by. since_year (0 for all) keeps documents recorded from
    that year on. Loaded for HPD-registered lots only. No satisfaction recorded is not proof a loan is outstanding, and a satisfaction or
    termination is not proof it was paid; it never says which loan is outstanding."""
    with read_session() as session:
        return mortgage_history(session, bbl, since_year or None)
