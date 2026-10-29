"""Q6: is a business address an aggregator or mail drop? (design note 0026). Read-only, parameterized.

One answer per method, each with its reasons: the project's mail-drop list, BOR's masking of aggregator addresses, and the number of parties the graph holds at the address.
Masking and the list are decisions of a method, named here with the run or snapshot; the list is unreviewed. An address that no method flags is not shown to be unshared."""
import re

from langchain.tools import tool

from agent.db import read_session
from agent.tools.linkrules import HUB_DEGREE, address_degree, mail_drop
from agent.tools.records import snapshot
from etl.address import a2_key

CAVEATS = [
    "Each method's answer is that method's decision, named with its run or snapshot. The project's mail-drop list is a first cut and every row is unreviewed; BOR's masking is its rule for the Operational Network layer (an address shared by more landlord records than its threshold).",
    "'No' from a method means that method did not flag the address. It does not show the address is not a service address, and 'yes' links nothing: an address on the list or masked never ties two entities on its own.",
    "The degree counts parties in the graph (HPD contacts and ACRIS parties) whose address key matches under rule A2: house, street and ZIP, with unit text dropped. DOS process addresses are counted only through the list.",
]
BOR_MASK = "MATCH (r:BorRun) WITH r ORDER BY r.built_at DESC LIMIT 1 MATCH (a:BorMaskedAddress {run_id: r.run_id}) WHERE a.address_text = $t RETURN r.run_id AS run, a {.address_id, .degree, .mask_threshold, .method} AS a"
BOR_RUN = "MATCH (r:BorRun) RETURN r.run_id AS run ORDER BY r.built_at DESC LIMIT 1"


def _ordinal(n: int) -> str:
    return f"{n}{'TH' if 10 <= n % 100 <= 20 else {1: 'ST', 2: 'ND', 3: 'RD'}.get(n % 10, 'TH')}"


def _variants(house_number: str, street: str, zip5: str) -> list[str]:
    """The A2 key as typed, then with a numbered street written as an ordinal (61 STREET -> 61ST ST), since A2 does not map ordinals (note 0006)."""
    keys = [a2_key(house_number, street, zip5)]
    words = street.split()
    for i, w in enumerate(words):
        if w.isdigit():
            keys.append(a2_key(house_number, " ".join([*words[:i], _ordinal(int(w)), *words[i + 1:]]), zip5))
            break
    return keys


def check_address(runner, house_number: str = "", street: str = "", zip5: str = "", address_key: str = "") -> dict:
    """The methods applied to an address given as house number, street and ZIP, or as an A2 key with its ZIP."""
    base = snapshot(runner)
    tried = [address_key.strip().upper()] if address_key.strip() else (_variants(house_number, street, zip5) if house_number and street and zip5 else [])
    key = next((k for k in tried if mail_drop(runner, k) or any(address_degree(runner, k).values())), tried[0] if tried else "")
    if not key or not re.search(r" \d{5}$", key):
        return {**base, "status": "need_address", "note": "Give a house number, street and 5-digit ZIP, or an address key ending in the ZIP."}
    out = {**base, "address_key": key, "keys_tried": tried, "rule": "A2: uppercase, punctuation deleted, whitespace collapsed, street suffixes mapped; unit and floor text are not part of the key.", "caveats": CAVEATS}
    md = mail_drop(runner, key)
    run = runner.run(BOR_RUN).single()
    methods = [{"method": "the project's mail-drop list", "snapshot": md.get("snapshot_id") if md else base.get("snapshot_id"), "flagged": md is not None, **(
        {"kind": md["kind"], "basis": md["basis"], "review_status": md["review_status"], "list_sources": md.get("list_sources"), "reading": "the address is on the list; it links nothing on its own"}
        if md else {"reading": "the address is not on the list; the list is unreviewed and covers only addresses above its thresholds"})}]
    bor_hit = bool(md and md.get("bor_address_ids"))
    methods.append({"method": "BOR's masking of aggregator addresses", "run_id": run["run"] if run else None, "flagged": bor_hit,
                    "reading": (f"the list records that BOR masked this address (BOR address ids {md['bor_address_ids']}, shared by {md['bor_degree']} landlord records); the Operational Network layer does not link on it"
                                if bor_hit else "no BOR masked address is recorded for this key. BOR's address text has no ZIP, so the match is made through the list, and this is not proof BOR did not see it")})
    deg = address_degree(runner, key)
    methods.append({"method": "parties at the address in the graph", "flagged": deg["hpd_parties"] >= HUB_DEGREE, "threshold": HUB_DEGREE, **deg,
                    "reading": f"{deg['hpd_parties']} HPD parties, {deg['hpd_roles']} HPD roles and {deg['acris_parties']} ACRIS parties carry this address; "
                               + (f"at least {HUB_DEGREE} HPD parties, so it is treated as shared by unrelated parties" if deg["hpd_parties"] >= HUB_DEGREE else f"fewer than {HUB_DEGREE} HPD parties, so it is not treated as a hub")})
    out["status"] = "found"
    out["methods"] = methods
    out["summary"] = f"{sum(1 for m in methods if m['flagged'])} of {len(methods)} methods flag this address"
    return out


@tool
def check_address_aggregator(house_number: str = "", street: str = "", zip5: str = "", address_key: str = "") -> dict:
    """Say, method by method, whether a business address is an aggregator or mail drop. Give a house number, street and 5-digit ZIP (for example 746, 61 Street, 11220),
    or an address key as other tools return it (for example '746 61ST ST 11220'). Answers for: the project's mail-drop list (unreviewed), BOR's masking of aggregator
    addresses (with the run), and how many HPD and ACRIS parties carry the address in the graph. Each method's answer is its own decision; 'yes' links nothing on its own
    and 'no' does not show the address is not a service address."""
    with read_session() as session:
        return check_address(session, house_number, street, zip5, address_key)
