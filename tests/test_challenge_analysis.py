import copy

import pytest

from petromind.challenge_analysis import build_challenge_report
from petromind.challenge_offline import analyze_m3
from petromind.challenge_protocol import GATE, METHODS, _pick_stratified
from petromind.eval_protocol import digest


def experiment(decisions):
    """Synthetic scorer fixtures: half wrong baselines, half correct."""
    protocol = {"protocol_id": "test", "gate": dict(GATE), "selection": {"enriched": True}}
    rows, reviews = [], []
    for index, decision in enumerate(decisions):
        wrong = index < 4
        assessment = {"decision": decision, "claims": [{"interpretation": "Fixture"}],
            "alternative_fault_type": 2 if decision == "CHALLENGE" else None,
            "mechanical_citations_valid": True}
        row = {"case_id": str(index), "method": "challenger", "status": "completed",
            "assessment": assessment, "baseline_correct": not wrong, "true_event": 2 if wrong else 1,
            "sensor_sequence": ["P-TPT"], "sensor_quality": {"P-TPT": {"available": True}},
            "graph_calls": 0, "retrieval_calls": 0, "latency_seconds": 1.,
            "usage": {"input_tokens": 1, "output_tokens": 1, "cached_tokens": 0,
                      "reasoning_tokens": 0, "estimated_cost_usd": .001, "cost_complete": True}}
        rows.append(row)
        reviews.append({"case_id": str(index), "method": "challenger", "assessment_digest": digest(assessment),
            "useful_investigation": True, "meaningful_contradiction": decision == "CHALLENGE",
            "claim_judgments": ["supported"], "unsupported_physical_claims": 0,
            "reviewer": "Synthetic test reviewer", "rationale": "Synthetic fixture, not a scientific review."})
    return protocol, rows, reviews


def scored(protocol, rows, reviews=()):
    report = build_challenge_report(protocol, rows, [r["case_id"] for r in rows], reviews)
    return next(r for r in report["summary"] if r["method"] == "challenger")


def test_detection_metrics_and_predeclared_go_gate():
    p, rows, reviews = experiment(["CHALLENGE"] * 4 + ["SUPPORT"] * 4)
    summary = scored(p, rows, reviews)
    assert summary["challenge_recall"] == 1.
    assert summary["false_challenge_rate"] == 0.
    assert summary["challenge_precision"] == 1.
    assert summary["alternative_correct"] == 4
    assert summary["recommendation"] == "GO"


def test_partial_go_for_reviewed_useful_insufficiency_not_detection():
    p, rows, reviews = experiment(["INSUFFICIENT_EVIDENCE"] * 8)
    s = scored(p, rows, reviews)
    assert s["challenge_recall"] == 0 and s["challenge_precision"] is None
    assert s["insufficient_count"] == 8 and s["recommendation"] == "PARTIAL GO"


def test_no_go_false_challenges_and_unsupported_physical_claims():
    p, rows, reviews = experiment(["CHALLENGE"] * 8)
    reviews[0]["unsupported_physical_claims"] = 1
    s = scored(p, rows, reviews)
    assert s["false_challenge_rate"] == 1 and s["challenge_precision"] == .5
    assert s["recommendation"] == "NO GO"


def test_pending_without_review_or_sufficient_case_coverage():
    p, rows, reviews = experiment(["CHALLENGE"] * 4 + ["SUPPORT"] * 4)
    assert scored(p, rows)["recommendation"] == "PENDING"
    reviews[0]["claim_judgments"] = ["requires_domain_expertise"]
    assert scored(p, rows, reviews)["recommendation"] == "PENDING"
    assert scored(p, rows[:2], reviews[:2])["recommendation"] == "PENDING"


def test_review_binds_exact_assessment_and_rejects_duplicates():
    p, rows, reviews = experiment(["SUPPORT"] * 8)
    reviews[0]["assessment_digest"] = "stale"
    with pytest.raises(ValueError, match="bind"):
        scored(p, rows, reviews)
    with pytest.raises(ValueError, match="Duplicate"):
        scored(p, rows, [reviews[1], reviews[1]])


def test_complete_failure_is_no_go_with_sufficient_strata():
    p, rows, reviews = experiment(["SUPPORT"] * 8)
    for row in rows:
        row["status"], row["assessment"] = "failed", None
    assert scored(p, rows)["recommendation"] == "NO GO"


def test_stratified_selection_includes_wrong_correct_and_class_coverage():
    pool = [{"locator_hash": str(i), "baseline_correct": i % 2 == 0, "true_event": i % 3 + 1}
            for i in range(30)]
    selected = _pick_stratified(pool, 16, 104)
    assert len(selected) == 16
    assert {r["baseline_correct"] for r in selected} == {True, False}
    assert {r["true_event"] for r in selected} == {1, 2, 3}
    assert _pick_stratified(list(reversed(pool)), 16, 104) == selected


def test_m3_analysis_reports_observations_not_causal_explanations():
    row = {"case_id": "test", "method": "graphrag", "prediction": 2, "true_event": 7, "correct": False,
        "sensor_sequence": ["P-PDG"], "sensor_quality": {"P-PDG": {"available": True,
            "is_constant": True, "constant_value": 0., "quality_status": "constant"}},
        "graph_calls": 1, "retrieval_calls": 1,
        "retrieval_events": [{"result": {"matches": [{"training_event": 2}]}}]}
    report = analyze_m3([row])
    assert report["methods"]["graphrag"]["P_PDG_constant_zero"] == 1
    assert report["class7_retrieval_associations"][0]["nearest_2_ever"]
    assert any("anchoring" in s for s in report["not_established"])
