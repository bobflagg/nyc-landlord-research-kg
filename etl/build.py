"""Slice 1 build: PLUTO lots, then HPD registrations, buildings, parties and roles, one snapshot.

Loads from iterables of source rows, so a test can pass fixtures and the CLI can stream the justfixwow database.
PLUTO goes first, so a lot PLUTO holds keeps source `pluto` when HPD meets it again.
"""
from collections import defaultdict
from datetime import date
from itertools import islice

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
    regs, cons = iter(registrations), iter(contacts)
    pending = None
    while batch := list(islice(regs, chunk)):
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
