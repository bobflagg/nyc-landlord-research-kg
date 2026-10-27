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
