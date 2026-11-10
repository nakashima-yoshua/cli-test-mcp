"""Load and validate JSON contracts before an execution can start.

This module has no dependency on the test runner, CLI or MCP adapter.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from importlib.resources import files
from pathlib import Path, PureWindowsPath

from jsonschema import Draft202012Validator


class DefinitionError(ValueError):
    """A malformed or unsafe test definition."""


def load_json(path: str | Path) -> object:
    return json.loads(Path(path).read_text(encoding="utf-8"))


@lru_cache(maxsize=3)
def _schema(name: str) -> Draft202012Validator:
    if name not in {"suite", "case", "result"}:
        raise ValueError("unknown schema")
    resource = files("cli_test_mcp.definitions").joinpath("schemas", f"{name}.schema.json")
    schema = json.loads(resource.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def _check_schema(data: object, name: str) -> None:
    errors = sorted(_schema(name).iter_errors(data), key=lambda e: (tuple(map(str, e.absolute_path)), e.message))
    if errors:
        error = errors[0]
        loc = "/".join(map(str, error.absolute_path)) or "$"
        raise DefinitionError(f"{name} {loc}: {error.message}")


def safe_path(root: str | Path, value: str) -> Path:
    """Resolve only a workspace-relative path, rejecting traversal and escapes.

    The runner must also re-check paths at execution time to avoid symlink races.
    """
    if not isinstance(value, str) or not value or "\\" in value:
        raise DefinitionError("invalid relative path")
    relative = Path(value)
    if relative.is_absolute() or PureWindowsPath(value).drive or ".." in relative.parts:
        raise DefinitionError(f"path must remain workspace-relative: {value}")
    resolved_root = Path(root).resolve()
    candidate = resolved_root.joinpath(relative)
    if not candidate.resolve().is_relative_to(resolved_root):
        raise DefinitionError(f"path outside workspace: {value}")
    return candidate


def _check_log_path(base: Path, value: str) -> None:
    if "[" in value or "]" in value or "**" in value:
        raise DefinitionError("only * and ? filename globs are supported")
    path = Path(value)
    if any("*" in part or "?" in part for part in path.parts[:-1]):
        raise DefinitionError("log glob is allowed only in a filename")
    safe_path(base, re.sub(r"[?*]", "x", value))


def validate_case(case: object, base: str | Path) -> bool:
    _check_schema(case, "case")
    assert isinstance(case, dict)  # established by schema
    batches = {item["id"] for item in case["batches"]}
    if len(batches) != len(case["batches"]):
        raise DefinitionError("duplicate batch id")

    logs = [log["id"] for log in case.get("logs", [])]
    if len(logs) != len(set(logs)):
        raise DefinitionError("duplicate log id")

    for step in case.get("setup", []):
        safe_path(base, step["source"])
        safe_path(base, step["destination"])
    for log in case.get("logs", []):
        _check_log_path(Path(base), log["path"])
    points = [p["id"] for p in case.get("verification_points", [])]
    if len(points) != len(set(points)):
        raise DefinitionError("duplicate verification point id")
    known = set(points)

    def check_points(item: dict) -> None:
        unknown = set(item.get("verification_point_ids", [])) - known
        if unknown:
            raise DefinitionError(f"unknown verification point: {sorted(unknown)}")

    evidences = case.get("evidence", [])
    ids = [e["id"] for e in evidences]
    if len(ids) != len(set(ids)):
        raise DefinitionError("duplicate evidence id")
    roles = {
        "file": ({"content"}, {"content"}),
        "sql": ({"statement", "result"}, {"statement", "parameters", "result"}),
        "http": ({"request", "response"}, {"request", "response"}),
        "screenshot": ({"image"}, {"image"}),
    }
    for item in evidences:
        required, permitted = roles[item["kind"]]
        actual = set(item["artifacts"])
        if not required <= actual or not actual <= permitted:
            raise DefinitionError(f"invalid artifact roles: {item['id']}")
        for path in item["artifacts"].values():
            safe_path(base, path)
        check_points(item)
    for batch in case["batches"]:
        check_points(batch)
    for assertion in case.get("assertions", []):
        if assertion["type"] == "exit_code" and assertion["batch"] not in batches:
            raise DefinitionError("unknown batch in assertion")
        if assertion["type"] == "file_exists":
            safe_path(base, assertion["path"])
        check_points(assertion)
    return True


def validate_suite(suite: object, base: str | Path) -> bool:
    _check_schema(suite, "suite")
    assert isinstance(suite, dict)  # established by schema
    ids = set()
    for item in suite["cases"]:
        if item["id"] in ids:
            raise DefinitionError("duplicate case id")
        ids.add(item["id"])
        case = load_json(safe_path(base, item["definition"]))
        validate_case(case, base)
        if case["case_id"] != item["id"]:
            raise DefinitionError("case id mismatch")
    return True


def validate_result(result: object) -> bool:
    """Validate a stored summary. Used by the runner in the next PR."""
    _check_schema(result, "result")
    return True
