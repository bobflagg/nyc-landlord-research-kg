"""Q18: deeds that may restructure ownership (design note 0026, P4). Read-only, parameterized.

Each deed gets the patterns it shows (vocab/deed-pattern.ttl), which are hints about what the record shows and say nothing about intent. Whether the grantee is related to the
grantor is answered apart, by independent support: a record other than the deed that connects the two names. With none, the answer is "no relationship established"."""
from datetime import date, timedelta

from langchain.tools import tool

from agent.db import read_session
from agent.tools.evidence import pair_evidence, profile
from agent.tools.records import PARTIES, PROV, _clean, _plain, snapshot
from etl.names import n1
from etl.vocab import bor_term, deed_family_types

PAIR_DAYS = 90        # a $0 deed and a deed for value on one lot within this many days of each other
NEW_ENTITY_DAYS = 180 # a grantee filed with DOS this many days or fewer before the deed
NOMINAL = 100         # BOR's nominal-consideration limit (manifest parameter nominal_max)
CAVEATS = [
    "A pattern is a hint about what the recorded deed shows, not a finding of restructuring or of intent. A $0 deed can be a gift, a transfer between related parties, a correction or an administrative deed, and the amount does not say which.",
    "The grantee is 'no relationship established' unless a record other than the deed connects it to the grantor (independent support). Support is a lead, shown with its source and whether it was used or set aside; it is not a finding of common ownership.",
    "Only deed-family documents on lots in the graph are here, and a DOS filing date is for the entity currently on file (active entities only), so a missing DOS record says nothing about the grantee.",
]
DEEDS = f"""
MATCH (l:Lot {{bbl: $bbl}})<-[:ON_LOT]-(d:Document) WHERE d.doc_type IN $deed_types AND d.doc_type <> 'deed_correction'
OPTIONAL MATCH (d)-[:ON_LOT]->(other:Lot)
WITH d, collect(DISTINCT other.bbl) AS lots
RETURN d {{.document_id, .doc_type, .doc_date, .recorded, .amount, {PROV}}} AS d, lots
ORDER BY d.recorded, d.document_id
"""
BOR_BUNDLE = "MATCH (e:BorEvidence {document_id: $d}) RETURN e {.evidence_id, .stage, .parcel_count, .run_id} AS e"
DOS = "MATCH (e:DosEntity {name_n1: $n}) RETURN e {.dos_id, .entity_name, .initial_filing_date} AS e"


def _day(d) -> date | None:
    d = _plain(d)
    return date.fromisoformat(d[:10]) if isinstance(d, str) and d else None


def classify(runner, bbl: str, max_deeds: int = 12) -> dict:
    base = {"bbl": bbl, **snapshot(runner)}
    if runner.run("MATCH (l:Lot {bbl: $bbl}) RETURN l.bbl", bbl=bbl).single() is None:
        return {**base, "status": "lot_absent", "note": "The graph holds no such lot."}
    base |= {"caveats": CAVEATS, "independent_support_searched": ["a shared HPD business address", "the same person in a principal role", "a person name differing by spacing", "a shared managing agent",
                                                                  "a document other than a deed naming both parties", "the same DOS process address", "the same BOR group", "BOR's own deed evidence for this deed"],
            "windows": {"paired_with_sale_days": PAIR_DAYS, "to_new_entity_days": NEW_ENTITY_DAYS, "nominal_consideration_limit": NOMINAL}}
    rows = runner.run(DEEDS, bbl=bbl, deed_types=deed_family_types()).data()
    if not rows:
        return {**base, "status": "no_deed_in_graph", "note": "No deed-family document is in the graph for this lot; that is not 'no transfer happened'."}
    deeds = []
    for r in rows:
        d = r["d"]
        parties = runner.run(PARTIES, id=d["document_id"]).data()
        deeds.append({"d": d, "lots": r["lots"], "grantors": [x["p"] for x in parties if x["role_type"] == "grantor"], "grantees": [x["p"] for x in parties if x["role_type"] == "grantee"]})
    out_deeds = []
    for x in deeds[-max_deeds:]:
        d, amount = x["d"], x["d"].get("amount")
        when = _day(d.get("doc_date")) or _day(d.get("recorded"))
        pats = []
        if amount == 0:
            pats.append("zero_consideration")
        elif amount is not None and 0 < amount <= NOMINAL:
            pats.append("nominal_consideration")
        gk, ek = {n1(p["party_name"]) for p in x["grantors"] if p.get("party_name")}, {n1(p["party_name"]) for p in x["grantees"] if p.get("party_name")}
        same = sorted((gk & ek) - {""})
        if same:
            pats.append("same_name_transfer")
        if len(x["lots"]) > 1:
            pats.append("multi_lot_deed")
        paired = []
        for y in deeds:
            if y is x:
                continue
            a, b = x["d"].get("amount"), y["d"].get("amount")
            ra, rb = _day(x["d"].get("recorded")), _day(y["d"].get("recorded"))
            if a is not None and b is not None and ra and rb and abs((ra - rb).days) <= PAIR_DAYS and ((a == 0 and b > NOMINAL) or (b == 0 and a > NOMINAL)):
                paired.append({"document_id": y["d"]["document_id"], "recorded": _plain(y["d"].get("recorded")), "amount": b})
        if paired:
            pats.append("paired_with_sale")
        new = []
        for p in x["grantees"]:
            for e in runner.run(DOS, n=n1(p.get("party_name") or "")).data():
                f = _day(e["e"].get("initial_filing_date"))
                if f and when and timedelta(0) <= when - f <= timedelta(days=NEW_ENTITY_DAYS):
                    new.append({"grantee": p["party_name"], "dos_id": e["e"]["dos_id"], "filed": _plain(e["e"]["initial_filing_date"]), "days_before_the_deed": (when - f).days})
        if new:
            pats.append("to_new_entity")
        support, set_aside = [], []
        if not same:
            for g in x["grantors"][:2]:
                for t in x["grantees"][:2]:
                    if g.get("party_name") and t.get("party_name"):
                        items, _ = pair_evidence(runner, profile(runner, g["party_name"]), profile(runner, t["party_name"]))
                        for i in items:
                            if i["type"] == "shared_acris_document" and str(i["document"].get("doc_type", "")).startswith("deed"):
                                continue    # a deed that names both is the transfer being tested, not independent support
                            (support if i["status"] == "used" else set_aside).append({"between": [g["party_name"], t["party_name"]], **{k: v for k, v in i.items() if k in ("type", "reason", "address_key", "person_name", "agent", "document", "layer", "group_id", "dos_id_a", "dos_id_b")}})
        bundle = [dict(b["e"]) for b in runner.run(BOR_BUNDLE, d=d["document_id"]).data()]
        if bundle:
            support.append({"type": "bor_deed_evidence", "bundle": bundle, "note": "BOR's own rules used this deed to link lots (a derived lead, note 0024)"})
        if same:
            relation = "same name on both sides (a lead: one normalized name, not proof of one party)"
        elif support:
            relation = "support found: a record other than the deed connects the names (leads, not findings)"
        else:
            relation = "no relationship established"
        out_deeds.append(_clean({"document_id": d["document_id"], "doc_type": d["doc_type"], "doc_date": _plain(d.get("doc_date")), "recorded": _plain(d.get("recorded")), "amount": amount,
                                 "lots_on_deed": len(x["lots"]), "grantors": [p["party_name"] for p in x["grantors"]], "grantees": [p["party_name"] for p in x["grantees"]],
                                 "patterns": [bor_term("deed-pattern", p) for p in pats], "paired_with": paired or None, "grantee_filed_with_dos": new or None,
                                 "buyer_relationship": relation, "independent_support": support[:6] or None, "support_set_aside": set_aside[:4] or None, "support_items_total": len(support) or None}))
    counts: dict[str, int] = {}
    for d in out_deeds:
        for p in d.get("patterns", []):
            counts[p] = counts.get(p, 0) + 1
    return {**base, "status": "found", "deeds_in_graph": len(deeds), "deeds_classified": len(out_deeds), "most_recent_only": len(deeds) > max_deeds,
            "pattern_counts": dict(sorted(counts.items())), "deeds": out_deeds,
            "open_questions": ["Is the grantee related to the grantor? Answered per deed in buyer_relationship; 'no relationship established' is not 'unrelated'.",
                               "Why was the deed recorded for the amount shown? The record does not say."]}


@tool
def classify_deeds(bbl: str) -> dict:
    """Classify the deeds on a tax lot (BBL, a 10-digit string) by the patterns they show: zero consideration, nominal consideration, same-name transfer, a $0 deed paired
    with a deed for value within 90 days, a grantee with a DOS filing within 180 days before the deed, or a deed naming several lots. Each deed also lists independent support
    for a relationship between grantor and grantee (a record other than the deed: a shared HPD address or officer, a joint document, a shared BOR group, BOR's deed
    evidence), used or set aside, and otherwise says 'no relationship established'. A pattern is a hint, not a finding of restructuring."""
    with read_session() as session:
        return classify(session, bbl)
