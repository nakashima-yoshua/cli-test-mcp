"""Optional MCP adapter. Install with pip install '.[mcp]'."""
from pathlib import Path
import json
from .engine import load_json, run_suite, validate_suite, validate_case, safe_path


def build_server(workspace, registry, output):
    from mcp.server.fastmcp import FastMCP
    root = Path(workspace).resolve()
    results = Path(output).resolve()
    server = FastMCP("cli-test-mcp")

    @server.tool()
    def inspect_target(target_id: str) -> dict:
        """Inspect a registered CLI target."""
        value = load_json(registry).get(target_id)
        return {"target_id": target_id, "registered": isinstance(value, str), "path": value}

    @server.tool()
    def save_test_definition(path: str, definition: dict) -> dict:
        """Validate and save a case or suite definition inside the workspace."""
        dest = safe_path(root, path)
        if dest.suffix != ".json":
            raise ValueError("JSON file required")
        if "case_id" in definition:
            validate_case(definition, root)
        else:
            validate_suite(definition, root)
        if dest.exists():
            raise FileExistsError("existing definition cannot be overwritten")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(definition, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"path": path}

    @server.tool()
    def validate_test_definition(path: str) -> dict:
        """Validate a stored suite or case."""
        data = load_json(safe_path(root, path))
        if "case_id" in data:
            validate_case(data, root)
        else:
            validate_suite(data, root)
        return {"valid": True}

    @server.tool()
    def run_tests(suite_path: str, attempts: int = 1) -> dict:
        """Run a registered suite synchronously (asynchronous jobs are planned)."""
        return run_suite(safe_path(root, suite_path), registry, results, attempts)

    @server.tool()
    def get_test_status(run_id: str) -> dict:
        """Return persisted run status."""
        return load_json(safe_path(results, run_id + "/summary.json"))

    @server.tool()
    def get_test_results(run_id: str) -> dict:
        """Return run summary and case outcomes."""
        return load_json(safe_path(results, run_id + "/summary.json"))

    @server.tool()
    def get_evidence(run_id: str, artifact: str) -> str:
        """Read a bounded UTF-8 evidence file; no arbitrary paths."""
        path = safe_path(results, run_id + "/" + artifact)
        if path.suffix not in (".json", ".log", ".txt"):
            raise ValueError("unsupported artifact")
        if path.stat().st_size > 65536:
            raise ValueError("artifact too large")
        return path.read_text(encoding="utf-8", errors="replace")

    return server


def main():
    import os
    workspace = os.environ["CLI_TEST_WORKSPACE"]
    registry = os.environ["CLI_TEST_REGISTRY"]
    output = os.environ["CLI_TEST_RESULTS"]
    build_server(workspace, registry, output).run()


if __name__ == "__main__":
    main()
