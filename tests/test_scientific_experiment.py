"""Synthetic unit/HTTP-mock experiments. Never real 3W pilot results."""

import copy
import json
from contextlib import closing
from functools import partial
from pathlib import Path

import httpx
import numpy as np
import pandas as pd
import pytest

from petromind.audit import canonical, verify_audit
from petromind.baselines import GaussianEvidence
from petromind.challenger import observe_adaptively
from petromind.data import load_incidents
from petromind.diagnostic_tests import REGISTRY, compute
from petromind.eval_protocol import digest, inventory
from petromind.eval_runner import read_jsonl
from petromind.meta_api import MetaResponsesClient
from petromind.scientist import ExperimentSession, run_scientist
from petromind.science_evaluation import (
    freeze,
    run,
    analyze,
    choose_information_gain,
    SpendingLedger,
)
from petromind.splits import WellSplit
from test_challenger import hypothesis


def proposal(test="paired_pressure_trends"):
    return {
        "test_id": test,
        "required_sensors": list(REGISTRY[test].sensors),
        "baseline_expected": {"relation": "gt", "threshold": 0},
        "alternative_expected": {"relation": "lt", "threshold": 0},
        "knowledge_ids": [],
        "uncertainty": "Synthetic numeric expectations only; physical implications are unverified.",
    }


@pytest.fixture
def experiment(frame):
    session = ExperimentSession(frame, tuple(frame))
    session.get_sensor_history("P-TPT")
    session.get_sensor_history("T-TPT")
    session.bind_experiment(hypothesis())
    return session


def test_registry_provenance_scope_and_no_fabricated_causal_thresholds():
    for t in REGISTRY.values():
        physical = t.public(True)
        blind = t.public(False)
        assert (
            1 <= len(t.sensors) <= 2 and t.computation and t.measures and t.limitations
        )
        assert physical["physical_basis"] and all(
            f["provenance"] and f["locator"] and f["status"] == "documented"
            for f in physical["physical_basis"]
        )
        assert "physical_basis" not in blind
        assert (
            physical["sensors"] == blind["sensors"]
            and physical["computation"] == blind["computation"]
        )
    assert (
        "not an established spectral threshold"
        in REGISTRY["tree_oscillation"].limitations
    )


def test_proposal_precedes_measurement_and_updates_only_through_charged_sensors(
    experiment,
):
    assert experiment.dispatch("execute_test", {})["validation_code"] == "plan_required"
    assert len(experiment.queries) == 2
    result = experiment.dispatch("propose_test", proposal())
    assert result["accepted"] and len(experiment.queries) == 2
    observed = experiment.dispatch("execute_test", {})
    assert observed["sensor_cost"] == 1 and experiment.remaining_budget == 2
    assert observed["primary_value"] == 4.0 and observed["values"]["P-PDG_delta"] == 2.0
    before = experiment.queries
    cached = experiment.dispatch("execute_test", {})
    assert cached["cached"] and experiment.queries == before
    assert verify_audit(experiment.audit_trail)


def test_two_new_sensors_cost_two_and_insufficient_budget_never_partially_spent(frame):
    frame = frame.copy()
    frame["P-MON-CKP"] = 5.0
    frame["P-JUS-CKP"] = 3.0
    s = ExperimentSession(frame, tuple(frame))
    s.get_sensor_history("P-TPT")
    s.get_sensor_history("T-TPT")
    s.bind_experiment(hypothesis())
    assert s.dispatch("propose_test", proposal("choke_pressure_difference"))["accepted"]
    r = s.dispatch("execute_test", {})
    assert r["sensor_cost"] == 2 and len(s.queries) == 4 and r["primary_value"] == 2.0
    other = ExperimentSession(frame, tuple(frame))
    other.get_sensor_history("P-TPT")
    other.get_sensor_history("T-TPT")
    other.bind_experiment(hypothesis())
    other.get_sensor_history("P-PDG")
    other.get_sensor_history("T-PDG")
    before = other.queries
    r = other.dispatch("propose_test", proposal("choke_pressure_difference"))
    assert r["validation_code"] == "test_not_executable" and other.queries == before


@pytest.mark.parametrize(
    "mutation,code",
    [
        (lambda a: a.update(test_id="private/7/WELL-file.parquet"), "unknown_test"),
        (
            lambda a: a.update(required_sensors=["P-PDG"]),
            "sensor_requirements_mismatch",
        ),
        (lambda a: a.update(knowledge_ids=["private-label"]), "source_not_provided"),
        (
            lambda a: a["baseline_expected"].update(threshold=True),
            "invalid_expectation",
        ),
        (lambda a: a.update(true_event=7), "invalid_fields"),
    ],
)
def test_invalid_requests_are_label_safe_and_repeats_stop(experiment, mutation, code):
    args = proposal()
    mutation(args)
    first = experiment.dispatch("propose_test", args)
    assert first["validation_code"] == code
    second = experiment.dispatch("propose_test", args)
    assert (
        second["validation_code"] == "repeated_invalid_submission"
        and experiment._sealed
    )
    assert experiment.assessment is None and "WELL-file" not in canonical(second)
    assert "private-label" not in experiment.audit_trail[-1].arguments_json


def test_precommit_cannot_be_revised_after_observation_and_numeric_interpretation_checked(
    experiment,
):
    experiment.dispatch("propose_test", proposal())
    r = experiment.dispatch("execute_test", {})
    assert (
        experiment.dispatch("propose_test", proposal())["validation_code"]
        == "plan_already_committed"
    )
    bad = {
        "result_id": r["result_id"],
        "baseline_relation": "contradicts",
        "alternative_relation": "inconclusive",
        "uncertainty": "Needs physical review.",
    }
    assert (
        experiment.dispatch("assess_test", bad)["validation_code"]
        == "numeric_interpretation_mismatch"
    )
    good = {
        **bad,
        "baseline_relation": "supports",
        "alternative_relation": "contradicts",
    }
    result = experiment.dispatch("assess_test", good)
    assert (
        result["primary_value"] == 4.0 and not result["physical_correctness_verified"]
    )
    assert experiment.diagnosis is None and experiment._sealed
    assert experiment.dispatch("execute_test", {})["error"] == "investigation_closed"


def test_missing_test_result_requires_explicit_abstention(frame):
    frame["P-TPT"] = np.nan
    s = ExperimentSession(frame, tuple(frame))
    s.get_sensor_history("P-TPT")
    s.get_sensor_history("T-TPT")
    s.bind_experiment(hypothesis())
    s.dispatch("propose_test", proposal())
    r = s.dispatch("execute_test", {})
    assert r["primary_value"] is None and s.remaining_budget == 2
    args = {
        "result_id": r["result_id"],
        "baseline_relation": "supports",
        "alternative_relation": "inconclusive",
        "uncertainty": "Missing samples.",
    }
    assert (
        s.dispatch("assess_test", args)["validation_code"] == "unavailable_comparison"
    )
    result = s.dispatch("assess_test", {**args, "baseline_relation": "inconclusive"})
    assert result["baseline_relation"] == "inconclusive" and s.assessment


def test_fft_uses_contiguous_samples_and_reports_known_sine():
    y = np.sin(2 * np.pi * np.arange(128) / 16)
    r = compute(REGISTRY["tree_oscillation"], {"P-TPT": pd.Series(y)})
    assert r["values"]["peak_period_seconds"] == 16 and r["primary_value"] > 0.9
    y = np.tile([1.0, np.nan], 64)
    r = compute(REGISTRY["tree_oscillation"], {"P-TPT": pd.Series(y)})
    assert r["primary_value"] is None and r["quality"]["contiguous_samples"] == 1
    r = compute(REGISTRY["tree_oscillation"], {"P-TPT": pd.Series(np.zeros(40))})
    assert r["primary_value"] == 0.0 and r["quality"]["P-TPT"]["constant"]


def test_raw_numeric_filters_preserve_zero_and_difference_uses_joint_samples():
    r = compute(
        REGISTRY["choke_pressure_difference"],
        {
            "P-MON-CKP": pd.Series([0.0, 4.0, np.inf, 1e14]),
            "P-JUS-CKP": pd.Series([0.0, 2.0, 3.0, 4.0]),
        },
    )
    assert r["primary_value"] == 1.0 and r["quality"]["joint_valid_count"] == 2


def test_information_gain_is_deterministic_and_does_not_inspect_unobserved_target(
    training, frame
):
    model = GaussianEvidence(training, tuple(frame))
    sessions = []
    for target in (frame, frame * 999):
        s = ExperimentSession(target, tuple(frame))
        s.get_sensor_history("P-TPT")
        s.get_sensor_history("T-TPT")
        s.bind_experiment(hypothesis())
        sessions.append(s)
    # Replace unqueried raw data only; retain identical initial evidence.
    sessions[1]._observed = dict(sessions[0].observations)
    assert choose_information_gain(model, sessions[0]) == choose_information_gain(
        model, sessions[1]
    )
    assert all(len(s.queries) == 2 for s in sessions)


@pytest.fixture
def science_parent(tmp_path):
    root = tmp_path / "dataset"
    wells = [f"WELL-{i:05d}" for i in range(1, 13)]
    for i, well in enumerate(wells, 1):
        event = 2 if i % 2 else 8
        amplitude = 1.0 if event == 2 else 10.0
        if 5 <= i <= 10 and i % 2:
            amplitude = 10.0  # Deliberate synthetic model errors.
        folder = root / str(event)
        folder.mkdir(parents=True, exist_ok=True)
        data = {
            s: amplitude * np.linspace(1, 1.1, 640)
            for s in (
                "P-TPT",
                "T-TPT",
                "P-PDG",
                "T-PDG",
                "P-MON-CKP",
                "P-JUS-CKP",
                "QGL",
            )
        }
        data.update({"class": [0] * 40 + [100 + event] * 600, "state": [8] * 640})
        pd.DataFrame(
            data, index=pd.date_range("2020", periods=640, freq="s")
        ).to_parquet(folder / f"{well}_20200101000000.parquet")
    records = load_incidents(root)
    original = WellSplit(tuple(wells[:10]), tuple(wells[10:]))
    fit_split = WellSplit(tuple(wells[:4]), tuple(wells[4:]))
    rows = inventory(root, records, original)
    fit = [r for r in records if r.well in fit_split.train_wells]
    names = tuple(fit[0].measurements)
    model = GaussianEvidence(fit, names)
    import hashlib

    lookup = {
        hashlib.sha256(r.path.relative_to(root).as_posix().encode()).hexdigest(): r
        for r in records
    }
    entries = []
    selected = []
    for loc, row in rows.items():
        r = lookup[loc]
        cid = digest(loc)[:32]
        role = (
            "fit"
            if r.well in fit_split.train_wells
            else "development_pool"
            if r.well in wells[4:10]
            else "excluded_test"
        )
        entries.append({**row, "case_id": cid, "role": role})
        if role == "development_pool":
            from petromind.session import DiagnosticSession

            s = DiagnosticSession(r.measurements, names)
            h = observe_adaptively(model, s, 2)
            seq = list(s.queries)
            final = observe_adaptively(model, s, 3)
            selected.append(
                {
                    "case_id": cid,
                    "locator_hash": loc,
                    "true_event": r.event,
                    "baseline_prediction": h["prediction"],
                    "baseline_correct": h["prediction"] == r.event,
                    "initial_hypothesis": h,
                    "initial_sensor_sequence": seq,
                    "five_query_prediction": final["prediction"],
                }
            )
    from dataclasses import asdict

    parent = {
        "study": "synthetic-fixture",
        "records": entries,
        "selected": selected,
        "seconds": 600,
        "original_split": asdict(original),
        "retrieval_split": asdict(fit_split),
        "development_wells": wells[4:10],
    }
    parent["protocol_id"] = digest(parent)
    return root, parent, tmp_path / "experiment"


def mock_factory(monkeypatch):
    monkeypatch.setenv("MODEL_API_KEY", "synthetic-test-placeholder")
    seen = []

    def respond(request):
        body = json.loads(request.content)
        context = json.loads(body["input"][0]["content"][0]["text"])
        seen.append(body)
        assert all(
            x not in request.content.decode()
            for x in ("WELL-", ".parquet", "true_event", "development_wells")
        )
        outputs = [
            json.loads(x["output"])
            for x in body["input"]
            if x.get("type") == "function_call_output"
        ]
        if not outputs:
            test = next(t for t in context["tests"] if t["id"] == "tree_oscillation")
            args = proposal(test["id"])
            args["baseline_expected"] = {"relation": "unknown", "threshold": 0}
            args["alternative_expected"] = {"relation": "unknown", "threshold": 0}
            tool = "propose_test"
        elif len(outputs) == 1:
            tool, args = "execute_test", {}
        else:
            tool = "assess_test"
            args = {
                "result_id": outputs[-1]["result_id"],
                "baseline_relation": "inconclusive",
                "alternative_relation": "inconclusive",
                "uncertainty": "Synthetic fixture abstention; not a scientific success.",
            }
        return httpx.Response(
            200,
            json={
                "status": "completed",
                "error": None,
                "usage": {"input_tokens": 100, "output_tokens": 20},
                "output": [
                    {
                        "type": "function_call",
                        "name": tool,
                        "call_id": f"c{len(outputs)}",
                        "arguments": json.dumps(args),
                    }
                ],
            },
        )

    return partial(MetaResponsesClient, transport=httpx.MockTransport(respond)), seen


def test_frozen_mock_pilot_pairing_reference_and_no_auto_larger_run(
    science_parent, monkeypatch
):
    root, parent, out = science_parent
    p = freeze(root, parent, out)
    factory, seen = mock_factory(monkeypatch)
    assert len(p["case_ids"]) == 6 and p["initial_correct"] == 3
    before = canonical(parent)
    report = run(out, root, client_factory=factory)
    rows = read_jsonl(out / "results.jsonl")
    assert len(rows) == 6 and len(seen) == 12 and report["stage_complete"]
    assert all(
        s["recommendation"] == "PENDING"
        for m, s in report["summary"].items()
        if m != "information_gain"
    )
    for c in p["pilot_case_ids"]:
        pair = [r for r in rows if r["case_id"] == c]
        assert all(
            r["initial_hypothesis"] == pair[0]["initial_hypothesis"]
            and r["alternative_fault_type"] == pair[0]["alternative_fault_type"]
            for r in pair
        )
        assert all(r["audit_valid"] and len(r["sensor_sequence"]) <= 5 for r in pair)
    assert canonical(parent) == before
    run(out, root, client_factory=factory)
    assert len(seen) == 12
    with pytest.raises(ValueError, match="review"):
        run(out, root, "development", client_factory=factory)
    packets = (out / "review-packets.json").read_text()
    assert "true_event" not in packets and "initial_correct" not in packets
    ledger = read_jsonl(out / "reservations.jsonl")
    assert (
        len(ledger) == 12
        and sum(r["estimated_usd_reserved"] for r in ledger)
        <= p["limits"]["pilot"]["estimated_usd"]
    )


def test_cost_cap_prevents_http_and_failed_tests_never_retried(
    science_parent, monkeypatch
):
    root, parent, out = science_parent
    p = freeze(root, parent, out, pilot_cost=0.00001)
    factory, seen = mock_factory(monkeypatch)
    result = run(out, root, client_factory=factory)
    assert not seen and any(
        r["reason"] == "science_spending_cap" for r in read_jsonl(out / "results.jsonl")
    )
    run(out, root, client_factory=factory)
    assert not seen


def test_freeze_preserves_original_and_rejects_drift(science_parent):
    root, parent, out = science_parent
    p = freeze(root, parent, out)
    with pytest.raises(ValueError, match="fresh"):
        freeze(root, parent, out)
    p["agent_config"]["max_turns"] = 9
    (out / "protocol.json").write_text(json.dumps(p))
    with pytest.raises(ValueError, match="modified"):
        run(out, root)


def test_missing_key_fails_before_intents_or_paid_calls(science_parent, monkeypatch):
    from petromind.meta_api import MetaAPIError

    root, parent, out = science_parent
    freeze(root, parent, out)
    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    with pytest.raises(MetaAPIError, match="missing_or_invalid_api_key"):
        run(out, root)
    assert not (out / "results.jsonl").exists() and not list((out / "traces").iterdir())


def test_known_primary_is_not_presented_as_a_prospective_test(experiment):
    entry = next(t for t in experiment.catalog() if t["id"] == "tree_trend")
    assert entry["primary_previously_observed"] and not entry["executable"]
    assert (
        experiment.dispatch("propose_test", proposal("tree_trend"))["validation_code"]
        == "test_not_executable"
    )
    assert next(t for t in experiment.catalog() if t["id"] == "tree_oscillation")[
        "executable"
    ]


def test_full_development_requires_review_and_expert_gate_is_not_auto_success(
    science_parent, monkeypatch
):
    root, parent, out = science_parent
    p = freeze(root, parent, out)
    factory, seen = mock_factory(monkeypatch)
    run(out, root, client_factory=factory)
    report = run(out, root, "development", reviewed=True, client_factory=factory)
    assert (
        report["stage_complete"]
        and len(read_jsonl(out / "results.jsonl")) == 18
        and len(seen) == 36
    )
    reviews = json.loads((out / "review-template.json").read_text())
    assert len(reviews) == 18
    for review in reviews:
        review.update(
            reviewer="Synthetic test reviewer, not an actual engineer",
            rationale="Unit test of a negative decision gate.",
            physically_justified_plan=False,
            expectations_documented=False,
            meaningful_discrimination=False,
            interpretation_faithful=True,
            abstention_appropriate=True,
            unsupported_plan_claims=0,
            unsupported_interpretation_claims=0,
        )
    rows = read_jsonl(out / "results.jsonl")
    judged = analyze(p, rows, p["case_ids"], reviews)
    assert all(
        s["recommendation"] == "NO GO"
        for m, s in judged["summary"].items()
        if m != "information_gain"
    )
    changed = copy.deepcopy(rows)
    changed[0]["plan"]["uncertainty"] = "Altered after review."
    with pytest.raises(ValueError, match="exact investigations"):
        analyze(p, changed, p["case_ids"], reviews)
    corrupted = copy.deepcopy(p)
    corrupted["gate"]["useful_discrimination"] = 0
    with pytest.raises(ValueError, match="modified"):
        analyze(corrupted, rows, p["case_ids"], reviews)


def test_numerical_linear_fit_residue_is_not_reported_as_oscillation():
    r = compute(
        REGISTRY["tree_oscillation"], {"P-TPT": pd.Series(np.linspace(1e7, 1.1e7, 600))}
    )
    assert (
        r["primary_value"] == 0.0 and r["quality"]["numerical_residual_floor_applied"]
    )
    assert r["values"]["peak_period_seconds"] is None


def test_test_reference_is_strictly_pre_window_and_not_verified_normal():
    from petromind.reference import PreWindowReference

    data = pd.DataFrame(
        {"P-TPT": [10.0] * 40 + [99.0] * 40, "class": [0] * 40 + [102] * 40},
        index=pd.date_range("2020", periods=80, freq="s"),
    )
    ref = PreWindowReference(data, data.index[40], ["P-TPT"])
    r = compute(
        REGISTRY["tree_reference_change"], {"P-TPT": pd.Series([15.0, 15.0])}, ref
    )
    assert (
        r["primary_value"] == 5.0
        and r["values"]["reference"]["normality"] == "unverified_pre_window"
    )
    assert r["values"]["reference"]["physical_threshold"] is False


def test_no_unregistered_sensor_or_diagnosis_tool_after_binding(experiment):
    for tool, args in [
        ("get_sensor_history", {"sensor_name": "P-PDG"}),
        ("submit_assessment", {}),
        ("submit_diagnosis", {}),
    ]:
        assert experiment.dispatch(tool, args)["error"] == "tool_not_available"
    assert len(experiment.queries) == 2


def test_documented_example_matching_is_scoped_and_requires_provided_sources(frame):
    from petromind.science_evaluation import expectation_source_matches

    s = ExperimentSession(frame, tuple(frame), physical=True)
    s.get_sensor_history("P-TPT")
    s.get_sensor_history("T-TPT")
    h = hypothesis()
    h["prediction"] = 2
    for row in h["probabilities"]:
        row["probability"] = 1.0 if row["fault_type"] == 2 else 0.0
    s.bind_experiment(h)
    args = proposal()
    args["baseline_expected"] = {"relation": "lt", "threshold": 0}
    args["knowledge_ids"] = ["example:2:P-PDG", "example:2:P-TPT"]
    assert s.dispatch("propose_test", args)["accepted"]
    assert expectation_source_matches(s)["baseline"] is True
    assert not expectation_source_matches(s)["alternative"]


def test_committed_real_cohort_lock_matches_registry_and_rubric():
    from dataclasses import asdict
    from petromind.science_evaluation import GATE
    from petromind.scientist import INSTRUCTIONS, tools

    lock = json.loads(
        (
            Path(__file__).resolve().parents[1] / "docs/m5-cohort-lock-v1.json"
        ).read_text()
    )
    assert (
        digest({k: v for k, v in lock.items() if k != "cohort_lock_id"})
        == lock["cohort_lock_id"]
    )
    assert (
        len(lock["case_ids"]) == 6
        and lock["initial_correct"] == 3
        and sum(lock["class_counts"].values()) == 6
    )
    assert lock["gate"] == GATE and lock["registry_digest"] == digest(
        [asdict(t) for t in REGISTRY.values()]
    )
    assert lock["prompt_digest"] == digest(INSTRUCTIONS) and lock[
        "tool_digest"
    ] == digest(tools())
    assert lock["api_requests"] == 0 and not any(
        "WELL-" in c or ".parquet" in c for c in lock["case_ids"]
    )
