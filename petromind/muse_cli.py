"""Run a real Muse investigation with the credential in MODEL_API_KEY."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent import AgentConfig, run_agent
from .audit import canonical
from .meta_api import MetaAPIError, MetaResponsesClient
from .pipeline import prepare_investigation


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--budget", type=int, choices=range(1, 6), default=5)
    parser.add_argument("--seconds", type=int, default=600)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--split", type=Path, default=Path(".petromind/split.json"))
    parser.add_argument("--model", default="muse-spark-1.3")
    parser.add_argument("--max-turns", type=int, default=20)
    parser.add_argument("--max-tool-calls", type=int, default=40)
    parser.add_argument("--max-requests", type=int, default=24)
    parser.add_argument("--max-output-tokens", type=int, default=2048)
    parser.add_argument("--output-budget", type=int, default=40960)
    parser.add_argument("--reasoning", choices=("low", "medium", "high"), default="medium")
    parser.add_argument("--timeout", type=float, default=60)
    parser.add_argument("--run-timeout", type=float, default=300)
    parser.add_argument("--max-retries", type=int, default=2)
    parser.add_argument("--trace", type=Path, help="Optional sanitized JSONL; refuses to overwrite an existing file")
    parser.add_argument("--reveal", action="store_true", help="Run evaluator only after validated submission")
    args = parser.parse_args(argv)
    trace_file, client = None, None
    def emit(kind, result):
        line = canonical({"kind": kind, "result": result})
        print(line, flush=True)
        if trace_file:
            trace_file.write(line + "\n")
            trace_file.flush()
    try:
        config = AgentConfig(args.model, args.max_turns, args.max_tool_calls, args.max_output_tokens,
                             args.reasoning, args.run_timeout)
        client = MetaResponsesClient(max_requests=args.max_requests, max_output_budget=args.output_budget,
                                      timeout=args.timeout, max_retries=args.max_retries)
        prepared = prepare_investigation(args.dataset, args.budget, args.seconds, args.seed, args.split)
        if args.trace:
            args.trace.parent.mkdir(parents=True, exist_ok=True)
            trace_file = args.trace.open("x", encoding="utf-8")
        emit("protocol", {"scripted_demo": False, "meta_model": True, "model": args.model,
             "known_transient_onset": True, "training_incidents": prepared.training_incidents,
             "test_incidents": prepared.test_incidents, "confidence_calibrated": False})
        result = run_agent(prepared.session, client, config,
                           on_event=lambda e: emit(e.kind, {"sequence": e.sequence,
                                                           **json.loads(e.details_json)}))
        emit("run_summary", {"status": result.status, "reason": result.reason,
             "requests": result.requests, "reserved_output_tokens": result.reserved_output_tokens,
             "sensor_queries": len(prepared.session.queries),
             "remaining_budget": prepared.session.remaining_budget})
        if result.status != "completed":
            return 2
        emit("final_diagnosis", json.loads(result.diagnosis_json))
        if args.reveal:
            emit("evaluation_only", prepared.evaluator.reveal(prepared.session))
        return 0
    except MetaAPIError as exc:
        emit("configuration_error", {"code": exc.code, "status": exc.status})
        return 2
    except (ValueError, OSError):
        emit("configuration_error", {"code": "check_dataset_split_limits_and_trace_destination"})
        return 2
    finally:
        if client:
            client.close()
        if trace_file:
            trace_file.close()
