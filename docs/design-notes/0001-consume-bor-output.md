# 0001: The graph consumes BOR's output

Date: 2026-10-15

## Decision
The graph consumes the output of the existing resolution pipelines (`nyc-landlord-resolution` "NLR", and `nyc-beneficial-owner-resolution` "BOR") as derived knowledge. Entity resolution is not rebuilt inside this repo.

## Context
- Both pipelines already produce the two derived layers the competency questions need: **Owner Portfolio** (BOR's Owner Portfolios, called "owner groups" before 2026-10-21) and **Operational Network**, with the management relationship kept separate (`docs/competency-questions.md`, draft 2).
- BOR's release carries four files: `owner_portfolios.csv`, `owner_portfolio_bbls.csv`, `operational_networks.csv`, `operational_network_bbls.csv` (the first two were `owner_groups.csv` and `owner_group_bbls.csv` before 2026-10-21; the contract in `beneficial-ownership-resolution/docs/release-contract.md` supersedes this legacy format). These give memberships and summary counts, keyed on BBL and opaque group ids.
- Two facts about the release limit what the graph can offer:
  - Group ids are stable within a build, not across builds.
  - No edge-level or record-level evidence file was found in the release. Competency questions 8, 9 and 19 need the edges, the linkage stage and the connecting path.

## Alternatives considered
- **Rebuild resolution here with Splink** (the original week 5 plan). Duplicates working, evaluated code, and the course's value is the ontology and agent, not a second matcher.
- **Consume memberships only.** Cheapest, but cannot answer "why are these grouped?" (Q19), which is the project's distinctive competency.

## Consequences
- Week 5 becomes loading and modelling derived layers: memberships as Type II, each tied to a build and pipeline run, with the source records behind each edge as Type I evidence.
- The graph must not treat group ids as durable identifiers. Membership is the durable content, and each assertion names its run.
- The evidence export is a requirement on the BOR and NLR repos, not on this one. **Open:** the form it takes (edge list, stage, path) is still to be agreed.
- `resolution/` keeps only what the graph still needs itself. **Open:** whether the curated mail-drop list stays here or comes from BOR's aggregator masking, and how the two are reconciled.
- BOR's person anchor is not an owner. The graph stores it, if at all, as a display attribute of a group and never as a role node (see `CLAUDE.md`, "Publishing responsibly").
- To revisit: the load cost of edge-level evidence at citywide scale.

- **Update 2026-10-20:** BOR now has a draft release contract. The boundary, how releases are loaded and the open evidence questions are in note 0007.
