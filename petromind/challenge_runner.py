"""Bounded, resumable development experiment; labels enter only offline scoring."""
from __future__ import annotations

import fcntl
import json
import time
from dataclasses import asdict, replace
from pathlib import Path

from .agent import AgentConfig
from .audit import canonical
from .baselines import GaussianEvidence
from .challenge_analysis import build_challenge_report
from .challenge_protocol import METHODS, VARIANTS, validate_development
from .challenger import ChallengeSession, observe_adaptively, run_challenger
from .eval_protocol import digest
from .eval_runner import EvaluationBudget, append_json, audit_metrics, read_jsonl, usage_and_cost
from .meta_api import MetaResponsesClient
from .retrieval import IncidentRetriever
from .session import DiagnosticSession


def plan_tasks(protocol, ids):
    return [{"case_id": k, "method": m} for k in ids for m in
            sorted(METHODS, key=lambda m: digest([protocol["seed"], k, m]))]


def write_challenge_report(directory, protocol, rows, ids, reviews=()):
    report = build_challenge_report(protocol, rows, ids, reviews)
    directory = Path(directory)
    (directory / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    lines = ["# Hypothesis challenger feasibility", "", f"Protocol: `{protocol['protocol_id']}`", "",
        "Failure-enriched development cases. No population accuracy claim. Interpretations require expert review.", "",
        "| Method | Completed | Recall | False challenge rate | Precision | Insufficient | Cost USD | Gate |",
        "|---|---:|---:|---:|---:|---:|---:|---|"]
    for row in report["summary"]:
        if row["method"] == "baseline":
            lines.extend([f"| baseline | {row['attempted']} | — | — | — | — | 0 | — |"])
        else:
            def fmt(k):
                return f"{row[k]:.3f}" if row[k] is not None else "—"
            lines.append(f"| {row['method']} | {row['completed']}/{len(ids)} | {fmt('challenge_recall')} | {fmt('false_challenge_rate')} | {fmt('challenge_precision')} | {row['insufficient_count']} | {row['estimated_cost_usd']:.6f} | {row['recommendation']} |")
    lines.extend(["", "## Limitations", ""] + ["- " + s for s in report["limitations"]])
    (directory / "report.md").write_text("\n".join(lines) + "\n")
    # Independent expert review template: judgments deliberately left unfilled.
    template = []
    for row in rows:
        assessment = row.get("assessment")
        if assessment:
            template.append({"case_id": row["case_id"], "method": row["method"],
                "assessment_digest": digest(assessment), "reviewer": "", "rationale": "",
                "claim_judgments": ["requires_domain_expertise"] * len(assessment["claims"]),
                "useful_investigation": None, "meaningful_contradiction": None, "unsupported_physical_claims": None})
    (directory / "review-template.json").write_text(json.dumps(template, indent=2) + "\n")
    # Labels, correctness and source identifiers are intentionally absent from review packets.
    packets = [{k: row[k] for k in ("case_id", "method", "initial_hypothesis", "assessment", "sensor_quality",
                "sensor_sequence", "graph_events", "retrieval_events")}
               for row in rows if row.get("assessment")]
    (directory / "review-packets.json").write_text(json.dumps(packets, indent=2) + "\n")
    return report


def run_challenge_evaluation(directory, dataset, stage="pilot", *, max_requests=None,
                             max_output_tokens=None, client_factory=MetaResponsesClient, on_progress=None):
    directory = Path(directory)
    if stage not in {"pilot", "full"}:
        raise ValueError("Invalid stage")
    with (directory / "run.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError("Another evaluation is running") from None
        protocol = json.loads((directory / "protocol.json").read_text())
        split, by_id = validate_development(protocol, dataset)
        rows = read_jsonl(directory / "results.jsonl")
        key = lambda r: (r["case_id"], r["method"])
        completed = {key(r): r for r in rows}
        all_ids = [r["case_id"] for r in protocol["selected"]]
        valid = {key(t) for t in plan_tasks(protocol, all_ids)}
        if (len(completed) != len(rows) or not set(completed) <= valid
                or any(r["protocol_id"] != protocol["protocol_id"] for r in rows)):
            raise ValueError("Invalid results or protocol")
        pilot_plan = plan_tasks(protocol, protocol["pilot_case_ids"])
        if stage == "full" and not all(key(t) in completed and completed[key(t)]["status"] == "completed" for t in pilot_plan):
            raise ValueError("A successful complete pilot is required")
        ids = protocol["pilot_case_ids"] if stage == "pilot" else all_ids
        plan = plan_tasks(protocol, ids)
        traces = directory / "traces"
        traces.mkdir(exist_ok=True)
        for task in plan:
            if key(task) not in completed and (traces / (digest(task) + ".jsonl")).exists():
                raise ValueError("Interrupted task: no automatic paid retry")
        if any(key(t) not in completed and t["method"] in VARIANTS for t in plan):
            probe = client_factory(**protocol["per_run_transport"])
            probe.close()  # Fail missing credentials before creating task intents.
        fit = [by_id[r["case_id"]] for r in protocol["records"] if r["role"] == "fit"]
        names = tuple(sorted({s for r in fit for s in r.measurements}))
        model = GaussianEvidence(fit, names)
        retriever = IncidentRetriever(fit, split, case_ids={r.path: k for k, r in by_id.items()})
        if retriever.index_wells & set(split.test_wells):
            raise ValueError("Retrieval well isolation violated")
        n_live = 3 * len(ids)
        total = EvaluationBudget(directory / "reservations.jsonl", protocol["protocol_id"],
            max_requests if max_requests is not None else (120 if stage == "pilot" else 1000),
            max_output_tokens if max_output_tokens is not None else n_live * protocol["per_run_transport"]["max_output_budget"])
        selected = {r["case_id"]: r for r in protocol["selected"]}
        for task in plan:
            if key(task) in completed:
                continue
            target, method = by_id[task["case_id"]], task["method"]
            variant = VARIANTS.get(method, "sensor_only")
            cls = ChallengeSession if method in VARIANTS else DiagnosticSession
            session = cls(target.measurements, names, protocol["budget"],
                          retriever if variant == "graphrag" else None, variant=variant)
            hypothesis = observe_adaptively(model, session, protocol["initial_queries"])
            frozen = selected[task["case_id"]]
            if hypothesis != frozen["initial_hypothesis"] or list(session.queries) != frozen["initial_sensor_sequence"]:
                raise ValueError("Initial evidence differs from frozen cohort")
            trace = traces / (digest(task) + ".jsonl")
            append_json(trace, {"kind": "task_started", "protocol_id": protocol["protocol_id"], **task})
            for audit in session.audit_trail:
                append_json(trace, {"kind": "initial_sensor_query", "sequence": audit.sequence,
                    "result": json.loads(audit.result_json), "digest": audit.digest})
            started = time.monotonic()
            if method == "baseline":
                final = observe_adaptively(model, session, session.remaining_budget)
                if final["prediction"] != frozen["five_query_prediction"]:
                    raise ValueError("Baseline final prediction differs from frozen cohort")
                status, reason, events, requests = "completed", "baseline_completed", (), 0
                assessment = None
                five_prediction = final["prediction"]
            else:
                session.bind_hypothesis(hypothesis)
                client = client_factory(**protocol["per_run_transport"],
                    request_guard=lambda cap, task=task: total.reserve(task, cap))
                try:
                    result = run_challenger(session, client,
                        replace(AgentConfig(**protocol["agent_config"]), variant=variant),
                        on_event=lambda e: append_json(trace, {"sequence": e.sequence, "kind": e.kind,
                                                              "details": json.loads(e.details_json)}))
                finally:
                    client.close()
                status, reason, events, requests = result.status, result.reason, result.events, result.requests
                assessment, five_prediction = session.assessment, None
            row = {"protocol_id": protocol["protocol_id"], **task,
                "baseline_prediction": hypothesis["prediction"], "initial_hypothesis": hypothesis,
                "initial_sensor_sequence": frozen["initial_sensor_sequence"],
                "baseline_correct": hypothesis["prediction"] == target.event,
                "true_event": target.event, "five_query_prediction": five_prediction,
                "assessment": assessment, "status": status, "reason": reason,
                "latency_seconds": time.monotonic() - started, "requests": requests,
                "usage": usage_and_cost(events, requests, protocol["prices"]), **audit_metrics(session),
                "well_group": next(r["well_group"] for r in protocol["records"] if r["case_id"] == task["case_id"]),
                "assessment_validation_errors": [{k: value[k] for k in
                    ("validation_code", "field", "correction", "submission_attempt", "repairs_remaining", "contract_version",
                     "validation_context", "underlying_validation_code", "underlying_field")
                    if k in value} for a in session.audit_trail if a.tool == "submit_assessment"
                    for value in [json.loads(a.result_json)] if "error" in value],
                "rejected_assessment_attempts": sum(a.tool == "submit_assessment" and
                    "error" in json.loads(a.result_json) for a in session.audit_trail)}
            append_json(trace, {"kind": "audit_snapshot", "entries": [asdict(a) for a in session.audit_trail]})
            append_json(directory / "results.jsonl", row)
            rows.append(row)
            completed[key(task)] = row
            if on_progress:
                on_progress({**task, "status": status, "reason": reason,
                    "decision": assessment["decision"] if assessment else None,
                    "requests": requests, "estimated_cost_usd": row["usage"]["estimated_cost_usd"]})
            if reason.startswith("evaluation_"):
                break
        return write_challenge_report(directory, protocol, rows, ids)
