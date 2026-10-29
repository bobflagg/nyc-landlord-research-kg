"""Label what a test loaded, so validation checks only those nodes (etl.validate.validate(scope=...)).

The tests load fixtures into nyclr inside a transaction that is rolled back, and nyclr already holds the citywide load.
Tagging uses the key constraints, so it is an index lookup; the label never outlives the transaction."""
from etl.acris import party_id as acris_party_id
from etl.hpd import party_id as hpd_party_id, real_bin

SCOPE = "TestScope"


def tag(tx, label: str, key: str, values) -> None:
    values = sorted({str(v) for v in values})
    if values:
        tx.run(f"MATCH (n:`{label}`) WHERE n.`{key}` IN $values SET n:`{SCOPE}`", values=values).consume()


def tag_hpd(tx, pluto=(), registrations=(), contacts=()) -> None:
    tag(tx, "Lot", "bbl", [str(r["bbl"]).strip() for r in [*pluto, *registrations]])
    tag(tx, "Building", "bin", [real_bin(r.get("bin")) for r in registrations if real_bin(r.get("bin"))])
    tag(tx, "Registration", "registration_id", [r["registrationid"] for r in registrations])
    tag(tx, "Party", "party_id", [hpd_party_id(c) for c in contacts])
    tag(tx, "Role", "role_id", [f"hpd:{c['registrationcontactid']}" for c in contacts])


def tag_acris(tx, documents, parties) -> None:
    tag(tx, "Document", "document_id", [d["documentid"] for d in documents])
    tag(tx, "Party", "party_id", [acris_party_id(p) for p in parties])
    # the roles of those documents: reached through the document key, an index lookup
    tx.run(f"MATCH (d:Document:`{SCOPE}`)<-[:IN_DOCUMENT]-(r:AcrisRole) SET r:`{SCOPE}`").consume()


def tag_dos(tx, rows) -> None:
    tag(tx, "Party", "party_id", [f"dos:{r['dosid']}" for r in rows])


def tag_litigation(tx, rows) -> None:
    tag(tx, "Litigation", "litigation_id", [r["litigationid"] for r in rows])


def tag_bor(tx, run_id: str) -> None:
    """Label the nodes of one BOR run. Each BOR label is small, so a label scan is cheap (never scan unlabelled nodes)."""
    for label in ("BorRun", "BorGroup", "BorNode", "BorDecision", "BorEvidence", "BorLinkSet", "BorMaskedAddress", "BorMetric"):
        tx.run(f"MATCH (n:`{label}`) WHERE n.run_id = $run SET n:`{SCOPE}`", run=run_id).consume()
