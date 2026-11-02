#!/usr/bin/env python3
"""Isolated GraphRAG/claim-audit research. No changes to the hackathon demo."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from research.sprint_a.experiment import SessionLedger, load, prepare, report, run


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("prepare")
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--capture", type=Path)
    p.add_argument("--science-run", type=Path)
    p.add_argument(
        "--benchmark",
        type=Path,
        help="Independently authored frozen exchange; never edit its private references here.",
    )
    p.add_argument("--max-cost-usd", type=float, default=5)
    for cmd in ("offline", "pilot", "evaluate"):
        p = sub.add_parser(cmd)
        p.add_argument("--out", type=Path, required=True)
        if cmd != "offline":
            p.add_argument("--authorize-paid-meta", action="store_true")
    args = parser.parse_args()
    try:
        if args.command == "prepare":
            if bool(args.benchmark) == bool(args.capture) or (
                args.capture and not args.science_run
            ):
                raise ValueError(
                    "choose_independent_benchmark_or_capture_plus_science_run"
                )
            value = prepare(
                args.out,
                capture=args.capture,
                science_run=args.science_run,
                exchange=json.loads(args.benchmark.read_text())
                if args.benchmark
                else None,
                max_cost=args.max_cost_usd,
            )
        elif args.command == "offline":
            protocol, data = load(args.out)
            value = report(
                args.out, protocol, data, SessionLedger(protocol["ledger_directory"])
            )
            value = {
                "status": "offline_complete",
                "api_requests": 0,
                "controls": value["controls"],
                "deterministic": value["summary"]["deterministic"],
                "gate": value["gate"],
            }
        else:
            value = run(
                args.out,
                authorize_paid=args.authorize_paid_meta,
                all_cases=args.command == "evaluate",
            )
        print(json.dumps(value, sort_keys=True))
        return 2 if value.get("status") == "blocked" else 0
    except (ValueError, OSError, KeyError, TypeError, StopIteration) as error:
        # Avoid private paths, source contents and exception bodies in diagnostics.
        code = (
            str(error)
            if isinstance(error, ValueError) and str(error).replace("_", "").isalnum()
            else "research_precondition_failed"
        )
        print(
            json.dumps(
                {
                    "status": "research_precondition_failed",
                    "code": code,
                    "api_requests": 0,
                }
            )
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
