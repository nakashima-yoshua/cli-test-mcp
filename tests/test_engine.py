"""Test attempt reproducibility and failure containment with a harmless Python program."""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from cli_test_mcp.cli import main
from cli_test_mcp.engine import run_suite


def make_suite(root: Path, script: str, *, logs=None, assertions=None, attempts=1, timeout=5):
    (root / "fixtures").mkdir(exist_ok=True)
    (root / "fixtures" / "batch.py").write_text(script)
    case = {
        "schema_version": "1.0", "case_id": "TC1",
        "setup": [{"type": "copy", "source": "fixtures/batch.py", "destination": "batch.py"}],
        "batches": [{"id": "B1", "target": "python", "args": ["batch.py"], "timeout_seconds": timeout}],
        "logs": logs or [],
        "assertions": assertions or [{"type": "exit_code", "batch": "B1", "equals": 0}]
    }
    (root / "case.json").write_text(json.dumps(case))
    suite = {"schema_version": "1.0", "suite_id": "S1", "cases": [{"id": "TC1", "definition": "case.json"}]}
    (root / "suite.json").write_text(json.dumps(suite))
    (root / "registry.json").write_text(json.dumps({"python": sys.executable}))
    return root / "suite.json", root / "registry.json"


def test_repeated_attempts_are_isolated(tmp_path):
    suite, registry = make_suite(tmp_path, "from pathlib import Path\n"
        "Path('count.txt').write_text(Path('count.txt').read_text() + 'x' if Path('count.txt').exists() else 'x')\n"
        "Path('app.log').write_text('abc')\n",
        logs=[{"id": "app", "path": "app.log", "reset": "truncate"}],
        assertions=[{"type": "exit_code", "batch": "B1", "equals": 0},
                    {"type": "file_exists", "path": "count.txt"}])
    summary = run_suite(suite, registry, tmp_path / "results", attempts=2, runtime_dir=tmp_path / "runtime")
    assert [c["verdict"] for c in summary["cases"]] == ["passed", "passed"]
    run_root = tmp_path / "results" / summary["run_id"] / "TC1"
    for number in (1, 2):
        attempt = run_root / f"ATTEMPT-{number:03d}"
        assert (attempt / "outputs" / "count.txt").read_text() == "x"
        assert (attempt / "logs").is_dir()
        assert (attempt / "manifest.json").exists()
    assert not (tmp_path / "runtime" / summary["run_id"] / "slot-01" / "work").exists()
    assert not (tmp_path / "count.txt").exists()


def test_missing_log_keeps_previously_captured_source(tmp_path):
    suite, registry = make_suite(tmp_path, "from pathlib import Path\nPath('app.log').write_text('keep')\n",
        logs=[{"id": "first", "path": "app.log", "reset": "truncate"},
              {"id": "missing", "path": "missing.log", "reset": "truncate"}])
    summary = run_suite(suite, registry, tmp_path / "results", runtime_dir=tmp_path / "runtime")
    assert summary["status"] == "error"
    assert summary["cases"][0]["evidence_status"] == "failed"
    work = tmp_path / "runtime" / summary["run_id"] / "slot-01" / "work"
    assert (work / "app.log").read_text() == "keep"


def test_nonzero_exit_and_cli_codes(tmp_path, monkeypatch, capsys):
    suite, registry = make_suite(tmp_path, "import sys\nsys.exit(4)\n")
    monkeypatch.setattr(sys, "argv", ["cli-test", "run", str(suite), "--registry", str(registry),
                                       "--output", str(tmp_path / "results")])
    assert main() == 1
    assert '"verdict": "failed"' in capsys.readouterr().out


def test_engine_error_exit_code(tmp_path, monkeypatch):
    suite, registry = make_suite(tmp_path, "print('hello')\n",
                                 logs=[{"id": "missing", "path": "notfound.log"}])
    monkeypatch.setattr(sys, "argv", ["cli-test", "run", str(suite), "--registry", str(registry),
                                       "--output", str(tmp_path / "results")])
    assert main() == 2


@pytest.mark.skipif(os.name != "posix", reason="POSIX process group test")
def test_timeout_kills_grandchild(tmp_path):
    marker = tmp_path / "outside-marker"
    code = ("import subprocess, sys, time\n"
            "subprocess.Popen([sys.executable, '-c', " + repr("import time; from pathlib import Path; time.sleep(3); Path(" + repr(str(marker)) + ").write_text('bad')") + "])\n"
            "time.sleep(30)\n")
    suite, registry = make_suite(tmp_path, code, timeout=1)
    summary = run_suite(suite, registry, tmp_path / "results", runtime_dir=tmp_path / "runtime")
    assert summary["cases"][0]["verdict"] == "failed"
    result_path = tmp_path / "results" / summary["run_id"] / "TC1" / "ATTEMPT-001" / "result.json"
    result = json.loads(result_path.read_text())
    assert result["batches"][0]["timed_out"]
    time.sleep(3.3)
    assert not marker.exists()
