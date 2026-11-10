"""Capture declared input/output evidence; do not infer or execute operations."""
from __future__ import annotations

from pathlib import Path
from typing import Callable

from .definitions import safe_path


def capture_declared(work: Path, root: Path, specs: list[dict], stage: str,
                     records: list[dict], snapshot: Callable[[Path, Path], dict],
                     batch_id: str | None = None) -> None:
    """Copy a declared group, refusing incomplete required groups."""
    for spec in specs:
        if spec.get("capture_after", "attempt") != stage:
            continue
        sources = {role: safe_path(work, name) for role, name in spec["artifacts"].items()}
        missing = [role for role, source in sources.items()
                   if not source.is_file() or source.is_symlink()]
        if missing and spec.get("required", True):
            raise FileNotFoundError(f"required evidence {spec['id']} missing: {', '.join(missing)}")
        record = {
            "id": spec["id"], "kind": spec["kind"], "capture_after": stage,
            "batch_id": batch_id, "required": spec.get("required", True),
            "verification_point_ids": spec.get("verification_point_ids", []),
            "status": "missing" if missing else "captured", "artifacts": {},
        }
        if missing:
            record["missing_roles"] = missing
        else:
            part = batch_id if stage == "each_batch" else stage
            for role, name in spec["artifacts"].items():
                target = root / "captured" / spec["id"] / part / f"{role}-{Path(name).name}"
                meta = snapshot(sources[role], target)
                record["artifacts"][role] = {
                    "source": name, "path": target.relative_to(root).as_posix(),
                    "size": meta["size"], "sha256": meta["sha256"],
                }
        records.append(record)


def record_process(batch: dict, outcome: dict, root: Path) -> dict:
    """Index subprocess stdout/stderr and exit status as process evidence."""
    artifacts = {}
    for role in ("stdout", "stderr"):
        meta = outcome[role]
        artifacts[role] = {
            "path": Path(meta["path"]).relative_to(root).as_posix(),
            "size": meta["size"], "sha256": meta["sha256"],
        }
    return {
        "id": f"PROCESS-{batch['id']}", "kind": "process",
        "capture_after": "each_batch", "batch_id": batch["id"],
        "verification_point_ids": batch.get("verification_point_ids", []),
        "required": True, "status": "captured",
        "exit_code": outcome["exit_code"], "timed_out": outcome["timed_out"],
        "artifacts": artifacts,
    }


def evaluate_points(points: list[dict], checks: list[dict], evidence: list[dict]) -> list[dict]:
    """A captured file alone does not establish that its content passed validation."""
    result = []
    for point in points:
        ident = point["id"]
        linked_checks = [c for c in checks if ident in c.get("verification_point_ids", [])]
        linked_evidence = [e for e in evidence if ident in e.get("verification_point_ids", [])]
        if any(not c["passed"] for c in linked_checks):
            status = "failed"
        elif not linked_checks or any(e["required"] and e["status"] != "captured"
                                      for e in linked_evidence):
            status = "not_evaluated"
        else:
            status = "passed"
        result.append({
            "id": ident, "description": point["description"],
            "expected": point["expected"], "status": status,
            "evidence_ids": sorted({e["id"] for e in linked_evidence}),
        })
    return result
