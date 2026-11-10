"""Typed evidence: capture, hashes, traceability and failure containment."""
import hashlib
import json
import sys

import pytest

from cli_test_mcp.definitions import DefinitionError, validate_case
from cli_test_mcp.engine import run_suite


def make_case(root, *, missing_required=False, optional_missing=False):
    (root / "fixtures").mkdir()
    (root / "fixtures" / "app.ini").write_text("mode=test\n")
    script = """from pathlib import Path
import base64
for folder in ('db', 'api', 'screens'):
    Path(folder).mkdir()
Path('db/query.sql').write_text('SELECT id FROM orders WHERE id = :id;')
Path('db/params.json').write_text('{"id": "ORD-1001"}')
Path('db/result.csv').write_text('id\\nORD-1001\\n')
Path('api/request.json').write_text('{"id": "ORD-1001"}')
Path('api/response.json').write_text('{"status": 200}')
Path('screens/dialog.png').write_bytes(base64.b64decode(
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO/j4QAAAABJRU5ErkJggg=='))
"""
    (root / "fixtures" / "batch.py").write_text(script)
    result_file = "db/missing.csv" if missing_required else "db/result.csv"
    extra = ([{"id": "optional", "kind": "file", "required": False,
               "artifacts": {"content": "optional-missing.txt"}}] if optional_missing else [])
    case = {
        "schema_version": "1.0", "case_id": "TC1",
        "setup": [
            {"type": "copy", "source": "fixtures/batch.py", "destination": "batch.py"},
            {"type": "copy", "source": "fixtures/app.ini", "destination": "app.ini"},
        ],
        "verification_points": [
            {"id": "VP-DB", "description": "Order exists", "expected": "one row"},
            {"id": "VP-API", "description": "API acknowledged", "expected": "200"},
            {"id": "VP-CONFIG", "description": "Correct settings", "expected": "test mode"},
        ],
        "batches": [{"id": "B1", "target": "python", "args": ["batch.py"],
                     "verification_point_ids": ["VP-API"]}],
        "assertions": [
            {"type": "exit_code", "batch": "B1", "equals": 0,
             "verification_point_ids": ["VP-API"]},
            {"type": "file_exists", "path": "db/result.csv",
             "verification_point_ids": ["VP-DB"]},
            {"type": "file_exists", "path": "app.ini",
             "verification_point_ids": ["VP-CONFIG"]},
        ],
        "evidence": [
            {"id": "config", "kind": "file", "capture_after": "setup",
             "artifacts": {"content": "app.ini"}, "verification_point_ids": ["VP-CONFIG"]},
            {"id": "db-after", "kind": "sql", "artifacts": {
                "statement": "db/query.sql", "parameters": "db/params.json", "result": result_file
             }, "verification_point_ids": ["VP-DB"]},
            {"id": "api", "kind": "http", "artifacts": {
                "request": "api/request.json", "response": "api/response.json"
             }, "verification_point_ids": ["VP-API"]},
            {"id": "dialog", "kind": "screenshot", "artifacts": {"image": "screens/dialog.png"}},
            *extra,
        ]
    }
    (root / "case.json").write_text(json.dumps(case))
    (root / "suite.json").write_text(json.dumps({
        "schema_version": "1.0", "suite_id": "SC1",
        "cases": [{"id": "TC1", "definition": "case.json"}]
    }))
    (root / "registry.json").write_text(json.dumps({"python": sys.executable}))
    return case


def execute(root):
    return run_suite(root / "suite.json", root / "registry.json",
                     root / "results", runtime_dir=root / "runtime")


def attempt(root, summary):
    return root / "results" / summary["run_id"] / "TC1" / "ATTEMPT-001"


def test_typed_evidence_and_verification_points(tmp_path):
    make_case(tmp_path)
    summary = execute(tmp_path)
    assert summary["cases"][0]["verdict"] == "passed"
    folder = attempt(tmp_path, summary)
    result = json.loads((folder / "result.json").read_text())
    assert {e["kind"] for e in result["evidence"]} == {
        "file", "sql", "http", "process", "screenshot"
    }
    assert {p["status"] for p in result["verification_points"]} == {"passed"}
    for record in result["evidence"]:
        for artifact in record["artifacts"].values():
            raw = (folder / artifact["path"]).read_bytes()
            assert artifact["size"] == len(raw)
            assert artifact["sha256"] == hashlib.sha256(raw).hexdigest()
    sql = next(e for e in result["evidence"] if e["kind"] == "sql")
    assert set(sql["artifacts"]) == {"statement", "parameters", "result"}
    assert (folder / sql["artifacts"]["statement"]["path"]).read_text().startswith("SELECT")
    assert "ORD-1001" in (folder / sql["artifacts"]["result"]["path"]).read_text()
    assert json.loads((folder / "manifest.json").read_text())["suite_id"] == "SC1"
    assert not (tmp_path / "runtime" / summary["run_id"] / "slot-01" / "work").exists()


def test_required_missing_evidence_is_error(tmp_path):
    make_case(tmp_path, missing_required=True)
    summary = execute(tmp_path)
    assert summary["status"] == "error"
    assert summary["cases"][0]["evidence_status"] == "failed"
    assert summary["cases"][0]["cleanup_status"] == "skipped"


def test_optional_missing_evidence_is_recorded(tmp_path):
    make_case(tmp_path, optional_missing=True)
    summary = execute(tmp_path)
    assert summary["cases"][0]["verdict"] == "passed"
    result = json.loads((attempt(tmp_path, summary) / "result.json").read_text())
    record = next(e for e in result["evidence"] if e["id"] == "optional")
    assert record["status"] == "missing"
    assert record["missing_roles"] == ["content"]


@pytest.mark.parametrize("mutation", [
    lambda c: c["evidence"][1]["artifacts"].update({"result": "../escape.csv"}),
    lambda c: c["evidence"][1]["artifacts"].pop("statement"),
    lambda c: c["evidence"][0].update({"verification_point_ids": ["UNKNOWN"]}),
    lambda c: c["verification_points"].append(c["verification_points"][0]),
    lambda c: c["evidence"].append(c["evidence"][0]),
])
def test_bad_evidence_contract(tmp_path, mutation):
    case = make_case(tmp_path)
    mutation(case)
    with pytest.raises(DefinitionError):
        validate_case(case, tmp_path)


def test_point_without_assertion_is_not_passed(tmp_path):
    case = make_case(tmp_path)
    case["assertions"] = [x for x in case["assertions"]
                          if "VP-CONFIG" not in x.get("verification_point_ids", [])]
    (tmp_path / "case.json").write_text(json.dumps(case))
    summary = execute(tmp_path)
    assert summary["cases"][0]["verdict"] == "failed"
    result = json.loads((attempt(tmp_path, summary) / "result.json").read_text())
    point = next(p for p in result["verification_points"] if p["id"] == "VP-CONFIG")
    assert point["status"] == "not_evaluated"
