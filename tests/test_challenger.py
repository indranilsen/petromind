"""Synthetic unit fixtures only; no fabricated evidence enters real experiments."""
import copy
import json
from functools import partial
from contextlib import closing

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
    source = next(k for k, v in session.evidence_sources.items() if v.get("sensor_name") == sensor)
    baseline = json.loads(session._hypothesis)["prediction"]
    alt = 2 if baseline != 2 else 1
    claim = {"category": "contradictory" if decision == "CHALLENGE" else
                         "supporting" if decision == "SUPPORT" else "uncertainty",
             "source_id": source, "hypothesis_fault_type": baseline,
             "sensor_name": sensor, "field": "median", "value": obs.median,
             "interpretation": "The cited pressure differs from the declared expectation.",
             "expected_if_hypothesis_true": "Synthetic hypothesis predicts a constant pressure reading."
                                           if decision == "CHALLENGE" else None}
    claims = [claim]
    if decision == "CHALLENGE":
        claims.append({**claim, "hypothesis_fault_type": alt, "category": "supporting",
                       "expected_if_hypothesis_true": None})
    return {"decision": decision, "confidence": .6,
        "alternative_fault_type": alt if decision == "CHALLENGE" else None,
        "claims": claims, "relationships": [], "uncertainty": "No verified per-well topology."}


def tool_arguments(canonical):
    """Synthetic mock adapter only: produce the selected tool's explicit arguments."""
    return {k: v for k, v in canonical.items()
            if k != "decision" and (k != "alternative_fault_type" or v is not None)}


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
    args["claims"][1]["hypothesis_fault_type"] = args["alternative_fault_type"]
    result = session._submit_assessment(args)
    assert result["baseline_prediction"] == current["prediction"]
    assert result["alternative_fault_type"] != result["baseline_prediction"]
    assert session.diagnosis is None  # An assessment is never a replacement statistical diagnosis.
    assert session.dispatch("submit_diagnosis", {})["error"] == "investigation_closed"
    assert session.get_sensor_history(session.queries[0])["error"] == "investigation_closed"
    assert verify_audit(session.audit_trail)


@pytest.mark.parametrize("decision", ["SUPPORT", "CHALLENGE", "INSUFFICIENT_EVIDENCE"])
def test_decisions_validated_sealed_and_defensive_copies(challenge, decision):
    result = challenge._submit_assessment(assessment(challenge, decision))
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
    assert challenge._submit_assessment(args)["error"] == "invalid_assessment"
    assert challenge.assessment is None
    assert "WELL-secret" not in challenge.audit_trail[-1].arguments_json


def test_support_cannot_propose_alternative(challenge):
    args = assessment(challenge, "SUPPORT")
    args["alternative_fault_type"] = 2
    assert "error" in challenge._submit_assessment(args)


def test_missing_readings_charged_and_cannot_be_contradiction(frame):
    frame["P-TPT"] = float("nan")
    session = ChallengeSession(frame, frame.columns)
    session.bind_hypothesis(hypothesis())
    session.get_sensor_history("P-TPT")
    assert session.remaining_budget == 4
    args = {"decision": "INSUFFICIENT_EVIDENCE", "confidence": .2, "alternative_fault_type": None,
        "claims": [{"category": "unavailable", "sensor_name": "P-TPT", "field": "available", "value": False,
                    "source_id": next(iter(session.evidence_sources)), "hypothesis_fault_type": 1,
                    "expected_if_hypothesis_true": None, "interpretation": "No usable reading."}], "relationships": [], "uncertainty": "Missing evidence."}
    invalid = copy.deepcopy(args)
    invalid["decision"] = "CHALLENGE"
    invalid["claims"][0]["category"] = "contradictory"
    assert "error" in session._submit_assessment(invalid)
    assert session._submit_assessment(args)["decision"] == "INSUFFICIENT_EVIDENCE"


def test_zero_constant_is_valid_not_missing(frame):
    frame["P-TPT"] = 0.
    session = ChallengeSession(frame, frame.columns)
    session.bind_hypothesis(hypothesis())
    session.get_sensor_history("P-TPT")
    assert session.observations["P-TPT"].available
    args = assessment(session, "SUPPORT")
    args["claims"][0].update(field="constant_value", value=0.)
    assert "error" not in session._submit_assessment(args)


def test_graph_relations_require_actual_return_and_illustrative_status(challenge):
    args = assessment(challenge)
    args["relationships"] = [{"sensor": "P-TPT", "equipment": "tubing", "relation": "associated_with", "verification": "illustrative"}]
    assert "error" in challenge._submit_assessment(args)
    challenge.get_equipment_neighbors("P-TPT")
    assert "error" not in challenge._submit_assessment(args)


def test_variant_capabilities_and_no_direct_diagnosis(frame):
    for variant in ("sensor_only", "topology", "graphrag"):
        session = ChallengeSession(frame, frame.columns, variant=variant)
        tools = {t["name"] for t in assessment_tools(variant)}
        assert "submit_diagnosis" not in tools and "submit_assessment" not in tools
        assert "submit_support" in tools
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
        assert "submit_challenge_with_alternative" in {t["name"] for t in body["tools"]}
        return httpx.Response(200, json={"status": "completed", "error": None,
            "usage": {"input_tokens": 100, "output_tokens": 20}, "output": [{"type": "function_call",
                "call_id": "assessment1", "name": "submit_challenge_with_alternative", "arguments": json.dumps(tool_arguments(assessment(challenge)))}]})
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


def test_validation_feedback_is_actionable_and_never_reflects_rejected_data(challenge):
    args = assessment(challenge)
    args["claims"][0]["value"] = 999999
    error = challenge._submit_assessment(args)
    assert error["validation_code"] == "citation_value_mismatch"
    assert error["field"] == "claims[0].value" and challenge.validation_failures == 1
    assert error["correction"] and error["repairs_remaining"] == 2
    args["claims"][0]["sensor_name"] = "/private/7/WELL-secret.parquet"
    error = challenge._submit_assessment(args)
    assert error["validation_code"] == "sensor_not_observed"
    assert "WELL-secret" not in json.dumps(error)
    assert "WELL-secret" not in challenge.audit_trail[-1].arguments_json
    assert challenge.assessment is None


def test_model_can_repair_a_quote_using_feedback_without_more_sensor_queries(challenge, monkeypatch):
    monkeypatch.setenv("MODEL_API_KEY", "synthetic-test-placeholder")
    def respond(request):
        body = json.loads(request.content)
        outputs = [i for i in body["input"] if i.get("type") == "function_call_output"]
        args = assessment(challenge)
        if not outputs:
            args["claims"][0]["value"] = -999
        else:
            assert json.loads(outputs[-1]["output"])["validation_code"] == "citation_value_mismatch"
        return httpx.Response(200, json={"status": "completed", "error": None,
            "output": [{"type": "function_call", "name": "submit_challenge_with_alternative",
                        "call_id": f"repair{len(outputs)}", "arguments": json.dumps(tool_arguments(args))}]})
    with closing(MetaResponsesClient(transport=httpx.MockTransport(respond))) as client:
        result = run_challenger(challenge, client)
    assert result.status == "completed" and result.requests == 2
    assert challenge.remaining_budget == 4 and challenge.validation_failures == 1


def test_rejected_submissions_stop_spending_without_inventing_an_assessment(challenge, monkeypatch):
    monkeypatch.setenv("MODEL_API_KEY", "synthetic-test-placeholder")
    def respond(request):
        body = json.loads(request.content)
        count = sum(i.get("type") == "function_call_output" for i in body["input"])
        return httpx.Response(200, json={"status": "completed", "error": None,
            "output": [{"type": "function_call", "name": "submit_challenge_with_alternative",
                        "call_id": f"invalid{count}", "arguments": "{}"}]})
    with closing(MetaResponsesClient(transport=httpx.MockTransport(respond))) as client:
        result = run_challenger(challenge, client)
    assert result.status == "failed" and result.reason == "assessment_repeated_invalid_submission"
    assert result.requests == 2 and challenge.validation_failures == 2
    assert challenge.assessment is None and challenge.diagnosis is None


@pytest.mark.parametrize("text", ["expert review needed for this contradictory observation",
    "Expert review needed.", "Consult an expert to evaluate this observation."])
def test_pilot_generic_recommendation_is_not_contradictory_evidence(challenge, text):
    args = assessment(challenge)
    args["claims"][0]["interpretation"] = text
    result = challenge._submit_assessment(args)
    assert result["validation_code"] == "generic_evidence_claim"
    assert result["field"] == "claims[0].interpretation" and result["correction"]
    assert challenge.assessment is None


def test_pilot_contradicting_alternative_is_not_baseline_contradiction(challenge):
    args = assessment(challenge)
    args["claims"] = [args["claims"][0]]
    args["claims"][0]["hypothesis_fault_type"] = args["alternative_fault_type"]
    result = challenge._submit_assessment(args)
    assert result["validation_code"] == "challenge_requires_baseline_contradiction"


def test_alternative_requires_its_own_support_and_cannot_be_contradicted(challenge):
    args = assessment(challenge)
    args["claims"].pop()
    assert challenge._submit_assessment(args)["validation_code"] == "alternative_requires_support"
    args = assessment(challenge)
    args["claims"][1]["category"] = "contradictory"
    args["claims"][1]["expected_if_hypothesis_true"] = "The synthetic alternative predicts a different pressure level."
    assert challenge._submit_assessment(args)["validation_code"] == "alternative_conflicts_with_evidence"


def test_support_cannot_keep_unresolved_baseline_contradiction(challenge):
    args = assessment(challenge, "SUPPORT")
    contradiction = assessment(challenge)["claims"][0]
    contradiction.update(field="std", value=challenge.observations["P-TPT"].std)
    args["claims"].append(contradiction)
    assert challenge._submit_assessment(args)["validation_code"] == "support_conflicts_with_contradiction"


def test_same_fact_cannot_support_and_contradict_same_hypothesis(challenge):
    args = assessment(challenge)
    args["claims"].append({**args["claims"][0], "category": "supporting"})
    assert challenge._submit_assessment(args)["validation_code"] == "conflicting_evidence_relationships"


@pytest.mark.parametrize("mutation, code", [
    (lambda a: a["claims"][0].pop("source_id"), "missing_claim_field"),
    (lambda a: a["claims"][0].update(source_id="measurement:99999"), "source_not_observed"),
    (lambda a: a["claims"][0].update(hypothesis_fault_type=True), "invalid_claim_hypothesis"),
    (lambda a: a["claims"][0].update(expected_if_hypothesis_true=None), "contradiction_requires_expectation"),
])
def test_missing_or_unsupported_citations_and_expectations(challenge, mutation, code):
    args = assessment(challenge)
    mutation(args)
    assert challenge._submit_assessment(args)["validation_code"] == code


def test_measurement_sources_bind_to_audited_query_and_cannot_be_reassigned(challenge):
    source_id, source = next(iter(challenge.evidence_sources.items()))
    audit = challenge.audit_trail[source["audit_sequence"] - 1]
    assert audit.tool == "get_sensor_history"
    assert json.loads(audit.result_json)["source_id"] == source_id
    source["sensor_name"] = "T-PDG"
    assert challenge.evidence_sources[source_id]["sensor_name"] == "P-TPT"
    args = assessment(challenge)
    result = challenge._submit_assessment(args)
    assert result["evidence_provenance"][source_id]["sensor_name"] == "P-TPT"
    assert result["claims"][0]["hypothesis_fault_type"] == 1
    assert result["claims"][0]["relationship"] == "contradicts"
    assert result["physical_correctness_verified"] is False


def test_illustrative_graph_edges_are_context_not_evidence_sources(challenge):
    returned = challenge.get_equipment_neighbors("P-TPT")
    assert returned["relationships"] and not returned["evidence_sources"]
    args = assessment(challenge)
    args["claims"][0]["source_id"] = f"graph:{len(challenge.audit_trail)}:0"
    assert challenge._submit_assessment(args)["validation_code"] == "source_not_observed"


def test_only_actually_returned_verified_graph_relationship_can_be_cited(challenge):
    from types import SimpleNamespace
    # Synthetic verified fixture, not a claim about actual PetroMind topology.
    relation = {"sensor": "P-TPT", "equipment": "synthetic_fixture", "relation": "monitors",
                "verification": "verified_generic", "provenance": "Synthetic unit-test source only"}
    challenge._graph = SimpleNamespace(neighbors=lambda *a: {"relationships": [relation], "equipment": [],
        "neighbor_sensors": [], "sensor": "P-TPT", "note": "Synthetic test"})
    returned = challenge.get_equipment_neighbors("P-TPT")
    source = returned["evidence_sources"][0]
    args = assessment(challenge, "INSUFFICIENT_EVIDENCE")
    args["claims"] = [{"source_id": source["source_id"], "hypothesis_fault_type": 1,
        "category": "uncertainty", "sensor_name": None, "field": None, "value": None,
        "interpretation": "A generic relation cannot establish an event cause.", "expected_if_hypothesis_true": None}]
    result = challenge._submit_assessment(args)
    assert result["claims"][0]["relationship"] == "inconclusive"
    assert result["evidence_provenance"][source["source_id"]]["relationship"] == relation
    assert result["physical_correctness_verified"] is False


def test_repeated_identical_invalid_payload_key_order_is_detected(challenge):
    args = assessment(challenge)
    args["claims"][0]["value"] = -999
    challenge._submit_assessment(args)
    args = dict(reversed(list(args.items())))
    result = challenge._submit_assessment(args)
    assert result["validation_code"] == "repeated_invalid_submission"
    assert result["repairs_remaining"] == 0
    assert challenge.dispatch("get_sensor_history", {"sensor_name": "T-TPT"})["error"] == "investigation_closed"


def test_rejected_diagnostic_metadata_does_not_store_unknown_fields_or_text(challenge):
    secret = "/private/7/WELL-secret.parquet secret-reasoning"
    args = assessment(challenge)
    args[secret] = secret
    result = challenge._submit_assessment(args)
    audit = challenge.audit_trail[-1]
    assert result["validation_code"] == "invalid_submission_fields" and result["field"] == "$"
    assert secret not in audit.arguments_json + audit.result_json
    assert json.loads(audit.arguments_json)["field"] == "$"
    assert verify_audit(challenge.audit_trail)


@pytest.mark.parametrize("valid_third", [False, True])
def test_at_most_two_repairs_after_initial_submission(challenge, monkeypatch, valid_third):
    monkeypatch.setenv("MODEL_API_KEY", "synthetic-test-placeholder")
    def respond(request):
        body = json.loads(request.content)
        count = sum(i.get("type") == "function_call_output" for i in body["input"])
        args = assessment(challenge)
        if count < 2 or not valid_third:
            args["confidence"] = count + 2  # Distinct invalid payloads, not an identical retry.
        return httpx.Response(200, json={"status": "completed", "error": None,
            "output": [{"type": "function_call", "name": "submit_challenge_with_alternative",
                        "call_id": f"repair{count}", "arguments": json.dumps(tool_arguments(args))}]})
    with closing(MetaResponsesClient(transport=httpx.MockTransport(respond))) as client:
        result = run_challenger(challenge, client)
    assert result.requests == 3
    if valid_third:
        assert result.status == "completed" and challenge.assessment
    else:
        assert result.status == "failed" and result.reason == "assessment_repair_limit"
        assert challenge.assessment is None


@pytest.mark.parametrize("raw, code", [('{broken', 'invalid_assessment_json'),
    ('{"decision":"SUPPORT","decision":"CHALLENGE"}', 'invalid_assessment_json'),
    ('{"confidence":NaN}', 'invalid_assessment_json'), ('{"confidence":1e309}', 'invalid_assessment_json'), ('[]', 'assessment_object_required'),
    ('x' * 8193, 'assessment_arguments_too_large')])
def test_malformed_argument_diagnostics_are_specific_and_label_safe(challenge, raw, code):
    from petromind.assessment import decode_submission
    result = challenge._submit_assessment(decode_submission(raw))
    assert result["validation_code"] == code and result["field"] == "$" and result["correction"]
    assert raw not in challenge.audit_trail[-1].result_json
    assert challenge.assessment is None


def test_identical_malformed_submission_stops_and_terminal_failure_cannot_be_reopened(challenge):
    from petromind.assessment import decode_submission
    raw = '{"private/WELL-secret": '
    challenge._submit_assessment(decode_submission(raw))
    result = challenge._submit_assessment(decode_submission(raw))
    assert result["validation_code"] == "repeated_invalid_submission"
    assert raw not in json.dumps(result)
    assert challenge._submit_assessment(assessment(challenge))["error"] == "investigation_closed"
    assert challenge.assessment is None


def test_malformed_json_reaches_actionable_tool_feedback_and_stops_duplicate(challenge, monkeypatch):
    monkeypatch.setenv("MODEL_API_KEY", "synthetic-test-placeholder")
    def respond(request):
        body = json.loads(request.content)
        outputs = [i for i in body["input"] if i.get("type") == "function_call_output"]
        if outputs:
            assert json.loads(outputs[-1]["output"])["validation_code"] == "invalid_assessment_json"
        return httpx.Response(200, json={"status": "completed", "error": None,
            "output": [{"type": "function_call", "name": "submit_challenge_with_alternative", "call_id": f"bad{len(outputs)}",
                        "arguments": "{broken"}]})
    with closing(MetaResponsesClient(transport=httpx.MockTransport(respond))) as client:
        result = run_challenger(challenge, client)
    assert result.requests == 2 and result.reason == "assessment_repeated_invalid_submission"
    assert challenge.assessment is None


def test_reliability_patch_keeps_original_diagnostic_prompt_unchanged():
    from petromind.challenger import INSTRUCTIONS
    from petromind.eval_protocol import digest
    # Original user-executed v1 pilot's frozen prompt digest.
    assert digest(INSTRUCTIONS) == "438384c677d7d0dafb0efad0054320d9f390412b1240bfa217f6dd955e1d9fd1"


def test_requerying_verified_graph_does_not_hide_conflicting_claims(challenge):
    from types import SimpleNamespace
    relation = {"sensor": "P-TPT", "equipment": "synthetic_fixture", "relation": "monitors",
                "verification": "verified_generic", "provenance": "Synthetic unit-test source only"}
    challenge._graph = SimpleNamespace(neighbors=lambda *a: {"relationships": [relation], "equipment": [],
        "neighbor_sensors": [], "sensor": "P-TPT", "note": "Synthetic test"})
    first = challenge.get_equipment_neighbors("P-TPT")["evidence_sources"][0]["source_id"]
    second = challenge.get_equipment_neighbors("P-TPT")["evidence_sources"][0]["source_id"]
    assert first != second
    args = assessment(challenge, "INSUFFICIENT_EVIDENCE")
    claim = {"source_id": first, "hypothesis_fault_type": 1, "category": "supporting",
        "sensor_name": None, "field": None, "value": None,
        "interpretation": "The synthetic monitored relation bears on this hypothesis.", "expected_if_hypothesis_true": None}
    args["claims"] = [claim, {**claim, "source_id": second, "category": "contradictory",
        "expected_if_hypothesis_true": "The synthetic hypothesis expects a different monitored relation."}]
    assert challenge._submit_assessment(args)["validation_code"] == "conflicting_evidence_relationships"


def test_unqueried_measurements_do_not_enter_sources_errors_or_model_context(frame, monkeypatch):
    monkeypatch.setenv("MODEL_API_KEY", "synthetic-test-placeholder")
    sentinel = 918273645.
    frame["QGL"] = sentinel
    session = ChallengeSession(frame, frame.columns)
    session.get_sensor_history("P-TPT")
    session.bind_hypothesis(hypothesis())
    args = assessment(session)
    args["claims"][0].update(source_id="measurement:999", sensor_name="QGL", value=0.)
    error = session._submit_assessment(args)
    assert error["validation_code"] == "source_not_observed"
    assert "918273645" not in json.dumps(error) + json.dumps(session.evidence_sources)
    assert all(s.get("sensor_name") != "QGL" for s in session.evidence_sources.values())
    def respond(request):
        assert "918273645" not in request.content.decode()
        return httpx.Response(200, json={"status": "completed", "error": None,
            "output": [{"type": "function_call", "call_id": "safe", "name": "submit_support",
                        "arguments": json.dumps(tool_arguments(assessment(session, "SUPPORT")))}]})
    with closing(MetaResponsesClient(transport=httpx.MockTransport(respond))) as client:
        assert run_challenger(session, client).status == "completed"
    assert session.remaining_budget == 4


@pytest.mark.parametrize("decision, alt, expected", [
    ("SUPPORT", 2, "alternative_not_allowed_for_decision"),
    ("CHALLENGE", True, "alternative_wrong_type"),
    ("CHALLENGE", "2", "alternative_wrong_type"),
    ("CHALLENGE", 0, "alternative_out_of_range"),
    ("CHALLENGE", 10, "alternative_out_of_range"),
    ("CHALLENGE", 2.5, "alternative_not_integer"),
    ("CHALLENGE", 1, "alternative_matches_baseline"),
])
def test_alternative_rejection_reports_exact_contract_reason(challenge, decision, alt, expected):
    args = assessment(challenge, decision)
    args["alternative_fault_type"] = alt
    error = challenge._submit_assessment(args)
    assert error["validation_code"] == expected
    assert error["field"] == "alternative_fault_type" and error["correction"]
    assert set(error["validation_context"]) == {"provided_json_type", "is_integral_number",
        "in_public_fault_range", "matches_baseline_prediction", "decision_allows_alternative"}
    assert "true_event" not in json.dumps(error)


def test_schema_integral_fault_numbers_accept_2_point_0_without_coercing_readings(challenge):
    args = assessment(challenge)
    args["alternative_fault_type"] = 2.0
    args["claims"][0]["hypothesis_fault_type"] = 1.0
    args["claims"][1]["hypothesis_fault_type"] = 2.0
    original_reading = args["claims"][0]["value"]
    result = challenge._submit_assessment(args)
    assert result["decision"] == "CHALLENGE"
    assert type(result["alternative_fault_type"]) is int
    assert all(type(c["hypothesis_fault_type"]) is int for c in result["claims"])
    assert result["claims"][0]["value"] == original_reading


def test_duplicate_rejection_retains_underlying_safe_reason(challenge):
    args = assessment(challenge)
    args["alternative_fault_type"] = "secret-value"
    challenge._submit_assessment(args)
    error = challenge._submit_assessment(args)
    assert error["validation_code"] == "repeated_invalid_submission"
    assert error["underlying_validation_code"] == "alternative_wrong_type"
    assert error["underlying_field"] == "alternative_fault_type"
    assert error["validation_context"]["provided_json_type"] == "string"
    assert "secret-value" not in challenge.audit_trail[-1].arguments_json + json.dumps(error)


def test_model_tool_contract_discloses_alternative_support_before_validation():
    tools = {t["name"]: t for t in assessment_tools("sensor_only")}
    assert "submit_assessment" not in tools
    for name in ("submit_support", "submit_insufficient_evidence", "submit_challenge_without_alternative"):
        properties = tools[name]["parameters"]["properties"]
        assert "alternative_fault_type" not in properties and "decision" not in properties
    tool = tools["submit_challenge_with_alternative"]
    properties = tool["parameters"]["properties"]
    assert "supporting claim" in properties["alternative_fault_type"]["description"]
    assert properties["alternative_fault_type"]["type"] == "integer"
    assert properties["claims"]["minItems"] == 2


def test_unsourced_alternative_still_rejected_with_schema_integral_number(challenge):
    args = assessment(challenge)
    args["alternative_fault_type"] = 2.0
    args["claims"].pop()
    error = challenge._submit_assessment(args)
    assert error["validation_code"] == "alternative_requires_support"
    assert challenge.assessment is None


@pytest.mark.parametrize("field", ["confidence", "citation"])
def test_large_json_integers_fail_safely_without_overflow(challenge, field):
    args = assessment(challenge)
    if field == "confidence":
        args["confidence"] = 10 ** 400
    else:
        args["claims"][0]["value"] = 10 ** 400
    error = challenge._submit_assessment(args)
    assert error["validation_code"] in {"invalid_confidence", "citation_value_mismatch"}
    assert challenge.assessment is None


TOOL_PATHS = [
    ("submit_support", "SUPPORT", False),
    ("submit_insufficient_evidence", "INSUFFICIENT_EVIDENCE", False),
    ("submit_challenge_without_alternative", "CHALLENGE", False),
    ("submit_challenge_with_alternative", "CHALLENGE", True),
]


def path_arguments(session, decision, alternative):
    args = assessment(session, decision)
    if not alternative:
        args["alternative_fault_type"] = None
        args["claims"] = args["claims"][:1]
    return tool_arguments(args)


@pytest.mark.parametrize("tool,decision,alternative", TOOL_PATHS)
def test_mocked_agent_each_decision_tool_normalizes_and_seals(challenge, monkeypatch, tool, decision, alternative):
    """Four HTTP-mocked interactions; no connection to Meta or real dataset."""
    from petromind.assessment import ASSESSMENT_VERSION
    from petromind.challenger import MODEL_INSTRUCTIONS, TOOL_CONTRACT_VERSION
    monkeypatch.setenv("MODEL_API_KEY", "synthetic-test-placeholder")
    args = path_arguments(challenge, decision, alternative)
    def respond(request):
        body = json.loads(request.content)
        assert body["instructions"] == MODEL_INSTRUCTIONS
        assert "submit_assessment" not in body["instructions"]
        definition = next(t for t in body["tools"] if t["name"] == tool)
        schema = definition["parameters"]
        assert set(args) == set(schema["required"]) == set(schema["properties"])
        assert schema["additionalProperties"] is False
        assert all(s not in request.content.decode() for s in ("true_event", "WELL-", ".parquet", "locator_hash"))
        return httpx.Response(200, json={"status": "completed", "error": None,
            "output": [{"type": "function_call", "name": tool,
                        "call_id": "new-contract", "arguments": json.dumps(args)}]})
    with closing(MetaResponsesClient(transport=httpx.MockTransport(respond))) as client:
        result = run_challenger(challenge, client)
    assert result.status == "completed" and result.requests == 1
    normalized = challenge.assessment
    assert normalized["decision"] == decision
    assert normalized["baseline_prediction"] == 1
    assert normalized["alternative_fault_type"] == (2 if alternative else None)
    assert normalized["contract_version"] == ASSESSMENT_VERSION
    assert normalized["tool_contract_version"] == TOOL_CONTRACT_VERSION
    assert normalized["submission_tool"] == tool
    assert normalized["evidence_provenance"] and normalized["mechanical_citations_valid"]
    assert normalized["physical_correctness_verified"] is False
    assert challenge.audit_trail[-1].tool == tool
    assert challenge.remaining_budget == 4 and challenge.diagnosis is None
    assert challenge.dispatch(tool, args)["error"] == "investigation_closed"
    assert verify_audit(challenge.audit_trail)


@pytest.mark.parametrize("tool,decision,alternative", TOOL_PATHS)
def test_each_surface_path_rejects_missing_citation(challenge, tool, decision, alternative):
    args = path_arguments(challenge, decision, alternative)
    args["claims"][0].pop("source_id")
    error = challenge.dispatch(tool, args)
    assert error["validation_code"] == "missing_claim_field"
    assert error["field"] == "claims[0].source_id"
    assert challenge.assessment is None


@pytest.mark.parametrize("tool,decision,alternative", TOOL_PATHS)
def test_each_surface_path_repeated_invalid_submission_stops_immediately(challenge, tool, decision, alternative):
    args = path_arguments(challenge, decision, alternative)
    args["claims"][0]["source_id"] = "/private/7/WELL-secret.parquet"
    first = challenge.dispatch(tool, args)
    second = challenge.dispatch(tool, dict(reversed(list(args.items()))))
    assert first["validation_code"] == "source_not_observed"
    assert second["validation_code"] == "repeated_invalid_submission"
    assert second["repairs_remaining"] == 0 and challenge.validation_failures == 2
    assert challenge.assessment is None and challenge._sealed
    assert "WELL-secret" not in challenge.audit_trail[-1].arguments_json + json.dumps(second)


@pytest.mark.parametrize("tool,decision,alternative", TOOL_PATHS[:3])
@pytest.mark.parametrize("extra", [{"alternative_fault_type": None}, {"alternative_fault_type": "null"},
                                    {"alternative_fault_type": 2}, {"decision": "CHALLENGE"}])
def test_irrelevant_fields_are_rejected_not_dropped_or_coerced(challenge, tool, decision, alternative, extra):
    args = path_arguments(challenge, decision, alternative)
    error = challenge.dispatch(tool, {**args, **extra})
    assert error["validation_code"] == "invalid_submission_fields"
    assert challenge.assessment is None
    # A genuinely corrected assessment can succeed; no automatic abstention.
    result = challenge.dispatch(tool, args)
    assert result["decision"] == decision and result["alternative_fault_type"] is None


@pytest.mark.parametrize("mutation,code", [
    (lambda a: a.pop("alternative_fault_type"), "missing_submission_field"),
    (lambda a: a.update(alternative_fault_type=None), "alternative_required"),
    (lambda a: a.update(alternative_fault_type="2"), "alternative_wrong_type"),
    (lambda a: a.update(alternative_fault_type=1), "alternative_matches_baseline"),
    (lambda a: a["claims"].pop(), "alternative_requires_support"),
    (lambda a: a["claims"][1].update(hypothesis_fault_type=3), "alternative_requires_support"),
    (lambda a: a["claims"][1].update(category="contradictory",
        expected_if_hypothesis_true="The synthetic alternative expects a different pressure reading."), "alternative_conflicts_with_evidence"),
])
def test_explicit_alternative_path_still_requires_consistent_separate_support(challenge, mutation, code):
    args = path_arguments(challenge, "CHALLENGE", True)
    mutation(args)
    error = challenge.dispatch("submit_challenge_with_alternative", args)
    assert error["validation_code"] == code and challenge.assessment is None
    if code in {"alternative_requires_support", "alternative_wrong_type", "alternative_matches_baseline"}:
        assert "submit_challenge_without_alternative" in error["correction"]
        assert "or JSON null" not in error["correction"]


def test_cannot_use_removed_universal_tool_or_smuggle_baseline_override(challenge):
    assert challenge.dispatch("submit_assessment", assessment(challenge))["error"] == "unknown_tool"
    assert challenge.assessment is None
    args = path_arguments(challenge, "SUPPORT", False)
    assert challenge.dispatch("submit_support", {**args, "baseline_prediction": 9})["validation_code"] == "invalid_submission_fields"
    assert challenge.assessment is None


def test_repair_budget_shared_across_decision_tools_no_successful_fallback(challenge):
    for index, (tool, decision, alternative) in enumerate(TOOL_PATHS[:3]):
        args = path_arguments(challenge, decision, alternative)
        args["confidence"] = 2 + index
        error = challenge.dispatch(tool, args)
        assert error["submission_attempt"] == index + 1
    assert challenge._assessment_stop_reason == "assessment_repair_limit"
    assert challenge.assessment is None
    args = path_arguments(challenge, "INSUFFICIENT_EVIDENCE", False)
    assert challenge.dispatch("submit_insufficient_evidence", args)["error"] == "investigation_closed"


def test_valid_abstention_with_missing_measurement_preserves_budget_and_source(frame):
    frame["P-TPT"] = float("nan")
    session = ChallengeSession(frame, frame.columns)
    observed = session.get_sensor_history("P-TPT")
    session.bind_hypothesis(hypothesis())
    args = {"confidence": .1, "uncertainty": "Pressure is missing, so this hypothesis cannot be tested.",
        "relationships": [], "claims": [{"source_id": observed["source_id"], "hypothesis_fault_type": 1,
        "category": "unavailable", "sensor_name": "P-TPT", "field": "available", "value": False,
        "interpretation": "The requested pressure sensor has no usable measurements.", "expected_if_hypothesis_true": None}]}
    result = session.dispatch("submit_insufficient_evidence", args)
    assert result["decision"] == "INSUFFICIENT_EVIDENCE"
    assert result["claims"][0]["relationship"] == "inconclusive" and result["remaining_budget"] == 4
    assert result["alternative_fault_type"] is None


@pytest.mark.parametrize("tool,decision,alternative", TOOL_PATHS)
def test_malformed_arguments_use_same_bounded_repair_for_every_tool(challenge, tool, decision, alternative):
    from petromind.assessment import decode_submission
    first = challenge.dispatch(tool, decode_submission('{broken'))
    second = challenge.dispatch(tool, decode_submission('{broken'))
    assert first["validation_code"] == "invalid_assessment_json"
    assert second["validation_code"] == "repeated_invalid_submission"
    assert challenge.assessment is None and challenge._sealed


def test_mock_agent_valid_abstention_after_repair_is_explicit_not_fallback(challenge, monkeypatch):
    monkeypatch.setenv("MODEL_API_KEY", "synthetic-test-placeholder")
    args = path_arguments(challenge, "INSUFFICIENT_EVIDENCE", False)
    def respond(request):
        body = json.loads(request.content)
        outputs = [i for i in body["input"] if i.get("type") == "function_call_output"]
        submitted = copy.deepcopy(args)
        if not outputs:
            submitted["claims"][0].pop("source_id")
        else:
            assert json.loads(outputs[-1]["output"])["validation_code"] == "missing_claim_field"
        return httpx.Response(200, json={"status": "completed", "error": None,
            "output": [{"type": "function_call", "name": "submit_insufficient_evidence",
                        "call_id": f"abstain{len(outputs)}", "arguments": json.dumps(submitted)}]})
    with closing(MetaResponsesClient(transport=httpx.MockTransport(respond))) as client:
        result = run_challenger(challenge, client)
    assert result.status == "completed" and result.requests == 2
    assert challenge.assessment["decision"] == "INSUFFICIENT_EVIDENCE"
    assert challenge.validation_failures == 1 and challenge.remaining_budget == 4
