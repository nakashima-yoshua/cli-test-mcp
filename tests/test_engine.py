import json
import os
import sys
from pathlib import Path

import pytest

from cli_test_mcp.engine import run_suite, safe_path, validate_case


def test_path_traversal(tmp_path):
    with pytest.raises(ValueError):
        safe_path(tmp_path, "../escape")


def test_unknown_target(tmp_path):
    case = {"schema_version": "1.0", "case_id": "TC1",
            "batches": [{"id": "B1", "target": "missing"}],
            "assertions": [{"type": "exit_code", "batch": "B1", "equals": 0}]}
    (tmp_path / "case.json").write_text(json.dumps(case))
    suite = {"schema_version": "1.0", "suite_id": "S1", "cases": [{"id": "TC1", "definition": "case.json"}]}
    (tmp_path / "suite.json").write_text(json.dumps(suite))
    (tmp_path / "registry.json").write_text("{}")
    result = run_suite(tmp_path / "suite.json", tmp_path / "registry.json", tmp_path / "results")
    assert result["status"] == "error"
    assert result["cases"][0]["evidence_status"] == "failed"


def test_capture_and_reset(tmp_path):
    script = tmp_path / "batch.py"
    script.write_text("#!/usr/bin/env python3\nfrom pathlib import Path\nPath('app.log').write_text('hello')\n")
    script.chmod(0o755)
    case = {"schema_version": "1.0", "case_id": "TC1",
            "batches": [{"id": "B1", "target": "batch"}],
            "logs": [{"id": "app", "path": "app.log", "capture_after": "attempt", "reset": "truncate"}],
            "assertions": [{"type": "exit_code", "batch": "B1", "equals": 0}]}
    (tmp_path / "case.json").write_text(json.dumps(case))
    suite = {"schema_version": "1.0", "suite_id": "S1", "cases": [{"id": "TC1", "definition": "case.json"}]}
    (tmp_path / "suite.json").write_text(json.dumps(suite))
    (tmp_path / "registry.json").write_text(json.dumps({"batch": str(script)}))
    result = run_suite(tmp_path / "suite.json", tmp_path / "registry.json", tmp_path / "results")
    assert result["cases"][0]["verdict"] == "passed"
    assert (tmp_path / "app.log").read_bytes() == b""
    run_dir = tmp_path / "results" / result["run_id"] / "TC1" / "ATTEMPT-001"
    assert list((run_dir / "logs").glob("*"))
