"""Predeclared challenge metrics. Mechanically valid quotations are not physics."""
from __future__ import annotations

import itertools
import statistics

from .challenge_protocol import METHODS, VARIANTS
from .eval_protocol import digest


def _rate(n, d):
    return n / d if d else None


def build_challenge_report(protocol, rows, case_ids, reviews=()):
    ids = set(case_ids)
    rows = [r for r in rows if r["case_id"] in ids]
    review_by_key = {}
    for review in reviews:
        key = review.get("case_id"), review.get("method")
        if key in review_by_key or review.get("method") not in VARIANTS:
            raise ValueError("Duplicate or invalid expert review")
        review_by_key[key] = review
    summaries = []
    for method in METHODS:
        part = [r for r in rows if r["method"] == method]
        complete = len(part) == len(ids) and {r["case_id"] for r in part} == ids
        if method == "baseline":
            summaries.append({"method": method, "attempted": len(part), "complete": complete,
                "initial_hypothesis_correct": sum(r["baseline_correct"] for r in part),
                "five_query_correct": sum(r["five_query_prediction"] == r["true_event"] for r in part),
                "population_accuracy_claim_allowed": False})
            continue
        wrong = sum(not r["baseline_correct"] for r in part)
        correct = len(part) - wrong
        challenges = [r for r in part if (r.get("assessment") or {}).get("decision") == "CHALLENGE"]
        tp = sum(not r["baseline_correct"] for r in challenges)
        fp = len(challenges) - tp
        successes = [r for r in part if r["status"] == "completed"]
        claims = sum(len(r["assessment"]["claims"]) for r in successes)
        reviewed_claims = expert_challenges = useful = unsupported = reviewed_cases = 0
        for row in successes:
            review = review_by_key.get((row["case_id"], method))
            if review is None:
                continue
            assessment = row["assessment"]
            # Bind human judgments to exact output; no stale or duplicate reviews.
            if (review.get("assessment_digest") != digest(assessment)
                    or type(review.get("useful_investigation")) is not bool
                    or type(review.get("meaningful_contradiction")) is not bool
                    or type(review.get("unsupported_physical_claims")) is not int
                    or review["unsupported_physical_claims"] < 0
                    or not isinstance(review.get("reviewer"), str) or not review["reviewer"].strip()
                    or not isinstance(review.get("rationale"), str) or not review["rationale"].strip()
                    or not isinstance(review.get("claim_judgments"), list)
                    or len(review["claim_judgments"]) != len(assessment["claims"])
                    or any(j not in {"supported", "unsupported", "requires_domain_expertise"}
                           for j in review["claim_judgments"])):
                raise ValueError("Expert review must bind to exact assessment and judge every claim")
            reviewed_claims += sum(j != "requires_domain_expertise" for j in review["claim_judgments"])
            all_supported = all(j == "supported" for j in review["claim_judgments"])
            useful += review["useful_investigation"] and all_supported
            unsupported += review["unsupported_physical_claims"]
            unsupported += sum(j == "unsupported" for j in review["claim_judgments"])
            reviewed_cases += 1
            expert_challenges += (assessment["decision"] == "CHALLENGE"
                                  and review["meaningful_contradiction"] and all_supported
                                  and review["unsupported_physical_claims"] == 0)
        mechanical = _rate(sum(len(r["assessment"]["claims"]) for r in successes
                               if r["assessment"]["mechanical_citations_valid"]), claims)
        summary = {"method": method, "attempted": len(part), "complete": complete,
            "completed": len(successes), "baseline_wrong": wrong, "baseline_correct": correct,
            "challenge_count": len(challenges), "true_challenges": tp, "false_challenges": fp,
            "challenge_recall": _rate(tp, wrong), "false_challenge_rate": _rate(fp, correct),
            "challenge_precision": _rate(tp, len(challenges)),
            "alternative_correct": sum(r["assessment"]["alternative_fault_type"] == r["true_event"] for r in challenges),
            "alternatives_proposed": sum(r["assessment"]["alternative_fault_type"] is not None for r in challenges),
            "insufficient_count": sum(r["assessment"]["decision"] == "INSUFFICIENT_EVIDENCE" for r in successes),
            "mechanical_accepted_claims_rate": mechanical,
            "rejected_assessment_attempts": sum(r.get("rejected_assessment_attempts", 0) for r in part),
            "expert_reviewed_cases": reviewed_cases, "expert_claim_coverage": _rate(reviewed_claims, claims),
            "expert_meaningful_challenge_precision": _rate(expert_challenges, len(challenges)),
            "expert_useful_case_rate": _rate(useful, len(part)), "unsupported_claims": unsupported,
            "sensor_queries": sum(len(r["sensor_sequence"]) for r in part),
            "unavailable_queries": sum(not obs["available"] for r in part for obs in r["sensor_quality"].values()),
            "graph_calls": sum(r["graph_calls"] for r in part), "retrieval_calls": sum(r["retrieval_calls"] for r in part),
            "mean_latency_seconds": statistics.mean(r["latency_seconds"] for r in part) if part else None,
            "estimated_cost_usd": sum(r["usage"]["estimated_cost_usd"] for r in part),
            "cost_complete": all(r["usage"]["cost_complete"] for r in part),
            "tokens": {k: sum(r["usage"][k] for r in part) for k in ("input_tokens", "output_tokens", "cached_tokens", "reasoning_tokens")}}
        gate = protocol["gate"]
        enough = complete and wrong >= gate["min_wrong_cases"] and correct >= gate["min_correct_cases"]
        operational = len(successes) / len(ids) >= gate["completion_rate"] if ids else False
        reviewed = (summary["expert_claim_coverage"] == 1. and reviewed_cases == len(successes))
        faithful = (mechanical is not None and mechanical >= gate["mechanical_citation_rate"]
                    and unsupported <= gate["unsupported_physical_claims_max"])
        detection = (summary["challenge_recall"] is not None and summary["challenge_recall"] >= gate["challenge_recall"]
            and summary["false_challenge_rate"] is not None and summary["false_challenge_rate"] <= gate["false_challenge_rate_max"]
            and summary["challenge_precision"] is not None and summary["challenge_precision"] >= gate["challenge_precision"]
            and summary["expert_meaningful_challenge_precision"] is not None
            and summary["expert_meaningful_challenge_precision"] >= gate["expert_challenge_precision"])
        summary["recommendation"] = ("PENDING" if not enough else "NO GO" if not operational else
            "PENDING" if not reviewed else "GO" if faithful and detection
            else "PARTIAL GO" if faithful and summary["expert_useful_case_rate"] >= gate["expert_useful_case_rate"] else "NO GO")
        summaries.append(summary)
    pairs = []
    for left, right in itertools.combinations(VARIANTS, 2):
        a = {r["case_id"]: r for r in rows if r["method"] == left}
        b = {r["case_id"]: r for r in rows if r["method"] == right}
        shared = sorted(a.keys() & b.keys())
        pairs.append({"left": left, "right": right, "n_pairs": len(shared),
            "sequence_changes": sum(a[k]["sensor_sequence"] != b[k]["sensor_sequence"] for k in shared),
            "sensor_set_changes": sum(set(a[k]["sensor_sequence"]) != set(b[k]["sensor_sequence"]) for k in shared),
            "decision_changes": sum((a[k].get("assessment") or {}).get("decision") !=
                                    (b[k].get("assessment") or {}).get("decision") for k in shared),
            "causal_graph_effect_established": False})
    expected = {(k, m) for k in ids for m in METHODS}
    finished = {(r["case_id"], r["method"]) for r in rows}
    return {"protocol_id": protocol["protocol_id"], "n_cases": len(ids), "summary": summaries,
        "paired_comparisons": pairs, "stage_complete": finished == expected,
        "pilot_ready": finished == expected and all(r["status"] == "completed" for r in rows),
        "selection": protocol["selection"], "gate": protocol["gate"],
        "limitations": ["Failure-enriched development sample; not population accuracy or independent confirmation",
            "Mechanical quotation checks do not establish support, contradiction, physics or absence of unsupported prose",
            "Expert review must examine every claim, uncertainty text and any implicit relationship assertion",
            "One stochastic draw per condition; no causal claim from changed sensors or decisions",
            "Insufficient sample or missing expert review yields PENDING, not evidence for GO",
            "Baseline hypothesis uses two sensors; baseline-only comparator additionally records five-sensor prediction"]}
