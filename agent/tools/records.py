"""Q3 and Q24: templated, parameterized, read-only queries over the graph (design notes 0009, 0015, 0016).

Q3 compares the latest deed's grantees with the HPD registered owners of a lot. Q24 starts from a name. Names are
compared by rule N1 at query time and a match is a lead, never "same party" or ownership. Every record carries its
source and snapshot. Dates are returned as ISO text."""
import csv
from functools import cache

from langchain.tools import tool

from agent.db import read_session
from etl.config import ROOT
from etl.names import n1

PROV = ".reliability, .source_category, .source, .snapshot_id"
CAVEATS_Q3 = [
    "Name agreement is a comparison of normalized strings (rule N1), not a finding that two records are the same party. "
    "A name match is a lead.",
    "Address agreement compares the ACRIS party address with the HPD business address (rule A2). 'absent' means one side has "
    "no comparable address. An address at a mail-drop or registered-agent address links nothing on its own.",
    "A $0 deed is not a sale. DEEDO is a catch-all that counts as a transfer only after the document is read. "
    "Deed corrections (DEED COR) are not counted. Only the deed family is loaded; mortgages and other documents are not.",
]
CAVEATS_Q24 = [
    "Records are matched on the exact normalized name (rule N1). Other spellings are not searched for, and a name match is a lead, not a finding.",
    "ACRIS coverage is the deed family on lots in the graph; mortgages and other document types are not loaded yet. A deed recorded for $0 is not "
    "necessarily a sale. DOS holds active entities only: no DOS record is not 'does not exist'. A DOS entity is not tied to any lot, and its CEO and "
    "officer fields are not carried for LLCs, so their absence does not mean there are none.",
    "A person's name is returned only in the role the record gives it, with its source. This is what was found in the snapshot, not a claim of completeness.",
]


SNAPSHOT = "MATCH (s:Snapshot {source: 'justfixwow'}) RETURN s.snapshot_id AS snapshot_id, s.snapshot_date AS snapshot_date ORDER BY s.snapshot_date DESC LIMIT 1"


def snapshot(runner) -> dict:
    """The snapshot the graph was built from, stated in every answer, absence included (mission: answers state their limits)."""
    r = runner.run(SNAPSHOT).single()
    return {"snapshot_id": r["snapshot_id"], "snapshot_date": _plain(r["snapshot_date"])} if r else {}


def _plain(v):
    """Neo4j dates to ISO text, so results are plain JSON."""
    return v.iso_format() if hasattr(v, "iso_format") else v


def _clean(d: dict) -> dict:
    return {k: _plain(v) for k, v in d.items() if v is not None}


N1_RULE = ("N1: uppercase, punctuation deleted, whitespace collapsed; nothing fuzzy. So 'Acme L.L.C.' and 'ACME LLC' are the same name, "
           "while 'Acme LLC' and 'Acme II LLC', or 'KS Acme' and 'K S Acme', are different names.")
SAME_NAME_NOTE = ("Counts of records with the same normalized name. They include this party's own record, and dos_entities counts active DOS entities only. "
                  "A shared name is a lead, not a finding.")
MAIL_DROP_NOTE = "Addresses were checked against the project's mail-drop list (resolution/mail_drop_addresses.csv); a mail_drop of null means the address is not on it."


@cache
def mail_drops() -> dict[str, dict]:
    """{A2 key with zip: row} from resolution/mail_drop_addresses.csv. Every row links nothing on its own."""
    with open(ROOT / "resolution" / "mail_drop_addresses.csv", newline="") as f:
        return {f'{r["address_key"]} {r["zip5"]}': {"kind": r["kind"], "basis": r["basis"], "review_status": r["review_status"]}
                for r in csv.DictReader(f)}


def _mail_drop(key: str | None) -> dict | None:
    return mail_drops().get(key) if key else None


def _name_counts(runner, name_n1: str) -> dict:
    out = {}
    for label, key in (("HpdParty", "hpd_parties"), ("AcrisParty", "acris_parties"), ("DosEntity", "dos_entities")):
        out[key] = runner.run(f"MATCH (p:`{label}` {{name_n1: $n}}) RETURN count(p) AS c", n=name_n1).single()["c"]
    return out


# ---- Q3 -----------------------------------------------------------------------------------------------------

DEEDS = f"""
MATCH (l:Lot {{bbl: $bbl}})<-[:ON_LOT]-(d:Document) WHERE d.doc_type IS NOT NULL AND d.doc_type <> 'deed_correction'
RETURN d {{.document_id, .doc_type, .doc_type_raw, .doc_date, .doc_date_raw, .recorded, .amount, {PROV}}} AS d
ORDER BY d.recorded DESC, d.doc_date DESC, d.document_id
"""
PARTIES = f"""
MATCH (d:Document {{document_id: $id}})<-[:IN_DOCUMENT]-(r:AcrisRole)-[:HELD_BY]->(p:AcrisParty)
RETURN r.role_type AS role_type, r.source_role_code AS party_type,
       p {{.party_name, .name_n1, .address_line1, .address_line2, .city, .state, .zip, .address_key}} AS p
ORDER BY r.source_role_code, p.party_name
"""
OWNERS = f"""
MATCH (l:Lot {{bbl: $bbl}})<-[:ON_LOT]-(reg:Registration)<-[:IN_REGISTRATION]-(role:HpdRole {{role_type: 'registered_owner'}})-[:HELD_BY]->(p:HpdParty)
RETURN reg {{.registration_id, .last_registration_date, .registration_end_date, .owner_kind}} AS reg,
       role {{.source_record_id, .source_role_code, {PROV}}} AS role,
       p {{.organization_name, .person_name, .name_n1, .business_house, .business_street, .business_apartment, .business_zip, .business_address_key}} AS p
ORDER BY reg.registration_id, role.source_record_id
"""


def _name_agreement(grantee_n1: str | None, owner: dict) -> str:
    if not owner.get("organization_name"):
        return "not_comparable"   # the HPD owner is a person; a person's name is not compared with an entity's
    return "exact_normalized" if grantee_n1 and grantee_n1 == owner.get("name_n1") else "different"


def _address_agreement(grantee: dict, owner: dict) -> str:
    if not owner.get("organization_name"):
        return "not_comparable"
    a, b = grantee.get("address_key"), owner.get("business_address_key")
    return "absent" if not a or not b else "same" if a == b else "differs"


def _deed(runner, d: dict, owners: list[dict]) -> dict:
    parties = runner.run(PARTIES, id=d["document_id"]).data()
    grantors = [_clean(r["p"]) | {"party_type": r["party_type"]} for r in parties if r["role_type"] == "grantor"]
    grantees = []
    for r in parties:
        if r["role_type"] != "grantee":
            continue
        g, comparisons = r["p"], []
        for o in owners:
            comparisons.append({
                "registration_id": o["reg"]["registration_id"],
                "registration_dates": _clean({"last_registration_date": o["reg"].get("last_registration_date"),
                                              "registration_end_date": o["reg"].get("registration_end_date")}),
                "hpd_owner": o["p"].get("organization_name") or o["p"].get("person_name"),
                "hpd_owner_n1": o["p"].get("name_n1"),
                "hpd_contact_id": o["role"]["source_record_id"], "hpd_type": o["role"]["source_role_code"],
                "name_agreement": _name_agreement(g.get("name_n1"), o["p"]),
                "address_agreement": _address_agreement(g, o["p"]),
                **({"not_comparable_reason": "the HPD owner is a person (no organization name); a person's name is not compared with an entity's"}
                   if not o["p"].get("organization_name") else {}),
                "units": _clean({"acris_address_line2": g.get("address_line2"), "hpd_apartment": o["p"].get("business_apartment")}),
                "mail_drop": _mail_drop(g.get("address_key")) or _mail_drop(o["p"].get("business_address_key")),
                "source": o["role"]["source"], "snapshot_id": o["role"]["snapshot_id"]})
        grantees.append(_clean(g) | {"party_type": r["party_type"], "mail_drop": _mail_drop(g.get("address_key")),
                                     "records_with_same_normalized_name_including_this_one": _name_counts(runner, g.get("name_n1")) if g.get("name_n1") else None,
                                     "same_name_note": SAME_NAME_NOTE,
                                     "vs_hpd_owners": comparisons})
    return _clean(d) | {"grantors": grantors, "grantees": grantees}


def compare_deed_and_owner(runner, bbl: str) -> dict:
    """The latest deed or deeds on a lot with their grantees, each compared with the lot's HPD registered owners."""
    lot = runner.run("MATCH (l:Lot {bbl: $bbl}) RETURN l.bbl AS bbl", bbl=bbl).single()
    if lot is None:
        return {"status": "lot_absent", "bbl": bbl, "note": "The graph holds no such lot.", **snapshot(runner)}
    deeds = [r["d"] for r in runner.run(DEEDS, bbl=bbl)]
    owners = runner.run(OWNERS, bbl=bbl).data()
    base = {"bbl": bbl, **snapshot(runner), "mail_drop_list": MAIL_DROP_NOTE, "deeds_on_lot": len(deeds), "caveats": CAVEATS_Q3, "ordering": "most recent by recording date, then document date; ties are all reported"}
    if not deeds:
        return {**base, "status": "no_deed_in_graph", "hpd_registered_owners": len(owners),
                "note": "No deed-family document on this lot is in the graph. That is not 'no deed exists': documents on condo unit lots and other types are not loaded."}
    key = lambda d: (d["recorded"], d.get("doc_date"))
    latest = [d for d in deeds if key(d) == key(deeds[0])]
    valued = next((d for d in deeds if d.get("amount")), None)
    out = {**base, "status": "found",
           "hpd_registered_owners": len({o["reg"]["registration_id"] for o in owners}),
           "latest_deeds": [_deed(runner, d, owners) for d in latest]}
    if not owners:
        out["hpd_note"] = "no HPD registration with a registered owner on this lot, so no comparison"
    if valued is not None:
        out["last_deed_for_value"] = _deed(runner, valued, owners) | {"is_latest": valued in latest}
    return out


@tool
def compare_deed_grantee_with_hpd_owner(bbl: str) -> dict:
    """For one tax lot (10-digit BBL string, from find_lot_by_address), return the most recent deed or deeds recorded on it,
    their grantors and grantees, and the last deed for value, and compare each grantee with the lot's HPD registered owners.

    Name agreement and address agreement are separate fields. 'exact_normalized' means the names are equal after
    punctuation and case are removed; it is a lead, never proof the two are the same party. Everything carries its source and
    snapshot. A mail-drop address links nothing."""
    with read_session() as session:
        return compare_deed_and_owner(session, bbl)


# ---- Q24 ----------------------------------------------------------------------------------------------------

ACRIS = f"""
MATCH (p:AcrisParty {{name_n1: $n}})<-[:HELD_BY]-(r:AcrisRole)-[:IN_DOCUMENT]->(d:Document)
OPTIONAL MATCH (d)-[:ON_LOT]->(l:Lot)
WITH p, r, d, collect(DISTINCT l.bbl) AS bbls
RETURN d {{.document_id, .doc_type, .doc_type_raw, .doc_date, .doc_date_raw, .recorded, .amount, {PROV}}} AS d,
       r.role_type AS role_type, r.source_role_code AS party_type, p.party_name AS name, bbls
ORDER BY d.recorded DESC, d.document_id, r.source_role_code LIMIT $limit
"""
ACRIS_N = "MATCH (:AcrisParty {name_n1: $n})<-[:HELD_BY]-(r:AcrisRole) RETURN count(r) AS c"
HPD = f"""
MATCH (p:HpdParty {{name_n1: $n}})<-[:HELD_BY]-(role:HpdRole)-[:IN_REGISTRATION]->(reg:Registration)
OPTIONAL MATCH (reg)-[:ON_LOT]->(l:Lot) OPTIONAL MATCH (reg)-[:ON_BUILDING]->(b:Building)
WITH p, role, reg, collect(DISTINCT l.bbl) AS bbls, collect(DISTINCT b.bin) AS bins
RETURN reg.registration_id AS registration_id, role.source_record_id AS contact_id, role.source_role_code AS hpd_type,
       role.role_type AS role_type, role.title AS title, coalesce(p.organization_name, p.person_name) AS name, bbls, bins,
       role {{{PROV}}} AS prov
ORDER BY registration_id, contact_id LIMIT $limit
"""
HPD_N = "MATCH (:HpdParty {name_n1: $n})<-[:HELD_BY]-(r:HpdRole) RETURN count(r) AS c"
DOS = f"""
MATCH (e:DosEntity {{name_n1: $n}})
RETURN e {{.dos_id, .entity_name, .entity_type, .initial_filing_date, .county, .jurisdiction, .process_name, .process_address_line1,
          .process_city, .process_state, .process_zip, .registered_agent_name, {PROV}}} AS e ORDER BY e.dos_id
"""


def find_by_name(runner, name: str, limit: int = 50) -> dict:
    """Every ACRIS deed-family party row, HPD contact row and DOS entity whose normalized name equals this one."""
    n = n1(name)
    if not n:
        return {"status": "no_name_given"}
    acris = [{**_clean(r["d"]), "party_type": r["party_type"], "role_type": r["role_type"], "name_as_recorded": r["name"], "bbls": sorted(r["bbls"])}
             for r in runner.run(ACRIS, n=n, limit=limit)]
    hpd = [{"registration_id": r["registration_id"], "contact_id": r["contact_id"], "hpd_type": r["hpd_type"], "role_type": r["role_type"],
            "title": r["title"], "name_as_recorded": r["name"], "bbls": sorted(r["bbls"]), "bins": sorted(r["bins"]),
            "source": r["prov"]["source"], "snapshot_id": r["prov"]["snapshot_id"], "reliability": r["prov"]["reliability"]}
           for r in runner.run(HPD, n=n, limit=limit)]
    dos = [_clean(r["e"]) for r in runner.run(DOS, n=n)]
    totals = {"acris_party_rows": runner.run(ACRIS_N, n=n).single()["c"], "hpd_contact_rows": runner.run(HPD_N, n=n).single()["c"], "dos_entities": len(dos)}
    spellings = sorted({r["name_as_recorded"] for r in acris} | {r["name_as_recorded"] for r in hpd} | {e["entity_name"] for e in dos})
    base = {"searched_name": name, "normalized_name": n, "rule": N1_RULE,
            **snapshot(runner), "caveats": CAVEATS_Q24}
    if not (acris or hpd or dos):
        return {**base, "status": "no_record", "reason": "no deed-family party, HPD contact or active DOS entity has this normalized name",
                "variants_tried": [n]}
    return {**base, "status": "found", "totals": totals, "limit": limit, "truncated": totals["acris_party_rows"] > len(acris) or totals["hpd_contact_rows"] > len(hpd),
            "spellings_recorded": spellings, "dos_candidates": len(dos) if len(dos) > 1 else None,
            "acris_documents": acris, "hpd": hpd, "dos": dos}


@tool
def find_records_by_name(name: str) -> dict:
    """Start from a name, such as a company name from a letter or a lease. Returns the ACRIS deed-family documents it appears in
    (with its role as recorded and the lots), the HPD registrations and contact roles that carry it, and every active NY
    Department of State entity with that name. The name is matched after punctuation and case are removed (rule N1) and nothing
    fuzzy is tried. Several DOS entities with the same name are all returned. A person's name is returned only in the role the
    record gives it, with its source. A match is a lead, never a finding."""
    with read_session() as session:
        return find_by_name(session, name)
