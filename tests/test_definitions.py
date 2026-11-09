"""Contract checks; no real programs or databases are executed."""

import json

import pytest

from cli_test_mcp.definitions import DefinitionError, safe_path, validate_case, validate_suite
from cli_test_mcp.definitions.validator import validate_result


def example_case():
    return {
        "schema_version": "1.0", "case_id": "TC1",
        "setup": [{"type": "copy", "source": "fixtures/a.ini", "destination": "work/a.ini"}],
        "batches": [{"id": "B1", "target": "batch", "args": ["--mode", "test"],
                     "environment": {"TEST_MODE": "1"}}],
        "logs": [{"id": "app", "path": "logs/app*.log", "reset": "truncate"}],
        "assertions": [{"type": "exit_code", "batch": "B1", "equals": 0},
                       {"type": "file_exists", "path": "work/output.csv"}]
    }


def test_valid_case(tmp_path):
    assert validate_case(example_case(), tmp_path)


def test_valid_suite(tmp_path):
    (tmp_path / "case.json").write_text(json.dumps(example_case()), encoding="utf-8")
    suite = {"schema_version": "1.0", "suite_id": "S1",
             "cases": [{"id": "TC1", "definition": "case.json"}]}
    assert validate_suite(suite, tmp_path)


@pytest.mark.parametrize("value", ["../escape", "/etc/passwd", "C:\\Windows\\win.ini", "a/../../b", ""])
def test_bad_path(tmp_path, value):
    with pytest.raises(DefinitionError):
        safe_path(tmp_path, value)


def test_symlink_escape(tmp_path):
    (tmp_path / "outside").symlink_to(tmp_path.parent, target_is_directory=True)
    with pytest.raises(DefinitionError):
        safe_path(tmp_path, "outside/file.log")


@pytest.mark.parametrize("field,value", [
    ("batches", [{"id": "B1", "target": "batch", "timeout_seconds": 0}]),
    ("batches", [{"id": "B1", "target": "batch", "environment": {"X": 1}}]),
    ("batches", [{"id": "B1", "target": "batch", "args": "a"}]),
    ("batches", [{"id": "B1", "target": "batch"}, {"id": "B1", "target": "batch"}]),
    ("logs", [{"id": "L1", "path": "../outside.log"}]),
    ("logs", [{"id": "L1", "path": "dir*/app.log"}]),
    ("logs", [{"id": "L1", "path": "a.log"}, {"id": "L1", "path": "b.log"}]),
    ("assertions", [{"type": "exit_code", "batch": "missing", "equals": 0}]),
    ("assertions", [{"type": "file_exists", "path": "/etc/passwd"}])
])
def test_invalid_case(tmp_path, field, value):
    case = example_case()
    case[field] = value
    with pytest.raises(DefinitionError):
        validate_case(case, tmp_path)


def test_unknown_fields_rejected(tmp_path):
    case = example_case()
    case["batches"][0]["shell"] = True
    with pytest.raises(DefinitionError):
        validate_case(case, tmp_path)


def test_suite_case_mismatch(tmp_path):
    (tmp_path / "case.json").write_text(json.dumps(example_case()))
    suite = {"schema_version": "1.0", "suite_id": "S1",
             "cases": [{"id": "TC2", "definition": "case.json"}]}
    with pytest.raises(DefinitionError):
        validate_suite(suite, tmp_path)


def test_valid_result():
    result = {"schema_version": "1.0", "run_id": "RUN-001", "status": "running", "cases": []}
    assert validate_result(result)
