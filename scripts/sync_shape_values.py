"""Write the allowed values in ontology/core.shapes.ttl from the vocab files.

Each generated list sits between `# generated:<vocab file> begin` and `# generated:<vocab file> end`
(optionally `only=a,b` to take a subset). Notations are read from `skos:notation` in vocab/<file>.ttl.
`--check` exits 1 if the shapes file is out of date instead of rewriting it.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SHAPES = ROOT / "ontology" / "core.shapes.ttl"
BLOCK = re.compile(r"^([ \t]*)# generated:(\S+) begin(?: only=(\S+))?\n.*?^[ \t]*# generated:\2 end$", re.M | re.S)


def notations(name: str) -> list[str]:
    text = (ROOT / "vocab" / f"{name}.ttl").read_text()
    return re.findall(r'skos:notation\s+"([^"]+)"', text)


def render(m: re.Match) -> str:
    indent, name, only = m.group(1), m.group(2), m.group(3)
    values = notations(name)
    if only:
        wanted = only.split(",")
        missing = [v for v in wanted if v not in values]
        if missing:
            sys.exit(f"{name}: not in vocabulary: {missing}")
        values = wanted
    lst = " ".join(f'"{v}"' for v in values)
    head = f"{indent}# generated:{name} begin" + (f" only={only}" if only else "")
    return f"{head}\n{indent}( {lst} )\n{indent}# generated:{name} end"


def main() -> None:
    old = SHAPES.read_text()
    new = BLOCK.sub(render, old)
    if "--check" in sys.argv:
        if new != old:
            sys.exit("core.shapes.ttl is out of date; run scripts/sync_shape_values.py")
        return
    SHAPES.write_text(new)


if __name__ == "__main__":
    main()
