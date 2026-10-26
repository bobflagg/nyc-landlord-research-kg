"""Run the compiled SHACL checks (ontology/generated/) and the hand-written checks (etl/checks/).

Every returned row is a violation and fails the build (design note 0010). Read-only.
Works on a session or an open transaction, so a test can validate inside a transaction and roll it back.
"""
import re
from dataclasses import dataclass
from pathlib import Path

from etl.config import ROOT

LIMIT = 1000  # violations reported per rule


@dataclass(frozen=True)
class Violation:
    rule: str
    detail: str


def compiled_rules() -> list[tuple[str, str]]:
    text = (ROOT / "ontology" / "generated" / "core.cypher").read_text()
    out = []
    for block in re.split(r"\n(?=// name: )", text)[1:]:
        name = re.match(r"// name: (\S+)", block).group(1)
        if name.endswith("#summary"):  # counting variants that need a sampleSize parameter
            continue
        out.append((name, "\n".join(l for l in block.splitlines() if not l.startswith("//")).rstrip().rstrip(";")))
    return out


def handwritten_checks() -> list[tuple[str, str]]:
    return [(p.stem, "\n".join(l for l in p.read_text().splitlines() if not l.startswith("//")).strip())
            for p in sorted((ROOT / "etl" / "checks").glob("*.cypher"))]


def validate(runner) -> list[Violation]:
    """`runner` is a neo4j Session or Transaction."""
    found = []
    for name, query in compiled_rules():
        for rec in runner.run(query, limit=LIMIT):
            found.append(Violation(name, rec.get("message") or str(dict(rec))))
    for name, query in handwritten_checks():
        for rec in runner.run(query):
            found.append(Violation(name, str(dict(rec))))
    return found
