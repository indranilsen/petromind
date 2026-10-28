"""Freeze, pilot, resume and analyze the paired evaluation (Mac/Linux)."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent import AgentConfig
from .audit import canonical
from .eval_protocol import freeze_protocol
from .eval_runner import read_jsonl, run_evaluation, write_reports
from .meta_api import MetaAPIError


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("prepare", help="Freeze existing split, data hashes, code and configuration; no API calls")
    prepare.add_argument("--dataset", type=Path, required=True)
    prepare.add_argument("--split", type=Path, default=Path(".petromind/split.json"))
    prepare.add_argument("--out", type=Path, required=True)
    prepare.add_argument("--budgets", type=int, nargs="+", default=[5])
    prepare.add_argument("--seconds", type=int, default=600)
    prepare.add_argument("--expected-test-incidents", type=int, default=33)
    prepare.add_argument("--pilot-cases", type=int, default=2)
    prepare.add_argument("--max-turns", type=int, default=20)
    prepare.add_argument("--max-output-tokens", type=int, default=2048)
    prepare.add_argument("--cohort-from", type=Path,
                         help="Existing protocol for a token-only revision; preserves exact cohort, IDs, pilot and prompts")
    for name in ("pilot", "full"):
        command = commands.add_parser(name, help="Run pending paired tasks; full requires a successful pilot")
        command.add_argument("--dataset", type=Path, required=True)
        command.add_argument("--out", type=Path, required=True)
        command.add_argument("--max-requests-total", type=int, default=120 if name == "pilot" else 2000)
        command.add_argument("--max-output-tokens-total", type=int, default=None,
                             help="Default: planned Muse runs times frozen per-run output reservation")
    analyze = commands.add_parser("analyze", help="Regenerate reports without API calls")
    analyze.add_argument("--out", type=Path, required=True)
    analyze.add_argument("--cohort", choices=("pilot", "full"), default="full")
    args = parser.parse_args(argv)
    try:
        if args.command == "prepare":
            if (args.out / "protocol.json").exists() or (args.out / "results.jsonl").exists():
                raise ValueError("Use a fresh output directory; never overwrite a protocol")
            protocol = freeze_protocol(args.dataset, args.split, budgets=tuple(args.budgets),
                seconds=args.seconds, expected_test=args.expected_test_incidents, pilot_cases=args.pilot_cases,
                config=AgentConfig(max_turns=args.max_turns, max_output_tokens=args.max_output_tokens),
                cohort_from=json.loads(args.cohort_from.read_text()) if args.cohort_from else None)
            args.out.mkdir(parents=True, exist_ok=True)
            with (args.out / "protocol.json").open("x") as stream:
                stream.write(json.dumps(protocol, indent=2) + "\n")
            print(canonical({"status": "protocol_frozen", "protocol_id": protocol["protocol_id"],
                "test_incidents": sum(r["partition"] == "test" for r in protocol["records"]),
                "pilot_cases": len(protocol["pilot_case_ids"]), "budgets": protocol["budgets"],
                "methods": protocol["methods"], "api_requests": 0}), flush=True)
        elif args.command in {"pilot", "full"}:
            report = run_evaluation(args.out, args.dataset, args.command,
                max_requests=args.max_requests_total, max_output_tokens=args.max_output_tokens_total,
                on_progress=lambda row: print(canonical(row), flush=True))
            print(canonical({"status": "stage_finished", "stage_complete": report["stage_complete"],
                             "pilot_ready": report["pilot_ready"], "n_cases": report["n_cases"]}), flush=True)
            if not report["stage_complete"] or (args.command == "pilot" and not report["pilot_ready"]):
                return 2
        else:
            protocol = json.loads((args.out / "protocol.json").read_text())
            ids = protocol["pilot_case_ids"] if args.cohort == "pilot" else [
                r["case_id"] for r in protocol["records"] if r["partition"] == "test"]
            write_reports(args.out, protocol, read_jsonl(args.out / "results.jsonl"), ids)
            print(canonical({"status": "analysis_complete", "api_requests": 0}), flush=True)
    except MetaAPIError as exc:
        print(canonical({"error": exc.code, "status": exc.status}), flush=True)
        return 2
    except (ValueError, OSError) as exc:
        reason = "check_protocol_and_inputs"
        for text, code in (("successful complete pilot", "pilot_required"),
                           ("Interrupted task detected", "interrupted_task_requires_review"),
                           ("Code or runtime differs", "frozen_code_or_runtime_changed"),
                           ("Dataset/cohort content differs", "frozen_data_changed"),
                           ("Held-out incident count differs", "expected_33_incidents_or_explicit_test_override"),
                           ("never overwrite a protocol", "protocol_already_exists")):
            if text in str(exc):
                reason = code
        # Evaluation files are private. Do not accidentally print original paths/labels.
        print(canonical({"error": "evaluation_precondition_failed", "reason": reason, "hint":
            "Check existing split/cohort count, frozen code/runtime/data, pilot completion, "
            "interrupted traces, limits, and use a fresh directory for prepare."}), flush=True)
        return 2
    return 0
