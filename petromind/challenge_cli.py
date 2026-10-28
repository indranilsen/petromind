"""Separate M4 development experiment. No UI and no automatic full-cohort spend."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .audit import canonical
from .challenge_offline import analyze_m3
from .challenge_protocol import freeze_development
from .challenge_runner import run_challenge_evaluation, write_challenge_report
from .eval_runner import read_jsonl
from .meta_api import MetaAPIError


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("prepare")
    prepare.add_argument("--dataset", type=Path, required=True)
    prepare.add_argument("--split", type=Path, required=True)
    prepare.add_argument("--out", type=Path, required=True)
    prepare.add_argument("--cases", type=int, default=16)
    prepare.add_argument("--pilot-cases", type=int, default=2)
    for name in ("pilot", "full"):
        run = commands.add_parser(name)
        run.add_argument("--dataset", type=Path, required=True)
        run.add_argument("--out", type=Path, required=True)
        run.add_argument("--max-requests-total", type=int, default=None)
        run.add_argument("--max-output-tokens-total", type=int, default=None)
        if name == "full":
            run.add_argument("--reviewed-pilot", action="store_true", required=True,
                             help="Explicit acknowledgement that pilot outputs and spending have been reviewed")
    analyze = commands.add_parser("analyze")
    analyze.add_argument("--out", type=Path, required=True)
    analyze.add_argument("--cohort", choices=("pilot", "full"), default="full")
    analyze.add_argument("--reviews", type=Path)
    offline = commands.add_parser("offline-m3")
    offline.add_argument("--results", type=Path, required=True)
    offline.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "prepare":
            if args.out.exists() and any(args.out.iterdir()):
                raise ValueError("Use a new empty output directory")
            protocol = freeze_development(args.dataset, args.split, n_cases=args.cases, pilot_cases=args.pilot_cases)
            args.out.mkdir(parents=True, exist_ok=True)
            with (args.out / "protocol.json").open("x") as stream:
                stream.write(json.dumps(protocol, indent=2) + "\n")
            print(canonical({"status": "development_protocol_frozen", "protocol_id": protocol["protocol_id"],
                "cases": len(protocol["selected"]), "pilot_cases": len(protocol["pilot_case_ids"]),
                "selection": protocol["selection"], "fit_classes": protocol["fit_classes"], "api_requests": 0}))
        elif args.command in {"pilot", "full"}:
            report = run_challenge_evaluation(args.out, args.dataset, args.command,
                max_requests=args.max_requests_total, max_output_tokens=args.max_output_tokens_total,
                on_progress=lambda row: print(canonical(row), flush=True))
            print(canonical({"status": "stage_finished", "stage_complete": report["stage_complete"],
                             "pilot_ready": report["pilot_ready"], "n_cases": report["n_cases"]}))
            if not report["pilot_ready"]:
                return 2
        elif args.command == "analyze":
            protocol = json.loads((args.out / "protocol.json").read_text())
            ids = protocol["pilot_case_ids"] if args.cohort == "pilot" else [r["case_id"] for r in protocol["selected"]]
            reviews = json.loads(args.reviews.read_text()) if args.reviews else []
            report = write_challenge_report(args.out, protocol, read_jsonl(args.out / "results.jsonl"), ids, reviews)
            print(canonical({"status": "analysis_complete", "api_requests": 0,
                             "recommendations": {r["method"]: r.get("recommendation") for r in report["summary"]}}))
        else:
            result = analyze_m3(read_jsonl(args.results))
            with args.out.open("x") as stream:
                stream.write(json.dumps(result, indent=2) + "\n")
            print(canonical({"status": "offline_analysis_complete", "api_requests": 0}))
    except MetaAPIError as exc:
        print(canonical({"error": exc.code, "status": exc.status}))
        return 2
    except (ValueError, OSError, KeyError, TypeError):
        print(canonical({"error": "challenge_precondition_failed", "hint":
            "Check dataset, existing original split, frozen code/runtime, fresh output, pilot, interrupted traces and reviews"}))
        return 2
    return 0
