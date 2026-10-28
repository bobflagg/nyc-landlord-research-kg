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
    out = []
    for path in sorted((ROOT / "ontology" / "generated").glob("*.cypher")):
        for block in re.split(r"\n(?=// name: )", path.read_text())[1:]:
            name = re.match(r"// name: (\S+)", block).group(1)
            if name.endswith("#summary"):  # counting variants that need a sampleSize parameter
                continue
            out.append((name, "\n".join(l for l in block.splitlines() if not l.startswith("//")).rstrip().rstrip(";")))
    return out


def handwritten_checks() -> list[tuple[str, str]]:
    return [(p.stem, "\n".join(l for l in p.read_text().splitlines() if not l.startswith("//")).strip())
            for p in sorted((ROOT / "etl" / "checks").glob("*.cypher"))]


def _scoped(query: str, scope: str) -> str:
    """The same rule, run only on nodes that carry the label `scope`. Every rule starts at its focus node, so the label
    is added to that first MATCH and a hint makes the planner start from the small label. A check that scans
    relationships cannot be scoped and is dropped in scope mode (its node half stays)."""
    query = query.split("UNION ALL")[0]
    def add(m: re.Match) -> str:
        var, label = m.group(1), m.group(2) or ""
        return f"MATCH ({var}{label}:`{scope}`) USING SCAN {var}:`{scope}`"
    return re.sub(r"MATCH \((\w+)(:`?\w+`?)?\)", add, query, count=1)


def validate(runner, only: tuple[str, ...] | None = None, scope: str | None = None) -> list[Violation]:
    """`runner` is a neo4j Session or Transaction. `only` limits the run to rules and checks whose name starts with
    one of the prefixes. `scope` is a node label: only nodes carrying it are checked. A test that loads a few nodes
    into a database already holding the citywide load labels what it loaded and passes the label, so it does not
    scan millions of nodes it did not create. The build passes neither and checks everything."""
    keep = (lambda name: True) if only is None else (lambda name: name.startswith(only))
    fit = (lambda q: q) if scope is None else (lambda q: _scoped(q, scope))
    found = []
    for name, query in filter(lambda r: keep(r[0]), compiled_rules()):
        for rec in runner.run(fit(query), limit=LIMIT):
            found.append(Violation(name, rec.get("message") or str(dict(rec))))
    for name, query in filter(lambda r: keep(r[0]), handwritten_checks()):
        for rec in runner.run(fit(query)):
            found.append(Violation(name, str(dict(rec))))
    return found
