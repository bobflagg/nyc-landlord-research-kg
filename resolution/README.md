# resolution/ (week 5)

Derived layers: grouping owners, officers and companies into Owner Portfolios and Operational Networks. Resolution itself is done by the BOR and NLR pipelines, not here (`docs/design-notes/0001-consume-bor-output.md`).

- Load BOR's Owner Portfolio and Operational Network memberships as Type II links, each tied to its build and pipeline run, with the supporting records and linkage stage as evidence.
- Do not treat group ids as durable; membership is the durable content.
- Maintain `mail_drop_addresses.csv`: registered-agent services, virtual offices and mail-drop stores whose addresses must not, on their own, link unrelated companies (PESP guide, section 2). Reconcile it with BOR's aggregator masking (open item in note 0001).

Done when: three portfolios are compared against Who Owns What and the differences are explained.

## mail_drop_addresses.csv (first version, unreviewed)

One row per address (rule A2 of design note 0006: unit text dropped, street suffixes mapped, matched on house, street and ZIP5). Built from snapshot `justfixwow-2026-05-29` and BOR release v0.2.1 from three sources: DOS process addresses used by at least 1,000 entities (`dos_process`), HPD Agent addresses on at least 400 registrations (`hpd_agent`), and BOR's masked aggregator addresses (`bor_masked`). The thresholds are a first cut, not a finding.

- **`kind`** (provisional values, not yet a vocabulary): `registered_agent` (a filing or registered-agent service is at least 25% of the entities' process names), `law_firm` (law-firm names are at least 25%), `management_office` (an HPD Agent contact is at the address on at least 75% of the registrations that list it), `unknown`. A kind is assigned only when the evidence in `basis` supports it; everything else stays `unknown` for a person to review.
- **Rule:** every row, whatever its kind, links nothing on its own. A `management_office` is masked because many unrelated landlords share it, which is not the same as a mail drop.
- **`review_status`** is `unreviewed` on every row. Only a person changes it (design note 0003).
- **Not yet done:** a person's review of the `unknown` rows; classification of addresses below the thresholds; ACRIS party addresses and DOS CEO addresses; a decision on whether BOR will take this list over (open in note 0001).
