from petromind.agent import RunEvent
from petromind.audit import canonical
from petromind.eval_analysis import build_report, paired_comparison
from petromind.eval_protocol import DEFAULT_PRICES
from petromind.eval_runner import usage_and_cost
import pytest


def test_paired_accuracy_and_cluster_bootstrap():
    left, right = [], []
    for i in range(4):
        common = {"case_id": str(i), "true_event": 2, "well_group": str(i // 2)}
        left.append({**common, "correct": i == 0, "sensor_sequence": ["P-TPT"]})
        right.append({**common, "correct": i in {0, 1, 2}, "sensor_sequence": ["T-TPT"]})
    report = paired_comparison(left, right)
    assert report["n_pairs"] == 4 and report["n_wells"] == 2
    assert report["accuracy_delta_right_minus_left"] == .5
    assert report["right_only_correct"] == ["1", "2"] and report["left_only_correct"] == []
    assert report["sequence_changed_cases"] == 4 and report["sensor_set_changed_cases"] == 4
    assert report == paired_comparison(left, right)
    assert len(report["well_cluster_bootstrap_95_percentile_interval"]) == 2


def test_cost_counts_cached_input_and_unknown_attempts():
    event = RunEvent(1, "usage", canonical({"input_tokens": 100, "cached_tokens": 40,
                                         "output_tokens": 20, "reasoning_tokens": 10}))
    report = usage_and_cost((event,), 2, DEFAULT_PRICES)
    assert abs(report["estimated_cost_usd"] - .000166) < 1e-12
    assert report["http_attempts_without_usage"] == 1 and report["cost_complete"] is False
    assert report["reasoning_tokens"] == 10  # Included in output, not billed twice.


def test_failures_are_wrong_and_unattempted_are_not_a_full_accuracy():
    protocol = {"budgets": [5], "training_classes": [2], "seed": 42, "protocol_id": "test"}
    row = {"case_id": "a", "well_group": "well", "method": "sensor_only", "budget": 5,
           "true_event": 2, "prediction": None, "correct": False, "status": "failed", "reason": "api_timeout",
           "confidence": None, "sensor_sequence": [], "sensor_quality": {}, "graph_calls": 0,
           "retrieval_calls": 0, "latency_seconds": 1., "estimated_cost_usd": 0., "cost_complete": False}
    report = build_report(protocol, [row], ["a", "b"])
    first = report["summary"][0]
    assert first["accuracy"] is None and first["accuracy_on_attempted"] == 0
    assert first["n_failed"] == 1 and first["n_attempted"] == 1 and first["n_expected"] == 2
    assert len(first["errors"]) == 1
    with pytest.raises(ValueError, match="Duplicate"):
        build_report(protocol, [row, row], ["a", "b"])
