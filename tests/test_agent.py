import json

import httpx
import pytest

from petromind.agent import AgentConfig, run_agent
from petromind.agent_tools import tool_definitions
from petromind.audit import verify_audit
from petromind.meta_api import MetaResponsesClient


def call(name, arguments, identifier):
    return {"type": "function_call", "name": name, "arguments": json.dumps(arguments),
            "call_id": identifier, "status": "completed"}


def response(*items, status="completed"):
    return {"status": status, "error": None, "output": list(items),
            "usage": {"input_tokens": 20, "output_tokens": 10, "total_tokens": 30}}


def invoke(session, responses, monkeypatch, config=None):
    monkeypatch.setenv("MODEL_API_KEY", "test-placeholder-not-a-real-credential")
    requests = []
    outputs = iter(responses)
    def respond(request):
        requests.append(json.loads(request.content))
        return httpx.Response(200, json=next(outputs))
    client = MetaResponsesClient(transport=httpx.MockTransport(respond))
    try:
        result = run_agent(session, client, config)
    finally:
        client.close()
    return result, requests


def test_model_selects_sensor_and_submits_without_label_access(session, monkeypatch):
    outputs = [response(call("list_sensors", {}, "c1")),
               response({"type": "reasoning", "encrypted_content": "opaque-do-not-log", "summary": []},
                        {"type": "message", "role": "assistant", "phase": "commentary",
                         "content": [{"type": "output_text", "text": "Checking a measurement"}]},
                        call("get_sensor_history", {"sensor_name": "T-PDG"}, "c2")),
               response(call("get_equipment_neighbors", {"sensor_name": "T-PDG"}, "c3")),
               response(call("search_similar_incidents", {"top_k": 3}, "c4")),
               response(call("submit_diagnosis", {"predicted_fault_type": 7, "confidence": .6,
                                                  "evidence": ["T-PDG"]}, "c5"))]
    result, requests = invoke(session, outputs, monkeypatch)
    assert result.status == "completed" and session.queries == ("T-PDG",)
    assert session.diagnosis.predicted_fault_type == 7
    assert result.requests == 5 and verify_audit(session.audit_trail)
    assert all(r["store"] is False and r["parallel_tool_calls"] is False for r in requests)
    assert all(r["include"] == ["reasoning.encrypted_content"] for r in requests)
    assert all(r["max_output_tokens"] == 2048 for r in requests)
    assert any(x.get("encrypted_content") == "opaque-do-not-log" for x in requests[2]["input"])
    assert any(x.get("phase") == "commentary" for x in requests[2]["input"])
    assert any(x.get("type") == "function_call_output" for x in requests[2]["input"])
    assert "opaque-do-not-log" not in str(result.events)
    assert "Checking a measurement" not in str(result.events)
    text = json.dumps(requests)
    assert "true_event" not in text and "WELL-" not in text and ".parquet" not in text
    assert "test-placeholder-not-a-real-credential" not in text + str(result)


def test_schema_declares_only_five_tools_and_all_properties_required():
    tools = tool_definitions()
    assert {t["name"] for t in tools} == {"list_sensors", "get_sensor_history",
        "get_equipment_neighbors", "search_similar_incidents", "submit_diagnosis"}
    for tool in tools:
        assert tool["strict"] and tool["parameters"]["additionalProperties"] is False
        assert set(tool["parameters"]["required"]) == set(tool["parameters"]["properties"])


@pytest.mark.parametrize("arguments", ["not JSON", "[]", '{"sensor_name":NaN}',
    '{"sensor_name":"P-TPT","sensor_name":"T-TPT"}', '"' + "x" * 9000 + '"'])
def test_bad_arguments_are_audited_and_recoverable(session, monkeypatch, arguments):
    bad = call("get_sensor_history", {}, "c1")
    bad["arguments"] = arguments
    outputs = [response(bad), response(call("get_sensor_history", {"sensor_name": "P-TPT"}, "c2")),
               response(call("submit_diagnosis", {"predicted_fault_type": 1, "confidence": .5,
                                                  "evidence": ["P-TPT"]}, "c3"))]
    result, _ = invoke(session, outputs, monkeypatch)
    assert result.status == "completed" and len(session.queries) == 1
    assert json.loads(session.audit_trail[0].result_json)["error"] == "invalid_arguments"


def test_unknown_tool_cannot_reach_evaluator(session, monkeypatch):
    result, _ = invoke(session, [response(call("evaluate", {"path": "/8/secret"}, "c1"))],
                       monkeypatch, AgentConfig(max_turns=1))
    assert result.status == "failed" and result.reason == "turn_limit"
    assert session.diagnosis is None and session.remaining_budget == 5
    assert "/8/secret" not in str(result.events) and "/8/secret" not in str(session.audit_trail)


def test_budget_cache_and_no_post_submission_calls(session, monkeypatch):
    outputs = []
    for i, name in enumerate(session._sensors):
        outputs.append(response(call("get_sensor_history", {"sensor_name": name}, f"c{i}")))
    outputs.extend([response(call("get_sensor_history", {"sensor_name": session._sensors[0]}, "cached")),
                    response(call("submit_diagnosis", {"predicted_fault_type": 1, "confidence": .5,
                              "evidence": [session._sensors[0]]}, "final"),
                             call("get_sensor_history", {"sensor_name": session._sensors[-1]}, "after"))])
    result, _ = invoke(session, outputs, monkeypatch)
    assert result.status == "completed" and session.remaining_budget == 0
    assert len(session.queries) == 5
    trace = str(result.events)
    assert "sensor_budget_exhausted" in trace and '"cached":true' in trace
    assert len(session.audit_trail) == 8  # Six requests, one cache hit, one submission.


def test_refusal_and_incomplete_outputs_do_not_execute_calls(session, monkeypatch):
    refusal = {"type": "message", "role": "assistant",
               "content": [{"type": "refusal", "refusal": "secret body"}]}
    result, _ = invoke(session, [response(refusal, call("get_sensor_history", {"sensor_name": "P-TPT"}, "c1"))], monkeypatch)
    assert result.reason == "model_refused_or_invalid_content" and not session.queries
    other, _ = invoke(session, [response(call("get_sensor_history", {"sensor_name": "P-TPT"}, "c2"), status="incomplete")], monkeypatch)
    assert other.reason == "model_response_not_completed" and not session.queries


def test_duplicate_ids_fail_before_any_dispatch(session, monkeypatch):
    duplicate = call("get_sensor_history", {"sensor_name": "P-TPT"}, "same")
    result, _ = invoke(session, [response(duplicate, duplicate)], monkeypatch)
    assert result.reason == "invalid_function_call" and not session.audit_trail


def test_plain_text_is_not_a_submission(session, monkeypatch):
    text = {"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "Fault is 1"}]}
    result, _ = invoke(session, [response(text)] * 3, monkeypatch)
    assert result.status == "failed" and result.reason == "no_submitted_diagnosis"
    assert session.diagnosis is None


def test_missing_encrypted_reasoning_fails_before_sensor_access(session, monkeypatch):
    result, _ = invoke(session, [response({"type": "reasoning", "summary": []},
        call("get_sensor_history", {"sensor_name": "P-TPT"}, "c1"))], monkeypatch)
    assert result.reason == "missing_encrypted_reasoning" and not session.audit_trail


def test_invalid_submission_can_be_corrected(session, monkeypatch):
    outputs = [response(call("submit_diagnosis", {"predicted_fault_type": 1, "confidence": .5,
                                                 "evidence": ["P-TPT"]}, "bad")),
               response(call("get_sensor_history", {"sensor_name": "P-TPT"}, "sensor")),
               response(call("submit_diagnosis", {"predicted_fault_type": 1, "confidence": .5,
                                                  "evidence": ["P-TPT"]}, "good"))]
    result, _ = invoke(session, outputs, monkeypatch)
    assert result.status == "completed" and "invalid_diagnosis" in str(result.events)


@pytest.mark.parametrize("config", [AgentConfig(max_turns=1), AgentConfig(max_tool_calls=1)])
def test_loop_limits_do_not_invent_a_diagnosis(session, monkeypatch, config):
    result, _ = invoke(session, [response(call("list_sensors", {}, "c1")),
                               response(call("list_sensors", {}, "c2"))], monkeypatch, config)
    assert result.status == "failed" and result.reason in {"turn_limit", "tool_call_limit"}
    assert session.diagnosis is None
