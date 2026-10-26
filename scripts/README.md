# scripts/

## build_cq_review.py

Rebuilds the Competency Question Review page from `docs/competency-questions.md` and `docs/competency-questions-detail.md`.

```bash
uv run scripts/build_cq_review.py          # writes build/cq-review.html
uv run scripts/build_cq_review.py --json build/cq-data.json   # also dump the parsed data
```

The script only builds the HTML. Publishing to the page's existing link needs Claude, because pages are published through Claude's artifact tool. Ask:

> Republish build/cq-review.html to https://claude.ai/artifact/XzNkY3iFcaXZXCAPijrRE4, keeping its db capability.

Republishing to the same link keeps every verdict and note saved on the page. Publishing to a new link starts with an empty review.

- **Template:** `cq_review_template.html` holds the page's layout, styles and script. The build fills in `__DATA__`, `__STAMP__` and `__COUNT__`.
- **What it reads:** the status line (draft number), the candidates table, `## Additional scenarios`, `## Answer contracts`, `## Notes`, `## Open items` and the `## Changes from draft N` sections in the main file; the anchor table, `### Qn:` blocks and pending summary in the detail file.
- **When it fails:** if a required section is renamed or a candidates row loses cells, the script stops and names what it could not find. A question with no detail block is kept with a warning.
- **Review data:** verdicts and notes live in the page's database under `reviews/q01`…`reviews/q28` and `meta/overall`, keyed by question number. Renumbering questions would attach old reviews to the wrong question, so finish a review round before renumbering.
