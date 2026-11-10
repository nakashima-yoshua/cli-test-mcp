"""MCP tool behavior without requiring the optional SDK or a live network."""
import json
import sys

import pytest

from cli_test_mcp.definitions import DefinitionError
from cli_test_mcp.mcp_server import create_handlers


def valid_case():
    return {"schema_version": "1.0", "case_id": "TC1",
            "setup": [{"type": "copy", "source": "fixtures/batch.py", "destination": "batch.py"}],
            "batches": [{"id": "B1", "target": "python", "args": ["batch.py"]}],
            "assertions": [{"type": "exit_code", "batch": "B1", "equals": 0}]}


def valid_suite():
    return {"schema_version": "1.0", "suite_id": "S1",
            "cases": [{"id": "TC1", "definition": "case.json"}]}


def test_mcp_tool_lifecycle(tmp_path):
    workspace = tmp_path / "definitions"
    workspace.mkdir()
    (workspace / "fixtures").mkdir()
    (workspace / "fixtures" / "batch.py").write_text("print('hello')\n")
    registry = tmp_path / "targets.json"
    registry.write_text(json.dumps({"python": sys.executable}))
    handlers = create_handlers(workspace, registry, tmp_path / "results")
    assert handlers["inspect_target"]("python")["registered"]
    assert handlers["save_test_definition"]("case.json", valid_case())["saved"]
    assert handlers["save_test_definition"]("suite.json", valid_suite())["saved"]
    assert handlers["validate_test_definition"]("suite.json") == {"valid": True}
    summary = handlers["run_tests"]("suite.json")
    assert summary["cases"][0]["verdict"] == "passed"
    run_id = summary["run_id"]
    assert handlers["get_test_status"](run_id)["status"] == "completed"
    result = handlers["get_test_results"](run_id)
    assert result["results"][0]["checks"][0]["passed"]
    text = handlers["get_evidence"](run_id, "TC1/ATTEMPT-001/batches/B1/stdout.log")
    assert "hello" in text


def test_mcp_disallows_traversal_and_overwrite(tmp_path):
    root = tmp_path / "definitions"
    root.mkdir()
    registry = tmp_path / "targets.json"
    registry.write_text("{}")
    handlers = create_handlers(root, registry, tmp_path / "results")
    with pytest.raises(DefinitionError):
        handlers["save_test_definition"]("../bad.json", valid_case())
    handlers["save_test_definition"]("case.json", {"schema_version": "1.0", "case_id": "TC1",
        "batches": [{"id": "B1", "target": "target"}]})
    with pytest.raises(FileExistsError):
        handlers["save_test_definition"]("case.json", {"schema_version": "1.0", "case_id": "TC1",
            "batches": [{"id": "B1", "target": "target"}]})
    with pytest.raises(DefinitionError):
        handlers["get_evidence"]("RUN-123", "../../secrets.txt")
