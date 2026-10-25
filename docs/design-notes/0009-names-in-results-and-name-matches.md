# 0009: Names in results, and what a name match is

Date: 2026-10-24

Status: **accepted 2026-10-24.** Amends `specs/mission.md` (Boundaries), `CLAUDE.md` (Quick rules), `docs/competency-questions.md`, `docs/competency-questions-detail.md` and `docs/demo-slice.md` as listed under Consequences. Builds on notes 0001, 0006 and 0007.

## Decision

1. **Names are shown wherever the data has them.** The rule "people appear only in recorded roles" is dropped. A person's name may appear in a result whether it comes from an HPD, ACRIS or DOS filing, a BOR release, a news report or a web page. JustFix results show names throughout, and hiding them in ours made results hard to review and share.
2. **The label stays on the fact, not on the display.** Every name still comes from a fact that carries `reliability`, `source_category`, `source` and `snapshot_id` (notes 0002 and 0005). An answer that shows a name says where it came from and whether it is recorded, attributed to a source, or derived. A name from a news report or web page remains `published_reporting` or `web_content` and `unreviewed`; showing it plainly does not make it a recorded role.
3. **A name does not make an ownership claim.** Showing a name is one thing and saying who owns or controls a building is another. Ownership and control stay role nodes with a source (tech stack). A group's person anchor from BOR is a display attribute of the group, never a role and never evidence of ownership (note 0001, competency requirement 7). The graph may now store it as that attribute.
4. **Name matches are computed when asked and are leads.** Q3 (HPD owner to DOS entity) and Q22 (deed grantee to HPD owner) compare names at query time, by the exact rule N1 of note 0006 (uppercase, delete punctuation, collapse whitespace). Nothing is stored. The result reports name agreement and address agreement as separate fields. The caveat changes from "names alone link nothing" to **"a name match is a lead"**: it is shown with its evidence (the matching names, the address agreement or disagreement, a mail-drop flag, how many other records share the name) and is never stated as "same party" or as ownership.
5. **No fuzzy matching.** Variants such as `Example Holdings LLC` and `Example Holdings II LLC` are reported as a possible connection with whatever evidence they share, not matched by a similarity rule. Fuzzy matching would be the project's own entity resolution, which stays a non-goal (note 0001).
6. **Stored name edges come only from BOR.** BOR's name edges already load as Type II layers (note 0007). The KG creates no stored name-match links of its own.
7. **What does not change.** "No personal information" holds: no following links to an individual's home address or other non-business information. Mail-drop addresses never link two entities on their own. Complaint data stays at building level. A masked or mail-drop address is still set aside and said so.

## Context

- The reason the rule existed was caution about a public demo concentrating officer and agent names (`docs/demo-slice.md`). The user's decision is that the confusion from hiding names outweighs it, and that the boundary that matters is personal information, not names.
- Name matches are weak on this data (note 0006): 55,754 of 88,542 distinct normalized HPD owner names (63%) match an active DOS entity name, and 71 match more than one. That is why the match stays a lead.
- Only 156 of BOR's 21,251 Operational Network path steps are name matches; shared address accounts for 11,771 (BOR's count, note 0007).
- BOR is being updated to include name information in its release. The graph then loads the build with names, and the group anchor becomes available as a display attribute.

## Alternatives considered

- **Drop the "recorded roles only" rule and the label together** (names from any source shown as plain names). Simpler to display, but a news mention would look like a filing, which breaks mission outcome 2 (recorded facts kept apart from derived ones). Not chosen; the label stays on the fact.
- **Store name-match links in the graph** with a `link_id` for later review. Gives a citable layer, but duplicates what BOR stores and adds a layer to reload with each snapshot. Revisit if the review process (later horizon) needs to cite a name match.
- **Drop the caveat and let a name match stand as a link.** The agent could then state ownership from a name collision. Not chosen.
- **Fuzzy name matching in the KG.** Moves the project into entity resolution, a standing non-goal.

## Consequences

- **Edits made with this note:**
  - `specs/mission.md`: the "people appear only in recorded roles" boundary is replaced by a rule that names are shown with their source and a name never asserts a role.
  - `CLAUDE.md`: the matching quick rule.
  - `docs/competency-questions.md`: the failure row no longer lists "a person shown outside a recorded role"; the Q22 caveat and the respondent field line are reworded.
  - `docs/competency-questions-detail.md`: the Q3 caveats, the neutral-buildings rule and the respondent example.
  - `docs/demo-slice.md`: "Publishing responsibly".
  - Notes 0001 and 0007 each get a dated update line.
- **Loader:** the BOR release with names is loaded as is, `project_derived`, as in note 0007. Names are properties of the run-scoped nodes. The person-free-build condition in note 0007 no longer applies.
- **Shapes:** SHACL still requires reliability, source category and snapshot on every fact that carries a name, and still forbids an ownership role without a source.
- **Evaluation:** cases that expected a person to be withheld are rewritten to expect the name with its role and source. Cases about name-only matches expect the "lead" wording, not a finding.
- **Revisit:** storing name-match links, when the review process is designed.
