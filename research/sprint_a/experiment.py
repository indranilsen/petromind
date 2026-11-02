"""Frozen research runner. No demo hooks; one aggregate Session-A spending ledger."""

from __future__ import annotations

import fcntl
import hashlib
import json
import math
import os
import time
from collections import Counter
from dataclasses import asdict
from pathlib import Path

from petromind.agent import AgentConfig, run_tool_agent
from petromind.audit import canonical, verify_audit
from petromind.eval_protocol import (
    DEFAULT_PRICES,
    digest,
    runtime_versions,
    source_digest,
)
from petromind.eval_runner import append_json, read_jsonl, usage_and_cost
from petromind.meta_api import MetaAPIError, MetaResponsesClient

from .benchmark import from_capture, validate_exchange
from .core import (
    INSTRUCTIONS,
    VARIANTS,
    VERDICTS,
    VERSION,
    ResearchSession,
    connected,
    lookup,
    mechanical,
    tool_definitions,
)

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_LEDGER = ROOT / ".petromind" / "research-session-a-budget"
RUBRIC = {
    "version": "sprint-a-scoring-v1",
    "primary": "Macro recall over SUPPORTED, NOT_ESTABLISHED and CONTRADICTED; missing/failed submissions count as incorrect.",
    "always_abstain_is_not_success": True,
    "minimum_completion": 1.0,
    "minimum_macro_recall": 0.8,
    "minimum_supported_recall": 0.8,
    "minimum_contradicted_recall": 0.8,
    "maximum_supported_causal_errors": 0,
    "minimum_additional_correct_vs_full_source_deterministic": 1,
    "independent_semantic_review_required": True,
    "pilot_only": True,
    "interpretation": "Predeclared research criteria, not industrial physical certification or a production release gate.",
}


def research_digest():
    return digest(
        {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(Path(__file__).parent.glob("*.py"))
        }
    )


class SessionLedger:
    """Hash-linked reservations before HTTP, shared across fresh study directories.

    Reservations never released, even on lost responses. Owner-controlled local
    files are not a tamper-proof billing service. All research invocations must
    use this same Session-A ledger; changing output directories cannot reset it.
    """

    def __init__(self, directory=DEFAULT_LEDGER, cap=5.0):
        if type(cap) not in (int, float) or not math.isfinite(cap) or not 0 < cap <= 5:
            raise ValueError("research_session_cap_must_be_at_most_5")
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        config = self.directory / "session.json"
        if not config.exists():
            with config.open("x") as stream:
                json.dump(
                    {
                        "version": "research-only-session-budget-v1",
                        "hard_estimated_usd": cap,
                        "max_requests": 80,
                        "max_output_tokens": 327680,
                    },
                    stream,
                )
        self.config = json.loads(config.read_text())
        if self.config != {
            "version": "research-only-session-budget-v1",
            "hard_estimated_usd": cap,
            "max_requests": 80,
            "max_output_tokens": 327680,
        }:
            raise ValueError("session_cap_or_configuration_changed")
        self.path = self.directory / "reservations.jsonl"
        self.rows()

    def rows(self):
        rows = read_jsonl(self.path)
        previous = "0" * 64
        for i, row in enumerate(rows, 1):
            if set(row) != {
                "sequence",
                "protocol_id",
                "task_id",
                "variant",
                "input_token_bound",
                "output_cap",
                "estimated_usd_reserved",
                "previous_hash",
                "digest",
            }:
                raise ValueError("reservation_schema_modified")
            if (
                row["sequence"] != i
                or row["previous_hash"] != previous
                or digest({k: v for k, v in row.items() if k != "digest"})
                != row["digest"]
            ):
                raise ValueError("reservation_chain_modified")
            if (
                type(row["estimated_usd_reserved"]) not in (int, float)
                or not math.isfinite(row["estimated_usd_reserved"])
                or row["estimated_usd_reserved"] <= 0
            ):
                raise ValueError("invalid_reservation")
            previous = row["digest"]
        if (
            math.fsum(r["estimated_usd_reserved"] for r in rows)
            > self.config["hard_estimated_usd"] + 1e-10
            or len(rows) > 80
            or sum(r["output_cap"] for r in rows) > 327680
        ):
            raise ValueError("ledger_exceeds_session_limits")
        return rows

    def reserve(self, protocol, task, output_cap, input_bound):
        if (
            type(output_cap) is not int
            or not 16 <= output_cap <= 8192
            or type(input_bound) is not int
            or input_bound <= 0
        ):
            raise ValueError("invalid_request_reservation")
        prices = protocol["prices"]
        estimate = (
            input_bound * prices["input_per_million_usd"]
            + output_cap * prices["output_per_million_usd"]
        ) / 1e6
        with (self.directory / "lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            rows = self.rows()
            cap = min(self.config["hard_estimated_usd"], protocol["max_estimated_usd"])
            if (
                len(rows) >= 80
                or sum(r["output_cap"] for r in rows) + output_cap > 327680
                or math.fsum(r["estimated_usd_reserved"] for r in rows) + estimate > cap
            ):
                raise MetaAPIError("research_session_spending_cap")
            row = {
                "sequence": len(rows) + 1,
                "protocol_id": protocol["protocol_id"],
                **task,
                "input_token_bound": input_bound,
                "output_cap": output_cap,
                "estimated_usd_reserved": estimate,
                "previous_hash": rows[-1]["digest"] if rows else "0" * 64,
            }
            row["digest"] = digest(row)
            append_json(self.path, row)
            with self.path.open("a") as stream:
                stream.flush()
                os.fsync(stream.fileno())

    def summary(self):
        rows = self.rows()
        total = math.fsum(r["estimated_usd_reserved"] for r in rows)
        return {
            "http_reservations": len(rows),
            "conservative_estimated_usd_reserved": total,
            "remaining_conservative_session_usd": self.config["hard_estimated_usd"]
            - total,
            "session_hard_estimated_usd": self.config["hard_estimated_usd"],
            "actual_billed_usd": None,
            "note": "Frozen repository prices and conservative reservations, not a provider invoice guarantee; unknown/failed responses keep full reservations.",
        }


class ResearchClient:
    def __init__(self, protocol, ledger, task, *, factory=MetaResponsesClient):
        self.input_bound = 0
        config = protocol["agent_config"]
        self.client = factory(
            max_requests=config["max_turns"],
            max_output_budget=config["max_turns"] * config["max_output_tokens"],
            max_retries=0,
            request_guard=lambda cap: ledger.reserve(
                protocol, task, cap, self.input_bound
            ),
        )

    @property
    def requests(self):
        return self.client.requests

    @property
    def reserved_output_tokens(self):
        return self.client.reserved_output_tokens

    def create(self, payload, **kw):
        self.input_bound = 2 * len(canonical(payload).encode()) + 8192
        return self.client.create(payload, **kw)

    def close(self):
        self.client.close()


def prepare(
    out,
    *,
    capture=None,
    science_run=None,
    exchange=None,
    max_cost=5,
    ledger_directory=DEFAULT_LEDGER,
):
    out = Path(out)
    if out.exists():
        raise ValueError("fresh_output_directory_required")
    if (
        type(max_cost) not in (int, float)
        or not math.isfinite(max_cost)
        or not 0 < max_cost <= 5
    ):
        raise ValueError("research_session_cap_must_be_at_most_5")
    if exchange is None:
        data, source = from_capture(capture, science_run)
    else:
        data = validate_exchange(exchange)
        source = {
            "independent_exchange_digest": digest(data),
            "reference_author": data["author"],
            "independence_note": "Author and review assertions are metadata, not software certification of independence.",
        }
    config = AgentConfig(
        max_turns=8,
        max_tool_calls=16,
        max_output_tokens=4096,
        reasoning_effort="medium",
        run_timeout=180,
        variant="sensor_only",
    )
    # Two preselected development tasks, not selected using M3 labels/outcomes.
    selected = [
        c
        for c in data["cases"]
        if c["reference"]["name"] in ("exact_observation", "fault9_sufficiency")
    ]
    if len(selected) != 2:
        selected = sorted(data["cases"], key=lambda c: digest(c["public"]))[
            : min(2, len(data["cases"]))
        ]
    protocol = {
        "study": VERSION,
        "research_digest": research_digest(),
        "production_source_digest": source_digest(),
        "runtime": runtime_versions(),
        "source": source,
        "benchmark_digest": digest(data),
        "agent_config": asdict(config),
        "instructions": INSTRUCTIONS,
        "prompt_digest": digest(INSTRUCTIONS),
        "tools": {
            v: tool_definitions(v, any(c["optional_summaries"] for c in data["cases"]))
            for v in VARIANTS
        },
        "variants": list(VARIANTS),
        "rubric": RUBRIC,
        "prices": dict(DEFAULT_PRICES),
        "price_note": "Existing frozen repository estimate, dated 2026-10-27; not current invoice verification.",
        "max_estimated_usd": max_cost,
        "ledger_directory": str(Path(ledger_directory).resolve()),
        "pilot_task_ids": [c["public"]["task_id"] for c in selected],
        "limitations": [
            "Constructed, formalized development claims, not real expert diagnoses or population accuracy.",
            "Full-source deterministic baseline receives the same public proposition contracts, not private reference answers.",
            "Documentation/source-scope scores are not independent engineering certification.",
            "D is a partial reconstruction: original equipment lookup plus captured development-history snapshots, not original M3 telemetry/index.",
            "A has no engineering lookup; B/E use the same fact pool, E changes only source-edge expansion; C adds history; D also exposes original training-event labels.",
            "Frozen historical snapshots use initial charged sensors only; no unqueried target availability is supplied.",
            "One stochastic sample per task/variant is exploratory and does not establish causal graph benefit.",
            "No production changes, M3 test tuning or automatic expansion.",
        ],
        "api_requests_at_freeze": 0,
    }
    protocol["protocol_id"] = digest(protocol)
    SessionLedger(
        ledger_directory
    )  # All study directories share the unchanged $5 hard Session-A cap.
    out.mkdir(parents=True)
    (out / "benchmark.private.json").write_text(canonical(data) + "\n")
    (out / "protocol.json").write_text(canonical(protocol) + "\n")
    (out / "public-cases.json").write_text(
        canonical([c["public"] for c in data["cases"]]) + "\n"
    )
    return {
        "status": "research_protocol_frozen",
        "protocol_id": protocol["protocol_id"],
        "cases": len(data["cases"]),
        "pilot_tasks": len(selected),
        "variants": list(VARIANTS),
        "api_requests": 0,
    }


def load(out):
    out = Path(out)
    protocol = json.loads((out / "protocol.json").read_text())
    if (
        digest({k: v for k, v in protocol.items() if k != "protocol_id"})
        != protocol["protocol_id"]
        or protocol["study"] != VERSION
    ):
        raise ValueError("protocol_modified")
    if (
        protocol["research_digest"] != research_digest()
        or protocol["production_source_digest"] != source_digest()
        or protocol["runtime"] != runtime_versions()
    ):
        raise ValueError("research_code_or_runtime_changed_use_fresh_protocol")
    data = validate_exchange(json.loads((out / "benchmark.private.json").read_text()))
    if digest(data) != protocol["benchmark_digest"]:
        raise ValueError("benchmark_modified")
    return protocol, data


def score_case(case, output, observations, returned_ids=(), facts=()):
    by_id = {f["claim_id"]: f for f in (output or {}).get("findings", [])}
    received = set(returned_ids)
    supplied_facts = [f for f in facts if "knowledge:" + f["id"] in received]
    scores = []
    for claim in case["public"]["claims"]:
        cid = claim["claim_id"]
        expected = case["reference"]["judgments"][cid]
        f = by_id.get(cid)
        observed = f["verdict"] if f else None
        _, required, _ = mechanical(claim, observations, facts, case["history"])
        conditioned, _, _ = mechanical(
            claim, observations, supplied_facts, case["history"]
        )
        citations = set(f["citations"]) if f else set()
        expert_reference = claim["predicate"]["kind"] == "expert_claim"
        warranted = (
            bool(f)
            and citations <= received
            and (
                observed == "NOT_ESTABLISHED"
                or (
                    bool(citations)
                    if expert_reference
                    else bool(required) and set(required) <= citations
                )
            )
        )
        correct = expected != "UNASSESSED" and expected == observed and warranted
        missing = set(required) - received
        if f is None:
            failure = "protocol_execution_failure"
        elif observed == "SUPPORTED" and expected == "NOT_ESTABLISHED":
            failure = "unsupported_inference_or_scope_error"
        elif missing:
            failure = (
                "knowledge_access_disabled"
                if case.get("_variant") in ("A_sensor", "D_legacy_partial")
                else "available_source_not_retrieved"
            )
        elif not correct:
            failure = "formal_reasoning_or_citation_error"
        else:
            failure = None
        scores.append(
            {
                "claim_id": cid,
                "reference": expected,
                "verdict": observed,
                "correct": correct,
                "verdict_matches_reference": expected == observed,
                "scorable": expected != "UNASSESSED",
                "citation_warranted_at_formal_scope": warranted,
                "evidence_conditioned_reference": conditioned,
                "evidence_conditioned_verdict_correct": observed == conditioned
                if conditioned != "UNASSESSED"
                else None,
                "failure_category": failure,
                "required_ids_not_received": sorted(missing),
                "unsupported_causal_supported": claim["predicate"]["kind"]
                in ("causal_inference", "history_implication")
                and expected == "NOT_ESTABLISHED"
                and observed == "SUPPORTED",
                "gap_field_present": bool(f and f["missing_premise"].strip()),
                "next_evidence_field_present": bool(f and f["next_evidence"].strip()),
                "all_citations_received": bool(f is not None and citations <= received),
                "physical_entailment_independently_verified": False,
                "reference_review_status": case["reference"]["review_status"],
                "semantic_entailment_automatically_checked": not expert_reference,
            }
        )
    return scores


def deterministic(case, facts):
    session = ResearchSession(
        case["public"],
        facts,
        case["history"],
        "B_knowledge",
        case["optional_summaries"],
    )
    # Strong baseline may acquire exactly named required evidence, without peeking at its values/availability first.
    for claim in case["public"]["claims"]:
        p = claim["predicate"]
        needed = (
            [p["left_sensor"], p["right_sensor"]]
            if p["kind"] == "cross_sensor_constraint"
            else [p["sensor"]]
            if "sensor" in p
            else p.get("sensors", [])
        )
        for sensor in needed:
            if (
                session.optional
                and sensor not in session.observed
                and session.remaining_budget
            ):
                session.dispatch(
                    "request_sensor",
                    {
                        "sensor_name": sensor,
                        "relevance": "Required by the public formal proposition.",
                    },
                )
    findings = []
    for claim in case["public"]["claims"]:
        verdict, citations, gap = mechanical(
            claim, session.observed, facts, case["history"]
        )
        findings.append(
            {
                "claim_id": claim["claim_id"],
                "verdict": verdict,
                "citations": citations,
                "missing_premise": gap,
                "next_evidence": gap,
                "public_justification": "Exact formal proposition and available source scope; no physical certification.",
            }
        )
    return {"findings": findings, "numeric_observations": []}, session


def summarize_rows(rows):
    result = {}
    for method in ("deterministic", *VARIANTS):
        selected = [r for r in rows if r["variant"] == method]
        scored = [s for r in selected for s in r["scores"] if s["scorable"]]
        reference_counts = Counter(s["reference"] for s in scored)
        recalls = {
            v: (
                sum(s["correct"] and s["reference"] == v for s in scored)
                / reference_counts[v]
                if reference_counts[v]
                else None
            )
            for v in VERDICTS
        }
        result[method] = {
            "attempted": len(selected),
            "completed": sum(r["status"] == "completed" for r in selected),
            "scorable_claims": len(scored),
            "correct": sum(s["correct"] for s in scored),
            "accuracy": sum(s["correct"] for s in scored) / len(scored)
            if scored
            else None,
            "recall_by_verdict": recalls,
            "macro_recall": sum(v for v in recalls.values() if v is not None)
            / sum(v is not None for v in recalls.values())
            if scored
            else None,
            "unsupported_causal_supported": sum(
                s["unsupported_causal_supported"] for s in scored
            ),
            "validation_rejections": sum(
                r.get("validation_rejections", 0) for r in selected
            ),
            "requests": sum(r.get("requests", 0) for r in selected),
            "tokens": {
                k: sum(r.get("usage", {}).get(k, 0) for r in selected)
                for k in ("input_tokens", "output_tokens", "cached_tokens")
            },
            "unsupported_free_text_physical_claims": None,
            "estimated_known_usage_usd": math.fsum(
                r.get("usage", {}).get("estimated_cost_usd", 0) for r in selected
            ),
            "mean_latency_seconds": math.fsum(r["latency_seconds"] for r in selected)
            / len(selected)
            if selected
            else None,
            "failure_categories": dict(
                Counter(s["failure_category"] for s in scored if s["failure_category"])
            ),
            "evidence_conditioned_verdict_correct": sum(
                s["evidence_conditioned_verdict_correct"] is True for s in scored
            ),
            "independent_semantic_reviews": 0,
            "missing_premise_correctness": None,
            "next_evidence_usefulness": None,
            "useful_sensor_selection_rate": None
            if not any(r.get("sensor_requests") for r in selected)
            else "requires_independent_review",
            "physical_correctness_verified": False,
        }
    return result


def paired_comparisons(rows):
    """Descriptive matched-task comparisons only; no independent-sample p-values."""
    indexed = {(r["task_id"], r["variant"]): r for r in rows}
    tasks = sorted({r["task_id"] for r in rows})
    pairs = []
    for left, right in [
        ("A_sensor", "B_knowledge"),
        ("B_knowledge", "C_history"),
        ("B_knowledge", "E_connected"),
        *[("deterministic", v) for v in VARIANTS],
    ]:
        deltas = []
        left_only = right_only = 0
        for task in tasks:
            if (task, left) not in indexed or (task, right) not in indexed:
                continue
            a, b = indexed[task, left], indexed[task, right]
            sa = [s for s in a["scores"] if s["scorable"]]
            sb = [s for s in b["scores"] if s["scorable"]]
            if not sa or len(sa) != len(sb):
                continue
            ac = sum(s["correct"] for s in sa) / len(sa)
            bc = sum(s["correct"] for s in sb) / len(sb)
            deltas.append(bc - ac)
            left_only += ac > bc
            right_only += bc > ac
        pairs.append(
            {
                "left": left,
                "right": right,
                "paired_tasks": len(deltas),
                "right_minus_left_accuracy": sum(deltas) / len(deltas)
                if deltas
                else None,
                "tasks_left_better": left_only,
                "tasks_right_better": right_only,
                "limitation": "Constructed tasks are correlated within incidents; one stochastic run per method cannot establish causal graph benefit.",
            }
        )
    return pairs


def retrieval_probe(data):
    """One fixed public-proposition query, not simulated model query selection."""
    probes = []
    for case in data["cases"]:
        public = case["public"]
        p = public["claims"][0]["predicate"]
        topic = p.get("subject") or (
            "fault:" + str(p["fault_type"])
            if "fault_type" in p
            else p.get("sensor", "P-TPT")
        )
        required = {
            v
            for claim in public["claims"]
            for v in mechanical(
                claim, public["observations"], data["facts"], case["history"]
            )[1]
            if v.startswith("knowledge:")
        }
        for variant in ("B_knowledge", "E_connected"):
            value = (
                connected(data["facts"], topic, public)
                if variant == "E_connected"
                else {"facts": lookup(data["facts"], topic)}
            )
            ids = {"knowledge:" + f["id"] for f in value["facts"]}
            probes.append(
                {
                    "task_id": public["task_id"],
                    "variant": variant,
                    "query": topic,
                    "returned_fact_ids": sorted(ids),
                    "returned_facts": len(ids),
                    "required_fact_count": len(required),
                    "required_fact_recall": len(required & ids) / len(required)
                    if required
                    else None,
                    "serialized_context_bytes": len(canonical(value).encode()),
                    "scope": "Offline lookup behavior only. Extra facts/paths do not establish semantic relevance or reasoning improvement.",
                }
            )
    return probes


def report(out, protocol, data, ledger):
    out = Path(out)
    rows = read_jsonl(out / "results.jsonl")
    baselines = []
    packets = []
    for case in data["cases"]:
        started = time.monotonic()
        output, session = deterministic(case, data["facts"])
        known = set(session.known) | {"knowledge:" + f["id"] for f in data["facts"]}
        baselines.append(
            {
                "task_id": case["public"]["task_id"],
                "variant": "deterministic",
                "status": "completed",
                "latency_seconds": time.monotonic() - started,
                "scores": score_case(
                    case, output, session.observed, known, data["facts"]
                ),
                "output": output,
                "sensor_requests": session.sensor_requests,
                "knowledge_access": "Full frozen fact collection and public proposition contracts; no private reference answers.",
            }
        )
        packets.append(
            {
                "task_id": case["public"]["task_id"],
                "claim": case["public"]["claims"],
                "observations": case["public"]["observations"],
                "reference_basis": case["reference"]["reference_basis"],
                "source_facts": [
                    f
                    for f in data["facts"]
                    if "knowledge:" + f["id"]
                    in {c for f in output["findings"] for c in f["citations"]}
                ],
                "questions": [
                    "Does the source explicitly establish this proposition at the stated scope?",
                    "Does the model identify the actual missing premise rather than inventing a necessary condition?",
                    "Is suggested next evidence concrete, realistic and genuinely discriminating?",
                    "Did any auditor introduce an unsupported physical assertion?",
                ],
                "physical_review_status": "not_self_certified",
            }
        )
    pilot = set(protocol["pilot_task_ids"])
    full_summary = summarize_rows(baselines + rows)
    pilot_summary = summarize_rows(
        [r for r in baselines + rows if r["task_id"] in pilot]
    )
    constant = []
    for c in data["cases"]:
        for v in c["reference"]["judgments"].values():
            if v != "UNASSESSED":
                constant.append(v)
    controls = {
        "always_not_established_accuracy": sum(v == "NOT_ESTABLISHED" for v in constant)
        / len(constant)
        if constant
        else None,
        "always_not_established_macro_recall": 1 / 3
        if set(constant) == set(VERDICTS)
        else None,
        "reference_class_counts": dict(Counter(constant)),
    }
    value = {
        "protocol_id": protocol["protocol_id"],
        "retrieval_probe": retrieval_probe(data),
        "summary": full_summary,
        "paired_comparisons": paired_comparisons(baselines + rows),
        "pilot_summary": pilot_summary,
        "controls": controls,
        "spending": ledger.summary(),
        "gate": "PENDING_LIVE_AND_INDEPENDENT_REVIEW",
        "limitations": protocol["limitations"],
        "api_requests": sum(r.get("requests", 0) for r in rows),
        "next_step": "No automatic expansion. The mechanically formalized set may already have a deterministic ceiling. Independent unreleased tasks and engineering review are needed to establish value beyond rules.",
    }
    (out / "deterministic-results.json").write_text(canonical(baselines) + "\n")
    (out / "report.json").write_text(canonical(value) + "\n")
    (out / "expert-review-packets.private.json").write_text(canonical(packets) + "\n")
    return value


def run(out, *, authorize_paid=False, all_cases=False, factory=MetaResponsesClient):
    out = Path(out)
    protocol, data = load(out)
    ledger = SessionLedger(protocol["ledger_directory"])
    if not authorize_paid:
        raise ValueError("explicit_paid_authorization_required")
    key = os.getenv("MODEL_API_KEY", "").strip()
    if not key or not key.isascii() or any(c.isspace() for c in key):
        value = {
            "status": "blocked",
            "code": "missing_or_invalid_api_key",
            "api_requests": 0,
            "spending": ledger.summary(),
            "instruction": "Export MODEL_API_KEY in the invoking shell, then rerun this same frozen pilot. No paid result or replay is substituted.",
        }
        (out / "execution-status.json").write_text(canonical(value) + "\n")
        report(out, protocol, data, ledger)
        return value
    with (out / "run.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        attempted = {
            (r["task_id"], r["variant"]) for r in read_jsonl(out / "attempts.jsonl")
        }
        selected = (
            data["cases"]
            if all_cases
            else [
                c
                for c in data["cases"]
                if c["public"]["task_id"] in protocol["pilot_task_ids"]
            ]
        )
        for case in selected:
            for variant in sorted(
                VARIANTS,
                key=lambda v: digest(
                    [protocol["protocol_id"], case["public"]["task_id"], v]
                ),
            ):
                task = {"task_id": case["public"]["task_id"], "variant": variant}
                if (task["task_id"], variant) in attempted:
                    continue  # Unknown interrupted attempts are not silently retried.
                append_json(
                    out / "attempts.jsonl",
                    {"protocol_id": protocol["protocol_id"], **task},
                )
                session = ResearchSession(
                    case["public"],
                    data["facts"],
                    case["history"],
                    variant,
                    case["optional_summaries"],
                )
                client = ResearchClient(protocol, ledger, task, factory=factory)
                start = time.monotonic()
                try:
                    config = AgentConfig(**protocol["agent_config"])
                    result = run_tool_agent(
                        session,
                        client,
                        config,
                        instructions=protocol["instructions"],
                        tools=session.model_tools(),
                        initial_history=[
                            {
                                "role": "user",
                                "content": [
                                    {
                                        "type": "input_text",
                                        "text": canonical(session.initial_context()),
                                    }
                                ],
                            }
                        ],
                        prompt_version=VERSION,
                        submission_reason="research_findings_submitted",
                        is_complete=lambda session=session: session.result is not None,
                        stop_reason=lambda session=session: session.stop,
                    )
                finally:
                    client.close()
                usage = usage_and_cost(
                    result.events, result.requests, protocol["prices"]
                )
                returned = {c for c in session.known if c.startswith("knowledge:")}
                relevant = {
                    cid
                    for claim in case["public"]["claims"]
                    for cid in mechanical(
                        claim, session.observed, data["facts"], case["history"]
                    )[1]
                    if cid.startswith("knowledge:")
                }
                snapshot = [asdict(a) for a in session.audit_trail]
                row = {
                    "protocol_id": protocol["protocol_id"],
                    **task,
                    "status": result.status,
                    "reason": result.reason,
                    "output": deepcopy_result(session.result),
                    "scores": score_case(
                        {**case, "_variant": variant},
                        session.result,
                        session.observed,
                        session.known,
                        data["facts"],
                    ),
                    "requests": result.requests,
                    "usage": usage,
                    "latency_seconds": time.monotonic() - start,
                    "validation_rejections": session.failures,
                    "numeric_quotes_validated": len(
                        (session.result or {}).get("numeric_observations", [])
                    ),
                    "tool_counts": dict(Counter(a.tool for a in session.audit_trail)),
                    "repair_attempts": max(0, session.failures - 1),
                    "sensor_sequence": list(session.observed),
                    "initial_sensor_count": len(session.initial),
                    "sensor_requests": session.sensor_requests,
                    "cache_hits": session.cache_hits,
                    "remaining_sensor_budget": session.remaining_budget,
                    "initial_unavailable": sum(
                        not v["available"]
                        for v in case["public"]["observations"].values()
                    ),
                    "new_unavailable": sum(
                        not v["available"]
                        for s, v in session.observed.items()
                        if s not in session.initial
                    ),
                    "context_calls": session.context_calls,
                    "returned_fact_ids": sorted(returned),
                    "required_source_fact_recall": len(relevant & returned)
                    / len(relevant)
                    if relevant
                    else None,
                    "required_source_fact_precision": len(relevant & returned)
                    / len(returned)
                    if relevant and returned
                    else None,
                    "retrieval_metric_scope": "Formal required fact IDs only, not independent semantic relevance.",
                    "audit_valid": verify_audit(session.audit_trail),
                    "audit_digest": session.audit_trail[-1].digest
                    if session.audit_trail
                    else None,
                }
                append_json(out / "results.jsonl", row)
                (out / "traces").mkdir(exist_ok=True)
                # run_tool_agent exports sanitized tool results and usage, not raw model text or encrypted reasoning.
                (out / "traces" / f"{task['task_id']}-{variant}.json").write_text(
                    canonical(
                        {
                            "events": [asdict(e) for e in result.events],
                            "audit": snapshot,
                        }
                    )
                    + "\n"
                )
                if result.reason == "research_session_spending_cap":
                    value = report(out, protocol, data, ledger)
                    return {
                        "status": "session_cap_reached",
                        "api_requests": value["api_requests"],
                        "spending": value["spending"],
                    }
    value = report(out, protocol, data, ledger)
    return {
        "status": "research_stage_finished",
        "stage": "full_explicit" if all_cases else "two_task_pilot",
        "api_requests": value["api_requests"],
        "spending": value["spending"],
        "gate": value["gate"],
    }


def deepcopy_result(result):
    return json.loads(canonical(result)) if result is not None else None
