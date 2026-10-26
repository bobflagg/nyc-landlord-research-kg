#!/usr/bin/env python3
"""Rebuild the Competency Question Review page from the question files.

Reads docs/competency-questions.md and docs/competency-questions-detail.md,
parses them into structured data, and writes a self-contained HTML page
(build/cq-review.html by default) from scripts/cq_review_template.html.

Usage (from the repo root):
    uv run scripts/build_cq_review.py
    uv run scripts/build_cq_review.py --out /tmp/cq-review.html

Publishing: this script only builds the HTML. To update the published page
at its existing link (keeping your saved verdicts and notes), ask Claude to
republish build/cq-review.html to the artifact URL in ARTIFACT_URL below,
with the same `db` capability.

Standard library only. The parser follows the files' current Markdown
layout; if a section is renamed or a table changes shape, it stops with a
message naming what it could not find.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ARTIFACT_URL = "https://claude.ai/artifact/XzNkY3iFcaXZXCAPijrRE4"

REPO = Path(__file__).resolve().parent.parent
DEFAULT_MAIN = REPO / "docs" / "competency-questions.md"
DEFAULT_DETAIL = REPO / "docs" / "competency-questions-detail.md"
DEFAULT_TEMPLATE = Path(__file__).resolve().parent / "cq_review_template.html"
DEFAULT_OUT = REPO / "build" / "cq-review.html"


class ParseError(Exception):
    pass


def section(text: str, heading: str, level: int = 2, required: bool = True) -> str:
    """Text between '#'*level + heading and the next heading of the same or higher level."""
    pat = re.compile(r"^" + "#" * level + r" " + re.escape(heading) + r"\s*$", re.M)
    m = pat.search(text)
    if not m:
        if required:
            raise ParseError(f'missing section "{"#" * level} {heading}"')
        return ""
    rest = text[m.end():]
    n = re.search(r"^#{1,%d} " % level, rest, re.M)
    return rest[: n.start()] if n else rest


def split_row(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split(" | ")]


def table_body(block: str, header_start: str) -> list[list[str]]:
    """Rows of the pipe table whose header row starts with header_start (header and rule excluded)."""
    rows, inside = [], False
    for line in block.splitlines():
        s = line.strip()
        if not s.startswith("|"):
            if inside:
                break
            continue
        if s.startswith("| " + header_start):
            inside = True
            continue
        if inside and not re.match(r"^\|\s*-", s):
            rows.append(split_row(s))
    return rows


def numbered_bold(block: str) -> list[dict]:
    items = []
    for line in block.splitlines():
        m = re.match(r"^(\d+)\. \*\*(.+?)\*\*\s*(.*)", line)
        if m:
            items.append({"n": int(m.group(1)), "title": m.group(2), "text": m.group(3)})
    return items


def bullets(block: str) -> list[str]:
    return [l[2:].strip() for l in block.splitlines() if l.startswith("- ")]


def parse(main: str, det: str) -> dict:
    # --- status line -> draft label
    status = re.search(r"\*\*Status:\s*([^*]+)\*\*", main)
    status_text = status.group(1).strip() if status else ""
    draft_m = re.search(r"draft\s+(\d+)", status_text, re.I)
    draft = f"draft {draft_m.group(1)}" if draft_m else ""
    stamp_tail = "awaiting ratification" if "awaiting ratification" in status_text.lower() else ""
    stamp = " · ".join(x for x in [draft.capitalize(), stamp_tail] if x) or "Draft"

    # --- candidates table
    qs: dict[int, dict] = {}
    for line in section(main, "Candidates").splitlines():
        if re.match(r"^\| \d+ \|", line):
            c = split_row(line)
            if len(c) < 5:
                raise ParseError(f"candidates row has {len(c)} cells, expected at least 5: {line[:80]}")
            n = int(c[0])
            qs[n] = dict(n=n, question=c[1], example=c[2], reliability=c[3].strip(), sourcesText=c[4])
    if not qs:
        raise ParseError('no question rows found in "## Candidates"')
    for q in qs.values():
        if q["reliability"] not in ("I", "II", "I+II"):
            raise ParseError(f'Q{q["n"]}: reliability "{q["reliability"]}" is not I, II or I+II')

    # --- anchors (needed to tag examples)
    anc = section(det, "Anchor properties", 3, required=False)
    anchors = []
    for l in anc.splitlines():
        if l.startswith("| **"):
            c = split_row(l)
            anchors.append({"key": c[0].strip("*"), "address": c[1], "bbl": c[2].strip("`"), "what": c[3]})
    bbl_to_key = {a["bbl"]: a["key"] for a in anchors}

    # --- detail blocks
    blocks = re.split(r"^### ", section(det, "Questions"), flags=re.M)[1:]
    for b in blocks:
        head, _, body = b.partition("\n")
        m = re.match(r"Q(\d+): (.*)", head.strip())
        if not m:
            continue
        n = int(m.group(1))
        if n not in qs:
            print(f"warning: detail block for Q{n} has no row in the candidates table; skipped", file=sys.stderr)
            continue
        items = []
        for line in body.splitlines():
            mm = re.match(r"^- \*\*(.+?):\*\*\s*(.*)", line)
            if mm:
                items.append({"label": mm.group(1), "text": mm.group(2)})
            elif line.startswith("- "):
                items.append({"label": "", "text": line[2:]})
        q = qs[n]
        q["title"] = m.group(2).strip()
        q["detail"] = items
        src = [i["text"] for i in items if i["label"] == "Sources"]
        keys = re.findall(r"`([a-z_]+)`", src[0]) if src else []
        if src and src[0].lower().startswith("all"):
            keys = ["all"]
        q["sourceKeys"] = keys
        ex = " ".join(i["text"] for i in items if i["label"].startswith("Example"))
        has_pending = any(i["label"] == "Pending" for i in items)
        all_text = " ".join(i["text"] for i in items)
        if re.search(r"\*\*pending", ex, re.I):
            q["exampleStatus"] = "pending"
        elif has_pending or re.search(r"to confirm|to be added", all_text, re.I):
            q["exampleStatus"] = "partial"
        else:
            q["exampleStatus"] = "verified"
        found = set()
        for i in items:
            if not i["label"].startswith("Example"):
                continue
            found.update(x for pair in re.findall(r"\(([A-G])(?: and ([A-G]))?\)", i["label"] + " " + i["text"]) for x in pair if x)
            found.update(re.findall(r"\*\*\(([A-G])\):\*\*", i["text"]))
            for bbl, key in bbl_to_key.items():
                if bbl in i["text"]:
                    found.add(key)
        q["anchors"] = sorted(found)

    missing = [n for n, q in qs.items() if "title" not in q]
    for n in missing:
        print(f"warning: Q{n} has no block in the detail file; shown with its table row only", file=sys.stderr)
        qs[n].update(title=f"Question {n}", detail=[], sourceKeys=[], exampleStatus="pending", anchors=[])

    # --- scenarios
    scen = section(main, "Additional scenarios", required=False)
    scen_intro = scen.split("\n**")[0].strip()
    for part in re.split(r"^\*\*", scen, flags=re.M)[1:]:
        head, _, body = part.partition("**")
        nums = [int(x) for x in re.findall(r"Q(\d+)", head)]
        label = re.sub(r"^Q\d+(?: and Q\d+)*: ", "", head.strip())
        for n in nums:
            if n in qs:
                qs[n].setdefault("scenarios", []).append({"label": label, "items": bullets(body)})

    # --- contracts
    con = section(main, "Answer contracts", required=False)
    for part in re.split(r"^### ", con, flags=re.M)[1:]:
        head, _, body = part.partition("\n")
        m = re.match(r"Q(\d+)", head)
        if not m or int(m.group(1)) not in qs:
            continue
        rows, extra = [], []
        for line in body.splitlines():
            s = line.strip()
            if s.startswith("| ") and not s.startswith("| Element") and not re.match(r"^\|\s*-", s):
                c = split_row(s)
                rows.append({"element": c[0], "spec": c[1] if len(c) > 1 else ""})
            elif s and not s.startswith("|"):
                extra.append(s)
        qs[int(m.group(1))]["contract"] = {"title": head.strip(), "rows": rows, "note": " ".join(extra)}

    # --- notes: PESP mapping, coverage, worked example, DOS
    notes = section(main, "Notes", required=False)
    pesp = []
    for c in table_body(notes, "PESP question"):
        cov, nums = c[1] if len(c) > 1 else "", []
        for a, b in re.findall(r"(\d+)(?:[–-](\d+))?", cov):
            nums += list(range(int(a), int(b) + 1)) if b else [int(a)]
        nums = [x for x in nums if x in qs]
        pesp.append({"question": c[0], "covered": cov, "nums": nums, "note": c[2] if len(c) > 2 else ""})
        for n in nums:
            qs[n].setdefault("pesp", []).append(c[0])

    coverage = []
    if "**Coverage.**" in notes:
        coverage = bullets(notes.split("**Coverage.**", 1)[1].split("\n**", 1)[0])
    for c in coverage[1:]:
        nums = {int(x) for x in re.findall(r"Q(\d+)", c)}
        for a, b in re.findall(r"Q(\d+)[–-](\d+)", c):
            nums.update(range(int(a), int(b) + 1))
        for n in nums:
            if n in qs:
                qs[n].setdefault("coverageNotes", []).append(c)

    wm = re.search(r"\*\*The guide's worked example\.\*\*\s*(.*)", notes)
    worked = wm.group(1) if wm else ""
    dos = {"head": "", "rows": [], "bullets": []}
    if "**NY DOS dataset" in notes:
        blk = notes.split("**NY DOS dataset", 1)[1].split("**Coverage.**", 1)[0]
        dos = {"head": "**NY DOS dataset" + blk.split("\n")[0],
               "rows": table_body(blk, "Field"), "bullets": bullets(blk)}

    # --- front matter, vocabulary, requirements, scope, e2e
    pre = main.split("## Vocabulary")[0]
    preamble = [p.strip() for p in pre.split("\n\n")[1:] if p.strip()]
    vocab = section(main, "Vocabulary used in the questions", required=False)
    vocab_rows = [split_row(l) for l in vocab.splitlines() if l.startswith("| **")]
    vocab_intro = [p.strip() for p in vocab.split("\n\n") if p.strip() and not p.strip().startswith("|")]
    req = section(main, "Requirements that apply to every answer", required=False)
    scope = section(main, "Scope", required=False)

    def between(text, start, end=None):
        if start not in text:
            return ""
        t = text.split(start, 1)[1]
        return t.split(end, 1)[0] if end and end in t else t

    handling_blk = between(scope, "**How web and document results are handled**", "**Process requirements**")
    process_blk = between(scope, "**Process requirements**", "**Out of scope:**")
    out_scope = ("**Out of scope:**" + between(scope, "**Out of scope:**")).strip() if "**Out of scope:**" in scope else ""

    e2e = section(main, "End-to-end acceptance requirement", required=False)
    open_items = []
    cur = None
    for l in section(main, "Open items", required=False).splitlines():
        m = re.match(r"^(\d+)\. \*\*(.+?)\*\*\s*(.*)", l)
        if m:
            cur = {"n": int(m.group(1)), "title": m.group(2), "text": m.group(3), "more": []}
            open_items.append(cur)
        elif cur and l.strip():
            cur["more"].append(l.strip())
    for o in open_items:
        t = o["text"].lower()
        if t.startswith("resolved"):
            o["state"] = "resolved"
        elif "resolved" in t and "still open" in t:
            o["state"] = "partial"
        elif "out of scope" in t:
            o["state"] = "out"
        else:
            o["state"] = "open"

    changes = []
    for h in re.findall(r"^## (Changes from draft \d+)\s*$", main, re.M):
        changes.append({"title": h, "items": bullets(section(main, h))})

    for a in anchors:
        a["questions"] = [n for n, q in sorted(qs.items()) if a["key"] in q.get("anchors", [])]

    return dict(
        draft=draft,
        stamp=stamp,
        questions=[qs[k] for k in sorted(qs)],
        pesp=pesp,
        coverage=coverage,
        worked=worked,
        dos=dos,
        preamble=preamble,
        vocab={"rows": vocab_rows, "intro": vocab_intro},
        requirements={"intro": req.strip().split("\n")[0] if req.strip() else "", "items": numbered_bold(req)},
        scope={
            "intro": scope.strip().split("\n\n")[0] if scope.strip() else "",
            "rows": [split_row(l) for l in scope.splitlines() if l.startswith("| **")],
            "handling": numbered_bold(handling_blk),
            "processHead": process_blk.strip().split("\n")[0] if process_blk.strip() else "",
            "process": bullets(process_blk),
            "out": out_scope,
        },
        e2e={
            "quote": " ".join(l.lstrip("> ").strip() for l in e2e.splitlines() if l.startswith(">")),
            "after": [p.strip() for p in e2e.split("\n\n") if p.strip() and not p.strip().startswith(">") and not re.match(r"^\d+\.", p.strip())],
            "items": numbered_bold(e2e),
        },
        openItems=open_items,
        changes=changes,
        anchors=anchors,
        anchorNotes=[p.strip() for p in anc.split("\n\n") if p.strip() and not p.strip().startswith("|")],
        chosen=bullets(section(det, "How the examples were chosen", required=False)),
        pending=table_body(section(det, "Pending summary", required=False), "Needs"),
        scenarioIntro=scen_intro,
    )


def build(data: dict, template: str) -> str:
    for token in ("__DATA__", "__STAMP__", "__COUNT__"):
        if token not in template:
            raise ParseError(f"template is missing the {token} placeholder")
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    stamp = data["stamp"].replace("&", "&amp;").replace("<", "&lt;")
    return (template.replace("__STAMP__", stamp)
                    .replace("__COUNT__", str(len(data["questions"])))
                    .replace("__DATA__", payload))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--main", type=Path, default=DEFAULT_MAIN, help="competency questions file")
    ap.add_argument("--detail", type=Path, default=DEFAULT_DETAIL, help="detail file")
    ap.add_argument("--template", type=Path, default=DEFAULT_TEMPLATE, help="HTML template")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT, help="output HTML path")
    ap.add_argument("--json", type=Path, help="also write the parsed data as JSON here")
    args = ap.parse_args()

    try:
        data = parse(args.main.read_text(encoding="utf-8"), args.detail.read_text(encoding="utf-8"))
        html = build(data, args.template.read_text(encoding="utf-8"))
    except FileNotFoundError as e:
        print(f"error: {e.filename} not found", file=sys.stderr)
        return 1
    except ParseError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(html, encoding="utf-8")
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")

    qs = data["questions"]
    by = lambda key: {v: sum(1 for q in qs if q[key] == v) for v in sorted({q[key] for q in qs})}
    print(f"Built {args.out} ({len(html) // 1024} KB)")
    print(f"  {data['stamp']}: {len(qs)} questions")
    print(f"  reliability: {by('reliability')}")
    print(f"  examples:    {by('exampleStatus')}")
    print(f"  contracts:   {', '.join('Q%d' % q['n'] for q in qs if q.get('contract')) or 'none'}")
    print()
    print("To update the published page (keeps saved verdicts and notes), ask Claude:")
    print(f'  "Republish {args.out.relative_to(REPO) if args.out.is_relative_to(REPO) else args.out}'
          f' to {ARTIFACT_URL}, keeping its db capability."')
    return 0


if __name__ == "__main__":
    sys.exit(main())
