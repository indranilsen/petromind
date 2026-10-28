#!/usr/bin/env python3
"""Milestone 5: freeze, run a capped pilot, and independently review one-test investigations."""

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from petromind.science_evaluation import freeze, run, analyze
from petromind.eval_runner import read_jsonl
from petromind.meta_api import MetaAPIError


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("prepare")
    p.add_argument("--dataset", type=Path, required=True)
    p.add_argument("--cohort-from", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--cases", type=int, default=6)
    p.add_argument("--pilot-max-cost-usd", type=float, default=5.0)
    for name in ("pilot", "development"):
        p = sub.add_parser(name)
        p.add_argument("--dataset", type=Path, required=True)
        p.add_argument("--out", type=Path, required=True)
        if name == "development":
            p.add_argument("--reviewed-pilot", action="store_true", required=True)
    p = sub.add_parser("analyze")
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--reviews", type=Path)
    p.add_argument("--cohort", choices=("pilot", "development"), default="pilot")
    args = parser.parse_args(argv)
    try:
        if args.command == "prepare":
            p = freeze(
                args.dataset,
                json.loads(args.cohort_from.read_text()),
                args.out,
                args.cases,
                args.pilot_max_cost_usd,
            )
            result = {
                "status": "protocol_frozen",
                "protocol_id": p["protocol_id"],
                "cases": len(p["case_ids"]),
                "pilot_cases": len(p["pilot_case_ids"]),
                "api_requests": 0,
            }
        elif args.command == "analyze":
            p = json.loads((args.out / "protocol.json").read_text())
            rows = read_jsonl(args.out / "results.jsonl")
            ids = p["case_ids"] if args.cohort == "development" else p["pilot_case_ids"]
            result = analyze(
                p,
                rows,
                ids,
                json.loads(args.reviews.read_text()) if args.reviews else (),
            )
            (args.out / "reviewed-report.json").write_text(
                json.dumps(result, indent=2) + "\n"
            )
        else:
            result = run(
                args.out,
                args.dataset,
                args.command,
                reviewed=getattr(args, "reviewed_pilot", False),
                on_progress=lambda r: print(json.dumps(r), flush=True),
            )
        print(json.dumps(result, sort_keys=True))
        return 0
    except MetaAPIError as exc:
        print(json.dumps({"error": exc.code, "status": exc.status}))
        return 2
    except (OSError, ValueError, KeyError, TypeError):
        print(
            json.dumps(
                {
                    "error": "science_precondition_failed",
                    "hint": "Check fresh output, frozen protocol/data/runtime, parent cohort and pilot review.",
                }
            )
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
