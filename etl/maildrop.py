"""The project's mail-drop list as nodes (design note 0026, P1). Pure; no database. The CSV stays the committed artifact; the graph holds a copy
with provenance, so a tool can join parties to it in a query. Every row links nothing on its own."""
import csv
from pathlib import Path

from etl.config import ROOT
from etl.vocab import bor_term

LIST = ROOT / "resolution" / "mail_drop_addresses.csv"


def _int(v):
    v = (v or "").strip()
    return int(float(v)) if v else None


def maildrop_nodes(path: Path = LIST) -> list[dict]:
    """One node per row that has a ZIP. A row without one cannot match a party's A2 key (which ends in the ZIP), so it stays in the CSV and is not loaded."""
    out = []
    with open(path, newline="") as f:
        for r in csv.DictReader(f):
            if not r["zip5"].strip():
                continue
            key = f'{r["address_key"].strip()} {r["zip5"].strip()}'
            node = {"maildrop_key": key, "reliability": "II", "source_category": "project_derived", "review_status": r["review_status"] or "unreviewed",
                    "source": "mail_drop_list", "source_record_id": key, "snapshot_id": r["snapshot_id"], "zip5": r["zip5"].strip(),
                    "kind": bor_term("address-kind", r["kind"]), "basis": r["basis"], "dos_process_entities": _int(r["dos_process_entities"]),
                    "hpd_agent_registrations": _int(r["hpd_agent_registrations"]), "bor_degree": _int(r["bor_degree"]), "bor_address_ids": r["bor_address_ids"],
                    "list_sources": r["sources"], "list_note": r["note"]}
            out.append({k: v for k, v in node.items() if v not in (None, "")})
    return out
