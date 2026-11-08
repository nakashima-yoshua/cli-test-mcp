"""Thin CLI entrypoint. Exit codes: 0 pass, 1 tests failed, 2 execution error."""
import argparse
import json
from pathlib import Path

from .definitions import load_json, validate_suite
from .engine import run_suite


def main() -> int:
    parser = argparse.ArgumentParser(prog="cli-test")
    subs = parser.add_subparsers(dest="command", required=True)
    validate = subs.add_parser("validate")
    validate.add_argument("suite")
    run = subs.add_parser("run")
    run.add_argument("suite")
    run.add_argument("--registry", required=True)
    run.add_argument("--output", default="results")
    run.add_argument("--runtime", default=None)
    run.add_argument("--attempts", type=int, default=1)
    args = parser.parse_args()
    try:
        if args.command == "validate":
            validate_suite(load_json(args.suite), Path(args.suite).resolve().parent)
            print('{"valid": true}')
            return 0
        summary = run_suite(args.suite, args.registry, args.output, args.attempts,
                            runtime_dir=args.runtime)
        print(json.dumps(summary, indent=2, ensure_ascii=False))
        if summary["status"] == "error":
            return 2
        return 0 if all(x["verdict"] == "passed" for x in summary["cases"]) else 1
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
