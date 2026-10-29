"""Q21: open HPD violations across the lots of a group (design note 0024). Read-only, parameterized.

For one layer, which lots hold the most open violations per residential unit and how concentrated they are, and how the answer changes with the other
layer. Each class is reported apart (A, B, C, I) and Class I is never added to them; no word describes a class as "hazardous". A violation is what an
inspector cited, not a finding by a court; the table holds about a fifth of all HPD violations; a group is a lead, not legal ownership."""
from langchain.tools import tool

from agent.db import read_session
from agent.tools.conditions import CAVEATS_Q15, VIOLATIONS_AS_OF
from agent.tools.layers import CAVEATS, LAYERS, MEMBERSHIP, OTHER, _group_summary, active_run
from agent.tools.records import _clean, _plain, snapshot

CLASSES = ("A", "B", "C", "I")
MEASURES = {"abc": "open violations of Class A, B and C together", "A": "open Class A violations", "B": "open Class B violations", "C": "open Class C violations", "I": "open Class I violations"}
OPEN_BY_LOT = """
MATCH (g:BorGroup {assertion_key: $key})<-[m:MEMBER_OF]-(l:Lot)
OPTIONAL MATCH (l)<-[:ON_LOT]-(v:Violation {status_group: 'open'})
WITH l, m, v.violation_class AS cls, count(v) AS n
WITH l, m, collect({cls: cls, n: n}) AS by_class
RETURN l.bbl AS bbl, l.address_text AS address, l.units_residential AS units, m.rental AS rental, by_class
ORDER BY bbl
"""
CAVEATS_Q21 = [
    "Each class is reported apart. Open violations of Class A, B and C are summed only for the combined ranking; Class I is never added to them. A violation is what an inspector cited, not a finding by a court.",
    "The violations table holds about a fifth of all HPD violations: open ones are present, closed history is partial. A lot with none here is not shown to have none.",
    "The rate divides open violations by PLUTO's residential units for the lot; a lot with no unit count has no rate and is listed apart. Co-op and condo lots outside the rental footprint are left out.",
    "The ranking depends on the layer: a different group of lots gives a different list. Neither layer is the true list of a landlord's buildings, and a concentration figure describes the lots in the group, not the group's owner.",
]


def _counts(by_class: list[dict]) -> dict[str, int]:
    out = dict.fromkeys(CLASSES, 0)
    for c in by_class:
        if c["cls"] in out:
            out[c["cls"]] += c["n"]
    return out


def _measure(counts: dict[str, int], measure: str) -> int:
    return counts["A"] + counts["B"] + counts["C"] if measure == "abc" else counts[measure]


def _group_rows(runner, key: str, measure: str) -> list[dict]:
    rows = []
    for r in runner.run(OPEN_BY_LOT, key=key).data():
        if not r["rental"]:
            continue
        counts = _counts(r["by_class"])
        value = _measure(counts, measure)
        rows.append({"bbl": r["bbl"], "address": r["address"], "residential_units": r["units"], "open_by_class": counts, "measure": value,
                     "per_unit": round(value / r["units"], 3) if r["units"] else None})
    return rows


def _concentration(rows: list[dict], top: int = 3) -> dict:
    total = sum(r["measure"] for r in rows)
    ranked = sorted(rows, key=lambda r: -r["measure"])[:top]
    held = sum(r["measure"] for r in ranked)
    return {"total_open": total, "lots": len(rows), "lots_with_any_open": sum(1 for r in rows if r["measure"]), f"top_{top}_lots": [r["bbl"] for r in ranked],
            f"share_held_by_top_{top}": round(held / total, 3) if total else None}


def _summary(rows: list[dict], measure: str) -> dict:
    units = [r["residential_units"] for r in rows if r["residential_units"]]
    total = sum(r["measure"] for r in rows if r["residential_units"])
    return {**_concentration(rows), "residential_units": sum(units), "lots_missing_a_unit_count": len(rows) - len(units),
            "open_per_unit_over_lots_with_units": round(total / sum(units), 3) if units else None, "by_class": {c: sum(r["open_by_class"][c] for r in rows) for c in CLASSES}}


def group_violations(runner, bbl: str, layer: str, measure: str = "abc", run_id: str | None = None, top: int = 15) -> dict:
    base = {"bbl": bbl, "layer": LAYERS[layer], **snapshot(runner), "caveats": CAVEATS_Q21 + CAVEATS_Q15[:1] + CAVEATS[:1]}
    if measure not in MEASURES:
        return {**base, "status": "bad_measure", "allowed": MEASURES}
    run = active_run(runner, run_id)
    if run is None:
        return {**base, "status": "no_run_loaded"}
    base |= {"bor_run": run, "ranked_by": MEASURES[measure]}
    meta = runner.run(VIOLATIONS_AS_OF).single()
    base["violation_data_as_of"] = _plain(meta["d"]) if meta and meta["d"] is not None else None
    m = runner.run(MEMBERSHIP, bbl=bbl, run=run["run_id"], layer=layer).single()
    if m is None:
        return {**base, "status": "not_in_group", "note": "This lot is in no " + LAYERS[layer] + " in this run, so there is no group to rank; get the group's absence reason with explain_what_is_missing."}
    rows = _group_rows(runner, m["g"]["assertion_key"], measure)
    with_units = sorted((r for r in rows if r["per_unit"] is not None), key=lambda r: (-r["per_unit"], -r["measure"], r["bbl"]))
    without = sorted((r for r in rows if r["per_unit"] is None), key=lambda r: (-r["measure"], r["bbl"]))
    out = {**base, "status": "found", "group": _group_summary(m["g"], layer), "this_lot": next((r for r in rows if r["bbl"] == bbl), None),
           "summary": _summary(rows, measure), "ranked_by_open_per_residential_unit": with_units[:top], "ranked_shown": min(top, len(with_units)),
           "lots_without_a_unit_count": without[:top], "lots_ranked": len(with_units)}
    other = OTHER[layer]
    om = runner.run(MEMBERSHIP, bbl=bbl, run=run["run_id"], layer=other).single()
    if om is None:
        out["other_layer"] = {"layer": LAYERS[other], "status": "this lot is in no " + LAYERS[other]}
    else:
        orows = _group_rows(runner, om["g"]["assertion_key"], measure)
        mine, theirs = {r["bbl"] for r in rows}, {r["bbl"] for r in orows}
        out["other_layer"] = {"layer": LAYERS[other], "group": _group_summary(om["g"], other), "summary": _summary(orows, measure), "lots_in_both": len(mine & theirs),
                              "top_lots_in_other_layer": [r["bbl"] for r in sorted((r for r in orows if r["per_unit"] is not None), key=lambda r: (-r["per_unit"], -r["measure"], r["bbl"]))[:3]],
                              "how_the_answer_changes": ("The same measure over the other layer's lots; the lots differ, so the totals, the rate and the concentration can all change.")}
    return out


@tool
def rank_violations_in_group(bbl: str, layer: str = "owner_portfolio", rank_by: str = "abc") -> dict:
    """Rank the lots of the group containing a tax lot (BBL, a 10-digit string) by open HPD violations per residential unit, and report how concentrated they
    are, for one layer: layer is "owner_portfolio" or "operational_network". rank_by is "abc" (open Class A, B and C together, the default), or one class
    alone: "A", "B", "C" or "I". Each class is reported apart with its counts, Class I is never added to the others, and lots without a unit count are listed
    apart. It gives the share of the open violations held by the three lots with the most, and the same figures for the other layer. A violation is what an
    inspector cited, the violation table is partial, and a group is a lead and not legal ownership."""
    if layer not in LAYERS:
        return {"status": "bad_layer", "allowed": list(LAYERS)}
    with read_session() as session:
        return group_violations(session, bbl, layer, rank_by)
