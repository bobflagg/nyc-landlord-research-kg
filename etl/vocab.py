"""Source-code mappings read from the vocab files, so the vocabulary stays the one place they are written."""
from functools import cache

from rdflib import Graph, Namespace
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


def deed_family_codes() -> list[str]:
    """ACRIS document type codes that have a concept: the codes a build loads."""
    g = Graph().parse(ROOT / "vocab" / "document-type.ttl")
    return sorted(str(l) for l in g.objects(None, SKOS.hiddenLabel) if l.language == "x-acris")


def acris_role_type(doc_type: str | None, party_type) -> str | None:
    """Party type to role_type for a deed-family document. Party 3 means life estate retained on DEED, LE only;
    elsewhere it has no confirmed meaning and maps to nothing."""
    role = _codes("role-type", "x-acris").get(str(party_type).strip())
    if role == "life_estate_retained" and doc_type != "deed_life_estate":
        return None
    return role
