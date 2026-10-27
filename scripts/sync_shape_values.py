"""Write the allowed values in ontology/*.shapes.ttl from the vocab files.

Each generated list sits between `# generated:<vocab file> begin` and `# generated:<vocab file> end`
(optionally `only=a,b` to take a subset). Notations are read from `skos:notation` in vocab/<file>.ttl.
`<vocab file>:x-hpd` takes the HPD codes on `skos:hiddenLabel "..."@x-hpd` instead, in file order, once each.
`--check` exits 1 if a shapes file is out of date instead of rewriting it.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BLOCK = re.compile(r"^([ \t]*)# generated:(\S+) begin(?: only=(\S+))?\n.*?^[ \t]*# generated:\2 end$", re.M | re.S)


def values(spec: str) -> list[str]:
    name, _, lang = spec.partition(":")
    text = (ROOT / "vocab" / f"{name}.ttl").read_text()
    if lang:
        found = re.findall(rf'skos:hiddenLabel\s+"([^"]+)"@{re.escape(lang)}', text)
    else:
        found = re.findall(r'skos:notation\s+"([^"]+)"', text)
    return list(dict.fromkeys(found))


def render(m: re.Match) -> str:
    indent, spec, only = m.group(1), m.group(2), m.group(3)
    vals = values(spec)
    if only:
        wanted = only.split(",")
        missing = [v for v in wanted if v not in vals]
        if missing:
            sys.exit(f"{spec}: not in vocabulary: {missing}")
        vals = wanted
    head = f"{indent}# generated:{spec} begin" + (f" only={only}" if only else "")
    return f"{head}\n{indent}( {' '.join(chr(34) + v + chr(34) for v in vals)} )\n{indent}# generated:{spec} end"


def main() -> None:
    stale = []
    for path in sorted((ROOT / "ontology").glob("*.shapes.ttl")):
        old = path.read_text()
        new = BLOCK.sub(render, old)
        if new != old:
            if "--check" in sys.argv:
                stale.append(path.name)
            else:
                path.write_text(new)
    if stale:
        sys.exit(f"out of date: {stale}; run scripts/sync_shape_values.py")


if __name__ == "__main__":
    main()
