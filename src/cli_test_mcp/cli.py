"""Command-line interface for the deterministic engine."""
import argparse
import json
from .engine import run_suite, validate_suite, load_json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(prog="cli-test")
    sub = parser.add_subparsers(dest="command", required=True)
    validate = sub.add_parser("validate")
    validate.add_argument("suite")
    run = sub.add_parser("run")
    run.add_argument("suite")
    run.add_argument("--registry", required=True)
    run.add_argument("--output", default="results")
    run.add_argument("--attempts", type=int, default=1)
    args = parser.parse_args()
    if args.command == "validate":
        validate_suite(load_json(args.suite), Path(args.suite).resolve().parent)
        print('{"valid": true}')
    else:
        print(json.dumps(run_suite(args.suite, args.registry, args.output, args.attempts), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
