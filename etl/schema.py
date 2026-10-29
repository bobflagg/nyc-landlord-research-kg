"""Graph schema derived from the ontology files: node keys, relationship types, constraints, indexes."""
import re
from dataclasses import dataclass
from typing import Iterable

from rdflib import RDF, Graph, Namespace, URIRef
from rdflib.namespace import OWL, SH

from etl.config import ROOT

WL = Namespace("https://bobflagg.github.io/Watchline/ontology/core#")
S2C = Namespace("https://w3id.org/shacl2cypher#")
SNAPSHOT_ID = re.compile(r"^[a-z][a-z0-9]*-\d{4}-\d{2}-\d{2}(-r\d+)?$")  # note 0008

# Indexed for lookup, not unique: "who else uses this address" (note 0010, item 2).
INDEXED = {"Lot": ["address_key"], "Building": ["address_key"], "HpdParty": ["business_address_key", "name_n1", "person_name_n1"],
           "AcrisParty": ["address_key", "name_n1"], "Document": ["crfn"], "DosEntity": ["name_n1", "dos_id"],
           "BorGroup": ["group_id"], "BorNode": ["node_id", "cluster_id", "group_id"], "BorDecision": ["cluster_id", "subject_id"], "BorEvidence": ["document_id"]}


def _local(uri) -> str:
    return str(uri).split("#")[-1]


@dataclass(frozen=True)
class Schema:
    keys: dict[str, str]          # label -> key property, from s2c:key on each targeted class
    relationships: frozenset[str]  # relationship types, from owl:ObjectProperty
    classes: frozenset[str]        # every owl:Class in the modules; the only labels a load may set

    def constraints(self) -> Iterable[str]:
        for label, key in self.keys.items():
            yield (f"CREATE CONSTRAINT {label.lower()}_{key}_unique IF NOT EXISTS "
                   f"FOR (n:`{label}`) REQUIRE n.`{key}` IS UNIQUE")
            yield (f"CREATE CONSTRAINT {label.lower()}_{key}_string IF NOT EXISTS "
                   f"FOR (n:`{label}`) REQUIRE n.`{key}` IS :: STRING")

    def indexes(self) -> Iterable[str]:
        for label, props in INDEXED.items():
            for p in props:
                yield f"CREATE INDEX {label.lower()}_{p}_idx IF NOT EXISTS FOR (n:`{label}`) ON (n.`{p}`)"


def load_schema() -> Schema:
    """Read every ontology module: ontology/*.ttl for classes and relationships, *.shapes.ttl for keys."""
    shapes, onto = Graph(), Graph()
    for f in sorted((ROOT / "ontology").glob("*.shapes.ttl")):
        shapes.parse(f)
    for f in sorted((ROOT / "ontology").glob("*.ttl")):
        if not f.name.endswith(".shapes.ttl"):
            onto.parse(f)
    keys = {}
    for shape, key in shapes.subject_objects(S2C.key):
        for cls in shapes.objects(shape, SH.targetClass):
            keys[_local(cls)] = str(key)
    rels = frozenset(_local(p).upper() for p in onto.subjects(RDF.type, OWL.ObjectProperty))
    classes = frozenset(_local(c) for c in onto.subjects(RDF.type, OWL.Class) if isinstance(c, URIRef))
    return Schema(keys, rels, classes)
