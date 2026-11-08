# PR #1 decomposition

PR #1 is a prototype and is not merged. This plan avoids force-pushing the old branch.

| Stage | Responsibility | Acceptance | Deferred |
|---|---|---|---|
| PR-A | Versioned JSON contracts and validation | Unit tests / CI pass; no runner dependency | Execution, DB access |
| PR-B | Sequential runner, per-attempt file workspace, evidence, CLI | Repeated cases do not share mutable state; verified logs only reset after all captures succeed; timeout children are terminated | DB adapters, concurrency |
| PR-C | MCP adapter using the engine | Register, validate, run, query results through stdio; public contract documented | AI planning loop |
| PR-D | DB state preparer as optional adapter | Dedicated reusable schema slot; deny writes to BASE; restore verification after every attempt | Non-isolatable DB side effects |

Design constraints:
- Share the Git revision; do not make a worktree or repository per test case.
- Prepare only mutable filesystem inputs into an attempt-scoped workspace; store evidence separately and immutably.
- Database schemas are reused per execution slot, not created per test. Isolation is verified; a separate schema alone is not an overwrite mechanism.
- A slot with failed restoration is quarantined until repaired. Do not retry an unknown state.
- Contract validation is not OS process isolation. Execute only trusted targets in dedicated test environments until a stronger sandbox exists.
- Later PRs retain `validate_suite(suite, base)`, `validate_case(case, base)`, `safe_path(root, value)` and `load_json(path)` interfaces.

PR-A intentionally includes no executable test engine, CLI or MCP service.
