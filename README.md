# cli-test-mcp

A deterministic CLI batch test runner with strict JSON contracts, reproducible attempt workspaces and an optional stdio MCP adapter. AI/humans plan tests and define expected outcomes; the engine executes declared instructions only.

## Quick start

```bash
python -m pip install -e '.[dev,mcp]'
python -m pytest -q
cli-test validate path/to/suite.json
cli-test run path/to/suite.json --registry targets.json --output results
```

For MCP, configure `CLI_TEST_WORKSPACE`, `CLI_TEST_REGISTRY` and `CLI_TEST_RESULTS`, then run `cli-test-mcp` through a trusted local stdio client. This prototype runs MCP tests synchronously.

## Safety and limitations

Executables are registered by absolute path and run with the caller's OS privileges. This is **not a sandbox**: only use trusted targets in disposable or isolated test environments, never production or sensitive data. There is no DB preparer, async worker, or automatic secret redaction yet. Test attempts use the same source revision and re-create mutable input state, **not** Git worktrees.

## Design documents

- [Plan](docs/plan.md)
- [Architecture](docs/architecture.md)
- [Contracts](docs/contracts.md)
- [Evidence and security](docs/evidence-security.md)
- [Runner](docs/runner.md)
- [MCP adapter](docs/mcp.md)
- [PR split](docs/pr-split-plan.md)

## Typed evidence collection

Cases can declare `verification_points` and typed `evidence` for settings/files, SQL statements and results, HTTP request/response, and screenshots. Process stdout/stderr are indexed automatically, with SHA-256 and verification-point links. See [typed evidence](docs/typed-evidence.md). Direct DB/API/GUI capture and one-page PDF rendering are not included in this PR.
