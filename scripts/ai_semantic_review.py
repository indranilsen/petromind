#!/usr/bin/env python3
"""Exploratory external AI review. Never qualified independent human validation."""

import argparse
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from research.ai_semantic_review.contract import LABEL
from research.ai_semantic_review.protocol import load, prepare
from research.ai_semantic_review.runner import freeze_reviews, report, run


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)
    s = sub.add_parser("prepare")
    s.add_argument("--bundle", type=Path, required=True)
    s.add_argument("--expected-packets-sha256", required=True)
    s.add_argument("--config", type=Path, required=True)
    s.add_argument("--out", type=Path, required=True)
    s.add_argument("--max-cost-usd", default="20")
    for name in ("review-a", "review-b", "adjudicate"):
        s = sub.add_parser(name)
        s.add_argument("--out", type=Path, required=True)
        s.add_argument("--authorize-paid-external-ai", action="store_true")
        s.add_argument("--limit", type=int)
    s = sub.add_parser("freeze-reviews")
    s.add_argument("--out", type=Path, required=True)
    s = sub.add_parser("report")
    s.add_argument("--out", type=Path, required=True)
    s.add_argument("--report", type=Path, required=True)
    s = sub.add_parser("check")
    s.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    try:
        if a.command == "prepare":
            result = prepare(
                a.bundle, a.expected_packets_sha256, a.config, a.out, a.max_cost_usd
            )
        elif a.command in ("review-a", "review-b", "adjudicate"):
            role = {
                "review-a": "reviewer_a",
                "review-b": "reviewer_b",
                "adjudicate": "adjudicator",
            }[a.command]
            result = run(
                a.out, role, authorize=a.authorize_paid_external_ai, limit=a.limit
            )
        elif a.command == "freeze-reviews":
            result = freeze_reviews(a.out)
        elif a.command == "report":
            result = report(a.out, a.report)
        else:
            protocol, packets = load(a.out)
            result = {
                "status": "ai_protocol_integrity_verified",
                "label": LABEL,
                "packets": len(packets),
                "protocol_id": protocol["protocol_id"],
                "api_requests": 0,
            }
        print(json.dumps(result, sort_keys=True))
        return 0
    except (
        ValueError,
        OSError,
        KeyError,
        TypeError,
        IndexError,
        AttributeError,
        RecursionError,
        sqlite3.Error,
    ) as e:
        code = (
            str(e)
            if isinstance(e, ValueError)
            and str(e).startswith("ai_")
            and str(e).replace("_", "").isalnum()
            else "ai_precondition_failed"
        )
        print(json.dumps({"label": LABEL, "status": "ai_review_stopped", "code": code}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
