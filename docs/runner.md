# Sequential runner (PR-B)

The engine is deterministic: upstream AI/humans create test definitions and expected values; the engine does not infer or relax them. Source revision and definitions are read-only; **no Git worktrees are created**.

## Isolation model

- A single `slot-01/work` is re-created from declared `setup` input copies before **each** attempt and case. Unlisted files from a previous attempt do not survive successful cleanup.
- CLI executables come from a local JSON registry of absolute paths; they run with their caller's OS privileges. This is **state reproducibility, not a security sandbox**. Do not execute untrusted targets or production workloads.
- All fixture sources must be workspace-relative; destination paths, stdout/stderr, declared logs and asserted outputs are captured in per-attempt evidence directories. A fresh run and attempt ID prevents overwriting.
- `capture_after: each_batch` logs are collected and safely reset once for each completed batch. `capture_after: attempt` logs are collected after the last executed batch. All declared logs at the same collection stage must be captured and verified **before resetting any**. If stage capture fails, no log at that stage is reset; the slot is preserved for diagnosis and the run stops.
- On POSIX, the runner starts a new subprocess session and kills lingering descendants at batch exit/timeout. On Windows, `taskkill /T /F` is best-effort and cannot guarantee all descendants are gone without a Job Object. Windows process-tree isolation remains a separate hardening task.
- A failed cleanup or capture marks the execution as errored. Never reuse a potentially dirty slot after a failure.
- The `runtime` directory is mutable (default `<output>/_runtime`); the evidence directory is append-only by unique `RUN-ID/CASE-ID/ATTEMPT-ID`. The caller must use test-only OS and DB permissions.

## CLI

```bash
python -m pip install -e '.[dev]'
cli-test validate path/to/suite.json
cli-test run path/to/suite.json --registry path/to/targets.json \
  --runtime /tmp/cli-test-runtime --output /tmp/cli-test-results --attempts 2
```

CLI exit code: 0 = all passed, 1 = completed with failed assertions, 2 = execution/definition error.

MCP and DB adapters are out of scope for PR-B. A future DB preparer will acquire a reusable schema slot, restore a known initial state, and quarantine a failed restoration. Schemas are not generated per test. A separate schema alone does not provide automatic table overrides or isolation from cross-schema writes.
