"""The investigator's tools (design note 0030): the existing read tools wrapped so every call is logged in the ledger, and the ledger tools the agent must use.

A wrapped tool calls the original, logs the result (id, time, label, source category, hash) and returns the result with its result_id and retrieved time added, so the agent can
cite it. Past the call or time budget a wrapped tool does not run and says so. Nothing here writes to the graph."""
import functools

from langchain_core.tools import StructuredTool

from agent.investigator.ledger import Ledger, LedgerError
from agent.tools.absences import explain_what_is_missing
from agent.tools.addresses import check_address_aggregator
from agent.tools.affiliations import get_affiliations, get_agent_footprint
from agent.tools.conditions import get_hpd_complaints, get_hpd_litigation, get_hpd_violations, get_registration_status
from agent.tools.dos import get_dos_record
from agent.tools.evidence import compare_entities, get_shared_evidence
from agent.tools.history import get_title_and_registrant_on_date
from agent.tools.hpd import get_hpd_contacts, get_hpd_registrations
from agent.tools.layer_violations import rank_violations_in_group
from agent.tools.layers import compare_ownership_layers, explain_why_grouped, get_operational_network, get_owner_portfolio
from agent.tools.lookup import find_lot_by_address
from agent.tools.mortgages import get_mortgage_history
from agent.tools.records import compare_deed_grantee_with_hpd_owner, find_records_by_name
from agent.tools.reports import lookup_registry, search_reports
from agent.tools.restructuring import classify_deeds
from agent.tools.transfers import get_deed_history

RECORDED, DERIVED, REPORTED = "recorded_assertion", "derived_lead", "reported_claim"
GRAPH_TOOLS = [                      # (tool, label of what it returns); StructuredTool is not hashable
    (find_lot_by_address, RECORDED), (get_hpd_registrations, RECORDED), (get_hpd_contacts, RECORDED), (get_dos_record, RECORDED), (get_deed_history, RECORDED), (get_mortgage_history, RECORDED),
    (get_title_and_registrant_on_date, RECORDED), (get_registration_status, RECORDED), (get_hpd_violations, RECORDED), (get_hpd_complaints, RECORDED), (get_hpd_litigation, RECORDED), (get_affiliations, RECORDED),
    (compare_deed_grantee_with_hpd_owner, DERIVED), (find_records_by_name, DERIVED), (get_owner_portfolio, DERIVED), (get_operational_network, DERIVED), (explain_why_grouped, DERIVED),
    (compare_ownership_layers, DERIVED), (rank_violations_in_group, DERIVED), (explain_what_is_missing, DERIVED), (check_address_aggregator, DERIVED), (get_shared_evidence, DERIVED),
    (compare_entities, DERIVED), (classify_deeds, DERIVED), (get_agent_footprint, DERIVED),
]
WEB_TOOLS = [(search_reports, REPORTED), (lookup_registry, RECORDED)]      # a registry record is that registry's recorded assertion (note 0028)


def _category(tool_name: str, label: str, result: dict) -> str | None:
    if tool_name == "search_reports":
        return "published_reporting" if any(i.get("source_category") == "published_reporting" for i in result.get("items", [])) else "web_content"
    return None


DROP_FOR_MODEL = {"caveats", "how_to_read", "rule", "search_provider", "mail_drop_list"}     # boilerplate the investigator does not need (the log keeps the full result)


def compact(x, max_list: int = 40, max_str: int = 1500):
    """What the model sees: the result without boilerplate keys, long text cut and long lists capped with a count. The ledger keeps the full result for quotes and replay."""
    if isinstance(x, dict):
        return {k: compact(v, max_list, max_str) for k, v in x.items() if k not in DROP_FOR_MODEL}
    if isinstance(x, list):
        out = [compact(v, max_list, max_str) for v in x[:max_list]]
        return out + [{"_more_not_shown": len(x) - max_list}] if len(x) > max_list else out
    if isinstance(x, str) and len(x) > max_str:
        return x[:max_str] + f"... [{len(x) - max_str} more characters not shown]"
    return x


def logged(tool, label: str, ledger: Ledger) -> StructuredTool:
    def run(**kwargs):
        if ledger.finished:
            return {"status": "finished", "note": "the investigation is finished"}
        if not ledger.reserve():
            return {"status": "budget_reached", "note": "the tool-call or time budget is spent; no tool was run. Close open leads and call finish.", "budget": ledger.budget_report()}
        result = tool.invoke(kwargs)
        if not isinstance(result, dict):
            result = {"result": result}
        rec = ledger.log(tool.name, kwargs, result, label, _category(tool.name, label, result))
        return {"result_id": rec.result_id, "retrieved_at": rec.called_at, "label": rec.label, "source_category": rec.source_category, **compact(result)}
    return StructuredTool.from_function(func=run, name=tool.name, description=tool.description + f" Returns a result_id to cite in claims and leads. Its label is {label}.", args_schema=tool.args_schema)


def graph_tools(ledger: Ledger) -> list[StructuredTool]:
    return [logged(t, label, ledger) for t, label in GRAPH_TOOLS]


def web_tools(ledger: Ledger) -> list[StructuredTool]:
    return [logged(t, label, ledger) for t, label in WEB_TOOLS]


def ledger_tools(ledger: Ledger) -> list[StructuredTool]:
    def guard(fn):
        @functools.wraps(fn)
        def run(**kw):
            try:
                return fn(**kw)
            except LedgerError as e:
                return {"status": "refused", "reason": str(e)}
            except ValueError as e:      # a value outside a vocabulary (a bad outcome, kind or reason) is a refusal the agent can read, not a crash
                return {"status": "refused", "reason": str(e)[:300]}
        return run

    def add_lead(kind: str, value: str, found_in: str) -> dict:
        """Offer a lead: an entity name or an address (kind entity_name, address, or person_name for a person, which is only logged) that appears in the result with id found_in.
        The ledger applies the lead rule and returns the lead with its disposition: queued (follow it), or set_aside with the reason (a person, a masked or mail-drop address, a duplicate, the budget)."""
        l = ledger.add_lead(kind, value, found_in)
        return l.model_dump(exclude_none=True) | {"next": "follow it, then close_lead" if l.disposition == "queued" else "not followed; it will be listed in the dossier"}

    def record_claim(statement: str, source_ids: list[str], quote: str = "") -> dict:
        """Record one claim in the dossier. source_ids are the result_ids of the tool results that show it. Its label (recorded assertion, derived lead, reported claim) and source category come from
        those results and cannot be raised. A reported claim needs a verbatim quote from a cited result. A claim resting on a derived or reported source cannot state ownership or control."""
        c = ledger.record_claim(statement, source_ids, quote or None)
        return c.model_dump(exclude_none=True)

    def close_lead(lead_id: str, outcome: str, reason: str = "", note: str = "") -> dict:
        """Close a queued lead as resolved (what it led to is in claims) or unresolved with a reason: needs_payment, inaccessible, unreadable, partial, not_found, budget_exhausted, no_further_record or conflicting_records."""
        return ledger.close_lead(lead_id, outcome, reason or None, note or None).model_dump(exclude_none=True)

    def get_ledger() -> dict:
        """The claims, leads and budget so far."""
        return {"claims": [c.model_dump(exclude_none=True) for c in ledger.claims], "leads": [l.model_dump(exclude_none=True) for l in ledger.leads], "budget": ledger.budget_report(), "finished": ledger.finished}

    def finish(note: str = "") -> dict:
        """End the investigation. The stop reason is computed by the ledger from the leads and the budget: you cannot choose it. Refused while leads are open unless the budget is spent, and until at least one claim is recorded."""
        return ledger.finish(note or None)

    mk = lambda fn, guarded=True: StructuredTool.from_function(func=guard(fn) if guarded else fn, name=fn.__name__, description=fn.__doc__)
    return [mk(add_lead), mk(record_claim), mk(close_lead), mk(get_ledger, False), mk(finish)]
