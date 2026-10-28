"""Durable paired evaluation; private scoring state never enters model input."""
from __future__ import annotations

import csv
import fcntl
import json
import os
import time
from dataclasses import replace
from pathlib import Path

from .agent import AgentConfig, run_agent
from .audit import canonical, verify_audit
from .baselines import GaussianEvidence
from .eval_analysis import build_report
from .eval_protocol import digest, validate_protocol
from .meta_api import MetaAPIError, MetaResponsesClient
from .retrieval import IncidentRetriever
from .session import DiagnosticSession
from .variants import METHODS, VARIANT_TOOLS


def append_json(path, value):
    with Path(path).open("a", encoding="utf-8") as stream:
        stream.write(canonical(value) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def read_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()] if Path(path).exists() else []


def task_key(row):
    return row["case_id"], row["method"], row["budget"]


def task_plan(protocol, case_ids):
    plan = []
    for case in case_ids:
        for budget in protocol["budgets"]:
            methods = sorted(METHODS, key=lambda m: digest([protocol["seed"], case, budget, m]))
            plan.extend({"case_id": case, "method": method, "budget": budget} for method in methods)
    return plan


class EvaluationBudget:
    """Persist reservations BEFORE each HTTP attempt; resume cannot reset them."""
    def __init__(self, path, protocol_id, max_requests, max_output_tokens):
        if (type(max_requests) is not int or max_requests < 1
                or type(max_output_tokens) is not int or max_output_tokens < 16):
            raise ValueError("Invalid total evaluation limits")
        self.path, self.protocol_id = Path(path), protocol_id
        self.max_requests, self.max_output_tokens = max_requests, max_output_tokens
        ledger = read_jsonl(path)
        if any(r["protocol_id"] != protocol_id for r in ledger):
            raise ValueError("Reservation ledger belongs to another protocol")
        self.requests = len(ledger)
        self.output_tokens = sum(r["output_cap"] for r in ledger)

    def reserve(self, task, cap):
        if self.requests >= self.max_requests:
            raise MetaAPIError("evaluation_request_budget_exhausted")
        if self.output_tokens + cap > self.max_output_tokens:
            raise MetaAPIError("evaluation_output_budget_exhausted")
        append_json(self.path, {"protocol_id": self.protocol_id, **task, "output_cap": cap})
        self.requests += 1
        self.output_tokens += cap


def usage_and_cost(events, requests, prices):
    usage_rows = [json.loads(e.details_json) for e in events if e.kind == "usage"]
    valid = [u for u in usage_rows if "input_tokens" in u and "output_tokens" in u]
    inputs = sum(u["input_tokens"] for u in valid)
    outputs = sum(u["output_tokens"] for u in valid)
    cached = sum(min(u.get("cached_tokens", 0), u["input_tokens"]) for u in valid)
    estimate = ((inputs - cached) * prices["input_per_million_usd"]
                + cached * prices["cached_input_per_million_usd"]
                + outputs * prices["output_per_million_usd"]) / 1_000_000
    return {"input_tokens": inputs, "output_tokens": outputs, "cached_tokens": cached,
            "reasoning_tokens": sum(u.get("reasoning_tokens", 0) for u in valid),
            "responses_with_usage": len(valid), "http_attempts_without_usage": requests - len(valid),
            "cache_usage_reported": all("cached_tokens" in u for u in valid),
            "estimated_cost_usd": estimate, "cost_complete": len(valid) == requests,
            "cost_note": "Known usage only; missing cache counts charged at normal input rate; unknown attempts excluded"}


def audit_metrics(session):
    graph, retrieval, graph_followed = [], [], []
    suggestions = set()
    for entry in session.audit_trail:
        result = json.loads(entry.result_json)
        if entry.tool == "get_equipment_neighbors":
            graph.append({"sequence": entry.sequence, "result": result})
            if "error" not in result:
                suggestions = set(result["neighbor_sensors"])
        elif entry.tool == "search_similar_incidents":
            retrieval.append({"sequence": entry.sequence, "result": result})
        elif entry.tool == "get_sensor_history" and "error" not in result and not result["cached"]:
            if result["sensor"] in suggestions:
                graph_followed.append(result["sensor"])
            suggestions = set()
    return {"sensor_sequence": list(session.queries),
            "sensor_quality": {s: obs.to_dict() for s, obs in session.observations.items()},
            "graph_calls": len(graph), "retrieval_calls": len(retrieval),
            "graph_successful_calls": sum("error" not in e["result"] for e in graph),
            "retrieval_successful_calls": sum("error" not in e["result"] for e in retrieval),
            "sensor_request_count": sum(e.tool == "get_sensor_history" for e in session.audit_trail),
            "graph_events": graph, "retrieval_events": retrieval,
            "graph_suggested_then_selected": graph_followed,
            "audit_valid": verify_audit(session.audit_trail),
            "audit_digest": session.audit_trail[-1].digest if session.audit_trail else None}


def write_reports(directory, protocol, rows, case_ids):
    report = build_report(protocol, rows, case_ids)
    (directory / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    table = ["# Paired PetroMind evaluation", "", f"Protocol: `{protocol['protocol_id']}`", "",
             "Failures count as incorrect. Blank accuracy means the planned matrix is incomplete.", "",
             "| Method | Budget | Attempted / planned | Failures | Accuracy | Mean sensor queries | Mean latency (s) | Known-usage cost (USD) |",
             "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for row in report["summary"]:
        acc = f"{row['accuracy']:.3f}" if row["accuracy"] is not None else ""
        queries = f"{row['mean_sensor_queries']:.2f}" if row["mean_sensor_queries"] is not None else ""
        latency = f"{row['mean_latency_seconds']:.2f}" if row["mean_latency_seconds"] is not None else ""
        table.append(f"| {row['method']} | {row['budget']} | {row['n_attempted']} / {row['n_expected']} | {row['n_failed']} | {acc} | {queries} | {latency} | {row['estimated_known_usage_cost_usd']:.6f} |")
    table.extend(["", "## Paired accuracy differences", "", "Right minus left, on matching incidents.", "",
                  "| Left | Right | Budget | Pairs | Accuracy delta | Well-bootstrap 95% interval |",
                  "|---|---|---:|---:|---:|---|"])
    for row in report["paired_comparisons"]:
        delta = row["accuracy_delta_right_minus_left"]
        value = f"{delta:.3f}" if delta is not None else ""
        table.append(f"| {row['left']} | {row['right']} | {row['budget']} | {row['n_pairs']} | {value} | {row['well_cluster_bootstrap_95_percentile_interval']} |")
    table.extend(["", "## Limitations", ""] + ["- " + item for item in report["limitations"]])
    (directory / "report.md").write_text("\n".join(table) + "\n")
    if rows:
        with (directory / "results.csv").open("w", newline="") as stream:
            columns = sorted({k for r in rows for k in r})
            writer = csv.DictWriter(stream, columns)
            writer.writeheader()
            writer.writerows({k: canonical(v) if isinstance(v, (dict, list)) else v for k, v in row.items()} for row in rows)
    return report


def run_evaluation(directory, dataset, stage="pilot", *, max_requests=120,
                   max_output_tokens=245760, client_factory=MetaResponsesClient, on_progress=None):
    directory = Path(directory)
    if stage not in {"pilot", "full"}:
        raise ValueError("Invalid stage")
    # Advisory nonblocking lock automatically releases if the process dies (Mac/Linux).
    with (directory / "run.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError("Another evaluation is running") from None
        protocol = json.loads((directory / "protocol.json").read_text())
        split, by_id = validate_protocol(protocol, dataset)
        rows = read_jsonl(directory / "results.jsonl")
        keys = [task_key(r) for r in rows]
        if len(keys) != len(set(keys)) or any(r["protocol_id"] != protocol["protocol_id"] for r in rows):
            raise ValueError("Results contain duplicates or a different protocol")
        all_ids = [r["case_id"] for r in protocol["records"] if r["partition"] == "test"]
        pilot_ids = protocol["pilot_case_ids"]
        completed = {task_key(r): r for r in rows}
        pilot_ready = all(task_key(t) in completed and completed[task_key(t)]["status"] == "completed"
                          for t in task_plan(protocol, pilot_ids))
        if stage == "full" and not pilot_ready:
            raise ValueError("A successful complete pilot is required before the full cohort")
        selected = pilot_ids if stage == "pilot" else all_ids
        plan = task_plan(protocol, selected)
        valid_tasks = {task_key(t) for t in task_plan(protocol, all_ids)}
        if any(k not in valid_tasks for k in keys):
            raise ValueError("Unexpected task in results")
        traces = directory / "traces"
        traces.mkdir(exist_ok=True)
        for task in plan:
            if task_key(task) not in completed and (traces / (digest(task) + ".jsonl")).exists():
                raise ValueError("Interrupted task detected; no automatic paid retry. Inspect its trace/ledger first")
        if any(task_key(t) not in completed and t["method"] in VARIANT_TOOLS for t in plan):
            # Configuration failure must not become a scored model failure or poison resume.
            probe = client_factory(**protocol["per_run_transport"])
            probe.close()  # No request; credential/configuration validation only.
        train = [by_id[r["case_id"]] for r in protocol["records"] if r["partition"] == "train"]
        names = tuple(sorted({s for r in train for s in r.measurements}))
        model = GaussianEvidence(train, names)
        case_ids = {record.path: key for key, record in by_id.items()}
        retriever = IncidentRetriever(train, split, case_ids=case_ids)
        if retriever.index_wells & set(split.test_wells):
            raise ValueError("Retrieval index contains a held-out well")
        total = EvaluationBudget(directory / "reservations.jsonl", protocol["protocol_id"],
                                  max_requests, max_output_tokens)
        for task in plan:
            if task_key(task) in completed:
                continue
            target = by_id[task["case_id"]]
            method = task["method"]
            variant = method if method in VARIANT_TOOLS else "sensor_only"
            session = DiagnosticSession(target.measurements, names, task["budget"],
                                         retriever if method == "graphrag" else None, variant=variant)
            trace_path = traces / (digest(task) + ".jsonl")
            # Intent persists before any paid attempt; a crash is never silently rerun.
            append_json(trace_path, {"kind": "task_started", "protocol_id": protocol["protocol_id"], **task})
            started = time.perf_counter()
            result, events, client = None, (), None
            prefix = []
            try:
                if method in VARIANT_TOOLS:
                    client = client_factory(**protocol["per_run_transport"],
                        request_guard=lambda cap: total.reserve(task, cap))
                    config = replace(AgentConfig(**protocol["agent_config"]), variant=method)
                    result = run_agent(session, client, config, on_event=lambda e: append_json(trace_path,
                         {"kind": e.kind, "sequence": e.sequence, "result": json.loads(e.details_json)}))
                    status, reason, events = result.status, result.reason, result.events
                else:
                    baseline = model.run(session, method)
                    status, reason, prefix = baseline["status"], baseline["reason"], baseline["prefix_predictions"]
            except MetaAPIError as exc:
                status, reason = "failed", exc.code
            finally:
                if client is not None:
                    client.close()
            elapsed = time.perf_counter() - started
            usage = usage_and_cost(events, client.requests if client else 0, protocol["prices"])
            prediction = session.diagnosis.predicted_fault_type if session.diagnosis else None
            # Scoring happens ONLY after this run terminates; never returned to the model.
            row = {"protocol_id": protocol["protocol_id"], **task,
                   "pilot": task["case_id"] in pilot_ids, "well_group": next(
                       r["well_group"] for r in protocol["records"] if r["case_id"] == task["case_id"]),
                   "status": status, "reason": reason, "prediction": prediction,
                   "true_event": target.event, "correct": prediction == target.event,
                   "confidence": session.diagnosis.confidence if session.diagnosis else None,
                "confidence_calibrated": False, "latency_seconds": elapsed,
                   "requests": client.requests if client else 0,
                   "reserved_output_tokens": client.reserved_output_tokens if client else 0,
                   "usage": usage, "estimated_cost_usd": usage["estimated_cost_usd"],
                   "cost_complete": usage["cost_complete"], "prefix_predictions": prefix,
                   **audit_metrics(session)}
            append_json(trace_path, {"kind": "task_finished", "status": status, "reason": reason})
            append_json(directory / "results.jsonl", row)
            rows.append(row)
            completed[task_key(task)] = row
            if on_progress:
                on_progress({k: row[k] for k in ("case_id", "method", "budget", "status", "reason", "requests", "estimated_cost_usd")})
            if reason.startswith("evaluation_") or reason in {"missing_or_invalid_api_key", "api_http_error", "api_connection_error"}:
                break
        report = write_reports(directory, protocol, rows, selected)
        ready = all(task_key(t) in completed for t in plan)
        report["stage_complete"] = ready
        report["pilot_ready"] = all(task_key(t) in completed and completed[task_key(t)]["status"] == "completed"
                                    for t in task_plan(protocol, pilot_ids))
        (directory / "report.json").write_text(json.dumps(report, indent=2) + "\n")
        return report
