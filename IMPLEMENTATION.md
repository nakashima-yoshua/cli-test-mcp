# CLI Test MCP — initial implementation

This branch contains a **prototype**, not a production-ready release.

## Install
```bash
python -m pip install -e '.[dev,mcp]'
pytest
```

## Run
Register an executable using an absolute path in a JSON object:
```json
{"batch-a": "/absolute/path/to/executable"}
```

```bash
cli-test validate /path/to/suite.json
cli-test run /path/to/suite.json --registry /path/to/targets.json --output /path/to/results
```

## MCP (stdio)
Set `CLI_TEST_WORKSPACE`, `CLI_TEST_REGISTRY`, and `CLI_TEST_RESULTS`, then run `cli-test-mcp`.

## Important limitations
- Initial adapter's run_tests is synchronous; async job orchestration is not implemented.
- DB setup, complete JSON Schema, robust child-process lifecycle control, input/output snapshotting, log redaction and sandbox isolation are not implemented.
- Only run trusted test programs in an isolated test workspace. Registered executables can perform arbitrary operations with the current OS user's privileges.
- Do not use against production environments or sensitive data.
- Implementation and tests have not yet been executed in CI.

See [plan](docs/plan.md), [architecture](docs/architecture.md), [contracts](docs/contracts.md), and [evidence/security](docs/evidence-security.md).
