"""Deterministic, sequential test execution. Never infer or change expectations."""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path

ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,79}$")


def now():
    return datetime.now(timezone.utc).isoformat()


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def check_id(value):
    if not isinstance(value, str) or not ID.fullmatch(value):
        raise ValueError(f"invalid identifier: {value!r}")
    return value


def safe_path(root, value):
    if not isinstance(value, str) or not value or Path(value).is_absolute():
        raise ValueError("only relative paths are allowed")
    root = Path(root).resolve()
    path = root / value
    if not path.resolve().is_relative_to(root):
        raise ValueError(f"path outside workspace: {value}")
    return path


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def capture(source, destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise FileExistsError(destination)
    before = (source.stat().st_size, sha256(source))
    shutil.copy2(source, destination)
    after = (destination.stat().st_size, sha256(destination))
    if before != after or before != (source.stat().st_size, sha256(source)):
        destination.unlink(missing_ok=True)
        raise OSError(f"source changed during capture: {source}")
    return {"path": str(destination), "size": after[0], "sha256": after[1]}


def validate_suite(suite, base):
    if suite.get("schema_version") != "1.0":
        raise ValueError("unsupported suite schema_version")
    check_id(suite["suite_id"])
    if suite.get("execution", {}).get("mode", "sequential") != "sequential":
        raise ValueError("only sequential execution is supported")
    if not isinstance(suite.get("cases"), list) or not suite["cases"]:
        raise ValueError("suite requires cases")
    ids = set()
    for item in suite["cases"]:
        check_id(item["id"])
        if item["id"] in ids:
            raise ValueError("duplicate case id")
        ids.add(item["id"])
        case = load_json(safe_path(base, item["definition"]))
        validate_case(case, base)
        if case["case_id"] != item["id"]:
            raise ValueError("case id mismatch")
    return True


def validate_case(case, base):
    if case.get("schema_version") != "1.0":
        raise ValueError("unsupported case schema_version")
    check_id(case["case_id"])
    batches = case.get("batches")
    if not isinstance(batches, list) or not batches:
        raise ValueError("case requires batches")
    ids = set()
    for batch in batches:
        check_id(batch["id"])
        check_id(batch["target"])
        if batch["id"] in ids:
            raise ValueError("duplicate batch id")
        ids.add(batch["id"])
        if not isinstance(batch.get("args", []), list) or not all(isinstance(x, str) for x in batch.get("args", [])):
            raise ValueError("args must be a string array")
        if not 0 < batch.get("timeout_seconds", 60) <= 3600:
            raise ValueError("invalid timeout")
        if not isinstance(batch.get("environment", {}), dict):
            raise ValueError("environment must be an object")
    for step in case.get("setup", []):
        if step.get("type") != "copy":
            raise ValueError("unsupported setup type")
        safe_path(base, step["source"])
        safe_path(base, step["destination"])
    for log in case.get("logs", []):
        check_id(log["id"])
        if log.get("capture_after", "attempt") not in ("each_batch", "attempt"):
            raise ValueError("invalid capture_after")
        if log.get("reset", "none") not in ("none", "truncate", "delete"):
            raise ValueError("invalid reset")
        safe_path(base, log["path"].replace("*", "x").replace("?", "x"))
    for assertion in case.get("assertions", []):
        if assertion["type"] not in ("exit_code", "file_exists"):
            raise ValueError("unsupported assertion")
        if assertion["type"] == "exit_code" and assertion["batch"] not in ids:
            raise ValueError("unknown batch in assertion")
        if assertion["type"] == "file_exists":
            safe_path(base, assertion["path"])
    return True


def capture_logs(base, logs, stage, evidence, records):
    for log in logs:
        if log.get("capture_after", "attempt") != stage:
            continue
        pattern = log["path"]
        matches = sorted(base.glob(pattern))
        if log.get("required", True) and not matches:
            raise FileNotFoundError(f"required log missing: {pattern}")
        staged = []
        for index, path in enumerate(matches):
            if not path.is_file() or path.is_symlink() or not path.resolve().is_relative_to(base.resolve()):
                raise ValueError("unsafe log path")
            destination = evidence / "logs" / f"{log['id']}-{len(records):04d}-{index}-{path.name}"
            meta = capture(path, destination)
            records.append({"log_id": log["id"], "source": str(path), **meta})
            staged.append(path)
        # Reset only after all captures for this log have been verified.
        for path in staged:
            if log.get("reset", "none") == "truncate":
                path.write_bytes(b"")
            elif log.get("reset", "none") == "delete":
                path.unlink()


def run_suite(suite_file, registry_file, output_dir, attempts=1, case_ids=None):
    suite_file = Path(suite_file).resolve()
    base = suite_file.parent
    suite = load_json(suite_file)
    validate_suite(suite, base)
    registry = load_json(registry_file)
    if not isinstance(registry, dict):
        raise ValueError("registry must be an object")
    if not isinstance(attempts, int) or not 1 <= attempts <= 100:
        raise ValueError("attempts out of range")
    run_id = "RUN-" + uuid.uuid4().hex[:16]
    run_dir = Path(output_dir).resolve() / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    summary = {"schema_version": "1.0", "run_id": run_id, "status": "running", "cases": []}
    write_json(run_dir / "summary.json", summary)
    selected = set(case_ids) if case_ids else None
    if selected and not selected.issubset({c["id"] for c in suite["cases"]}):
        raise ValueError("unknown case selected")
    try:
        stop = False
        for ref in suite["cases"]:
            if stop or (selected and ref["id"] not in selected):
                continue
            case = load_json(safe_path(base, ref["definition"]))
            for number in range(1, attempts + 1):
                attempt_id = f"ATTEMPT-{number:03d}"
                evidence = run_dir / ref["id"] / attempt_id
                evidence.mkdir(parents=True, exist_ok=False)
                result = {"case_id": ref["id"], "attempt_id": attempt_id, "execution_status": "running",
                          "verdict": "not_evaluated", "evidence_status": "pending",
                          "cleanup_status": "pending", "batches": [], "logs": [], "checks": []}
                try:
                    for step in case.get("setup", []):
                        source = safe_path(base, step["source"])
                        dest = safe_path(base, step["destination"])
                        if not source.is_file() or source.is_symlink():
                            raise ValueError("unsafe setup source")
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(source, dest)
                    for batch in case["batches"]:
                        executable = registry.get(batch["target"])
                        if not isinstance(executable, str):
                            raise ValueError(f"unregistered target: {batch['target']}")
                        command = Path(executable).resolve()
                        if not command.is_file():
                            raise ValueError("target executable missing")
                        folder = evidence / "batches" / batch["id"]
                        folder.mkdir(parents=True)
                        env = dict(os.environ)
                        env.update(batch.get("environment", {}))
                        try:
                            with (folder / "stdout.log").open("wb") as stdout, (folder / "stderr.log").open("wb") as stderr:
                                proc = subprocess.run([str(command), *batch.get("args", [])], cwd=base,
                                    env=env, stdout=stdout, stderr=stderr,
                                    timeout=batch.get("timeout_seconds", 60), check=False)
                            code = proc.returncode
                            timed_out = False
                        except subprocess.TimeoutExpired:
                            code, timed_out = None, True
                        result["batches"].append({"id": batch["id"], "exit_code": code, "timed_out": timed_out})
                        capture_logs(base, case.get("logs", []), "each_batch", evidence, result["logs"])
                        if (timed_out or code != 0) and not batch.get("continue_on_failure", False):
                            break
                    capture_logs(base, case.get("logs", []), "attempt", evidence, result["logs"])
                    for assertion in case.get("assertions", []):
                        if assertion["type"] == "exit_code":
                            found = next((b for b in result["batches"] if b["id"] == assertion["batch"]), None)
                            actual = found["exit_code"] if found else None
                            passed = found is not None and actual == assertion["equals"]
                        else:
                            actual = safe_path(base, assertion["path"]).is_file()
                            passed = actual
                        result["checks"].append({"type": assertion["type"], "passed": passed, "actual": actual})
                    result["execution_status"] = "completed"
                    result["verdict"] = "passed" if result["checks"] and all(c["passed"] for c in result["checks"]) else "failed"
                    result["evidence_status"] = "verified"
                    result["cleanup_status"] = "completed"
                except Exception as exc:
                    result["execution_status"] = "error"
                    result["evidence_status"] = "failed"
                    result["cleanup_status"] = "skipped"
                    result["error"] = f"{type(exc).__name__}: {exc}"
                finally:
                    write_json(evidence / "result.json", result)
                    write_json(evidence / "manifest.json", {"run_id": run_id, "case_id": ref["id"],
                        "attempt_id": attempt_id, "recorded_at": now(), "logs": result["logs"]})
                    summary["cases"].append({k: result[k] for k in ("case_id", "attempt_id",
                        "execution_status", "verdict", "evidence_status", "cleanup_status")})
                    write_json(run_dir / "summary.json", summary)
                if result["execution_status"] == "error" or (
                    result["verdict"] == "failed" and suite.get("execution", {}).get("stop_on_failure", False)):
                    stop = True
                    break
        summary["status"] = "completed" if not any(c["execution_status"] == "error" for c in summary["cases"]) else "error"
    except Exception:
        summary["status"] = "error"
        raise
    finally:
        write_json(run_dir / "summary.json", summary)
    return summary
