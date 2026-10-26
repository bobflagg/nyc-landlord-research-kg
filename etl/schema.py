"""Graph schema derived from the ontology files: node keys, relationship types, constraints, indexes."""
import re
from dataclasses import dataclass
from typing import Iterable

from rdflib import RDF, RDFS, Graph, Namespace
from rdflib.namespace import OWL, SH

from etl.config import ROOT

WL = Namespace("https://bobflagg.github.io/Watchline/ontology/core#")
S2C = Namespace("https://w3id.org/shacl2cypher#")
SNAPSHOT_ID = re.compile(r"^[a-z][a-z0-9]*-\d{4}-\d{2}-\d{2}(-r\d+)?$")  # note 0008

# Indexed for lookup, not unique: "who else uses this address" (note 0010, item 2).
INDEXED = {"Lot": ["address_key"], "Building": ["address_key"]}


def _local(uri) -> str:
    return str(uri).split("#")[-1]


@dataclass(frozen=True)
class Schema:
    keys: dict[str, str]          # label -> key property, from s2c:key on each targeted class
    relationships: frozenset[str]  # relationship types, from owl:ObjectProperty

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
    shapes = Graph().parse(ROOT / "ontology" / "core.shapes.ttl")
    core = Graph().parse(ROOT / "ontology" / "core.ttl")
    keys = {}
    for shape, key in shapes.subject_objects(S2C.key):
        for cls in shapes.objects(shape, SH.targetClass):
            keys[_local(cls)] = str(key)
    rels = frozenset(_local(p).upper() for p in core.subjects(RDF.type, OWL.ObjectProperty))
    return Schema(keys, rels)
