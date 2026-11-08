"""Optional stdio MCP facade; business logic remains in the engine."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Callable

from .definitions import DefinitionError, load_json, safe_path, validate_case, validate_suite
from .engine import run_suite


def create_handlers(workspace: str | Path, registry: str | Path, output: str | Path) -> dict[str, Callable]:
    """Build tool handlers separately so they can be tested without an MCP SDK."""
    root = Path(workspace).resolve()
    registry_file = Path(registry).resolve()
    results = Path(output).resolve()
    if results == root:
        raise DefinitionError("results directory must differ from the definition workspace")

    def inspect_target(target_id: str) -> dict:
        """Inspect a registered test executable without running it."""
        registrations = load_json(registry_file)
        if not isinstance(registrations, dict):
            raise DefinitionError("registry must be an object")
        value = registrations.get(target_id)
        return {"target_id": target_id, "registered": isinstance(value, str), "path": value}

    def save_test_definition(path: str, definition: dict) -> dict:
        """Validate and save a case or suite JSON without overwriting an existing revision."""
        destination = safe_path(root, path)
        if destination.suffix != ".json":
            raise DefinitionError("definition must use .json extension")
        if not isinstance(definition, dict):
            raise DefinitionError("definition must be an object")
        if "case_id" in definition:
            validate_case(definition, root)
        else:
            validate_suite(definition, root)
        destination.parent.mkdir(parents=True, exist_ok=True)
        # Exclusive creation guards against overwrite/races between MCP clients.
        with destination.open("x", encoding="utf-8") as stream:
            json.dump(definition, stream, indent=2, ensure_ascii=False)
            stream.write("\n")
        return {"path": path, "saved": True}

    def validate_test_definition(path: str) -> dict:
        """Validate a stored case or suite JSON definition."""
        definition = load_json(safe_path(root, path))
        if isinstance(definition, dict) and "case_id" in definition:
            validate_case(definition, root)
        else:
            validate_suite(definition, root)
        return {"valid": True}

    def run_tests(suite_path: str, attempts: int = 1, case_ids: list[str] | None = None) -> dict:
        """Execute a suite synchronously; asynchronous orchestration is not yet supported."""
        return run_suite(safe_path(root, suite_path), registry_file, results, attempts, case_ids=case_ids)

    def get_test_status(run_id: str) -> dict:
        """Return the persisted run summary and completion status."""
        return load_json(safe_path(results, run_id + "/summary.json"))

    def get_test_results(run_id: str) -> dict:
        """Return completed/partial case results and their evidence metadata."""
        summary = get_test_status(run_id)
        cases = []
        for item in summary["cases"]:
            path = safe_path(results, run_id + "/" + item["case_id"] + "/" + item["attempt_id"] + "/result.json")
            cases.append(load_json(path))
        return {"summary": summary, "results": cases}

    def get_evidence(run_id: str, artifact: str) -> str:
        """Read one small UTF-8 evidence file, bounded to a known run directory."""
        if not run_id.startswith("RUN-") or len(run_id) > 80 or any(x in run_id for x in ("/", "\\", "..")):
            raise DefinitionError("invalid run ID")
        run_root = safe_path(results, run_id)
        file = safe_path(run_root, artifact)
        if file.is_symlink() or file.suffix not in (".json", ".log", ".txt"):
            raise DefinitionError("unsupported or unsafe evidence file")
        if not file.is_file():
            raise FileNotFoundError(file)
        if file.stat().st_size > 65536:
            raise DefinitionError("evidence file is larger than 65536 bytes")
        return file.read_text(encoding="utf-8", errors="replace")

    return {
        "inspect_target": inspect_target,
        "save_test_definition": save_test_definition,
        "validate_test_definition": validate_test_definition,
        "run_tests": run_tests,
        "get_test_status": get_test_status,
        "get_test_results": get_test_results,
        "get_evidence": get_evidence,
    }


def build_server(workspace: str | Path, registry: str | Path, output: str | Path):
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:
        raise RuntimeError("Install the optional MCP dependency with pip install '.[mcp]'") from exc
    server = FastMCP("cli-test-mcp")
    for handler in create_handlers(workspace, registry, output).values():
        server.tool()(handler)
    return server


def main() -> None:
    build_server(
        os.environ["CLI_TEST_WORKSPACE"],
        os.environ["CLI_TEST_REGISTRY"],
        os.environ["CLI_TEST_RESULTS"],
    ).run()


if __name__ == "__main__":
    main()
