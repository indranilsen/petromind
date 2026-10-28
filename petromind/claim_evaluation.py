"""Frozen, small development claim audit. No automatic cohort expansion or self-grading."""

from __future__ import annotations

import fcntl
import json
import math
import time
from dataclasses import asdict, fields
from pathlib import Path

from .agent import AgentConfig
from .audit import AuditEntry, canonical, verify_audit
from .claim_auditor import (
    INSTRUCTIONS,
    VERSION,
    ClaimAuditSession,
    citation_checker,
    run_auditor,
    tools,
)
from .eval_protocol import DEFAULT_PRICES, digest, runtime_versions, source_digest
from .eval_runner import append_json, read_jsonl, usage_and_cost
from .knowledge import PhysicalKnowledge
from .meta_api import MetaResponsesClient
from .science_evaluation import CostedClient, SpendingLedger

RUBRIC = {
    "version": "claim-audit-rubric-v1",
    "pilot_tasks": 2,
    "completion_min": 1.0,
    "numeric_citation_faithfulness_min": 1.0,
    "false_rejection_supported_max": 0,
    "unsupported_auditor_claims_max": 0,
    "all_completed_outputs_independently_reviewed": True,
    "additional_correct_semantic_gap_detections_vs_checker_min": 1,
    "specific_actionable_next_evidence_min": 1,
    "note": "Pilot is an operational gate, not population accuracy or proof of general physical verification.",
}


def checked_protocol(p):
    if digest({k: v for k, v in p.items() if k != "protocol_id"}) != p["protocol_id"]:
        raise ValueError("Protocol modified")


def digest_well(w):
    import hashlib

    return hashlib.sha256(w.encode()).hexdigest()


def load_captured(source):
    """Verify the original captured session, not just its self-reported audit flag."""
    source = Path(source)
    p = json.loads((source / "protocol.json").read_text())
    checked_protocol(p)
    parent = p["parent"]
    checked_protocol(parent)
    fit = set(parent["retrieval_split"]["train_wells"])
    dev = set(parent["development_wells"])
    test = set(parent["original_split"]["test_wells"])
    if (
        fit & dev
        or (fit | dev) & test
        or not (dev | test) <= set(parent["retrieval_split"]["test_wells"])
    ):
        raise ValueError("Source well isolation violated")
    roles = {r["case_id"]: r["role"] for r in parent["records"]}
    groups = {r["case_id"]: r["well_group"] for r in parent["records"]}
    dev_groups = {digest_well(w) for w in dev}
    if len(roles) != len(parent["records"]):
        raise ValueError("Duplicate source identifiers")
    traces = {}
    for path in sorted((source / "traces").glob("*.jsonl")):
        events = read_jsonl(path)
        if not events or events[0].get("kind") != "task_started":
            continue
        h = events[0]
        key = (h["case_id"], h["method"])
        if key in traces:
            raise ValueError("Duplicate source traces")
        traces[key] = events
    packets = []
    for row in read_jsonl(source / "results.jsonl"):
        if row["method"] != "muse_physical" or row["status"] != "completed":
            continue
        c = row["case_id"]
        if (
            c not in p["case_ids"]
            or roles.get(c) != "development_pool"
            or groups[c] not in dev_groups
            or row["protocol_id"] != p["protocol_id"]
        ):
            raise ValueError("Source must contain development incidents only")
        events = traces[(c, row["method"])]
        if (
            events[0]["protocol_id"] != p["protocol_id"]
            or events[-1]["kind"] != "audit_snapshot"
        ):
            raise ValueError("Incomplete source trace")
        entries = tuple(AuditEntry(**e) for e in events[-1]["entries"])
        if not verify_audit(entries) or entries[-1].digest != row["audit_digest"]:
            raise ValueError("Source audit chain invalid")
        observed = {}
        for e in entries:
            v = json.loads(e.result_json)
            if e.tool == "get_sensor_history" and "error" not in v:
                observed[v["sensor"]] = v["summary"]
        if (
            observed != row["sensor_quality"]
            or list(observed) != row["sensor_sequence"]
            or not 1 <= len(observed) <= 5
        ):
            raise ValueError("Source observation/budget mismatch")
        h = row["initial_hypothesis"]
        # Explicit public whitelist; never export case labels, wells, filenames or private row metadata.
        hypothesis = {
            "prediction": h["prediction"],
            "confidence_calibrated": False,
            "probabilities": [
                {k: x[k] for k in ("fault_type", "probability", "represented_in_fit")}
                for x in h["probabilities"]
            ],
        }
        packets.append(
            {
                "source_case_id": c,
                "observations": observed,
                "baseline": hypothesis,
                "source_audit_digest": row["audit_digest"],
            }
        )
    if len(packets) < 2:
        raise ValueError(
            "At least two completed captured development incidents required"
        )
    fingerprints = {
        str(path.relative_to(source)): digest(path.read_text())
        for path in sorted(source.rglob("*.jsonl"))
    }
    return p, sorted(packets, key=lambda x: x["source_case_id"]), digest(fingerprints)


def construct_tasks(packets):
    # Coverage depends on the captured evidence; fail explicitly rather than fabricate measurements.
    rising = next(
        (
            p
            for p in packets
            if p["observations"].get("P-PDG", {}).get("delta", 0) > 0
            and p["observations"].get("P-TPT", {}).get("delta", 0) > 0
        ),
        None,
    )
    opposite = next(
        (
            p
            for p in packets
            if p["observations"].get("P-PDG", {}).get("delta", 0) > 0
            and p["observations"].get("P-TPT", {}).get("delta", 0) < 0
        ),
        None,
    )
    missing = next(
        (
            p
            for p in packets
            if not p["observations"].get("ABER-CKGL", {"available": True})["available"]
        ),
        None,
    )
    if not rising or not opposite or not missing:
        raise ValueError(
            "Captured cohort does not supply the predeclared sign/missingness coverage; no fabrication permitted"
        )
    tasks = []

    def add(key, p, claim, verdict, gap, values=(), citations=()):
        packet = {
            "claim": claim,
            "constructed_evaluation_claim": True,
            "observations": p["observations"],
            "baseline": p["baseline"],
            "claimed_values": list(values),
            "claim_citations": list(citations),
            "scope": "Previously charged retrospective 600-second diagnostic window; no new sensor access.",
        }
        tasks.append(
            {
                "task_id": key,
                "source_case_id": p["source_case_id"],
                "source_audit_digest": p["source_audit_digest"],
                "packet": packet,
                "review_target": {
                    "acceptable_verdicts": verdict,
                    "missing_premise": gap,
                },
            }
        )

    v = opposite["observations"]["P-TPT"]["delta"]
    add(
        "numeric_supported",
        opposite,
        f"P-TPT last-minus-first pressure change is {v} Pa. This is a measured trend, not proof of a fault.",
        ["SUPPORTED"],
        "No physical root-cause inference is claimed.",
        [{"sensor": "P-TPT", "metric": "delta", "value": v}],
        ["measurement:P-TPT"],
    )
    add(
        "numeric_contradicted",
        opposite,
        f"P-TPT last-minus-first pressure change is {v + 1000000} Pa.",
        ["CONTRADICTED"],
        "The supplied delta differs from the asserted number.",
        [{"sensor": "P-TPT", "metric": "delta", "value": v + 1000000}],
        ["measurement:P-TPT"],
    )
    add(
        "missing_claimed_observed",
        missing,
        "ABER-CKGL was measured at 25 percent opening in this window; that establishes its actual opening.",
        ["NOT_ESTABLISHED"],
        "All 600 ABER-CKGL samples are missing; obtain a valid calibrated measurement, not an inferred opening.",
        [{"sensor": "ABER-CKGL", "metric": "median", "value": 25}],
        ["measurement:ABER-CKGL"],
    )
    add(
        "valve_encoding",
        opposite,
        "For the 3W ESTADO-DHSV sensor encoding, code 1 means closed.",
        ["CONTRADICTED"],
        "Table 3 documents 1 as open; no actual DHSV reading is supplied here.",
    )
    add(
        "fault_expectation",
        rising,
        "P-PDG and P-TPT both rose. This establishes service-line hydrate (fault 9), because that fault necessarily makes both pressures rise.",
        ["PARTIALLY_SUPPORTED", "NOT_ESTABLISHED"],
        "The positive deltas are observed; no documented necessary/sufficient signature for fault 9 is provided.",
        citations=["measurement:P-PDG", "measurement:P-TPT"],
    )
    add(
        "published_example_consistency",
        opposite,
        "P-PDG rose and P-TPT fell, matching those two directions in the documented fault-2 example. This supports example consistency only; it does not establish fault 2 or exclude another cause.",
        ["SUPPORTED"],
        "Documented example consistency is defensible; universality and root cause are not claimed.",
        citations=["measurement:P-PDG", "measurement:P-TPT"],
    )
    add(
        "plausible_root_cause",
        opposite,
        "P-PDG rose while P-TPT fell, so unexpected DHSV closure is the proven root cause.",
        ["PARTIALLY_SUPPORTED", "NOT_ESTABLISHED"],
        "A matching published example is not a sufficient causal criterion; actual valve state, operational history and alternative causes remain unresolved.",
        citations=["measurement:P-PDG", "measurement:P-TPT"],
    )
    add(
        "single_sensor_analogue",
        opposite,
        "If a historical training incident matches only the P-TPT median, that single-sensor similarity confirms the same fault in this incident.",
        ["NOT_ESTABLISHED"],
        "Conditional constructed claim, not a fabricated retrieved match. Similarity needs discriminative validation and corroborating evidence; another match alone cannot prove fault.",
    )
    return tasks


def prepare(source, out, *, dataset=None, max_cost=2.0):
    if (
        type(max_cost) not in (int, float)
        or not math.isfinite(max_cost)
        or not 0 < max_cost <= 5
    ):
        raise ValueError("Pilot estimated cost cap must be positive and at most $5")
    out = Path(out)
    if out.exists():
        raise ValueError("Use a fresh output directory")
    parent, packets, capture_digest = load_captured(source)
    tasks = construct_tasks(packets)
    histories = {}
    if dataset is not None:
        from .grounding_offline import load_development_cohort
        from .measurements import SensorSummary
        from .retrieval import IncidentRetriever

        split, _, fitting = load_development_cohort(dataset, parent["parent"])
        index = IncidentRetriever(
            fitting,
            split,
            case_ids={r.path: digest(str(i))[:32] for i, r in enumerate(fitting)},
        )
        allowed = {f.name for f in fields(SensorSummary)}
        for p in packets:
            obs = {
                s: SensorSummary(**{k: v for k, v in summary.items() if k in allowed})
                for s, summary in p["observations"].items()
            }
            histories[p["source_case_id"]] = index.search(obs)
    config = AgentConfig(
        max_turns=6, max_tool_calls=8, max_output_tokens=4096, variant="sensor_only"
    )
    protocol = {
        "study": VERSION,
        "source_protocol_id": parent["protocol_id"],
        "capture_digest": capture_digest,
        "source_digest": source_digest(),
        "runtime": runtime_versions(),
        "knowledge_digest": digest(PhysicalKnowledge().graph()),
        "prompt_digest": digest(INSTRUCTIONS),
        "tools_digest": digest([tools(False), tools(True)]),
        "agent_config": asdict(config),
        "prices": DEFAULT_PRICES,
        "tasks": tasks,
        "histories": histories,
        "pilot_task_ids": ["fault_expectation", "published_example_consistency"],
        "rubric": RUBRIC,
        "limits": {
            "pilot": {"requests": 24, "output_tokens": 98304, "estimated_usd": max_cost}
        },
        "limitations": [
            "Eight constructed claims from two previously inspected development incidents; correlated tasks and no population estimate.",
            "Tasks were selected after M5 inspection to test a new capability, not an untouched generalization benchmark.",
            "Only already charged summary evidence is reused; raw sensor timelines are not available in this capture.",
            "The analogue claim is explicitly conditional, not a claimed real historical match.",
            "No independent engineering review is supplied by the software. Physical correctness is not established.",
            "One stochastic output per condition does not establish a causal graph benefit.",
            "No frozen M3 test measurements or labels are used. No automatic benchmark expansion.",
        ],
        "historical_retrieval_enabled": dataset is not None,
        "api_requests": 0,
    }
    protocol["protocol_id"] = digest(protocol)
    out.mkdir(parents=True)
    (out / "protocol.json").write_text(canonical(protocol) + "\n")
    (out / "review-packets.json").write_text(
        canonical([{"task_id": t["task_id"], **t["packet"]} for t in tasks]) + "\n"
    )
    return {
        "status": "protocol_frozen",
        "protocol_id": protocol["protocol_id"],
        "tasks": len(tasks),
        "pilot_tasks": 2,
        "api_requests": 0,
        "historical_retrieval_enabled": dataset is not None,
    }


def validate(p):
    checked_protocol(p)
    if p["source_digest"] != source_digest() or p["runtime"] != runtime_versions():
        raise ValueError("Code/runtime changed; prepare a fresh protocol")
    if (
        p["knowledge_digest"] != digest(PhysicalKnowledge().graph())
        or p["prompt_digest"] != digest(INSTRUCTIONS)
        or p["tools_digest"] != digest([tools(False), tools(True)])
    ):
        raise ValueError("Contract/knowledge changed")


def pilot(out, *, client_factory=MetaResponsesClient):
    out = Path(out)
    with (out / "run.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        p = json.loads((out / "protocol.json").read_text())
        validate(p)
        # Credential validation before any intent; never print or store key contents.
        probe = client_factory(max_requests=1, max_output_budget=4096)
        probe.close()
        rows = read_jsonl(out / "results.jsonl")
        keys = [(r["task_id"], r["method"]) for r in rows]
        if len(keys) != len(set(keys)) or any(
            r["protocol_id"] != p["protocol_id"] for r in rows
        ):
            raise ValueError("Invalid existing results")
        ledger = SpendingLedger(out / "reservations.jsonl", p, "pilot")
        (out / "traces").mkdir(exist_ok=True)
        for task in p["tasks"]:
            if task["task_id"] not in p["pilot_task_ids"]:
                continue
            for method in ("checker", "ungrounded", "grounded"):
                key = (task["task_id"], method)
                if key in keys:
                    continue
                trace = out / "traces" / (digest(key) + ".jsonl")
                if trace.exists():
                    raise ValueError(
                        "Interrupted task: preserve intent; do not selectively retry"
                    )
                append_json(
                    trace,
                    {
                        "kind": "task_started",
                        "protocol_id": p["protocol_id"],
                        "task_id": key[0],
                        "method": method,
                    },
                )
                start = time.monotonic()
                session = None
                if method == "checker":
                    result = citation_checker(task["packet"])
                    status = "completed"
                    reason = "mechanical_checks_only"
                    usage = {}
                    requests = 0
                else:
                    session = ClaimAuditSession(
                        task["packet"],
                        grounded=method == "grounded",
                        history=p["histories"].get(task["source_case_id"], ()),
                    )
                    client = CostedClient(
                        client_factory, ledger, {"task_id": key[0], "method": method}
                    )
                    try:
                        run = run_auditor(
                            session,
                            client,
                            AgentConfig(**p["agent_config"]),
                            on_event=lambda e, trace=trace: append_json(
                                trace,
                                {"kind": e.kind, "details": json.loads(e.details_json)},
                            ),
                        )
                        result = session.result
                        status = run.status
                        reason = run.reason
                        requests = run.requests
                        usage = usage_and_cost(run.events, run.requests, p["prices"])
                    finally:
                        client.close()
                row = {
                    "protocol_id": p["protocol_id"],
                    "task_id": key[0],
                    "method": method,
                    "status": status,
                    "reason": reason,
                    "result": result,
                    "usage": usage,
                    "requests": requests,
                    "latency_seconds": time.monotonic() - start,
                    "sensor_queries_inherited": len(task["packet"]["observations"]),
                    "new_sensor_queries": 0,
                    "audit": []
                    if session is None
                    else [asdict(a) for a in session.audit_trail],
                }
                append_json(out / "results.jsonl", row)
                keys.append(key)
                rows.append(row)
        review = [
            {
                "task_id": r["task_id"],
                "method": r["method"],
                "output_digest": digest(r["result"]),
                "reviewer": "",
                "independent_engineering_review": False,
                "verdict_correct": None,
                "missing_premise_correct": None,
                "next_evidence_specific_and_sufficient": None,
                "unsupported_auditor_claims": None,
                "value_beyond_checker": None,
                "rationale": "",
            }
            for r in rows
            if r["method"] != "checker" and r["status"] == "completed"
        ]
        if not (out / "review-template.json").exists():
            (out / "review-template.json").write_text(canonical(review) + "\n")
        completed_packets = [
            {
                "task_id": r["task_id"],
                "method": r["method"],
                "packet": next(
                    t["packet"] for t in p["tasks"] if t["task_id"] == r["task_id"]
                ),
                "output": r["result"],
                "output_digest": digest(r["result"]),
                "returned_context": [
                    json.loads(a["result_json"])
                    for a in r["audit"]
                    if a["tool"] in {"lookup_knowledge", "search_history"}
                ],
                "review_knowledge": PhysicalKnowledge().context(),
                "instruction": "Review source entailment independently; do not use incident labels or ask Muse to grade itself.",
            }
            for r in rows
            if r["method"] != "checker" and r["status"] == "completed"
        ]
        (out / "completed-review-packets.json").write_text(
            canonical(completed_packets) + "\n"
        )
        return analyze(out)


def verify_result(row, task, p):
    if row["method"] == "checker":
        if row["result"] != citation_checker(task["packet"]):
            raise ValueError("Checker output modified")
        return
    entries = tuple(AuditEntry(**e) for e in row["audit"])
    if not verify_audit(entries):
        raise ValueError("Result audit chain invalid")
    session = ClaimAuditSession(
        task["packet"],
        grounded=row["method"] == "grounded",
        history=p["histories"].get(task["source_case_id"], ()),
    )
    for entry in entries:
        args = json.loads(entry.arguments_json)
        result = json.loads(entry.result_json)
        if "error" in result:
            continue  # rejected arguments are intentionally not retained
        actual = session.dispatch(entry.tool, args)
        if actual != result:
            raise ValueError("Result provenance or computation changed")
    if row["status"] == "completed" and (
        session.result is None or session.result != row["result"]
    ):
        raise ValueError("Completed audit must match a valid terminal submission")
    if row["new_sensor_queries"] != 0 or row["sensor_queries_inherited"] != len(
        task["packet"]["observations"]
    ):
        raise ValueError("Sensor accounting changed")


def analyze(out, reviews=()):
    out = Path(out)
    p = json.loads((out / "protocol.json").read_text())
    checked_protocol(p)
    rows = read_jsonl(out / "results.jsonl")
    tasks = {t["task_id"]: t for t in p["tasks"]}
    planned = {
        (t, m)
        for t in p["pilot_task_ids"]
        for m in ("checker", "ungrounded", "grounded")
    }
    keys = [(r["task_id"], r["method"]) for r in rows]
    if (
        len(keys) != len(set(keys))
        or not set(keys) <= planned
        or any(r["protocol_id"] != p["protocol_id"] for r in rows)
    ):
        raise ValueError("Unplanned, duplicate or wrong-protocol results")
    for row in rows:
        verify_result(row, tasks[row["task_id"]], p)
    bykey = {(r["task_id"], r["method"]): r for r in rows}
    reviewed = {}
    for review in reviews:
        key = (review["task_id"], review["method"])
        r = bykey.get(key)
        if (
            key in reviewed
            or r is None
            or r["method"] == "checker"
            or r["status"] != "completed"
            or review["output_digest"] != digest(r["result"])
            or not review["reviewer"]
            or not review["rationale"]
            or review["independent_engineering_review"] is not True
            or any(
                type(review[x]) is not bool
                for x in (
                    "verdict_correct",
                    "missing_premise_correct",
                    "next_evidence_specific_and_sufficient",
                    "value_beyond_checker",
                )
            )
            or type(review["unsupported_auditor_claims"]) is not int
            or review["unsupported_auditor_claims"] < 0
        ):
            raise ValueError(
                "Complete independent reviews bound to exact outputs required"
            )
        reviewed[key] = review
    summary = {}
    for method in ("checker", "ungrounded", "grounded"):
        part = [r for r in rows if r["method"] == method]
        done = [r for r in part if r["status"] == "completed"]
        rr = [
            reviewed[(r["task_id"], method)]
            for r in done
            if (r["task_id"], method) in reviewed
        ]
        summary[method] = {
            "attempted": len(part),
            "completed": len(done),
            "requests": sum(r["requests"] for r in part),
            "estimated_cost_usd": sum(
                r["usage"].get("estimated_cost_usd", 0) for r in part
            ),
            "mean_latency_seconds": sum(r["latency_seconds"] for r in part) / len(part)
            if part
            else None,
            "tokens": {
                k: sum(r["usage"].get(k, 0) for r in part)
                for k in ("input_tokens", "output_tokens", "cached_tokens")
            },
            "reviewed": len(rr),
            "independently_correct_verdicts": sum(x["verdict_correct"] for x in rr)
            if rr
            else None,
            "independently_correct_missing_premises": sum(
                x["missing_premise_correct"] for x in rr
            )
            if rr
            else None,
            "independently_specific_next_evidence": sum(
                x["next_evidence_specific_and_sufficient"] for x in rr
            )
            if rr
            else None,
            "independently_useful_beyond_checker": sum(
                x["value_beyond_checker"] for x in rr
            )
            if rr
            else None,
            "validated_numeric_observations": sum(
                len(r["result"]["numeric_observations"]) for r in done
            )
            if method != "checker"
            else None,
            "validated_source_id_citations": sum(
                len(f["citations"]) for r in done for f in r["result"]["findings"]
            )
            if method != "checker"
            else None,
            "physical_correctness_verified": False,
            "failures_by_reason": {
                reason: sum(
                    r["reason"] == reason for r in part if r["status"] != "completed"
                )
                for reason in sorted(
                    {r["reason"] for r in part if r["status"] != "completed"}
                )
            },
            "unsupported_auditor_claims": sum(
                x["unsupported_auditor_claims"] for x in rr
            )
            if rr
            else None,
            "verdict_agreement_with_constructed_target_not_physical_truth": sum(
                r["result"]["verdict"]
                in tasks[r["task_id"]]["review_target"]["acceptable_verdicts"]
                for r in done
            )
            if method != "checker"
            else None,
        }
    # A semantic judgment is never replaced by matching a constructed target label.
    grounded = [reviewed[k] for k in reviewed if k[1] == "grounded"]
    gate = "PENDING"
    rubric = p["rubric"]
    expected_muse_reviews = 2 * len(p["pilot_task_ids"])
    if set(keys) == planned and len(reviewed) == expected_muse_reviews:
        good = (
            summary["grounded"]["completed"] / len(p["pilot_task_ids"])
            >= rubric["completion_min"]
            and all(
                x["verdict_correct"]
                and x["unsupported_auditor_claims"]
                <= rubric["unsupported_auditor_claims_max"]
                for x in grounded
            )
            and sum(
                x["missing_premise_correct"] and x["value_beyond_checker"]
                for x in grounded
            )
            >= rubric["additional_correct_semantic_gap_detections_vs_checker_min"]
            and sum(x["next_evidence_specific_and_sufficient"] for x in grounded)
            >= rubric["specific_actionable_next_evidence_min"]
        )
        gate = "BOUNDED_DEMO_GO" if good else "NARROW_SCOPE"
    report = {
        "protocol_id": p["protocol_id"],
        "api_requests": sum(r["requests"] for r in rows),
        "summary": summary,
        "gate": gate,
        "limitations": p["limitations"],
        "next_step": "Independent source-based review; no automatic larger run or UI capability claim.",
    }
    (out / "report.json").write_text(canonical(report) + "\n")
    return report


def offline_check(out):
    """Run all deterministic controls, without an API key or any model call."""
    out = Path(out)
    p = json.loads((out / "protocol.json").read_text())
    validate(p)
    results = [
        {"task_id": t["task_id"], **citation_checker(t["packet"])} for t in p["tasks"]
    ]
    payload = {
        "protocol_id": p["protocol_id"],
        "api_requests": 0,
        "tasks": len(results),
        "results": results,
        "limitation": "No semantic, physical or root-cause validation. False numeric match includes missing readings, which do not imply a contrary value.",
    }
    (out / "checker-results.json").write_text(canonical(payload) + "\n")
    return payload
