"""Slice 1 build: PLUTO lots, then HPD registrations, buildings, parties and roles, then ACRIS deed documents, one snapshot.

Loads from iterables of source rows, so a test can pass fixtures and the CLI can stream the justfixwow database.
PLUTO goes first, so a lot PLUTO holds keeps source `pluto` when HPD meets it again.
"""
from collections import defaultdict
from datetime import date
from itertools import islice

from etl.acris import document_node, party_nodes
from etl.dos import dos_entity_node
from etl.hpd import contact_nodes, pick_contacts, registration_nodes
from etl.load import apply_schema, load_edges, load_nodes, register_snapshot
from etl.pluto import lot_node
from etl.schema import Schema

LOT_KEEP = ("reliability", "source_category", "source", "snapshot_id", "source_record_id")  # set only on create


def load_pluto(tx, schema: Schema, rows, snapshot_id: str) -> int:
    return load_nodes(tx, schema, "Lot", (lot_node(r, snapshot_id) for r in rows))


def load_hpd(tx, schema: Schema, registrations: list[dict], contacts: list[dict], snapshot_id: str,
             conflicted_bins: frozenset = frozenset()) -> dict[str, int]:
    """Load a chunk of registrations with their contacts. Contacts of other registrations are ignored."""
    by_reg = defaultdict(list)
    for c in contacts:
        by_reg[str(c["registrationid"])].append(c)
    lots, buildings, regs, parties, roles = {}, {}, [], {}, []
    on_lot_b, on_lot_r, on_bld_r, on_lot_role, on_bld_role, in_reg, held = [], [], [], [], [], [], []
    for row in sorted(registrations, key=lambda r: str(r.get("lastregistrationdate") or "")):  # latest registration last
        rid = str(row["registrationid"])
        cs = pick_contacts(by_reg.get(rid, []))
        desc = next((c.get("contactdescription") for c in cs if c.get("contactdescription")), None)  # registration-level value
        n = registration_nodes(row, desc, snapshot_id, conflicted_bins)
        lots[n["lot"]["bbl"]] = n["lot"]
        regs.append(n["registration"])
        on_lot_r.append((rid, n["lot"]["bbl"]))
        if n["building"]:
            buildings[n["building"]["bin"]] = n["building"]
            on_lot_b.append((n["building"]["bin"], n["lot"]["bbl"]))
            on_bld_r.append((rid, n["building"]["bin"]))
        for c in cs:
            cn = contact_nodes(c, snapshot_id)
            parties[cn["party"]["party_id"]] = cn["party"]
            roles.append(cn["role"])
            held.append((cn["role"]["role_id"], cn["party"]["party_id"]))
            in_reg.append((cn["role"]["role_id"], rid))
            (on_bld_role if n["building"] else on_lot_role).append((cn["role"]["role_id"], n["building"]["bin"] if n["building"] else n["lot"]["bbl"]))
    counts = {
        "Lot": load_nodes(tx, schema, "Lot", lots.values(), on_create_only=LOT_KEEP),
        "Building": load_nodes(tx, schema, "Building", buildings.values()),
        "Registration": load_nodes(tx, schema, "Registration", regs),
        "Party": load_nodes(tx, schema, "Party", parties.values(), also=("HpdParty",)),
        "Role": load_nodes(tx, schema, "Role", roles, also=("HpdRole",)),
    }
    counts["ON_LOT"] = (load_edges(tx, schema, "ON_LOT", "Building", "Lot", on_lot_b) + load_edges(tx, schema, "ON_LOT", "Registration", "Lot", on_lot_r)
                        + load_edges(tx, schema, "ON_LOT", "Role", "Lot", on_lot_role))
    counts["ON_BUILDING"] = load_edges(tx, schema, "ON_BUILDING", "Registration", "Building", on_bld_r) + load_edges(tx, schema, "ON_BUILDING", "Role", "Building", on_bld_role)
    counts["IN_REGISTRATION"] = load_edges(tx, schema, "IN_REGISTRATION", "Role", "Registration", in_reg)
    counts["HELD_BY"] = load_edges(tx, schema, "HELD_BY", "Role", "Party", held)
    return counts


def _chunks(rows, size: int):
    """Chunks of about `size` rows that never split one registration: the rows of a registration id that spans
    several buildings stay together, so each gets the registration's contacts (note 0014)."""
    chunk, last = [], None
    for r in rows:
        rid = str(r["registrationid"])
        if len(chunk) >= size and rid != last:
            yield chunk
            chunk = []
        chunk.append(r)
        last = rid
    if chunk:
        yield chunk


def build(session, schema: Schema, snapshot_id: str, snapshot_date: date, pluto_rows, registrations, contacts, chunk: int = 2000,
          conflicted_bins: frozenset = frozenset()) -> dict:
    """Whole build in write transactions of `chunk` registrations. `registrations` and `contacts` are iterables
    ordered by registration id, so each chunk's contacts are the next ones in the stream."""
    apply_schema(session, schema)
    session.execute_write(register_snapshot, snapshot_id, "justfixwow", snapshot_date)
    totals: dict[str, int] = defaultdict(int)
    it = iter(pluto_rows)
    while batch := list(islice(it, 5000)):
        totals["Lot (PLUTO)"] += session.execute_write(load_pluto, schema, batch, snapshot_id)
    cons = iter(contacts)
    pending = None
    for batch in _chunks(registrations, chunk):
        last = max(int(r["registrationid"]) for r in batch)
        mine = []
        while True:
            c = pending or next(cons, None)
            pending = None
            if c is None:
                break
            if int(c["registrationid"]) > last:
                pending = c
                break
            mine.append(c)
        for k, v in session.execute_write(load_hpd, schema, batch, mine, snapshot_id, conflicted_bins).items():
            totals[k] += v
    return dict(totals)


def load_acris(tx, schema: Schema, documents: list[dict], parties: list[dict], legals: list[dict], lots: frozenset,
               snapshot_id: str, snapshot_date: date) -> dict[str, int]:
    """Load a chunk of ACRIS documents with their parties and legals. A document is loaded only if one of its legals
    is a lot in `lots`; the edge is made for each such lot."""
    on_lots: dict[str, set] = defaultdict(set)
    for lg in legals:
        bbl = (lg.get("bbl") or "").strip()
        if bbl in lots:
            on_lots[str(lg["documentid"]).strip()].add(bbl)
    docs = {}
    for d in documents:
        n = document_node(d, snapshot_id, snapshot_date)
        if n["document_id"] in on_lots:
            docs[n["document_id"]] = n
    pnodes, rnodes, held, in_doc = {}, {}, [], []
    for p in parties:
        did = str(p["documentid"]).strip()
        if did not in docs:
            continue
        pn = party_nodes(p, docs[did].get("doc_type"), snapshot_id)
        pnodes[pn["party"]["party_id"]] = pn["party"]
        rnodes[pn["role"]["role_id"]] = pn["role"]
        held.append((pn["role"]["role_id"], pn["party"]["party_id"]))
        in_doc.append((pn["role"]["role_id"], did))
    counts = {
        "Document": load_nodes(tx, schema, "Document", docs.values()),
        "AcrisParty": load_nodes(tx, schema, "Party", pnodes.values(), also=("AcrisParty",)),
        "AcrisRole": load_nodes(tx, schema, "Role", rnodes.values(), also=("AcrisRole",)),
    }
    counts["ON_LOT (Document)"] = load_edges(tx, schema, "ON_LOT", "Document", "Lot", [(d, b) for d, bs in on_lots.items() if d in docs for b in sorted(bs)])
    counts["IN_DOCUMENT"] = load_edges(tx, schema, "IN_DOCUMENT", "Role", "Document", in_doc)
    counts["HELD_BY (ACRIS)"] = load_edges(tx, schema, "HELD_BY", "Role", "Party", held)
    return counts


def build_acris(session, schema: Schema, snapshot_id: str, snapshot_date: date, documents, fetch_children, lots: frozenset,
                chunk: int = 2000) -> dict:
    """ACRIS deed documents in write transactions of `chunk` documents. `fetch_children(ids)` returns the parties
    and legals of those documents (a database query in the CLI, fixtures in a test)."""
    apply_schema(session, schema)
    session.execute_write(register_snapshot, snapshot_id, "justfixwow", snapshot_date)
    totals: dict[str, int] = defaultdict(int)
    it = iter(documents)
    while batch := list(islice(it, chunk)):
        parties, legals = fetch_children([str(d["documentid"]).strip() for d in batch])
        for k, v in session.execute_write(load_acris, schema, batch, parties, legals, lots, snapshot_id, snapshot_date).items():
            totals[k] += v
    return dict(totals)


def build_dos(session, schema: Schema, snapshot_id: str, snapshot_date: date, rows, chunk: int = 5000) -> dict:
    """DOS active entities in write transactions of `chunk` rows. Every row is loaded: a name search can start
    from any entity, and the dataset is statewide (note 0016)."""
    apply_schema(session, schema)
    session.execute_write(register_snapshot, snapshot_id, "justfixwow", snapshot_date)
    n = 0
    it = iter(rows)
    while batch := list(islice(it, chunk)):
        n += session.execute_write(lambda tx: load_nodes(tx, schema, "Party", (dos_entity_node(r, snapshot_id) for r in batch), also=("DosEntity",)))
    return {"DosEntity": n}
