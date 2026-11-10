"""Deterministic sequential runner. No AI planning or MCP dependencies."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import signal
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .definitions import DefinitionError, load_json, safe_path, validate_suite
from .evidence import capture_declared, evaluate_points, record_process


def _now():
    return datetime.now(timezone.utc).isoformat()


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for data in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(data)
    return digest.hexdigest()


def _metadata(path: Path) -> dict:
    return {"path": str(path), "size": path.stat().st_size, "sha256": _hash(path)}


def _snapshot(source: Path, destination: Path) -> dict:
    if not source.is_file() or source.is_symlink():
        raise DefinitionError(f"unsafe evidence source: {source}")
    if destination.exists():
        raise FileExistsError(destination)
    before = (source.stat().st_size, _hash(source))
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    after = (destination.stat().st_size, _hash(destination))
    if before != after or before != (source.stat().st_size, _hash(source)):
        destination.unlink(missing_ok=True)
        raise OSError(f"source changed during evidence capture: {source}")
    return _metadata(destination)


def _prepare_work(base: Path, work: Path, steps: list) -> list[dict]:
    """Reuse one slot; create fresh mutable inputs for every attempt."""
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    inputs = []
    for index, step in enumerate(steps):
        source = safe_path(base, step["source"])
        destination = safe_path(work, step["destination"])
        metadata = _snapshot(source, destination)
        inputs.append({"step": index, "source": str(source), **metadata})
    return inputs


def _terminate_tree(proc: subprocess.Popen) -> None:
    """Stop descendants in their dedicated POSIX session or Windows task tree."""
    if os.name == "posix":
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    elif os.name == "nt":
        # Windows has no os.killpg. taskkill stops descendants where allowed.
        subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       timeout=15, check=False)
    if proc.poll() is None:
        proc.kill()
    proc.wait()


def _execute_batch(work: Path, batch: dict, registry: dict, evidence: Path) -> dict:
    target = registry.get(batch["target"])
    if not isinstance(target, str) or not Path(target).is_absolute():
        raise DefinitionError(f"unregistered or non-absolute target: {batch['target']}")
    executable = Path(target).resolve()
    if not executable.is_file():
        raise FileNotFoundError(f"target executable missing: {batch['target']}")
    output = evidence / "batches" / batch["id"]
    output.mkdir(parents=True, exist_ok=False)
    env = dict(os.environ)
    env.update(batch.get("environment", {}))
    timed_out = False
    with (output / "stdout.log").open("wb") as stdout, (output / "stderr.log").open("wb") as stderr:
        proc = subprocess.Popen(
            [str(executable), *batch.get("args", [])], cwd=work, env=env,
            stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr,
            start_new_session=(os.name == "posix"),
            creationflags=(subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0),
        )
        try:
            proc.wait(timeout=batch.get("timeout_seconds", 60))
        except subprocess.TimeoutExpired:
            timed_out = True
        finally:
            _terminate_tree(proc)
    return {"id": batch["id"], "exit_code": None if timed_out else proc.returncode,
            "timed_out": timed_out,
            "stdout": _metadata(output / "stdout.log"),
            "stderr": _metadata(output / "stderr.log")}


def _collect_logs(work: Path, logs: list, stage: str, evidence: Path, records: list) -> None:
    """Snapshot and verify *every* matching log before any reset at this stage."""
    staged = []
    seen = set()
    for log in logs:
        if log.get("capture_after", "attempt") != stage:
            continue
        matches = sorted(work.glob(log["path"]))
        if log.get("required", True) and not matches:
            raise FileNotFoundError(f"required log missing: {log['path']}")
        for index, source in enumerate(matches):
            if not source.is_file() or source.is_symlink() or not source.resolve().is_relative_to(work.resolve()):
                raise DefinitionError(f"unsafe log path: {source}")
            if source in seen:
                raise DefinitionError(f"overlapping log declarations: {source}")
            seen.add(source)
            destination = evidence / "logs" / f"{log['id']}-{stage}-{len(records):04d}-{index}-{source.name}"
            record = {"log_id": log["id"], "stage": stage, "source": str(source),
                      **_snapshot(source, destination)}
            records.append(record)
            staged.append((source, log.get("reset", "none")))
    # Capture failures above leave every source untouched. Never reset live external logs.
    for source, reset in staged:
        if reset == "truncate":
            source.write_bytes(b"")
        elif reset == "delete":
            source.unlink()


def _evaluate_assertions(work: Path, assertions: list, batches: list, evidence: Path) -> tuple[list, list]:
    checks, outputs = [], []
    for assertion in assertions:
        if assertion["type"] == "exit_code":
            found = next((b for b in batches if b["id"] == assertion["batch"]), None)
            actual = found["exit_code"] if found else None
            passed = bool(found and not found["timed_out"] and actual == assertion["equals"])
        else:
            path = safe_path(work, assertion["path"])
            actual = path.is_file() and not path.is_symlink()
            passed = actual
            if passed:
                outputs.append({"source": str(path), **_snapshot(path, evidence / "outputs" / assertion["path"])})
        checks.append({"type": assertion["type"], "passed": passed, "actual": actual,
                       "expected": assertion.get("equals", True),
                       "verification_point_ids": assertion.get("verification_point_ids", [])})
    return checks, outputs


def run_suite(suite_file: str | Path, registry_file: str | Path, output_dir: str | Path,
              attempts: int = 1, case_ids: list[str] | None = None,
              runtime_dir: str | Path | None = None) -> dict:
    suite_file = Path(suite_file).resolve()
    base = suite_file.parent
    suite = load_json(suite_file)
    validate_suite(suite, base)
    registry = load_json(registry_file)
    if not isinstance(registry, dict):
        raise DefinitionError("registry must be a JSON object")
    if type(attempts) is not int or not 1 <= attempts <= 100:
        raise DefinitionError("attempts must be an integer from 1 to 100")
    available = {ref["id"] for ref in suite["cases"]}
    selected = set(case_ids) if case_ids is not None else available
    if not selected or not selected.issubset(available):
        raise DefinitionError("unknown or empty case selection")

    results_root = Path(output_dir).resolve()
    runtime_root = Path(runtime_dir).resolve() if runtime_dir is not None else results_root / "_runtime"
    # Runtime may be an ignored subdirectory, but must never replace the
    # definition directory or the evidence directory themselves.
    if runtime_root in (base, results_root):
        raise DefinitionError("runtime must not be the results or definition directory")
    if runtime_root.is_relative_to(results_root) and runtime_root != results_root / "_runtime":
        raise DefinitionError("runtime may not overlap the evidence namespace")

    run_id = "RUN-" + uuid.uuid4().hex[:16]
    run_dir = results_root / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    slot = runtime_root / run_id / "slot-01" / "work"
    summary = {"schema_version": "1.0", "run_id": run_id, "status": "running", "cases": []}
    _write_json(run_dir / "summary.json", summary)
    stop = False
    for ref in suite["cases"]:
        if ref["id"] not in selected or stop:
            continue
        case = load_json(safe_path(base, ref["definition"]))
        for number in range(1, attempts + 1):
            attempt_id = f"ATTEMPT-{number:03d}"
            evidence = run_dir / ref["id"] / attempt_id
            evidence.mkdir(parents=True, exist_ok=False)
            result = {"suite_id": suite["suite_id"], "case_id": ref["id"], "attempt_id": attempt_id,
                      "execution_status": "running", "verdict": "not_evaluated",
                      "evidence_status": "pending", "cleanup_status": "pending",
                      "batches": [], "logs": [], "inputs": [], "outputs": [], "checks": [],
                      "evidence": [], "verification_points": []}
            try:
                result["inputs"] = _prepare_work(base, slot, case.get("setup", []))
                capture_declared(slot, evidence, case.get("evidence", []),
                                 "setup", result["evidence"], _snapshot)
                for batch in case["batches"]:
                    record = _execute_batch(slot, batch, registry, evidence)
                    result["batches"].append(record)
                    result["evidence"].append(record_process(batch, record, evidence))
                    capture_declared(slot, evidence, case.get("evidence", []),
                                     "each_batch", result["evidence"], _snapshot, batch["id"])
                    _collect_logs(slot, case.get("logs", []), "each_batch", evidence, result["logs"])
                    if (record["timed_out"] or record["exit_code"] != 0) and not batch.get("continue_on_failure", False):
                        break
                _collect_logs(slot, case.get("logs", []), "attempt", evidence, result["logs"])
                capture_declared(slot, evidence, case.get("evidence", []),
                                 "attempt", result["evidence"], _snapshot)
                result["checks"], result["outputs"] = _evaluate_assertions(
                    slot, case.get("assertions", []), result["batches"], evidence)
                result["verification_points"] = evaluate_points(
                    case.get("verification_points", []), result["checks"], result["evidence"])
                result["execution_status"] = "completed"
                checks_pass = bool(result["checks"]) and all(c["passed"] for c in result["checks"])
                points_pass = all(p["status"] == "passed" for p in result["verification_points"])
                result["verdict"] = "passed" if checks_pass and points_pass else "failed"
                result["evidence_status"] = "verified"
                try:
                    shutil.rmtree(slot)
                    result["cleanup_status"] = "completed" if not slot.exists() else "failed"
                    if result["cleanup_status"] == "failed":
                        result["execution_status"] = "error"
                except OSError as exc:
                    result["cleanup_status"] = "failed"
                    result["execution_status"] = "error"
                    result["error"] = f"cleanup failed: {exc}"
            except Exception as exc:
                # Preserve the workspace for diagnosis; don't attempt another run on it.
                result["execution_status"] = "error"
                result["evidence_status"] = "failed"
                result["cleanup_status"] = "skipped"
                result["error"] = f"{type(exc).__name__}: {exc}"
            finally:
                manifest = {"run_id": run_id, "suite_id": suite["suite_id"], "case_id": ref["id"],
                            "attempt_id": attempt_id, "recorded_at": _now(),
                            "inputs": result["inputs"], "batches": result["batches"],
                            "logs": result["logs"], "outputs": result["outputs"],
                            "evidence": result["evidence"],
                            "verification_points": result["verification_points"],
                            "cleanup_status": result["cleanup_status"]}
                _write_json(evidence / "result.json", result)
                _write_json(evidence / "manifest.json", manifest)
                summary["cases"].append({k: result[k] for k in
                    ("case_id", "attempt_id", "execution_status", "verdict", "evidence_status", "cleanup_status")})
                _write_json(run_dir / "summary.json", summary)
            if (result["execution_status"] == "error" or result["cleanup_status"] != "completed"
                or (result["verdict"] == "failed" and suite.get("execution", {}).get("stop_on_failure", False))):
                stop = True
                break
    summary["status"] = "error" if any(c["execution_status"] == "error" for c in summary["cases"]) else "completed"
    _write_json(run_dir / "summary.json", summary)
    return summary
