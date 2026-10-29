"""Derive evals/expected/slice4.json and slice4.sql from the BOR release files and the justfixwow database (read-only), independent of the graph.

  uv run python -m evals.expected.derive_slice4 [release dir]

Q8, Q9, Q10, Q19, Q21 and Q26 (design note 0024) for the anchors C and D, the unlinked anchors, and groups found in the release itself (a network
that holds two portfolios, a portfolio that spans two networks, a Louvain community, a registered-LLC link set, a curated list, a masked address).
Group facts come from the release CSVs; lot facts (units, buildings, open violations, cases) come from the source tables."""
import csv
import json
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

from etl import source
from etl.config import ROOT
from etl.hpd import real_bin

OUT = ROOT / "evals" / "expected"
REL = Path(__import__("sys").argv[1]) if len(__import__("sys").argv) > 1 else ROOT.parent / "beneficial-ownership-resolution" / "release" / "v0.2.1"
ANCHOR_DOC = json.loads((OUT / "slice1.json").read_text())["anchors"]
OP, ON = "owner_portfolio", "operational_network"
# lots chosen from the release (not anchors), each for the evidence it shows
FOUND = {"H1": ("2037660051", "network ON-107620 holds two portfolios"), "H2": ("4100220010", "portfolio OP-5346 (deed-bridged) spans two networks"),
         "H3": ("1008890019", "Louvain community ON-2902"), "H4": ("3050747501", "registered-LLC link set (OP-25108)"),
         "H5": ("2034980021", "curated owner list (OP-5292)"), "M": ("1000167501", "masked aggregator address"), "V": ("1000150022", "first-name veto")}
PAIRS = [("C", "C2", "3008070024", "3067970008"), ("A", "B", "3008260002", "3008260005"), ("D", "D2", "3008210012", "3031990043"),
         ("H2", "H2b", "4100220010", "4100220013"), ("H3", "H3b", "1008890019", "3001830030"), ("H4", "H4b", "3050747501", "3050747502"), ("H5", "H5b", "2034980021", "2034980026")]

SQL = {
    "lot facts": "select bbl, address, bldgclass, unitsres from pluto_latest where bbl = any(%(bbls)s) order by bbl",
    "registrations (buildings by BIN)": "select bbl, registrationid, bin from hpd_registrations where bbl = any(%(bbls)s) order by bbl, registrationid",
    "open violations by class": "select bbl, class, count(*) as n from hpd_violations where bbl = any(%(bbls)s) and violationstatus = 'Open' group by bbl, class order by bbl, class",
    "all violations rows": "select bbl, count(*) as n from hpd_violations where bbl = any(%(bbls)s) group by bbl",
    "litigation cases": "select bbl, count(*) as n from hpd_litigations where bbl = any(%(bbls)s) group by bbl",
    "complaint problem rows": "select bbl, count(*) as n from hpd_complaints_and_problems where bbl = any(%(bbls)s) group by bbl",
}


def rows(name):
    with open(REL / f"{name}.csv", newline="") as f:
        return list(csv.DictReader(f))


def main() -> None:
    manifest = json.loads((REL / "manifest.json").read_text())
    groups = {(r["layer"], r["group_id"]): r for r in rows("groups")}
    gb = rows("group_bbls")
    lots_of, group_of = defaultdict(list), {}
    for r in gb:
        lots_of[(r["layer"], r["group_id"])].append(r)
        group_of[(r["layer"], r["bbl"])] = r["group_id"]
    members = defaultdict(list)
    for r in rows("group_members"):
        members[(r["layer"], r["group_id"])].append(r["node_id"])
    names = {r["node_id"]: r["name"] for r in rows("node_names")}
    witness = defaultdict(Counter)
    for r in rows("group_witness"):
        witness[(r["layer"], r["group_id"])][r["stage"]] += 1
    nedges = rows("network_edges")
    node_group = {n: g for (lay, g), ns in members.items() if lay == ON for n in ns}
    status = defaultdict(dict)
    for r in rows("bbl_status"):
        if r["status"] != "in_group":
            status[r["bbl"]][r["layer"]] = r
    masked_nodes = {r["node_id"]: r["address_id"] for r in rows("masked_address_nodes")}
    node_of_bbl = {}
    for r in rows("node_observations"):
        node_of_bbl[r["bbl"]] = r["node_id"]
    addr = {r["address_id"]: r for r in rows("masked_addresses")}

    anchors = {l: a["bbl"] for l, a in ANCHOR_DOC.items()}
    cases = {**anchors, **{k: v[0] for k, v in FOUND.items()}}
    need = set()
    for lay in (OP, ON):
        for b in cases.values():
            g = group_of.get((lay, b))
            if g:
                need |= {r["bbl"] for r in lots_of[(lay, g)]}
    need |= {b for p in PAIRS for b in p[2:]} | set(cases.values())
    with source.connect() as conn, conn.cursor() as cur:
        params = {"bbls": sorted(need)}
        cur.execute(SQL["lot facts"], params)
        pluto = {r["bbl"]: r for r in cur.fetchall()}
        cur.execute(SQL["registrations (buildings by BIN)"], params)
        regs = defaultdict(set)
        conflicted = source.conflicted_bins(conn)
        regrows = cur.fetchall()
        for r in regrows:
            b = real_bin(r["bin"])
            if b and b not in conflicted:
                regs[r["bbl"]].add(b)
        reg_count = Counter(r["bbl"] for r in regrows)
        cur.execute(SQL["open violations by class"], params)
        openv = defaultdict(lambda: dict.fromkeys("ABCI", 0))
        for r in cur.fetchall():
            if r["class"] in "ABCI":
                openv[r["bbl"]][r["class"]] += r["n"]
        counts = {}
        for key in ("all violations rows", "litigation cases", "complaint problem rows"):
            cur.execute(SQL[key], params)
            counts[key] = {r["bbl"]: r["n"] for r in cur.fetchall()}

    def facts(lay, bbl):
        g = group_of.get((lay, bbl))
        if not g:
            s = status.get(bbl, {}).get(lay)
            if s:
                out = {"in_group": False, "reason_code": s["reason_code"], "top_level_reason": s["top_level_reason"]}
                n = node_of_bbl.get(bbl)
                if lay == ON and n in masked_nodes:
                    a = addr[masked_nodes[n]]
                    out["masked_address"] = {"address": a["address"], "shared_by": int(a["degree"]), "threshold": int(a["threshold"])}
                return out
            return {"in_group": False, "reason_code": None, "note": "no row"}
        grp, ls = groups[(lay, g)], lots_of[(lay, g)]
        rental = sorted(r["bbl"] for r in ls if r["rental"] == "True")
        units = [int(pluto[b]["unitsres"]) for b in rental if pluto.get(b) and pluto[b]["unitsres"] is not None]
        ns = members[(lay, g)]
        out = {"in_group": True, "group_id": g, "composition": grp["composition"] or None, "split": grp["split"] or None, "lot_count": int(grp["lot_count"]),
               "total_lot_count": int(grp["total_lot_count"]), "lots": rental, "lots_outside_rental_footprint": sorted(r["bbl"] for r in ls if r["rental"] != "True"),
               "buildings": sum(len(regs[b]) for b in rental), "residential_units": sum(units), "lots_missing_a_unit_count": len(rental) - len(units),
               "landlord_records": len(ns), "anchor_node_id": grp["anchor_node_id"], "anchor_name": names.get(grp["anchor_node_id"]),
               "path_steps_by_stage": dict(sorted(witness[(lay, g)].items()))}
        if lay == ON:
            within = [e for e in nedges if node_group.get(e["node_a"]) == g and node_group.get(e["node_b"]) == g]
            cross = [e for e in nedges if (node_group.get(e["node_a"]) == g) != (node_group.get(e["node_b"]) == g) and (node_group.get(e["node_a"]) == g or node_group.get(e["node_b"]) == g)]
            out["accepted_edges_within"] = len(within)
            out["edges_by_kind"] = {"address": sum(1 for e in within if float(e["address_weight"]) > 0), "name": sum(1 for e in within if float(e["name_weight"]) > 0),
                                    "identity": sum(1 for e in within if float(e["identity_weight"]) > 0)}
            out["edges_to_other_networks"] = len(cross)
        return out

    def other_lots(lay, g):
        return {r["bbl"] for r in lots_of[(lay, g)]} if g else set()

    q9 = {k: facts(OP, b) for k, b in cases.items()}
    q8 = {k: facts(ON, b) for k, b in cases.items()}
    q10 = {}
    for k in ("D", "H1", "H2", "C"):
        b = cases[k]
        gp, gn = group_of.get((OP, b)), group_of.get((ON, b))
        P, N = other_lots(OP, gp), other_lots(ON, gn)
        diff = {}
        for lay, only in ((OP, sorted(P - N)), (ON, sorted(N - P))):
            other = ON if lay == OP else OP
            explained = []
            for x in only:
                g2 = group_of.get((other, x))
                explained.append({"bbl": x, "other_layer": ({"group_id": g2} if g2 else {"reason_code": status.get(x, {}).get(other, {}).get("reason_code") or "no_registration"})})
            diff[f"only_in_{lay}"] = {"count": len(only), "lots": explained}
        port_of_net = Counter(group_of.get((OP, x)) or "(none)" for x in N)
        net_of_port = Counter(group_of.get((ON, x)) or "(none)" for x in P)
        q10[k] = {"bbl": b, "owner_portfolio": gp, "operational_network": gn, "lots_in_both": len(P & N), "differences": diff,
                  "portfolios_in_the_network": dict(sorted(port_of_net.items())), "networks_in_the_portfolio": dict(sorted(net_of_port.items()))}
    q19 = []
    for a, b, la, lb in PAIRS:
        entry = {"a": a, "b": b, "bbl_a": la, "bbl_b": lb}
        for lay in (OP, ON):
            ga, gb2 = group_of.get((lay, la)), group_of.get((lay, lb))
            if ga and ga == gb2:
                v = "same_group"
            elif ga and gb2:
                v = "different_groups"
            elif ga or gb2:
                v = "only_one_in_a_group"
            else:
                v = "neither_in_a_group"
            entry[lay] = {"verdict": v, "groups": [ga, gb2], "absences": {x: facts(lay, x) for x in (la, lb) if not group_of.get((lay, x))}}
        q19.append(entry)
    q21 = {}
    for k in ("C", "D", "H2"):
        b = cases[k]
        res = {}
        for lay in (OP, ON):
            g = group_of.get((lay, b))
            if not g:
                continue
            lots = sorted(r["bbl"] for r in lots_of[(lay, g)] if r["rental"] == "True")
            per = []
            for x in lots:
                o = openv.get(x, dict.fromkeys("ABCI", 0))
                u = pluto[x]["unitsres"] if x in pluto else None
                m = o["A"] + o["B"] + o["C"]
                per.append({"bbl": x, "open_by_class": dict(o), "abc": m, "units": u, "per_unit": round(m / u, 3) if u else None})
            total = sum(p["abc"] for p in per)
            ranked = sorted((p for p in per if p["per_unit"] is not None), key=lambda p: (-p["per_unit"], -p["abc"], p["bbl"]))
            top3 = sorted(per, key=lambda p: (-p["abc"], p["bbl"]))[:3]
            res[lay] = {"group_id": g, "lots": len(lots), "total_open_abc": total, "by_class": {c: sum(p["open_by_class"][c] for p in per) for c in "ABCI"},
                        "lots_with_any_open": sum(1 for p in per if p["abc"]), "top_lots_by_open_per_unit": [p["bbl"] for p in ranked[:5]],
                        "top3_by_count": [p["bbl"] for p in top3], "share_held_by_top_3": round(sum(p["abc"] for p in top3) / total, 3) if total else None,
                        "residential_units": sum(p["units"] or 0 for p in per), "lots_missing_a_unit_count": sum(1 for p in per if not p["units"]), "per_lot": per}
        q21[k] = {"bbl": b, **res}
    q26 = {}
    for k in ("D", "F", "M", "V", "A", "C"):
        b = cases[k]
        q26[k] = {"bbl": b, "hpd_registrations": reg_count.get(b, 0), "violation_rows": counts["all violations rows"].get(b, 0), "litigation_cases": counts["litigation cases"].get(b, 0),
                  "complaint_problem_rows": counts["complaint problem rows"].get(b, 0), OP: facts(OP, b), ON: facts(ON, b)}
    doc = {"snapshot_id": manifest["snapshot_id"], "run_id": manifest["run_id"], "release": REL.name, "derived": date.today().isoformat(),
           "source": "the BOR release files and the justfixwow PostgreSQL (read-only); queries in slice4.sql",
           "how_to_read": ("Expected answers for the Slice 4 questions (Q8, Q9, Q10, Q19, Q21, Q26). Group facts are the release's own; lot facts are from the source tables. "
                           "Units are PLUTO residential units of lots in the rental footprint; buildings are distinct real, non-conflicted BINs on the lots' HPD registrations. "
                           "The cases other than the anchors were chosen from the release for the evidence they show (cases)."),
           "anchors": {l: {"bbl": a["bbl"]} for l, a in ANCHOR_DOC.items()}, "cases": {k: {"bbl": v[0], "why": v[1]} for k, v in FOUND.items()},
           "questions": {"Q9": q9, "Q8": q8, "Q10": q10, "Q19": q19, "Q21": q21, "Q26": q26}}
    (OUT / "slice4.json").write_text(json.dumps(doc, indent=1) + "\n")
    (OUT / "slice4.sql").write_text("-- Queries behind evals/expected/slice4.json, run read-only on the justfixwow database by derive_slice4.py.\n"
                                    "-- %(bbls)s = the lots of the groups of the cases. Group facts come from the BOR release CSVs, not from SQL.\n\n"
                                    + "\n\n".join(f"-- {n}\n{q};" for n, q in SQL.items()) + "\n")
    print("written; C:", q9["C"]["lot_count"], q8["C"]["lot_count"], "D:", q9["D"]["lot_count"], q8["D"]["lot_count"])


if __name__ == "__main__":
    main()
