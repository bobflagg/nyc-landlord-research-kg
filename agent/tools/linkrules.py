"""Shared rules for the Slice 5 tools (design note 0026): the hub threshold, the mail-drop list in the graph, address degree, and the relation between
two names (rules N1 and N2). Read-only, parameterized. Every comparison here is a lead; nothing creates or changes a stored link."""
import re
from difflib import SequenceMatcher

from etl.address import a2_key
from etl.names import n1, n2

HUB_DEGREE = 25      # distinct parties at one business address from which the address is treated as shared by unrelated parties (BOR's own threshold, note 0024)
COMMON_NAME = 25     # distinct HPD parties with one person name from which the name is treated as common
COMMERCIAL_AGENT_LOTS = 25
LEGAL_SUFFIX = {"LLC", "INC", "CORP", "CO", "LP", "LLP", "LTD", "PC", "PLLC", "TRUST"}
ROMAN = re.compile(r"^(I|II|III|IV|V|VI|VII|VIII|IX|X|XI|XII)$")
ORDINAL = re.compile(r"^\d+(ST|ND|RD|TH)$")

MAILDROP = "MATCH (m:MailDropAddress {maildrop_key: $k}) RETURN m {.maildrop_key, .kind, .basis, .review_status, .list_sources, .snapshot_id, .bor_degree, .bor_address_ids} AS m"
HPD_DEGREE = "MATCH (p:HpdParty {business_address_key: $k}) RETURN count(p) AS parties"
HPD_REGS_AT = "MATCH (p:HpdParty {business_address_key: $k})<-[:HELD_BY]-(o:HpdRole) RETURN count(o) AS roles"
ACRIS_DEGREE = "MATCH (p:AcrisParty {address_key: $k}) RETURN count(p) AS parties"


def mail_drop(runner, key: str | None) -> dict | None:
    """The mail-drop-list row for an A2 key with its ZIP, or None. The list is unreviewed until a person changes it."""
    if not key:
        return None
    r = runner.run(MAILDROP, k=key).single()
    return dict(r["m"]) if r else None


def address_degree(runner, key: str) -> dict:
    return {"hpd_parties": runner.run(HPD_DEGREE, k=key).single()["parties"], "hpd_roles": runner.run(HPD_REGS_AT, k=key).single()["roles"],
            "acris_parties": runner.run(ACRIS_DEGREE, k=key).single()["parties"]}


def address_status(runner, key: str) -> dict:
    """Whether an address, taken alone, may link two entities: on the list, shared by at least HUB_DEGREE HPD parties, or neither."""
    md, deg = mail_drop(runner, key), address_degree(runner, key)
    if md:
        return {"set_aside": True, "reason": f"on the project's mail-drop list ({md['kind']}; list unreviewed, snapshot {md.get('snapshot_id')})", "mail_drop": md, "degree": deg}
    if deg["hpd_parties"] >= HUB_DEGREE:
        return {"set_aside": True, "reason": f"shared by {deg['hpd_parties']} HPD parties (at least {HUB_DEGREE}), so it does not tie them", "mail_drop": None, "degree": deg}
    return {"set_aside": False, "reason": None, "mail_drop": None, "degree": deg}


def dos_process_key(e: dict) -> str | None:
    line, zip5 = e.get("process_address_line1"), e.get("process_zip")
    if line and zip5 and line[0].isdigit() and " " in line:
        house, street = line.split(" ", 1)
        return a2_key(house, street, zip5)
    return None


def _kind(tok: str) -> str:
    if tok in LEGAL_SUFFIX:
        return "a legal suffix"
    if tok.isdigit() or ORDINAL.match(tok):
        return "a number"
    if ROMAN.match(tok):
        return "a numeral"
    return "a word"


def name_relation(a: str, b: str) -> dict:
    """How two names relate under N1 and N2. Outcomes: normalization_match (N1 equal), spacing_match (N2 equal, N1 not), differs_by_one_token
    (one token added, removed or replaced: not the same unless a record other than the name connects them), different."""
    na, nb = n1(a), n1(b)
    base = {"name_a": a, "name_b": b, "n1_a": na, "n1_b": nb, "n2_a": n2(a), "n2_b": n2(b)}
    if not na or not nb:
        return {**base, "relation": "unusable", "reading": "a name is empty after normalization"}
    if na == nb:
        return {**base, "relation": "normalization_match", "reading": "equal after case, punctuation and whitespace are normalized (rule N1)" + ("" if a == b else "; the strings differ as written")}
    if n2(a) == n2(b):
        return {**base, "relation": "spacing_match", "reading": "equal once spaces are also removed (rule N2); they differ by where the spaces fall"}
    ta, tb = na.split(), nb.split()
    ops = [o for o in SequenceMatcher(a=ta, b=tb, autojunk=False).get_opcodes() if o[0] != "equal"]
    if len(ops) == 1:
        tag, i1, i2, j1, j2 = ops[0]
        if max(i2 - i1, j2 - j1) == 1 and min(i2 - i1, j2 - j1) <= 1:
            changed = (ta[i1:i2] + tb[j1:j2])
            return {**base, "relation": "differs_by_one_token", "different_tokens": changed, "token_kind": _kind(changed[-1]),
                    "reading": f"the names differ by one token ({' / '.join(changed)}, {_kind(changed[-1])}); that is a different name, and the same entity only if a record other than the name connects them"}
    return {**base, "relation": "different", "reading": "different names under N1 and N2"}
