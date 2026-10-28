# 0012: Model provider, test framework and the first end-to-end question

Date: 2026-10-26

Status: **accepted 2026-10-26.** Settles two open decisions in `specs/tech-stack.md` (model provider, test framework) and amends its Agent and runtime rows. Builds on notes 0010 and 0011.

## Decision

1. **Model provider: Anthropic Claude,** reached through LangChain's model strings (`anthropic:<model id>`). The agent model is `AGENT_MODEL` in `.env` (default `anthropic:claude-sonnet-5-5`). The model that judges evaluations is a separate setting, `JUDGE_MODEL`, so either can change alone. A provider swap is a configuration change.
2. **Test framework: pytest plus LangSmith.**
   - pytest covers what needs no model: addresses, the loader, the shapes and checks, the agent's tools. It runs without a network.
   - LangSmith datasets and evaluators cover agent behavior: tool trajectory, citations and caveats, and later answer correctness with the judge model.
   - Agent tests carry the `agent` marker (`pytest -m "not agent"` skips them) and skip themselves without a model key. They log to LangSmith only when `LANGSMITH_TRACING=true`.
3. **Database tests run in rolled-back transactions on `nyclr`,** as the load framework's self-test does. No test database, so the `nyclr`-only rule (note 0011) is unchanged.
   - **Scoped validation (2026-10-28).** Once `nyclr` held the citywide load, validating the whole database in every test took 40 minutes. A test now labels what it loaded (`tests/scope.py`, label `TestScope`, an index lookup on each key) and calls `validate(..., scope=SCOPE)`, which adds the label and a scan hint to each rule's first `MATCH`. A check that scans relationships is dropped in scope mode. The build calls `validate` with no scope and checks everything. Tests prove the scope is not blind: the bad-row tests must trip their rule in scope mode, and one test breaks a loaded registration and expects the violation. The five database test files run in about 17 seconds.
4. **The first end-to-end question is Q1** (address to lot and buildings, with the not-found case). One templated, parameterized, read-only Cypher tool, `find_lot_by_address`, over the sample load. The address key is rule A2 (note 0006); a miss reports the key it tried and does not guess a nearby lot. Units are not in the graph yet, so the tool reports `units: null` and says so.
5. **Read-only is enforced where the agent connects:** its sessions open in read mode (`agent/db.py`), and the tool accepts only fixed query templates. A database-level read-only role is not used for now.

## Consequences

- `specs/tech-stack.md`: the model-provider and test-framework decisions are removed from Open decisions and stated in the Agent and runtime table.
- Slice 0 exit test: the sample load validates, and Q1 runs end to end (`uv run pytest -m agent`). The agent tests need the sample committed in `nyclr` (`uv run python -m etl.sample`).
- Not yet done: the LangSmith dataset and judge-based evaluators (the deterministic checks live in `tests/test_q1_agent.py`), and re-deriving expected answers from the real snapshot.
- Revisit: a database read-only role when the agent leaves development; the model choice if evaluation shows tool-calling errors.
