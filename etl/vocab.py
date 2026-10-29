"""Source-code mappings read from the vocab files, so the vocabulary stays the one place they are written."""
from functools import cache

from rdflib import Graph, Namespace, URIRef
from rdflib.namespace import SKOS

from etl.config import ROOT

BASE = "https://bobflagg.github.io/Watchline/vocab/"


@cache
def _codes(scheme: str, lang: str) -> dict[str, str]:
    """{source code, case-folded: notation} from skos:hiddenLabel with the given language tag."""
    g = Graph().parse(ROOT / "vocab" / f"{scheme}.ttl")
    out = {}
    for concept, label in g.subject_objects(SKOS.hiddenLabel):
        if label.language == lang:
            out[str(label).casefold()] = str(g.value(concept, SKOS.notation))
    return out


def hpd_role_type(contact_type: str) -> str:
    """HPD contact type to role_type. An unknown type is an error: a role is never dropped quietly."""
    try:
        return _codes("role-type", "x-hpd")[contact_type.casefold()]
    except KeyError:
        raise ValueError(f"HPD contact type {contact_type!r} has no concept in vocab/role-type.ttl") from None


def hpd_owner_kind(description: str | None) -> str | None:
    """contactdescription to owner_kind, or None when the recorded value has no concept (the raw value is kept)."""
    return _codes("entity-kind", "x-hpd").get((description or "").strip().casefold())


def acris_doc_type(code: str | None) -> str | None:
    """ACRIS document type code to doc_type, or None for a code with no concept (the raw code is kept)."""
    return _codes("document-type", "x-acris").get((code or "").strip().casefold())


def _family_codes(family: str) -> list[str]:
    g = Graph().parse(ROOT / "vocab" / "document-type.ttl")
    parent = URIRef(f"{BASE}document-type/{family}")
    return sorted(str(l) for c in g.subjects(SKOS.broader, parent) for l in g.objects(c, SKOS.hiddenLabel) if l.language == "x-acris")


def mortgage_family_types() -> list[str]:
    """doc_type notations of the mortgage family, as stored on Document nodes."""
    g = Graph().parse(ROOT / "vocab" / "document-type.ttl")
    parent = URIRef(f"{BASE}document-type/mortgage_family")
    return sorted(str(g.value(c, SKOS.notation)) for c in g.subjects(SKOS.broader, parent))


def deed_family_types() -> list[str]:
    """doc_type notations of the deed family, as stored on Document nodes."""
    g = Graph().parse(ROOT / "vocab" / "document-type.ttl")
    parent = URIRef(f"{BASE}document-type/deed_family")
    return sorted(str(g.value(c, SKOS.notation)) for c in g.subjects(SKOS.broader, parent))


def deed_family_codes() -> list[str]:
    """ACRIS document type codes of the deed family: the codes the deed build loads."""
    return _family_codes("deed_family")


def mortgage_family_codes() -> list[str]:
    """ACRIS document type codes of the mortgage family (note 0022)."""
    return _family_codes("mortgage_family")


def acris_role_type(doc_type: str | None, party_type) -> str | None:
    """Party type to role_type. Deed family: party 3 means life estate retained on DEED, LE only; elsewhere it has no confirmed meaning and
    maps to nothing. Mortgage family: the meaning of party 1 and 2 depends on the document type (vocab/role-type.ttl, x-acris-by-type)."""
    by_type = _codes("role-type", "x-acris-by-type").get(f"{doc_type}:{str(party_type).strip()}".casefold())
    if by_type is not None:
        return by_type
    if doc_type is None or not doc_type.startswith("deed"):
        return None     # a mortgage-class party code with no confirmed meaning for its document type
    role = _codes("role-type", "x-acris").get(str(party_type).strip())
    if role == "life_estate_retained" and doc_type != "deed_life_estate":
        return None
    return role


def violation_class(code: str | None) -> str | None:
    """HPD violation class letter to violation_class, or None for a letter with no concept."""
    return _codes("violation-class", "x-hpd").get((code or "").strip().casefold())


def violation_status_group(status: str | None) -> str | None:
    """HPD violationstatus (Open, Close) to status_group, or None when the value has no concept."""
    return _codes("violation-status-group", "x-hpd").get((status or "").strip().casefold())


def complaint_type(raw: str | None) -> str | None:
    return _codes("complaint-type", "x-hpd").get((raw or "").strip().casefold())


def litigation_case_type(raw: str | None) -> str | None:
    """HPD case type to case_type, or None for a type with no concept (the raw value is kept)."""
    return _codes("litigation-case-type", "x-hpd").get((raw or "").strip().casefold())
