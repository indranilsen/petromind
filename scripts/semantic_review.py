#!/usr/bin/env python3
"""Offline Sprint C human-review workflow. Never calls Meta or opens evaluator keys."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from research.semantic_review.workflow import (
    assemble,
    bundle,
    compare,
    finalize,
    prepare,
    read,
    validate_form,
    validate_item,
    verify,
)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)
    s = sub.add_parser("prepare")
    s.add_argument("--packets", type=Path, required=True)
    s.add_argument("--expected-sha256", required=True)
    s.add_argument("--out", type=Path, required=True)
    s = sub.add_parser("validate")
    s.add_argument("--bundle", type=Path, required=True)
    s.add_argument("--form", type=Path, required=True)
    s.add_argument("--role", choices=["R-A", "R-B"], required=True)
    for name in ("compare", "finalize"):
        s = sub.add_parser(name)
        s.add_argument("--bundle", type=Path, required=True)
        s.add_argument("--a", type=Path, required=True)
        s.add_argument("--b", type=Path, required=True)
        s.add_argument("--out", type=Path, required=True)
        if name == "finalize":
            s.add_argument("--adjudication", type=Path, required=True)
    s = sub.add_parser("verify")
    s.add_argument("--bundle", type=Path, required=True)
    s.add_argument("--packets", type=Path, required=True)
    s.add_argument("--expected-sha256", required=True)
    s.add_argument("--receipt", type=Path, required=True)
    s = sub.add_parser("validate-item")
    s.add_argument("--bundle", type=Path, required=True)
    s.add_argument("--form", type=Path, required=True)
    s.add_argument("--role", choices=["R-A", "R-B"], required=True)
    s = sub.add_parser("assemble")
    s.add_argument("--bundle", type=Path, required=True)
    s.add_argument("--role", choices=["R-A", "R-B"], required=True)
    s.add_argument("--items", type=Path, required=True)
    s.add_argument("--attestation", type=Path, required=True)
    s.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    try:
        if a.command == "prepare":
            result = prepare(a.packets, a.out, a.expected_sha256)
        elif a.command == "verify":
            result = verify(a.bundle, a.packets, a.expected_sha256, a.receipt)
        elif a.command == "assemble":
            result = assemble(a.bundle, a.role, a.items, a.attestation, a.out)
        elif a.command == "validate-item":
            m, packets = bundle(a.bundle)
            validate_item(read(a.form), m, packets, a.role)
            result = {"status": "completed_item_validated", "api_requests": 0}
        elif a.command == "validate":
            m, packets = bundle(a.bundle)
            rows = validate_form(read(a.form), m, packets, a.role)
            result = {
                "status": "complete_human_form_validated",
                "reviews": len(rows),
                "credential_attestation_not_verified": True,
            }
        elif a.command == "compare":
            result = compare(a.bundle, a.a, a.b, a.out)
        else:
            result = finalize(a.bundle, a.a, a.b, a.adjudication, a.out)
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
    ) as e:
        code = (
            str(e)
            if isinstance(e, ValueError) and str(e).replace("_", "").isalnum()
            else "review_input_invalid_or_unavailable"
        )
        print(
            json.dumps(
                {
                    "status": "review_precondition_failed",
                    "code": code,
                    "api_requests": 0,
                }
            )
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
