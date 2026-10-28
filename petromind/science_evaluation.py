"""Frozen development-only, paired, one-test study with durable spending caps."""

from __future__ import annotations

import fcntl
import json
import math
import time
from dataclasses import asdict
from pathlib import Path

import numpy as np
import pandas as pd

from .agent import AgentConfig
from .audit import canonical
from .baselines import GaussianEvidence, posterior
from .challenger import observe_adaptively
from .diagnostic_tests import REGISTRY, VERSION
from .eval_protocol import DEFAULT_PRICES, digest, runtime_versions, source_digest
from .eval_runner import append_json, read_jsonl, audit_metrics, usage_and_cost
from .grounding_offline import load_development_cohort
from .knowledge import PhysicalKnowledge
from .meta_api import MetaAPIError, MetaResponsesClient
from .reference import PreWindowReference
from .scientist import (
    ExperimentSession,
    INSTRUCTIONS,
    PROMPT_VERSION,
    run_scientist,
    tools,
)

METHODS = ("information_gain", "muse_no_graph", "muse_physical")
GATE = {
    "min_cases": 6,
    "min_correct_initial": 3,
    "min_wrong_initial": 3,
    "completion": 0.8,
    "physically_justified_planning": 0.8,
    "faithful_interpretation": 0.8,
    "useful_discrimination": 0.5,
    "unsupported_plan_claims_max": 0,
    "unsupported_interpretation_claims_max": 0,
    "additional_correct_vs_information_gain_min": 1,
    "additional_discriminating_tests_vs_information_gain_min": 1,
    "all_completed_cases_independently_reviewed": True,
}
IG = {
    "samples": 64,
    "seed": 501,
    "assumption": "Fitted diagonal-Gaussian features conditionally independent across new sensors; entropy gain per new sensor. Does not model spectral/reference features.",
}


def predicate(value, expected):
    if value is None or expected["relation"] == "unknown":
        return None
    return (
        value > expected["threshold"]
        if expected["relation"] == "gt"
        else value < expected["threshold"]
    )


def choose_information_gain(model, session):
    """Monte Carlo expected entropy reduction, no unrequested target measurements."""
    score = model.prior.copy()
    for s, o in session.observations.items():
        score += model.evidence(s, o)
    probs = posterior(score)
    entropy = -float(np.sum(probs * np.log(np.maximum(probs, 1e-300))))
    choices = []
    for definition in session.catalog():
        if not definition["executable"]:
            continue
        template = REGISTRY[definition["id"]]
        new = sorted(set(template.sensors) - set(session.queries))
        rng = np.random.default_rng(IG["seed"] + int(digest(template.id)[:8], 16))
        classes = rng.choice(len(model.classes), size=IG["samples"], p=probs)
        simulated = np.tile(score, (IG["samples"], 1))
        for sensor in new:
            _, _, means, var = model.params[sensor]
            z = np.clip(rng.normal(means[classes], np.sqrt(var[classes])), -10, 10)
            simulated += -0.5 * (
                np.log(2 * np.pi * var)[None, :, :]
                + (z[:, None, :] - means[None, :, :]) ** 2 / var[None, :, :]
            ).sum(axis=2)
        weights = np.exp(simulated - simulated.max(axis=1, keepdims=True))
        weights /= weights.sum(axis=1, keepdims=True)
        after = -np.sum(weights * np.log(np.maximum(weights, 1e-300)), axis=1).mean()
        gain = max(0.0, entropy - float(after)) if new else 0.0
        choices.append((gain / max(1, len(new)), template.id, gain))
    if not choices:
        raise ValueError("No executable test")
    best = sorted(choices, key=lambda x: (-x[0], x[1]))[0]
    return best[1], {
        "expected_entropy_reduction_nats": best[2],
        "gain_per_new_sensor": best[0],
        **IG,
    }


def cohort_spec(parent, n_cases=6):
    """Freeze membership/rubric from existing private development metadata only."""
    if (
        digest({k: v for k, v in parent.items() if k != "protocol_id"})
        != parent["protocol_id"]
    ):
        raise ValueError("Parent protocol modified")
    if type(n_cases) is not int or not 5 <= n_cases <= 8:
        raise ValueError("Use 5–8 development cases")
    groups = {
        r["case_id"]: r["well_group"]
        for r in parent["records"]
        if r["role"] == "development_pool"
    }
    selected = []
    used_classes = set()
    used_wells = set()
    pool = list(parent["selected"])
    while pool and len(selected) < n_cases:
        for correct in (False, True):
            candidates = [r for r in pool if r["baseline_correct"] == correct]
            if not candidates:
                continue
            row = min(
                candidates,
                key=lambda r: (
                    r["true_event"] in used_classes,
                    groups[r["case_id"]] in used_wells,
                    digest([501, r["case_id"]]),
                ),
            )
            selected.append(row["case_id"])
            used_classes.add(row["true_event"])
            used_wells.add(groups[row["case_id"]])
            pool.remove(row)
            if len(selected) == n_cases:
                break
    if len(selected) < 5:
        raise ValueError("Fewer than five independent development incidents available")
    lookup = {r["case_id"]: r for r in parent["selected"]}
    if not {lookup[k]["baseline_correct"] for k in selected} == {False, True}:
        raise ValueError("Both correct and incorrect initial diagnoses required")
    result = {
        "version": "m5-cohort-lock-v1",
        "parent_protocol_id": parent["protocol_id"],
        "case_ids": selected,
        "pilot_case_ids": selected[:2],
        "class_counts": {
            str(c): sum(lookup[k]["true_event"] == c for k in selected)
            for c in sorted(used_classes)
        },
        "initial_correct": sum(lookup[k]["baseline_correct"] for k in selected),
        "selected_well_count": len(used_wells),
        "selection": "Alternating wrong/correct; prefer new classes and wells; hash seed 501. Outcome-stratified, not population accuracy.",
        "gate": dict(GATE),
        "registry_digest": digest([asdict(t) for t in REGISTRY.values()]),
        "knowledge_digest": digest(PhysicalKnowledge().graph()),
        "prompt_digest": digest(INSTRUCTIONS),
        "tool_digest": digest(tools()),
        "api_requests": 0,
    }
    result["cohort_lock_id"] = digest(result)
    return result


def freeze(dataset, parent, out, n_cases=6, pilot_cost=5.0):
    if (
        type(n_cases) is not int
        or not 5 <= n_cases <= 8
        or not math.isfinite(pilot_cost)
        or not 0 < pilot_cost <= 20
    ):
        raise ValueError("Use 5–8 cases and a positive pilot cap up to $20")
    out = Path(out)
    if out.exists() and any(out.iterdir()):
        raise ValueError("Use a fresh output directory")
    load_development_cohort(dataset, parent)
    cohort = cohort_spec(parent, n_cases)
    selected = cohort["case_ids"]
    config = AgentConfig(
        max_turns=8, max_tool_calls=12, max_output_tokens=4096, variant="sensor_only"
    )
    protocol = {
        "study": "m5-one-test-v1",
        "parent": parent,
        "case_ids": selected,
        "pilot_case_ids": selected[:2],
        "selection": "Alternating initial wrong/correct, preferring new classes and wells, hash tie-break; outcome-stratified, not population accuracy.",
        "class_counts": cohort["class_counts"],
        "initial_correct": cohort["initial_correct"],
        "selected_well_count": cohort["selected_well_count"],
        "cohort_lock_id": cohort["cohort_lock_id"],
        "source_digest": source_digest(),
        "runtime": runtime_versions(),
        "registry_version": VERSION,
        "registry_digest": digest([asdict(t) for t in REGISTRY.values()]),
        "knowledge_digest": digest(PhysicalKnowledge().graph()),
        "prompt_version": PROMPT_VERSION,
        "prompt_digest": digest(INSTRUCTIONS),
        "tool_digest": digest(tools()),
        "agent_config": asdict(config),
        "gate": dict(GATE),
        "information_gain": dict(IG),
        "prices": dict(DEFAULT_PRICES),
        "limits": {
            "pilot": {
                "requests": 40,
                "output_tokens": 163840,
                "estimated_usd": float(pilot_cost),
            },
            "development": {
                "requests": 120,
                "output_tokens": 491520,
                "estimated_usd": float(pilot_cost * 3),
            },
        },
        "reference": {
            "seconds": 300,
            "min_samples": 30,
            "normality": "unverified_pre_window",
        },
        "cadence_hz": 1,
        "api_requests": 0,
    }
    protocol["protocol_id"] = digest(protocol)
    out.mkdir(parents=True, exist_ok=True)
    (out / "protocol.json").write_text(json.dumps(protocol, indent=2) + "\n")
    return protocol


class SpendingLedger:
    def __init__(self, path, protocol, stage):
        self.path = Path(path)
        self.protocol = protocol
        self.limits = protocol["limits"][stage]
        self.rows = read_jsonl(path)
        if any(r["protocol_id"] != protocol["protocol_id"] for r in self.rows):
            raise ValueError("Wrong reservation ledger")

    def reserve(self, task, cap, input_bound):
        prices = self.protocol["prices"]
        estimate = (
            input_bound * prices["input_per_million_usd"]
            + cap * prices["output_per_million_usd"]
        ) / 1e6
        if (
            len(self.rows) >= self.limits["requests"]
            or sum(r["output_cap"] for r in self.rows) + cap
            > self.limits["output_tokens"]
            or sum(r["estimated_usd_reserved"] for r in self.rows) + estimate
            > self.limits["estimated_usd"]
        ):
            raise MetaAPIError("science_spending_cap")
        row = {
            "protocol_id": self.protocol["protocol_id"],
            **task,
            "output_cap": cap,
            "input_token_bound": input_bound,
            "estimated_usd_reserved": estimate,
        }
        append_json(self.path, row)
        self.rows.append(row)


class CostedClient:
    """Conservative byte-based input reservation plus fixed framing allowance.

    A cap on estimated charges under frozen prices, not a vendor invoice guarantee.
    Every retry reserves separately through the ordinary transport guard.
    """

    def __init__(self, factory, ledger, task):
        self.input_bound = 0
        self.client = factory(
            max_requests=10,
            max_output_budget=40960,
            max_retries=2,
            request_guard=lambda cap: ledger.reserve(task, cap, self.input_bound),
        )

    @property
    def requests(self):
        return self.client.requests

    @property
    def reserved_output_tokens(self):
        return self.client.reserved_output_tokens

    def create(self, payload, **kwargs):
        self.input_bound = 2 * len(canonical(payload).encode()) + 8192
        return self.client.create(payload, **kwargs)

    def close(self):
        self.client.close()


def load_reference(target, settings):
    # Trusted retrospective onset selection, same as read_incident. The reference
    # uses no class/state labels for normality or fitting; only strict earlier rows.
    raw = pd.read_parquet(target.path)
    labels = pd.to_numeric(raw["class"], errors="coerce")
    start = raw.index[np.flatnonzero(labels.isin(range(101, 110)).to_numpy())[0]]
    return PreWindowReference(
        raw,
        start,
        ["P-TPT"],
        seconds=settings["seconds"],
        min_samples=settings["min_samples"],
    )


def expectation_source_matches(session):
    plan = session.plan
    if not plan:
        return {}
    result = {}
    hypotheses = {
        "baseline": json.loads(session._hypothesis)["prediction"],
        "alternative": session.alternative,
    }
    facts = {f.id: f for f in PhysicalKnowledge().facts}
    for role, fault in hypotheses.items():
        e = plan[role + "_expected"]
        ids = plan["knowledge_ids"]
        direction = None
        tree = f"example:{fault}:P-TPT"
        downhole = f"example:{fault}:P-PDG"
        if tree in ids and tree in facts:
            tree_direction = facts[tree].relation
            if plan["test_id"] == "tree_trend":
                direction = {"example:increase": "gt", "example:decrease": "lt"}.get(
                    tree_direction
                )
            elif (
                plan["test_id"] == "paired_pressure_trends"
                and downhole in ids
                and downhole in facts
            ):
                a, b = facts[downhole].relation, tree_direction
                if a in {"example:increase", "example:decrease"} and b in {
                    "example:increase",
                    "example:decrease",
                }:
                    direction = "gt" if a == b else "lt"
        result[role] = bool(
            session.physical
            and e["threshold"] == 0
            and direction
            and e["relation"] == direction
        )
    return result


def run(
    directory,
    dataset,
    stage="pilot",
    *,
    reviewed=False,
    client_factory=MetaResponsesClient,
    on_progress=None,
):
    directory = Path(directory)
    if stage not in {"pilot", "development"}:
        raise ValueError("Invalid stage")
    with (directory / "run.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        protocol = json.loads((directory / "protocol.json").read_text())
        if (
            digest({k: v for k, v in protocol.items() if k != "protocol_id"})
            != protocol["protocol_id"]
        ):
            raise ValueError("Protocol modified")
        if (
            protocol["source_digest"] != source_digest()
            or protocol["runtime"] != runtime_versions()
        ):
            raise ValueError("Frozen code/runtime changed")
        split, by_id, fit = load_development_cohort(dataset, protocol["parent"])
        ids = protocol["pilot_case_ids"] if stage == "pilot" else protocol["case_ids"]
        rows = read_jsonl(directory / "results.jsonl")
        done = {(r["case_id"], r["method"]): r for r in rows}
        valid = {(c, m) for c in protocol["case_ids"] for m in METHODS}
        if (
            len(done) != len(rows)
            or not set(done) <= valid
            or any(r["protocol_id"] != protocol["protocol_id"] for r in rows)
        ):
            raise ValueError("Invalid results")
        if stage == "development" and (
            not reviewed
            or not all(
                (c, m) in done and done[c, m]["status"] == "completed"
                for c in protocol["pilot_case_ids"]
                for m in METHODS
            )
        ):
            raise ValueError("Explicit review of a complete successful pilot required")
        plan = [
            {"case_id": c, "method": m}
            for c in ids
            for m in sorted(METHODS, key=lambda m: digest([501, c, m]))
        ]
        traces = directory / "traces"
        traces.mkdir(exist_ok=True)
        for task in plan:
            if (task["case_id"], task["method"]) not in done and (
                traces / (digest(task) + ".jsonl")
            ).exists():
                raise ValueError("Interrupted task: no automatic retry")
        if any(
            (t["case_id"], t["method"]) not in done
            and t["method"] != "information_gain"
            for t in plan
        ):
            probe = client_factory(
                max_requests=10, max_output_budget=40960, max_retries=2
            )
            probe.close()
        names = tuple(sorted({s for r in fit for s in r.measurements}))
        model = GaussianEvidence(fit, names)
        ledger = SpendingLedger(directory / "reservations.jsonl", protocol, stage)
        frozen = {r["case_id"]: r for r in protocol["parent"]["selected"]}
        for task in plan:
            key = task["case_id"], task["method"]
            if key in done:
                continue
            target = by_id[task["case_id"]]
            reference = load_reference(target, protocol["reference"])
            session = ExperimentSession(
                target.measurements,
                names,
                physical=task["method"] == "muse_physical",
                reference=reference,
            )
            hypothesis = observe_adaptively(model, session, 2)
            if (
                hypothesis != frozen[task["case_id"]]["initial_hypothesis"]
                or list(session.queries)
                != frozen[task["case_id"]]["initial_sensor_sequence"]
            ):
                raise ValueError("Initial evidence differs")
            session.bind_experiment(hypothesis)
            trace = traces / (digest(task) + ".jsonl")
            append_json(
                trace,
                {
                    "kind": "task_started",
                    **task,
                    "protocol_id": protocol["protocol_id"],
                },
            )
            started = time.monotonic()
            ig = None
            if task["method"] == "information_gain":
                test_id, ig = choose_information_gain(model, session)
                session.dispatch(
                    "propose_test",
                    {
                        "test_id": test_id,
                        "required_sensors": list(REGISTRY[test_id].sensors),
                        "baseline_expected": {"relation": "unknown", "threshold": 0},
                        "alternative_expected": {"relation": "unknown", "threshold": 0},
                        "knowledge_ids": [],
                        "uncertainty": "Selection by statistical entropy gain, without a verified physical direction.",
                    },
                )
                result = session.dispatch("execute_test", {})
                session.dispatch(
                    "assess_test",
                    {
                        "result_id": result["result_id"],
                        "baseline_relation": "inconclusive",
                        "alternative_relation": "inconclusive",
                        "uncertainty": "Conventional policy supplies posterior updates, not physical interpretations.",
                    },
                )
                status, reason, events, requests = (
                    "completed",
                    "conventional_test_completed",
                    (),
                    0,
                )
            else:
                client = CostedClient(client_factory, ledger, task)
                try:
                    result = run_scientist(
                        session,
                        client,
                        AgentConfig(**protocol["agent_config"]),
                        on_event=lambda e: append_json(
                            trace,
                            {"kind": e.kind, "details": json.loads(e.details_json)},
                        ),
                    )
                    status, reason, events, requests = (
                        result.status,
                        result.reason,
                        result.events,
                        result.requests,
                    )
                finally:
                    client.close()
            # No new queries: every policy's original classifier gets all acquired evidence.
            updated = observe_adaptively(model, session, 0)
            value = (
                session.test_result["primary_value"] if session.test_result else None
            )
            comparisons = (
                [
                    predicate(value, session.plan[k + "_expected"])
                    for k in ("baseline", "alternative")
                ]
                if session.plan
                else [None, None]
            )
            row = {
                "protocol_id": protocol["protocol_id"],
                **task,
                "status": status,
                "reason": reason,
                "initial_hypothesis": hypothesis,
                "alternative_fault_type": session.alternative,
                "updated_hypothesis": updated,
                "true_event": target.event,
                "candidate_pair_contains_truth": target.event
                in {hypothesis["prediction"], session.alternative},
                "initial_correct": hypothesis["prediction"] == target.event,
                "updated_correct": updated["prediction"] == target.event,
                "plan": session.plan,
                "test_result": session.test_result,
                "assessment": session.assessment,
                "ig": ig,
                "example_source_matches_not_physical_proof": expectation_source_matches(
                    session
                ),
                "numeric_predictions_distinguished": all(
                    v is not None for v in comparisons
                )
                and comparisons[0] != comparisons[1],
                "validation_errors": [
                    {
                        "tool": a.tool,
                        "code": json.loads(a.result_json)["validation_code"],
                        "field": json.loads(a.result_json)["field"],
                    }
                    for a in session.audit_trail
                    if isinstance(json.loads(a.result_json), dict)
                    and "validation_code" in json.loads(a.result_json)
                ],
                "validation_failures": session.validation_failures,
                "latency_seconds": time.monotonic() - started,
                "requests": requests,
                "usage": usage_and_cost(events, requests, protocol["prices"]),
                **audit_metrics(session),
            }
            append_json(
                trace,
                {
                    "kind": "audit_snapshot",
                    "entries": [asdict(a) for a in session.audit_trail],
                },
            )
            append_json(directory / "results.jsonl", row)
            rows.append(row)
            done[key] = row
            if on_progress:
                on_progress(
                    {
                        **task,
                        "status": status,
                        "reason": reason,
                        "requests": requests,
                        "estimated_cost_usd": row["usage"]["estimated_cost_usd"],
                    }
                )
            if reason == "science_spending_cap":
                break
        report = analyze(protocol, rows, ids)
        (directory / "report.json").write_text(json.dumps(report, indent=2) + "\n")
        packets = [
            {
                k: r[k]
                for k in (
                    "case_id",
                    "method",
                    "initial_hypothesis",
                    "alternative_fault_type",
                    "plan",
                    "test_result",
                    "assessment",
                    "sensor_sequence",
                )
            }
            for r in rows
        ]
        for packet in packets:
            packet["review_knowledge"] = PhysicalKnowledge().context()
        (directory / "review-packets.json").write_text(
            json.dumps(packets, indent=2) + "\n"
        )
        template = [
            {
                "case_id": r["case_id"],
                "method": r["method"],
                "investigation_digest": investigation_digest(r),
                "reviewer": "",
                "rationale": "",
                "physically_justified_plan": None,
                "expectations_documented": None,
                "meaningful_discrimination": None,
                "interpretation_faithful": None,
                "abstention_appropriate": None,
                "unsupported_plan_claims": None,
                "unsupported_interpretation_claims": None,
            }
            for r in rows
            if r["assessment"]
        ]
        (directory / "review-template.json").write_text(
            json.dumps(template, indent=2) + "\n"
        )
        return report


def investigation_digest(row):
    return digest(
        {
            k: row[k]
            for k in (
                "plan",
                "test_result",
                "assessment",
                "initial_hypothesis",
                "alternative_fault_type",
            )
        }
    )


def analyze(protocol, rows, ids, reviews=()):
    if (
        digest({k: v for k, v in protocol.items() if k != "protocol_id"})
        != protocol["protocol_id"]
    ):
        raise ValueError("Protocol modified")
    gate = protocol["gate"]
    valid = {(c, m) for c in protocol["case_ids"] for m in METHODS}
    keys = [(r["case_id"], r["method"]) for r in rows]
    if (
        len(set(keys)) != len(keys)
        or not set(keys) <= valid
        or any(r["protocol_id"] != protocol["protocol_id"] for r in rows)
    ):
        raise ValueError("Invalid results")
    if not set(ids) <= set(protocol["case_ids"]) or len(set(ids)) != len(ids):
        raise ValueError("Invalid comparison cohort")
    part = [r for r in rows if r["case_id"] in ids]
    summaries = {}
    review_map = {(r["case_id"], r["method"]): r for r in reviews}
    if len(review_map) != len(reviews) or not set(review_map) <= {
        (c, m) for c in ids for m in METHODS
    }:
        raise ValueError("Duplicate or unrelated reviews")
    conventional = {r["case_id"]: r for r in part if r["method"] == "information_gain"}
    for method in METHODS:
        records = [r for r in part if r["method"] == method]
        completed = [r for r in records if r["status"] == "completed"]
        summary = {
            "attempted": len(records),
            "candidate_pair_contains_truth": sum(
                r["candidate_pair_contains_truth"] for r in records
            ),
            "completed": len(completed),
            "updated_correct": sum(r["updated_correct"] for r in records),
            "initial_correct": sum(r["initial_correct"] for r in records),
            "sensor_queries": sum(len(r["sensor_sequence"]) for r in records),
            "numeric_predictions_distinguished": sum(
                r["numeric_predictions_distinguished"] for r in records
            ),
            "validation_failures": sum(r["validation_failures"] for r in records),
            "both_inconclusive": sum(
                bool(r["assessment"])
                and all(
                    r["assessment"][k + "_relation"] == "inconclusive"
                    for k in ("baseline", "alternative")
                )
                for r in records
            ),
            "estimated_cost_usd": sum(
                r["usage"]["estimated_cost_usd"] for r in records
            ),
            "usage_complete": all(r["usage"]["cost_complete"] for r in records),
            "requests": sum(r["requests"] for r in records),
            "mean_latency_seconds": float(
                np.mean([r["latency_seconds"] for r in records])
            )
            if records
            else None,
            "tokens": {
                k: sum(r["usage"][k] for r in records)
                for k in ("input_tokens", "output_tokens", "cached_tokens")
            },
            "recommendation": None,
        }
        judged = []
        for row in completed:
            review = review_map.get((row["case_id"], method))
            if review is None:
                continue
            if (
                review.get("investigation_digest") != investigation_digest(row)
                or not review.get("reviewer")
                or not review.get("rationale")
                or any(
                    type(review.get(k)) is not bool
                    for k in (
                        "physically_justified_plan",
                        "expectations_documented",
                        "meaningful_discrimination",
                        "interpretation_faithful",
                        "abstention_appropriate",
                    )
                )
                or any(
                    type(review.get(k)) is not int or review[k] < 0
                    for k in (
                        "unsupported_plan_claims",
                        "unsupported_interpretation_claims",
                    )
                )
            ):
                raise ValueError(
                    "Complete independent reviews bound to exact investigations required"
                )
            judged.append(review)
        summary.update(
            independent_reviews=len(judged),
            reviewed_meaningful_tests=sum(
                r["meaningful_discrimination"] for r in judged
            ),
            reviewed_faithful_interpretations=sum(
                r["interpretation_faithful"] for r in judged
            ),
            reviewed_appropriate_abstentions=sum(
                r["abstention_appropriate"] for r in judged
            ),
            unsupported_plan_claims=sum(r["unsupported_plan_claims"] for r in judged),
            unsupported_interpretation_claims=sum(
                r["unsupported_interpretation_claims"] for r in judged
            ),
            completed_updated_correct=sum(r["updated_correct"] for r in completed),
            executable_tests_selected=sum(r["plan"] is not None for r in records),
            tests_returning_measurement=sum(
                r["test_result"] is not None
                and r["test_result"]["primary_value"] is not None
                for r in records
            ),
            documented_example_matches_not_physical_proof=sum(
                sum(r["example_source_matches_not_physical_proof"].values())
                for r in records
            ),
            invalid_required_sensor_declarations=sum(
                e["code"] == "sensor_requirements_mismatch"
                for r in records
                for e in r.get("validation_errors", [])
            ),
            invalid_numeric_interpretations=sum(
                e["code"] == "numeric_interpretation_mismatch"
                for r in records
                for e in r.get("validation_errors", [])
            ),
        )
        if method != "information_gain":
            enough = (
                len(ids) >= gate["min_cases"]
                and sum(r["initial_correct"] for r in records)
                >= gate["min_correct_initial"]
                and sum(not r["initial_correct"] for r in records)
                >= gate["min_wrong_initial"]
            )
            complete = (
                len(records) == len(ids)
                and len(completed) / len(ids) >= gate["completion"]
            )
            recommendation = "PENDING"
            if enough and len(records) == len(ids) and not complete:
                recommendation = "NO GO"
            elif (
                enough
                and complete
                and len(judged) == len(completed)
                and summaries["information_gain"]["independent_reviews"] == len(ids)
            ):
                n = len(records)
                planning = (
                    sum(
                        r["physically_justified_plan"] and r["expectations_documented"]
                        for r in judged
                    )
                    / n
                    >= gate["physically_justified_planning"]
                    and sum(r["meaningful_discrimination"] for r in judged) / n
                    >= gate["useful_discrimination"]
                    and sum(r["unsupported_plan_claims"] for r in judged)
                    <= gate["unsupported_plan_claims_max"]
                )
                faithful = (
                    sum(r["interpretation_faithful"] for r in judged) / n
                    >= gate["faithful_interpretation"]
                    and sum(r["unsupported_interpretation_claims"] for r in judged)
                    <= gate["unsupported_interpretation_claims_max"]
                )
                delta = sum(
                    int(r["updated_correct"] and r["status"] == "completed")
                    - int(conventional[r["case_id"]]["updated_correct"])
                    for r in records
                    if r["case_id"] in conventional
                )
                useful_delta = (
                    summary["reviewed_meaningful_tests"]
                    - summaries["information_gain"]["reviewed_meaningful_tests"]
                )
                improvement = len(conventional) == len(ids) and (
                    delta >= gate["additional_correct_vs_information_gain_min"]
                    or useful_delta
                    >= gate["additional_discriminating_tests_vs_information_gain_min"]
                )
                summary.update(
                    additional_correct_vs_information_gain=delta,
                    additional_meaningful_tests_vs_information_gain=useful_delta,
                )
                recommendation = (
                    "GO"
                    if planning and faithful and improvement
                    else "PARTIAL GO"
                    if planning and not faithful and improvement
                    else "NO GO"
                )
            summary["recommendation"] = recommendation
        summaries[method] = summary
    return {
        "protocol_id": protocol["protocol_id"],
        "n_cases": len(ids),
        "summary": summaries,
        "stage_complete": {(r["case_id"], r["method"]) for r in part}
        == {(c, m) for c in ids for m in METHODS},
        "gate": protocol["gate"],
        "limitations": [
            "Outcome-stratified development cases, not population accuracy.",
            "Numeric agreement is not physical support; independent review is required.",
            "One stochastic draw per condition cannot establish causal graph benefit.",
            "Conservative estimated-cost reservations use frozen prices, not an invoice guarantee.",
        ],
    }
