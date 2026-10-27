"""Compile ontology/*.shapes.ttl to Cypher with shacl2cypher (design note 0010).

Writes ontology/generated/shapes.cypher and shapes.manifest.json. The generated files are committed so the
checks still run if the tool is dropped. Exits 1 if any rule is not compiled.
Usage: uv run --with shacl2cypher python scripts/compile_shapes.py [--check]
"""
import json
import sys
from pathlib import Path

import shacl2cypher

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "ontology" / "generated"


def main() -> None:
    """All modules compile together: a shape one module reuses from another (the provenance shape) must be in view,
    or the compiler treats the reference as empty and the rule passes silently."""
    check = "--check" in sys.argv
    OUT.mkdir(exist_ok=True)
    files = sorted((ROOT / "ontology").glob("*.shapes.ttl"))
    c = shacl2cypher.compile(files, dialect="neo4j")
    manifest = json.loads(c.manifest_json)
    bad = [r for r in manifest["rules"] if r.get("status") != "compiled"]
    if bad or manifest["staticDiagnostics"]:
        sys.exit(f"not fully compiled: {bad} {manifest['staticDiagnostics']}")
    outputs = {"shapes.cypher": c.cypher, "shapes.manifest.json": json.dumps(manifest, indent=1, sort_keys=True) + "\n"}
    stale = []
    for fname, text in outputs.items():
        p = OUT / fname
        if check:
            if not p.exists() or p.read_text() != text:
                stale.append(fname)
        else:
            p.write_text(text)
    if stale:
        sys.exit(f"stale: {stale}; run scripts/compile_shapes.py")


if __name__ == "__main__":
    main()
