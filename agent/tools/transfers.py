"""Q12: the deed transfers of a lot as a timeline (design notes 0015, 0022). Read-only, parameterized.

Counts documents, not lots: a deed that names several lots is one deed. Corrections are not transfers and are counted apart. A
$0 deed is not a sale. Nothing here attributes a transfer to the current owner."""
from langchain.tools import tool

from agent.db import read_session
from agent.tools.records import PARTIES, PROV, _clean, snapshot
from etl.vocab import deed_family_types

CAVEATS_Q12 = [
    "The timeline lists deed-family documents recorded against this lot, one entry per document, so a deed that covers several lots is one deed. Deed corrections are not transfers and are counted apart. "
    "Only the deed family is loaded; mortgages and other documents are not part of this timeline.",
    "A deed for $0 is not a sale (a gift, a transfer between related parties or an administrative deed look the same in the amount). 'for_value' means only that the recorded amount is above $0, not that a sale at market price took place. "
    "DEEDO is a catch-all type that counts as a transfer only after the document is read.",
    "A grantee is who the deed names, not proof of who owns or controls the building today. A later deed, a document not in the graph or a transfer not recorded may exist. "
    "This does not attribute any transfer to the building's current owner.",
]
DEED_TIMELINE = f"""
MATCH (l:Lot {{bbl: $bbl}})<-[:ON_LOT]-(d:Document) WHERE d.doc_type IN $deed_types
OPTIONAL MATCH (d)-[:ON_LOT]->(other:Lot)
WITH d, collect(DISTINCT other.bbl) AS lots
RETURN d {{.document_id, .doc_type, .doc_type_raw, .doc_date, .doc_date_raw, .recorded, .amount, {PROV}}} AS d, lots
ORDER BY d.recorded, d.doc_date, d.document_id
"""
NOTES = {"deed_other": "DEEDO is a catch-all type: it is a transfer only after the document is read.",
         "deed_life_estate": "A life estate deed: a party with the role life_estate_retained keeps a life interest.",
         "deed_timeshare": "A timeshare deed.", "deed_restrictive_covenant": "A restrictive covenant deed.",
         "deed_pre_rpt": "A deed recorded before the real property transfer tax return began (DEEDP)."}


def _party(p: dict) -> dict:
    return _clean({"name": p.get("party_name"), "name_n1": p.get("name_n1"), "address": ", ".join(x for x in (p.get("address_line1"), p.get("city"), p.get("state"), p.get("zip")) if x) or None})


def deed_history(runner, bbl: str, since_year: int | None = None) -> dict:
    """Every deed-family document on the lot, oldest first, with grantors and grantees, and counts of deeds, deeds for value and $0 deeds."""
    base = {"bbl": bbl, **snapshot(runner)}
    if runner.run("MATCH (l:Lot {bbl: $bbl}) RETURN l.bbl", bbl=bbl).single() is None:
        return {**base, "status": "lot_absent", "note": "The graph holds no such lot."}
    base |= {"caveats": CAVEATS_Q12, "since_year": since_year, "ordering": "oldest first by recording date, then document date"}
    rows = runner.run(DEED_TIMELINE, bbl=bbl, deed_types=deed_family_types()).data()
    corrections = [r for r in rows if r["d"]["doc_type"] == "deed_correction"]
    deeds = [r for r in rows if r["d"]["doc_type"] != "deed_correction"]
    earlier = None
    if since_year is not None:
        kept = [r for r in deeds if r["d"].get("recorded") is not None and r["d"]["recorded"].year >= since_year]
        earlier, deeds = len(deeds) - len(kept), kept
        base["deeds_recorded_before_since_year"] = earlier
    if not deeds:
        return {**base, "status": "no_deed_in_graph", "corrections_not_counted": len(corrections),
                "note": "No deed-family document" + (f" recorded from {since_year}" if since_year else "") + " is in the graph for this lot. That is not 'no transfer happened': "
                        "documents on condominium unit lots, other document types and anything not recorded are not here."}
    timeline = []
    for r in deeds:
        d = r["d"]
        parties = runner.run(PARTIES, id=d["document_id"]).data()
        grantors = [_party(x["p"]) | {"role": x["role_type"]} for x in parties if x["role_type"] == "grantor"]
        grantees = [_party(x["p"]) | {"role": x["role_type"]} for x in parties if x["role_type"] == "grantee"]
        retained = [_party(x["p"]) | {"role": x["role_type"]} for x in parties if x["role_type"] == "life_estate_retained"]
        same = sorted({g["name_n1"] for g in grantors if g.get("name_n1")} & {g["name_n1"] for g in grantees if g.get("name_n1")})
        entry = _clean(d) | {"lots_on_document": sorted(r["lots"]), "for_value": bool(d.get("amount")), "grantors": grantors, "grantees": grantees}
        if retained:
            entry["life_estate_retained_by"] = retained
        if same:
            entry["grantor_and_grantee_share_a_normalized_name"] = same
        if d["doc_type"] in NOTES:
            entry["note"] = NOTES[d["doc_type"]]
        timeline.append(entry)
    for_value = [t for t in timeline if t["for_value"]]
    return {**base, "status": "found", "deeds": len(timeline), "deeds_for_value": len(for_value), "deeds_for_zero_dollars": sum(1 for t in timeline if t.get("amount") == 0),
            "deeds_with_no_amount": sum(1 for t in timeline if t.get("amount") is None), "corrections_not_counted": len(corrections),
            "first_recorded": timeline[0].get("recorded"), "last_recorded": timeline[-1].get("recorded"),
            "last_deed_for_value": {k: for_value[-1].get(k) for k in ("document_id", "recorded", "amount")} if for_value else None,
            "timeline": timeline}


@tool
def get_deed_history(bbl: str, since_year: int = 0) -> dict:
    """List the deeds recorded on a tax lot (BBL, a 10-digit string) as a timeline, oldest first: document id, type, document and recorded dates,
    amount, grantors and grantees, and whether the amount is above $0. Counts deeds, not lots (a deed on several lots is one deed); deed
    corrections are counted apart; a $0 deed is not a sale. since_year (0 for all) keeps deeds recorded from that year on. It says who a
    deed names and never who owns or controls the building."""
    with read_session() as session:
        return deed_history(session, bbl, since_year or None)
