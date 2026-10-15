# resolution/ (week 5)

Derived layers: grouping owners, officers and companies into Owner Portfolios and Operational Networks. Resolution itself is done by the BOR and NLR pipelines, not here (`docs/design-notes/0001-consume-bor-output.md`).

- Load BOR's Owner Portfolio and Operational Network memberships as Type II links, each tied to its build and pipeline run, with the supporting records and linkage stage as evidence.
- Do not treat group ids as durable; membership is the durable content.
- Maintain `mail_drop_addresses.csv`: registered-agent services, virtual offices and mail-drop stores whose addresses must not, on their own, link unrelated companies (PESP guide, section 2). Reconcile it with BOR's aggregator masking (open item in note 0001).

Done when: three portfolios are compared against Who Owns What and the differences are explained.
