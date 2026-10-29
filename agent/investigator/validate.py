"""Check a finished dossier against the end-to-end acceptance requirement (design note 0030, I6). Deterministic: no model.

Each check returns (name, ok, detail). The seven parts of the requirement, plus the components Q20 requires (the identification, owner, deed, DOS, layer and
report steps were attempted). A dossier passes when every check does; the model judge reads the claims against the results separately."""
import json
import re

from agent.investigator.ledger import LABEL_ORDER, NEGATION, OWNERSHIP, LedgerError, compute_stop
from etl.vocab import bor_term

COMPONENTS = {   # a component of Q20 and the tools that count as having tried it (any one)
    "Q1 identify the property": {"find_lot_by_address"},
    "Q2 and Q4 HPD owner and contacts": {"get_hpd_registrations", "get_hpd_contacts"},
    "Q3 deed against owner": {"get_deed_history", "compare_deed_grantee_with_hpd_owner", "classify_deeds"},
    "Q5 DOS record": {"get_dos_record"},
    "Q9 and Q10 ownership layers": {"get_owner_portfolio", "get_operational_network", "compare_ownership_layers"},
    "Q16 reports": {"search_reports"},
}
FOREIGN = re.compile(r'"jurisdiction":\s*"(?!New York")([A-Za-z ]+)"')


def check(d: dict, bbl_given: bool = False, replay_diffs: list | None = None) -> list[tuple[str, bool, str]]:
    out = []
    add = lambda name, ok, detail="": out.append((name, bool(ok), detail))
    log = {r["result_id"]: r for r in d["retrieval_log"]}
    claims, leads, stop = d["claims"], d["leads"], (d.get("finished") or {}).get("stop_reason")

    # 1. lead rule
    bad = []
    for l in leads:
        r = log.get(l["found_in"])
        if r is None or re.sub(r"\s+", " ", l["value"]).strip().lower() not in re.sub(r"\s+", " ", r["text"]).lower():
            bad.append(f"{l['lead_id']} not in its source")
        if l["kind"] == "person_name" and l["disposition"] != "set_aside":
            bad.append(f"{l['lead_id']} follows a person")
        if l["disposition"] in ("resolved", "unresolved") and l.get("reason") in ("mail_drop_address", "masked_address"):
            bad.append(f"{l['lead_id']} follows a masked address")
    add("1 lead rule", not bad and sum(1 for l in leads if l["disposition"] != "set_aside") <= d["budget"]["leads_allowed"], "; ".join(bad))

    # 2. claim to source
    bad = []
    for c in claims:
        if not c["sources"]:
            bad.append(f"{c['claim_id']} has no source")
        for s in c["sources"]:
            if s["result_id"] not in log or not s.get("retrieved_at") or not s.get("source_category"):
                bad.append(f"{c['claim_id']} cites {s['result_id']} without time or category")
        if c["label"] != "recorded_assertion" and OWNERSHIP.search(c["statement"]) and not NEGATION.search(c["statement"]):
            bad.append(f"{c['claim_id']} states ownership on a {c['label']}")
        if c["label"] == "reported_claim" and not c.get("quote"):
            bad.append(f"{c['claim_id']} is reported without a quote")
        if c.get("quote") and not any(re.sub(r"\s+", " ", c["quote"]).lower() in re.sub(r"\s+", " ", log[s["result_id"]]["text"]).lower() for s in c["sources"] if s["result_id"] in log):
            bad.append(f"{c['claim_id']} quote is not in its sources")
    add("2 claim to source", claims and not bad, "; ".join(bad) or ("no claims" if not claims else ""))

    # 3. labels
    bad = []
    for c in claims:
        weakest = max((log[s["result_id"]]["label"] for s in c["sources"] if s["result_id"] in log), key=LABEL_ORDER.get, default=None)
        if c["label"] != weakest:
            bad.append(f"{c['claim_id']} is {c['label']}, its weakest source is {weakest}")
        if (c["label"] == "recorded_assertion") != (c.get("review_status") is None):
            bad.append(f"{c['claim_id']} review status {c.get('review_status')} for {c['label']}")
    add("3 labels", not bad, "; ".join(bad))

    # 4. unresolved leads each have a reason
    bad = [l["lead_id"] for l in leads if l["disposition"] in ("unresolved", "set_aside") and not l.get("reason")]
    bad += [l["lead_id"] for l in leads if l["disposition"] == "queued"]
    add("4 unresolved leads have reasons", not bad, f"without a reason or still open: {bad}" if bad else "")

    # 5. exactly one stop reason, supported by the leads and the budget
    try:
        expected = compute_stop(leads, d["budget"]["tool_calls_used"] >= d["budget"]["tool_calls_allowed"] or d["budget"]["seconds_used"] >= d["budget"]["seconds_allowed"])
    except LedgerError as e:
        expected = f"unsupported ({e})"
    try:
        bor_term("stop-reason", stop or "")
        known = True
    except ValueError:
        known = False
    add("5 stop reason", known and stop == expected, f"stop {stop!r}, ledger supports {expected!r}")

    # 6. other jurisdictions
    foreign = sorted({m.group(1).strip() for r in log.values() if r["tool"] == "get_dos_record" for m in FOREIGN.finditer(r["text"])})
    looked = any(r["tool"] == "lookup_registry" for r in log.values()) or any(l.get("reason") in ("needs_payment", "inaccessible") for l in leads)
    add("6 other jurisdictions", not foreign or looked, f"DOS shows {foreign}; registry step {'taken' if looked else 'missing'}")

    # 7. reproducibility
    add("7 reproducible", d["run"].get("snapshot_id") and d["run"].get("snapshot_date") and d["retrieval_log"] and (replay_diffs == [] if replay_diffs is not None else True),
        "no replay was run" if replay_diffs is None else f"{len(replay_diffs)} differences")

    # components
    tools = {r["tool"] for r in log.values()}
    for comp, need in COMPONENTS.items():
        if comp.startswith("Q1 ") and bbl_given:
            continue
        add(f"component {comp}", tools & need, f"none of {sorted(need)} was called" if not tools & need else "")
    return out


def passed(results) -> bool:
    return all(ok for _, ok, _ in results)
