#!/usr/bin/env python3
"""Freeze captured development evidence, run only a two-task capped pilot, review."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from petromind.claim_evaluation import analyze, offline_check, pilot, prepare
from petromind.meta_api import MetaAPIError


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("prepare")
    p.add_argument("--science-run", type=Path, required=True)
    p.add_argument("--dataset", type=Path)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--max-cost-usd", type=float, default=2)
    for name in ("pilot", "analyze", "check"):
        p = sub.add_parser(name)
        p.add_argument("--out", type=Path, required=True)
        if name == "analyze":
            p.add_argument("--reviews", type=Path)
    a = parser.parse_args()
    try:
        if a.command == "prepare":
            result = prepare(
                a.science_run, a.out, dataset=a.dataset, max_cost=a.max_cost_usd
            )
        elif a.command == "pilot":
            result = pilot(a.out)
        elif a.command == "check":
            result = offline_check(a.out)
        else:
            result = analyze(
                a.out, json.loads(a.reviews.read_text()) if a.reviews else ()
            )
        print(json.dumps(result, sort_keys=True))
        return 0
    except MetaAPIError as e:
        print(
            json.dumps(
                {
                    "status": "configuration_or_api_error",
                    "code": e.code,
                    "http_status": e.status,
                }
            )
        )
        return 2
    except (ValueError, OSError, KeyError, TypeError):
        print(
            json.dumps(
                {
                    "status": "precondition_failed",
                    "instruction": "Use a fresh protocol and verified completed M5 development capture; inspect documentation.",
                }
            )
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
