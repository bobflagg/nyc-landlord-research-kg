"""Derive evals/expected/slice5.json and slice5.sql from the justfixwow database (read-only), the mail-drop CSV and the earlier expected files, independent of the graph.

  uv run python -m evals.expected.derive_slice5

Q6 (parties at an address), Q22 (name relations, DOS records), Q7 and Q11 on A and B (and C), Q18 on B, Q23 on two managing agents (design note 0026)."""
import csv
import json
from collections import defaultdict
from datetime import date, timedelta

from etl import source
from etl.address import a2_key
from etl.config import ROOT
from etl.hpd import party_id, real_bin
from etl.names import n1, n2

OUT = ROOT / "evals" / "expected"
S1, S3 = json.loads((OUT / "slice1.json").read_text()), json.loads((OUT / "slice3.json").read_text())
ANCH = {l: a["bbl"] for l, a in S1["anchors"].items()}
PRINCIPAL = ("registered_owner", "head_officer", "officer", "shareholder", "lessee")
MAP = {"CorporateOwner": "registered_owner", "IndividualOwner": "registered_owner", "JointOwner": "registered_owner", "HeadOfficer": "head_officer", "Officer": "officer", "Shareholder": "shareholder", "Lessee": "lessee"}
ADDRESS_KEYS = ["746 61ST ST 11220", "418 BROADWAY 12207"]
NAME_PAIRS = [("KS Turnpike LLC", "K S TURNPIKE LLC"), ("702 54 STREET LLC", "702 PLAZA LLC"), ("5413 PLAZA LLC", "702 Plaza LLC"), ("Example Holdings LLC", "Example Holdings II LLC"), ("Acme L.L.C.", "ACME LLC")]
AGENTS = ["BRIGHTON MANAGEMENT", "BIG BROOKLYN REHAB INC"]
SQL = {
    "contacts at an address": "select * from hpd_contacts where businesshousenumber = %(house)s and businesszip like %(zip)s",
    "DOS entities by name": "select dosid, currententityname, initialdosfilingdate from dos_active_corporations where upper(currententityname) like any(%(patterns)s)",
    "mortgage-family parties of documents": "select documentid, partytype, name from real_property_parties where documentid = any(%(ids)s)",
    "registrations of an agent": "select distinct r.registrationid, r.bbl, c.corporationname from hpd_contacts c join hpd_registrations r on r.registrationid = c.registrationid where c.type = 'Agent' and upper(c.corporationname) like %(pattern)s",
    "units of lots": "select bbl, unitsres from pluto_latest where bbl = any(%(bbls)s)",
}


def rows(cur, name, **p):
    cur.execute(SQL[name], p)
    return cur.fetchall()


def main() -> None:
    mail = {f'{r["address_key"]} {r["zip5"]}': r for r in csv.DictReader(open(ROOT / "resolution" / "mail_drop_addresses.csv"))}
    bor_key = next(k for k, r in mail.items() if r["bor_address_ids"])
    keys = ADDRESS_KEYS + [bor_key]
    q6, q22, q7, q11, q18, q23 = {}, {}, {}, {}, {}, {}
    with source.connect() as conn, conn.cursor() as cur:
        for key in keys:
            house, zip5 = key.split()[0], key.split()[-1]
            cs = [c for c in rows(cur, "contacts at an address", house=house, zip=zip5 + "%")
                  if a2_key(str(c["businesshousenumber"]), str(c["businessstreetname"] or ""), str(c["businesszip"] or "")) == key]
            q6[key] = {"on_mail_drop_list": key in mail, "list_kind": mail[key]["kind"] if key in mail else None, "bor_masked_on_list": bool(key in mail and mail[key]["bor_address_ids"]),
                       "hpd_contact_rows": len({str(c["registrationcontactid"]) for c in cs}), "hpd_parties": len({party_id(c) for c in cs})}
        for a, b in NAME_PAIRS:
            pats = [f"%{w}%" for w in {a.upper().split()[0], b.upper().split()[0], n1(a).split()[0]}]
            dos = rows(cur, "DOS entities by name", patterns=pats)
            ids = lambda nm: sorted(str(d["dosid"]) for d in dos if n1(d["currententityname"]) == n1(nm))
            rel = "normalization_match" if n1(a) == n1(b) else "spacing_match" if n2(a) == n2(b) else None
            q22[f"{a} | {b}"] = {"n1_equal": n1(a) == n1(b), "n2_equal": n2(a) == n2(b), "relation": rel, "dos_ids_a": ids(a), "dos_ids_b": ids(b)}
        # Q7 and Q11 on the anchors
        contacts = S1["questions"]["Q4"]
        def people(letter):
            out = defaultdict(set)
            for reg, cs in contacts[letter].items():
                for c in cs:
                    role = MAP.get(c["type"])
                    if role and c["person_name"]:
                        out[n1(c["person_name"])].add(role)
            return out
        def agents(letter):
            return {n1(c["person_name"] or c["organization_name"]) for cs in contacts[letter].values() for c in cs if c["type"] == "Agent"}
        def addrs(letter):
            return {c["business_address"]["a2_key"] for cs in contacts[letter].values() for c in cs if c["business_address"] and c["business_address"].get("a2_key")}
        pa, pb = people("A"), people("B")
        docs = lambda l: {t["document_id"] for t in S3["questions"]["Q13"][l]["timeline"]}
        q7["A|B"] = {"shared_hpd_addresses": sorted(addrs("A") & addrs("B")), "same_person_names": sorted(set(pa) & set(pb)),
                     "spacing_only_person_names": sorted((n2(x), x, y) for x in pa for y in pb if x != y and n2(x) == n2(y)), "shared_managing_agents": sorted(agents("A") & agents("B")),
                     "documents_on_both_lots": sorted(docs("A") & docs("B")),
                     "dos_process_addresses": {l: S1["questions"]["Q5"][l]["record"]["process_address"] for l in "AB"}}
        for letter in ("A", "C"):
            ids = sorted({t["document_id"] for t in S3["questions"]["Q13"][letter]["timeline"] if t["doc_type"] in ("MTGE", "M&CON", "CORRM", "SAT", "PSAT")})
            ps = defaultdict(lambda: defaultdict(set))
            for p in rows(cur, "mortgage-family parties of documents", ids=ids):
                ps[p["documentid"].strip()][str(p["partytype"]).strip()].add(" ".join(p["name"].split()))
            lenders = sorted({n for d in ps.values() for n in d.get("2", ())})
            joint = sorted(d for d, v in ps.items() if len(v.get("1", ())) >= 2)
            q11[letter] = {"lenders_named": lenders, "documents_with_several_borrowers": joint, "documented_parent": None}
        # Q18 on B
        timeline = S3["questions"]["Q12"]["B"]["timeline"]
        names = sorted({n1(p) for d in timeline for p in d["grantees"] if p})
        dos = rows(cur, "DOS entities by name", patterns=[f"%{w}%" for w in ("702",)])
        filed = {n1(d["currententityname"]): d["initialdosfilingdate"] for d in dos}
        deeds = []
        for d in timeline:
            amt, rec = d["amount"], date.fromisoformat(d["recorded"])
            pats = []
            if amt == 0: pats.append("zero_consideration")
            elif amt is not None and 0 < amt <= 100: pats.append("nominal_consideration")
            if {n1(x) for x in d["grantors"]} & {n1(x) for x in d["grantees"]} - {""}: pats.append("same_name_transfer")
            if len(d["lots"] or []) > 1: pats.append("multi_lot_deed")
            if any(o is not d and o["amount"] is not None and abs((date.fromisoformat(o["recorded"]) - rec).days) <= 90 and ((amt == 0 and o["amount"] > 100) or (o["amount"] == 0 and amt is not None and amt > 100)) for o in timeline):
                pats.append("paired_with_sale")
            when = date.fromisoformat(d["doc_date"] or d["recorded"])
            if any(n1(g) in filed and timedelta(0) <= when - filed[n1(g)].date() <= timedelta(days=180) if hasattr(filed.get(n1(g)), "date") else (n1(g) in filed and timedelta(0) <= when - filed[n1(g)] <= timedelta(days=180)) for g in d["grantees"]):
                pats.append("to_new_entity")
            deeds.append({"document_id": d["document_id"], "recorded": d["recorded"], "amount": amt, "patterns": sorted(pats)})
        q18["B"] = {"deeds": deeds}
        # Q23
        for agent in AGENTS:
            regs = rows(cur, "registrations of an agent", pattern=agent + "%")
            regs = [r for r in regs if n1(r["corporationname"]) == n1(agent)]     # exact normalized name, as the tool matches
            bbls = sorted({r["bbl"] for r in regs})
            units = {u["bbl"]: u["unitsres"] for u in rows(cur, "units of lots", bbls=bbls)}
            q23[agent] = {"lots": len(bbls), "registrations": len({r["registrationid"] for r in regs}), "residential_units": sum(v or 0 for v in units.values()),
                          "lots_missing_a_unit_count": sum(1 for b in bbls if units.get(b) is None)}
    doc = {"snapshot_id": S1["snapshot_id"], "derived": date.today().isoformat(), "source": "justfixwow PostgreSQL (read-only), resolution/mail_drop_addresses.csv and slice1.json, slice3.json; queries in slice5.sql",
           "how_to_read": "Expected answers for Slice 5 (Q6, Q22, Q7, Q11, Q18, Q23) taken from the snapshot the graph is built from, without the graph. Agents are matched by the start of the registered name; the test compares counts of the exact-name footprint.",
           "anchors": {l: {"bbl": b} for l, b in ANCH.items()}, "questions": {"Q6": q6, "Q22": q22, "Q7": q7, "Q11": q11, "Q18": q18, "Q23": q23}}
    (OUT / "slice5.json").write_text(json.dumps(doc, indent=1, default=str) + "\n")
    (OUT / "slice5.sql").write_text("-- Queries behind evals/expected/slice5.json, run read-only on the justfixwow database by derive_slice5.py.\n\n" + "\n\n".join(f"-- {n}\n{q};" for n, q in SQL.items()) + "\n")
    print("written", q6, q23)


if __name__ == "__main__":
    main()
