"""Synthetic unit fixtures only; no fabricated evidence enters real experiments."""
import copy
import json
from functools import partial

import httpx
import pytest

from petromind.agent import AgentConfig
from petromind.audit import verify_audit
from petromind.baselines import GaussianEvidence
from petromind.challenger import ChallengeSession, assessment_tools, observe_adaptively, run_challenger
from petromind.meta_api import MetaResponsesClient


def hypothesis():
    return {"prediction": 1, "confidence_calibrated": False,
            "probabilities": [{"fault_type": c, "probability": 1. if c == 1 else 0.,
                               "represented_in_fit": c in {1, 2}} for c in range(1, 10)]}


def assessment(session, decision="CHALLENGE"):
    sensor, obs = next((s, o) for s, o in session.observations.items() if o.available)
    return {"decision": decision, "confidence": .6,
        "alternative_fault_type": 2 if decision == "CHALLENGE" else None,
        "claims": [{"category": "contradictory" if decision == "CHALLENGE" else "supporting",
                    "sensor_name": sensor, "field": "median", "value": obs.median,
                    "interpretation": "Synthetic interpretation, requires review."}],
        "relationships": [], "uncertainty": "No verified per-well topology."}


@pytest.fixture
def challenge(frame):
    session = ChallengeSession(frame, frame.columns)
    session.get_sensor_history("P-TPT")
    session.bind_hypothesis(hypothesis())
    return session


def test_shared_budget_cache_and_cannot_override_statistical_prediction(frame, training):
    model = GaussianEvidence(training, tuple(frame.columns))
    session = ChallengeSession(frame, frame.columns)
    current = observe_adaptively(model, session, 2)
    session.bind_hypothesis(current)
    assert len(session.queries) == 2 and session.remaining_budget == 3
    cached = session.get_sensor_history(session.queries[0])
    assert cached["cached"] and session.remaining_budget == 3
    for s in frame.columns:
        session.dispatch("get_sensor_history", {"sensor_name": s})
    assert len(session.queries) == 5 and session.remaining_budget == 0
    assert session.get_sensor_history(next(s for s in frame.columns if s not in session.queries))["error"] == "sensor_budget_exhausted"
    args = assessment(session)
    args["alternative_fault_type"] = 9 if current["prediction"] != 9 else 8
    result = session.dispatch("submit_assessment", args)
    assert result["baseline_prediction"] == current["prediction"]
    assert result["alternative_fault_type"] != result["baseline_prediction"]
    assert session.diagnosis is None  # An assessment is never a replacement statistical diagnosis.
    assert session.dispatch("submit_diagnosis", {})["error"] == "investigation_closed"
    assert session.get_sensor_history(session.queries[0])["error"] == "investigation_closed"
    assert verify_audit(session.audit_trail)


@pytest.mark.parametrize("decision", ["SUPPORT", "CHALLENGE", "INSUFFICIENT_EVIDENCE"])
def test_decisions_validated_sealed_and_defensive_copies(challenge, decision):
    result = challenge.dispatch("submit_assessment", assessment(challenge, decision))
    assert result["decision"] == decision and result["mechanical_citations_valid"]
    assert result["interpretation_review"] == "required"
    result["claims"].clear()
    assert challenge.assessment["claims"]
    assert challenge.dispatch("list_sensors", {})["error"] == "investigation_closed"


@pytest.mark.parametrize("mutation", [
    lambda a: a.update(decision="OVERRIDE"),
    lambda a: a.update(confidence=float("nan")),
    lambda a: a.update(confidence=True),
    lambda a: a.update(alternative_fault_type=1),
    lambda a: a.update(alternative_fault_type=True),
    lambda a: a.update(claims=[]),
    lambda a: a["claims"][0].update(sensor_name="T-PDG"),
    lambda a: a["claims"][0].update(sensor_name="/private/7/WELL-secret.parquet"),
    lambda a: a["claims"][0].update(value=999999),
    lambda a: a["claims"][0].update(field="true_event"),
    lambda a: a["claims"][0].update(category="supporting"),
    lambda a: a.update(relationships=[{"sensor": "P-TPT", "equipment": "tubing", "relation": "causes", "verification": "verified"}]),
    lambda a: a.update(true_event=7),
])
def test_invalid_citations_and_decisions_rejected(challenge, mutation):
    args = assessment(challenge)
    mutation(args)
    assert challenge.dispatch("submit_assessment", args)["error"] == "invalid_assessment"
    assert challenge.assessment is None
    assert "WELL-secret" not in challenge.audit_trail[-1].arguments_json


def test_support_cannot_propose_alternative(challenge):
    args = assessment(challenge, "SUPPORT")
    args["alternative_fault_type"] = 2
    assert "error" in challenge.dispatch("submit_assessment", args)


def test_missing_readings_charged_and_cannot_be_contradiction(frame):
    frame["P-TPT"] = float("nan")
    session = ChallengeSession(frame, frame.columns)
    session.bind_hypothesis(hypothesis())
    session.get_sensor_history("P-TPT")
    assert session.remaining_budget == 4
    args = {"decision": "INSUFFICIENT_EVIDENCE", "confidence": .2, "alternative_fault_type": None,
        "claims": [{"category": "unavailable", "sensor_name": "P-TPT", "field": "available", "value": False,
                    "interpretation": "No usable reading."}], "relationships": [], "uncertainty": "Missing evidence."}
    invalid = copy.deepcopy(args)
    invalid["decision"] = "CHALLENGE"
    invalid["claims"][0]["category"] = "contradictory"
    assert "error" in session.dispatch("submit_assessment", invalid)
    assert session.dispatch("submit_assessment", args)["decision"] == "INSUFFICIENT_EVIDENCE"


def test_zero_constant_is_valid_not_missing(frame):
    frame["P-TPT"] = 0.
    session = ChallengeSession(frame, frame.columns)
    session.bind_hypothesis(hypothesis())
    session.get_sensor_history("P-TPT")
    assert session.observations["P-TPT"].available
    args = assessment(session, "SUPPORT")
    args["claims"][0].update(field="constant_value", value=0.)
    assert "error" not in session.dispatch("submit_assessment", args)


def test_graph_relations_require_actual_return_and_illustrative_status(challenge):
    args = assessment(challenge)
    args["relationships"] = [{"sensor": "P-TPT", "equipment": "tubing", "relation": "associated_with", "verification": "illustrative"}]
    assert "error" in challenge.dispatch("submit_assessment", args)
    challenge.get_equipment_neighbors("P-TPT")
    assert "error" not in challenge.dispatch("submit_assessment", args)


def test_variant_capabilities_and_no_direct_diagnosis(frame):
    for variant in ("sensor_only", "topology", "graphrag"):
        session = ChallengeSession(frame, frame.columns, variant=variant)
        tools = {t["name"] for t in assessment_tools(variant)}
        assert "submit_diagnosis" not in tools and "submit_assessment" in tools
        if variant == "sensor_only":
            assert session.get_equipment_neighbors("P-TPT")["error"] == "tool_not_available"
        if variant != "graphrag":
            assert session.search_similar_incidents()["error"] == "tool_not_available"
        assert session.submit_diagnosis(1, .5, ["P-TPT"])["error"] == "tool_not_available"


def test_hypothesis_whitelist_rejects_metadata_and_is_immutable(frame):
    session = ChallengeSession(frame, frame.columns)
    args = hypothesis()
    args["true_event"] = 7
    with pytest.raises(ValueError):
        session.bind_hypothesis(args)
    session.bind_hypothesis(hypothesis())
    with pytest.raises(ValueError):
        session.bind_hypothesis(hypothesis())


def test_live_transport_contract_label_isolation_and_structured_terminal(challenge, monkeypatch):
    monkeypatch.setenv("MODEL_API_KEY", "synthetic-test-placeholder")
    def respond(request):
        body = json.loads(request.content)
        serialized = json.dumps(body)
        assert all(secret not in serialized for secret in ("true_event", "WELL-", ".parquet", "locator_hash", "split_membership"))
        assert "submit_assessment" in {t["name"] for t in body["tools"]}
        return httpx.Response(200, json={"status": "completed", "error": None,
            "usage": {"input_tokens": 100, "output_tokens": 20}, "output": [{"type": "function_call",
                "call_id": "assessment1", "name": "submit_assessment", "arguments": json.dumps(assessment(challenge))}]})
    client = MetaResponsesClient(transport=httpx.MockTransport(respond))
    try:
        result = run_challenger(challenge, client)
    finally:
        client.close()
    assert result.status == "completed" and result.reason == "assessment_submitted"
    assert challenge.assessment["baseline_prediction"] == 1


def test_plain_text_support_is_never_a_terminal_assessment(challenge, monkeypatch):
    monkeypatch.setenv("MODEL_API_KEY", "synthetic-test-placeholder")
    def respond(request):
        return httpx.Response(200, json={"status": "completed", "error": None,
            "output": [{"type": "message", "role": "assistant",
                        "content": [{"type": "output_text", "text": "SUPPORT"}]}]})
    client = MetaResponsesClient(transport=httpx.MockTransport(respond))
    try:
        result = run_challenger(challenge, client)
    finally:
        client.close()
    assert result.status == "failed" and result.reason == "no_submitted_assessment"
    assert result.requests == 3 and challenge.assessment is None and challenge.diagnosis is None
