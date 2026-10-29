"""Derive evals/expected/slice3.json and slice3.sql from the justfixwow database (read-only), independent of the graph.

  uv run python -m evals.expected.derive_slice3

Q12 (deed timeline) and Q13 (mortgage-family documents, citing only documents that are in the graph) on the anchor lots A-G of docs/competency-questions-detail.md; Q14 is added when its tool is built
(design note 0022). A deed is the latest version of each document in the deed family, not a correction, recorded on the lot."""
import json
from datetime import date

from etl import source
from etl.config import ROOT
from etl.vocab import deed_family_codes, mortgage_family_codes

OUT = ROOT / "evals" / "expected"
SNAPSHOT_ID = "justfixwow-2026-05-29"
ANCHOR_DOC = json.loads((OUT / "slice1.json").read_text())["anchors"]
BBLS = [a["bbl"] for a in ANCHOR_DOC.values()]

SQL = {
    "Q12 deeds on each lot (latest version of each document, corrections excluded)": """select l.bbl, m.documentid, m.doctype, m.docdate, m.recordedfiled, m.docamount,
       (select array_agg(distinct l2.bbl order by l2.bbl) from real_property_legals l2 where l2.documentid = m.documentid) as lots
from real_property_legals l
join (select distinct on (documentid) * from real_property_master order by documentid, modifieddate desc) m on m.documentid = l.documentid
where l.bbl = any(%(bbls)s) and m.doctype = any(%(deeds)s) and m.doctype <> 'DEED COR'
order by l.bbl, m.recordedfiled, m.docdate, m.documentid""",
    "Q12 corrections on each lot": """select l.bbl, count(distinct m.documentid) as n from real_property_legals l join real_property_master m on m.documentid = l.documentid
where l.bbl = any(%(bbls)s) and m.doctype = 'DEED COR' group by l.bbl order by l.bbl""",
    "Q12 parties of those deeds (party type 1 grantor, 2 grantee)": """select p.documentid, p.partytype, p.name from real_property_parties p
where p.documentid = any(%(doc_ids)s) and p.partytype in ('1', '2') order by p.documentid, p.partytype, p.name""",
}


SQL13 = {
    "Q13 mortgage-family documents on each lot (latest version of each document)": """select l.bbl, m.documentid, m.crfn, m.doctype, m.docdate, m.recordedfiled, m.docamount
from real_property_legals l
join (select distinct on (documentid) * from real_property_master order by documentid, modifieddate desc) m on m.documentid = l.documentid
where l.bbl = any(%(bbls)s) and m.doctype = any(%(mortgage_codes)s) order by l.bbl, m.recordedfiled, m.docdate, m.documentid""",
    "Q13 recorded references of those documents": """select documentid, referencebycrfn, referencebydocid from real_property_references where documentid = any(%(doc_ids)s)""",
    "Q13 the documents those references cite by CRFN or document id (latest version), with the lots they are on": """select m.documentid, m.crfn, m.doctype,
       (select array_agg(distinct l.bbl) from real_property_legals l where l.documentid = m.documentid) as lots
from (select distinct on (documentid) * from real_property_master where crfn = any(%(crfns)s) or documentid = any(%(docids)s) order by documentid, modifieddate desc) m""",
}
SQL.update(SQL13)


def _plain(v):
    return v.isoformat() if hasattr(v, "isoformat") else v


def main() -> None:
    params = {"bbls": BBLS, "deeds": deed_family_codes()}
    with source.connect() as conn, conn.cursor() as cur:
        cur.execute(SQL[list(SQL)[0]], params)
        deeds = [{k: _plain(v) for k, v in r.items()} for r in cur.fetchall()]
        cur.execute(SQL[list(SQL)[1]], params)
        corrections = {r["bbl"]: r["n"] for r in cur.fetchall()}
        cur.execute(SQL[list(SQL)[2]], {"doc_ids": sorted({d["documentid"].strip() for d in deeds})})
        parties = [{**p, "documentid": p["documentid"].strip(), "partytype": str(p["partytype"]).strip()} for p in cur.fetchall()]
    mcodes = mortgage_family_codes()
    with source.connect() as conn, conn.cursor() as cur:
        cur.execute(SQL13["Q13 mortgage-family documents on each lot (latest version of each document)"], {"bbls": BBLS, "mortgage_codes": mcodes})
        mdocs = [{k: _plain(v.strip() if isinstance(v, str) else v) for k, v in r.items()} for r in cur.fetchall()]
        ids = sorted({d["documentid"] for d in mdocs})
        cur.execute(SQL13["Q13 recorded references of those documents"], {"doc_ids": ids})
        refs = [{k: (v.strip() if isinstance(v, str) else v) for k, v in r.items()} for r in cur.fetchall()]
        crfns = sorted({r["referencebycrfn"] for r in refs if r["referencebycrfn"]})
        docids = sorted({str(r["referencebydocid"]) for r in refs if not r["referencebycrfn"] and r["referencebydocid"] is not None})
        cur.execute(SQL13["Q13 the documents those references cite by CRFN or document id (latest version), with the lots they are on"], {"crfns": crfns, "docids": docids})
        cited = [{**r, "documentid": r["documentid"].strip(), "crfn": r["crfn"].strip()} for r in cur.fetchall()]
        registered, graph_lots = source.registered_lots(conn), source.graph_lots(conn)
    in_graph, in_graph_by_id = {}, {}
    for c in cited:
        lots = {b.strip() for b in (c["lots"] or [])}
        fam = c["doctype"] in mcodes
        if (fam and lots & registered) or (c["doctype"] in deed_family_codes() and lots & graph_lots):
            in_graph.setdefault(c["crfn"], []).append(c["documentid"])
            in_graph_by_id[c["documentid"]] = c["documentid"]
    q13 = {}
    for letter, a in ANCHOR_DOC.items():
        mine = list({d["documentid"]: d for d in mdocs if d["bbl"] == a["bbl"]}.values())   # a document with several legal rows on the lot is one document
        timeline = []
        for d in mine:
            cites = sorted({t for r in refs if r["documentid"] == d["documentid"]
                            for t in (in_graph.get(r["referencebycrfn"], []) if r["referencebycrfn"] else [in_graph_by_id[str(r["referencebydocid"])]] if str(r["referencebydocid"]) in in_graph_by_id else [])
                            if t != d["documentid"]})
            timeline.append({"document_id": d["documentid"], "doc_type": d["doctype"], "recorded": d["recordedfiled"], "amount": d["docamount"], "cites": cites})
        mort = [t for t in timeline if t["doc_type"] in ("MTGE", "M&CON", "CORRM")]
        sat_cites = {c for t in timeline if t["doc_type"] in ("SAT", "PSAT") for c in t["cites"]}
        for t in timeline:
            t["cited_by"] = sorted(u["document_id"] for u in timeline if t["document_id"] in u["cites"])
        q13[letter] = {"documents": len(timeline), "by_type": dict(sorted({x: sum(1 for t in timeline if t["doc_type"] == x) for x in {t["doc_type"] for t in timeline}}.items())),
                       "mortgages": len(mort), "mortgages_cited_by_a_satisfaction": sum(1 for t in mort if t["document_id"] in sat_cites),
                       "mortgages_with_no_satisfaction_citing_them": [t["document_id"] for t in mort if t["document_id"] not in sat_cites], "timeline": timeline}
    q12 = {}
    for letter, a in ANCHOR_DOC.items():
        mine = list({d["documentid"]: d for d in deeds if d["bbl"] == a["bbl"]}.values())
        timeline = []
        for d in mine:
            ps = [p for p in parties if p["documentid"] == d["documentid"].strip()]
            timeline.append({"document_id": str(d["documentid"]).strip(), "doc_type": d["doctype"], "doc_date": d["docdate"], "recorded": d["recordedfiled"], "amount": d["docamount"],
                             "lots": d["lots"], "grantors": [p["name"] for p in ps if p["partytype"] == "1"], "grantees": [p["name"] for p in ps if p["partytype"] == "2"]})
        q12[letter] = {"deeds": len(timeline), "deeds_for_value": sum(1 for t in timeline if t["amount"]), "deeds_for_zero_dollars": sum(1 for t in timeline if t["amount"] == 0),
                       "corrections": corrections.get(a["bbl"], 0), "timeline": timeline}
    doc = {"snapshot_id": SNAPSHOT_ID, "derived": date.today().isoformat(), "source": "justfixwow PostgreSQL (read-only); queries in slice3.sql",
           "how_to_read": ("Expected answers for the Slice 3 questions on the anchors A-G, taken from the snapshot the graph is built from. Q12 counts documents, not lots; "
                           "party names are as recorded (design note 0009)."),
           "anchors": {l: {"bbl": a["bbl"]} for l, a in ANCHOR_DOC.items()}, "questions": {"Q12": q12, "Q13": q13}}
    (OUT / "slice3.json").write_text(json.dumps(doc, indent=1) + "\n")
    (OUT / "slice3.sql").write_text("-- Queries behind evals/expected/slice3.json, run read-only on the justfixwow database by derive_slice3.py.\n"
                                     "-- %(bbls)s = the seven anchor BBLs (A-G); %(deeds)s = the deed-family codes; %(doc_ids)s = the deeds found by the first query.\n\n"
                                     + "\n\n".join(f"-- {n}\n{q};" for n, q in SQL.items()) + "\n")
    print("written", {l: v["deeds"] for l, v in q12.items()})


if __name__ == "__main__":
    main()
