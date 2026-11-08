# MCP stdio adapter (PR-C)

This is a thin adapter on top of PR-A contracts and PR-B runner. It requires an optional install: `pip install -e '.[mcp]'`.

Set `CLI_TEST_WORKSPACE` to the test-definition directory, `CLI_TEST_REGISTRY` to an absolute executable registry JSON, and `CLI_TEST_RESULTS` to the immutable-results destination; start `cli-test-mcp` as a local stdio MCP server.

Tools:

| Name | Behavior |
|---|---|
| `inspect_target(target_id)` | Reads a target registry entry, does not execute |
| `save_test_definition(path, definition)` | Validates and creates a *new* definition JSON, never overwrites |
| `validate_test_definition(path)` | Validates a stored Case or Suite |
| `run_tests(suite_path, attempts=1, case_ids=null)` | **Synchronous** execution; returns the run summary |
| `get_test_status(run_id)` | Returns the persisted summary |
| `get_test_results(run_id)` | Returns summary and case-level results |
| `get_evidence(run_id, artifact)` | Reads a UTF-8 .json/.log/.txt file of at most 64KiB within that run |

Save referenced Case definitions before their Suite. This stage intentionally does not implement async jobs, progress polling during an active synchronous tool call, approval policies, AI-driven planning, or DB adapters. A future contract revision must introduce asynchronous `run_tests` without silently changing the v1.0 behavior.

**Security**: Registration is not a privilege boundary: these tools can run trusted executables with the MCP server OS user's privileges. Keep this server local, use test-only identities and data, protect registry/definition paths, and do not expose to untrusted clients or production resources. Evidence may contain secrets; redaction is not implemented. Runner workdir isolation alone is not a sandbox.
