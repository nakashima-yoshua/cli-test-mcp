# cli-test-mcp

A deterministic, sequential CLI test engine with versioned test definitions and attempt-scoped evidence. Upstream AI or humans select cases, preparation and expectations; the engine executes only declared instructions.

## Current PR-B scope

- Suite, Case and Result v1.0 JSON Schema with strict validation
- Multiple cases, attempts and batches executed sequentially
- Reusable work slot rebuilt before each attempt; no Git Worktree per test
- Evidence collection (stdout, stderr, declared logs and expected output files), SHA-256, conditional log reset
- CLI with distinct exit codes for pass, test failure and execution failure

## Quick start

```bash
python -m pip install -e '.[dev]'
python -m pytest -q
cli-test validate path/to/suite.json
cli-test run path/to/suite.json --registry targets.json --output results
```

Targets are mapped to **absolute executable paths** in a registry JSON file. Run trusted programs only in dedicated test environments; the runner does **not** enforce OS security isolation. The MCP adapter and database schema reuse are planned in separate PRs.

## Design

- [Plan](docs/plan.md)
- [Architecture](docs/architecture.md)
- [Contracts](docs/contracts.md)
- [Evidence and security](docs/evidence-security.md)
- [Runner limitations](docs/runner.md)
- [PR decomposition](docs/pr-split-plan.md)
