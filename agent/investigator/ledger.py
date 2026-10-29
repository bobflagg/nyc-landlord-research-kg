"""The investigation ledger (design note 0030, I1 to I4). Pure Python, no model and no database: the rules of the end-to-end acceptance requirement live here.

The agent proposes (which tool to call, which lead to follow, what a result shows). The ledger disposes: it logs every tool result with an id, a time, a source category and a hash;
applies the lead rule; builds a claim only from cited results and gives it the weakest label among them; refuses an ownership statement on a derived or reported source; and
computes the single stop reason. The agent cannot write a claim, a label or a stop reason the contract forbids."""
import hashlib
import json
import re
import threading
import time
from datetime import datetime, timezone

from pydantic import BaseModel, Field, field_validator

from etl.names import n1
from etl.vocab import bor_term

LABEL_ORDER = {"recorded_assertion": 0, "derived_lead": 1, "reported_claim": 2}          # a claim takes the weakest of its sources
CATEGORY_OF_LABEL = {"recorded_assertion": "public_record", "derived_lead": "project_derived", "reported_claim": "published_reporting"}
OWNERSHIP = re.compile(r"\b(owns|owned by|owner of|ownership of|controls|controlled by|ultimate owner|beneficial owner|beneficial ownership|is the owner|parent (?:company|of))\b", re.I)
NEGATION = re.compile(r"\b(not|no|never|neither|nor|without|cannot|does not|do not|did not)\b|n't", re.I)
OPEN = ("queued",)
FOREIGN = re.compile(r'"jurisdiction":\s*"(?!New York")([A-Za-z ]+)"')
LEAD_REASONS_UNRESOLVED = {"needs_payment", "inaccessible", "unreadable", "partial", "not_found", "budget_exhausted", "no_further_record", "conflicting_records"}


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


VOLATILE = {"seconds_used", "cached"}      # differ between a first run and a replay without the evidence differing


def _stable(x):
    if isinstance(x, dict):
        return {k: _stable(v) for k, v in x.items() if k not in VOLATILE}
    if isinstance(x, list):
        return [_stable(v) for v in x]
    return x


def result_hash(data) -> str:
    return hashlib.sha256(json.dumps(_stable(data), sort_keys=True, default=str).encode()).hexdigest()[:16]


class ToolRecord(BaseModel):
    result_id: str
    tool: str
    args: dict
    called_at: str
    label: str                       # claim-label of what the tool returns
    source_category: str
    result_hash: str
    text: str                        # the result as JSON text (capped), for verbatim quote checks
    truncated: bool = False
    status: str | None = None


class Source(BaseModel):
    result_id: str
    tool: str
    retrieved_at: str
    source_category: str


class Claim(BaseModel):
    claim_id: str
    statement: str
    quote: str | None = None
    sources: list[Source]
    label: str
    source_category: str
    review_status: str | None = None     # None for a recorded assertion; unreviewed or contested otherwise (note 0003)

    @field_validator("label")
    @classmethod
    def _label(cls, v):
        return bor_term("claim-label", v)


class Lead(BaseModel):
    lead_id: str
    kind: str
    value: str
    key: str
    found_in: str
    disposition: str
    reason: str | None = None
    note: str | None = None

    @field_validator("kind")
    @classmethod
    def _kind(cls, v):
        return bor_term("lead-kind", v)

    @field_validator("disposition")
    @classmethod
    def _disp(cls, v):
        return bor_term("lead-disposition", v)

    @field_validator("reason")
    @classmethod
    def _reason(cls, v):
        return None if v is None else bor_term("lead-reason", v)


class LedgerError(Exception):
    """A refusal the agent can read and act on."""


def _locked(fn):
    def run(self, *a, **k):
        with self._lock:
            return fn(self, *a, **k)
    run.__name__, run.__doc__ = fn.__name__, fn.__doc__
    return run


def compute_stop(leads: list[dict], budget_spent: bool) -> str:
    """The one stop reason the leads and the budget support, or a LedgerError saying what is still open. Order (note 0030, I3): with leads still open the only
    legitimate end is budget_reached; otherwise conflicting records alone; a trail that reached an address that links nothing with no unresolved lead; no further
    recorded link; a source that needs payment or is inaccessible. Pure, so a finished dossier can be checked against it."""
    open_ = [l for l in leads if l["disposition"] in OPEN]
    if open_:
        if budget_spent:
            return "budget_reached"
        raise LedgerError(f"{len(open_)} lead(s) are still open ({', '.join(l['lead_id'] for l in open_)}): follow and close them, or the budget must be spent")
    unresolved = [l for l in leads if l["disposition"] == "unresolved"]
    reasons = {l.get("reason") for l in unresolved}
    if "conflicting_records" in reasons and not (reasons - {"conflicting_records"}):
        return "conflicting_records_unresolved"
    aside = {l.get("reason") for l in leads if l["disposition"] == "set_aside"}
    if not unresolved and aside & {"mail_drop_address", "masked_address"}:
        return "reached_registered_agent_mail_drop_or_masked_address"
    if not unresolved:
        return "no_further_recorded_link"
    if reasons & {"needs_payment", "inaccessible", "unreadable", "partial"}:
        return "needs_payment_or_inaccessible"
    if "conflicting_records" in reasons:
        return "conflicting_records_unresolved"
    if any(l["disposition"] == "set_aside" and l.get("reason") == "budget_exhausted" for l in leads) or budget_spent:
        return "budget_reached"
    return "no_further_recorded_link"


class Ledger:
    def __init__(self, subject: str, max_calls: int = 40, max_seconds: float = 720.0, max_leads: int = 6, address_checker=None, entity_checker=None, text_cap: int = 60000, required_tools: tuple = ()):
        self.subject, self.max_calls, self.max_seconds, self.max_leads, self.text_cap = subject, max_calls, max_seconds, max_leads, text_cap
        self.address_checker, self.entity_checker = address_checker, entity_checker   # callables injected by the caller; None means 'nothing flagged'
        self.required_tools = tuple(required_tools)
        self.t0, self.started = time.monotonic(), _now()
        self._lock, self.calls = threading.RLock(), 0       # tool calls run in parallel threads: ids and counts are assigned under a lock
        self.records: list[ToolRecord] = []
        self.claims: list[Claim] = []
        self.leads: list[Lead] = []
        self.finished: dict | None = None

    # ---- budget -----------------------------------------------------------------
    def calls_used(self) -> int:
        return max(self.calls, len(self.records))

    def reserve(self) -> bool:
        """Count a tool call before it runs; False when the budget is spent (the call must not run)."""
        with self._lock:
            if self.budget_spent():
                return False
            self.calls += 1
            return True

    def budget_spent(self) -> bool:
        return self.calls_used() >= self.max_calls or time.monotonic() - self.t0 >= self.max_seconds

    def budget_report(self) -> dict:
        return {"tool_calls_used": self.calls_used(), "tool_calls_allowed": self.max_calls, "seconds_used": round(time.monotonic() - self.t0, 1), "seconds_allowed": self.max_seconds,
                "leads_accepted": sum(1 for l in self.leads if l.disposition != "set_aside"), "leads_allowed": self.max_leads}

    # ---- the log ----------------------------------------------------------------
    @_locked
    def log(self, tool: str, args: dict, result: dict, label: str, source_category: str | None = None) -> ToolRecord:
        text = json.dumps(result, sort_keys=True, default=str)
        rec = ToolRecord(result_id=f"R{len(self.records) + 1}", tool=tool, args=args, called_at=_now(), label=bor_term("claim-label", label),
                         source_category=source_category or CATEGORY_OF_LABEL[label], result_hash=result_hash(result), text=text[: self.text_cap], truncated=len(text) > self.text_cap,
                         status=result.get("status") if isinstance(result, dict) else None)
        self.records.append(rec)
        return rec

    def record(self, result_id: str) -> ToolRecord:
        for r in self.records:
            if r.result_id == result_id:
                return r
        raise LedgerError(f"no tool result has the id {result_id!r}; cite the result_id a tool returned")

    # ---- claims -----------------------------------------------------------------
    @_locked
    def record_claim(self, statement: str, source_ids: list[str], quote: str | None = None) -> Claim:
        statement = statement.strip()
        if not statement:
            raise LedgerError("a claim needs a statement")
        if not source_ids:
            raise LedgerError("a claim needs at least one source: cite the result_id of a tool result")
        recs = [self.record(i) for i in dict.fromkeys(source_ids)]
        label = max((r.label for r in recs), key=LABEL_ORDER.get)
        cited = " ".join(re.sub(r"\s+", " ", r.text) for r in recs)
        absent = sorted({v for v in re.findall(r"\b\d{6,}\b|\b\d{4}-\d{2}-\d{2}\b", statement) if v not in cited})
        if absent:
            raise LedgerError(f"these values are not in the cited results: {', '.join(absent)}. Cite the result that shows them (its result_id), or leave them out")
        if label == "reported_claim" and not quote:
            raise LedgerError("a reported claim must carry a verbatim quote from its source")
        if quote:
            flat = re.sub(r"\s+", " ", quote).strip().lower()
            if not any(flat in re.sub(r"\s+", " ", r.text).lower() for r in recs):
                raise LedgerError("the quote does not appear verbatim in the cited results")
        if label != "recorded_assertion" and OWNERSHIP.search(statement) and not NEGATION.search(statement):
            raise LedgerError("a claim resting on a derived layer, a comparison or a report cannot state ownership or control; state what the source shows (a group placement, a name match, a published claim) as a lead")
        weakest = max(recs, key=lambda r: LABEL_ORDER[r.label])
        c = Claim(claim_id=f"C{len(self.claims) + 1}", statement=statement, quote=quote, label=label, source_category=weakest.source_category,
                  sources=[Source(result_id=r.result_id, tool=r.tool, retrieved_at=r.called_at, source_category=r.source_category) for r in recs],
                  review_status=None if label == "recorded_assertion" else "unreviewed")
        self.claims.append(c)
        return c

    # ---- leads ------------------------------------------------------------------
    @_locked
    def add_lead(self, kind: str, value: str, found_in: str) -> Lead:
        """Apply the lead rule: the value must appear in a result already retrieved; a person is logged, not followed; a masked or mail-drop address, a duplicate and anything past the budget are set aside with the reason."""
        kind = bor_term("lead-kind", kind)
        src = self.record(found_in)
        norm = re.sub(r"\s+", " ", value).strip().lower()
        if not norm or norm not in re.sub(r"\s+", " ", src.text).lower():
            raise LedgerError(f"{value!r} does not appear in result {found_in}; a lead must come from a source already retrieved")
        key = n1(value)
        lead = Lead(lead_id=f"L{len(self.leads) + 1}", kind=kind, value=value.strip(), key=key, found_in=found_in, disposition="queued")
        def aside(reason: str, note: str | None = None) -> Lead:
            lead.disposition, lead.reason, lead.note = "set_aside", reason, note
            self.leads.append(lead)
            return lead
        if kind == "person_name":
            return aside("person_not_followed", "a person's name is shown in its recorded role and not followed")
        if any(l.key == key and l.kind == kind for l in self.leads) or key == n1(self.subject):
            return aside("already_followed")
        if kind == "address" and self.address_checker:
            verdict = self.address_checker(value)
            if verdict:
                return aside(verdict["reason"], verdict.get("note"))
        if kind == "entity_name" and self.entity_checker:
            verdict = self.entity_checker(value)
            if verdict:
                return aside(verdict["reason"], verdict.get("note"))
        if self.budget_spent() or sum(1 for l in self.leads if l.disposition != "set_aside") >= self.max_leads:
            return aside("budget_exhausted", "the call, time or lead budget is spent")
        self.leads.append(lead)
        return lead

    @_locked
    def close_lead(self, lead_id: str, outcome: str, reason: str | None = None, note: str | None = None) -> Lead:
        lead = next((l for l in self.leads if l.lead_id == lead_id), None)
        if lead is None:
            raise LedgerError(f"no lead has the id {lead_id!r}")
        if lead.disposition != "queued":
            raise LedgerError(f"lead {lead_id} is {lead.disposition}; only a queued lead can be closed")
        outcome = bor_term("lead-disposition", outcome)
        if outcome not in ("resolved", "unresolved"):
            raise LedgerError("close a lead as resolved or unresolved")
        if outcome == "unresolved":
            if not reason or reason not in LEAD_REASONS_UNRESOLVED:
                raise LedgerError(f"an unresolved lead needs a reason from {sorted(LEAD_REASONS_UNRESOLVED)}")
            lead.reason = bor_term("lead-reason", reason)
        elif reason:
            lead.reason = None
        lead.disposition, lead.note = outcome, note
        return lead

    def open_leads(self) -> list[Lead]:
        return [l for l in self.leads if l.disposition in OPEN]

    # ---- the stop reason ----------------------------------------------------------
    def decide_stop(self) -> str:
        return compute_stop([l.model_dump() for l in self.leads], self.budget_spent())

    @_locked
    def finish(self, note: str | None = None) -> dict:
        if self.finished:
            raise LedgerError("the investigation is already finished")
        stop = bor_term("stop-reason", self.decide_stop())
        missing = [r for r in self.required_tools if not any(rec.tool == r for rec in self.records)]
        if missing and not self.budget_spent():
            raise LedgerError(f"the investigation is not complete: {', '.join(missing)} has not been called (delegate it to the web-researcher for the subject's recorded owner entity, or for the lot's BBL if there is none)")
        foreign = sorted({m.group(1).strip() for r in self.records if r.tool == "get_dos_record" for m in FOREIGN.finditer(r.text)})
        if foreign and not self.budget_spent() and not any(r.tool == "lookup_registry" for r in self.records) and not any(l.reason in ("needs_payment", "inaccessible") for l in self.leads):
            raise LedgerError(f"DOS shows a recorded entity registered in {', '.join(foreign)}: look it up in that state's free registry (delegate lookup_registry to the web-researcher) before finishing")
        if not self.claims:
            raise LedgerError("record at least one claim before finishing")
        self.finished = {"stop_reason": stop, "finished_at": _now(), "note": note}
        return self.finished
