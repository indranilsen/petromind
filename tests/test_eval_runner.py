import json
from functools import partial

import httpx
import pytest

from petromind.eval_cli import main
from petromind.eval_protocol import digest
from petromind.eval_runner import read_jsonl, run_evaluation, task_plan
from petromind.meta_api import MetaResponsesClient
from petromind.meta_api import MetaAPIError


def fake_model(monkeypatch):
    monkeypatch.setenv("MODEL_API_KEY", "test-placeholder-not-a-real-credential")
    requests = []
    def respond(request):
        body = json.loads(request.content)
        requests.append(body)
        serialized = json.dumps(body)
        assert "WELL-" not in serialized and ".parquet" not in serialized and "true_event" not in serialized
        tools = {t["name"] for t in body["tools"]}
        completed = sum(i.get("type") == "function_call_output" for i in body["input"])
        steps = []
        if "get_equipment_neighbors" in tools:
            steps.append(("get_equipment_neighbors", {"sensor_name": "P-TPT"}))
        sensor = "T-TPT" if "get_equipment_neighbors" in tools else "P-TPT"
        steps.append(("get_sensor_history", {"sensor_name": sensor}))
        if "search_similar_incidents" in tools:
            steps.append(("search_similar_incidents", {"top_k": 3}))
        steps.append(("submit_diagnosis", {"predicted_fault_type": 2, "confidence": .6, "evidence": [sensor]}))
        name, arguments = steps[completed]
        return httpx.Response(200, json={"status": "completed", "error": None,
            "usage": {"input_tokens": 100, "output_tokens": 20, "total_tokens": 120,
                      "input_tokens_details": {"cached_tokens": 40}, "output_tokens_details": {"reasoning_tokens": 10}},
            "output": [{"type": "function_call", "call_id": f"call{completed}", "name": name,
                        "arguments": json.dumps(arguments), "status": "completed"}]})
    return partial(MetaResponsesClient, transport=httpx.MockTransport(respond)), requests


def test_pilot_full_pairing_resume_and_reports(dataset, prepared_protocol, monkeypatch):
    protocol, out, _ = prepared_protocol
    factory, requests = fake_model(monkeypatch)
    with pytest.raises(ValueError, match="pilot"):
        run_evaluation(out, dataset, "full", client_factory=factory)
    assert requests == []
    pilot = run_evaluation(out, dataset, client_factory=factory)
    assert pilot["stage_complete"] and pilot["pilot_ready"]
    rows = read_jsonl(out / "results.jsonl")
    assert len(rows) == 5 and len(requests) == 9
    assert all(row["budget"] == 2 and len(row["sensor_sequence"]) <= 2 for row in rows)
    assert all(row["audit_valid"] and row["cost_complete"] for row in rows)
    assert sum(row["requests"] for row in rows if row["method"] in {"fixed", "adaptive"}) == 0
    assert len(read_jsonl(out / "reservations.jsonl")) == 9
    compare = next(c for c in pilot["paired_comparisons"] if c["left"] == "sensor_only" and c["right"] == "topology")
    assert compare["sequence_changed_cases"] == 1
    assert compare["accuracy_delta_right_minus_left"] == 0.  # Different selection does not imply better accuracy.
    run_evaluation(out, dataset, client_factory=factory)
    assert len(requests) == 9  # Resume never reruns completed pilot tasks.
    full = run_evaluation(out, dataset, "full", client_factory=factory)
    assert full["stage_complete"] and full["n_cases"] == 2
    rows = read_jsonl(out / "results.jsonl")
    assert len(rows) == 10 and len(requests) == 18
    for method in {r["method"] for r in rows}:
        assert {r["case_id"] for r in rows if r["method"] == method} == {
            r["case_id"] for r in protocol["records"] if r["partition"] == "test"}
    assert all(s["complete"] for s in full["summary"])
    assert (out / "results.csv").is_file() and (out / "report.md").is_file()
    assert all(r["graph_calls"] == 0 and r["retrieval_calls"] == 0 for r in rows if r["method"] == "sensor_only")
    assert all(r["retrieval_calls"] == 0 for r in rows if r["method"] == "topology")
    for r in rows:
        for event in r["retrieval_events"]:
            for match in event["result"].get("matches", []):
                assert set(match["matched_sensors"]) <= set(r["sensor_sequence"])
                assert match["case_id"] in {x["case_id"] for x in protocol["records"] if x["partition"] == "train"}


def test_total_budget_is_persistent_and_prevents_extra_paid_calls(dataset, prepared_protocol, monkeypatch):
    _, out, _ = prepared_protocol
    factory, requests = fake_model(monkeypatch)
    result = run_evaluation(out, dataset, client_factory=factory, max_requests=1)
    assert not result["stage_complete"] and not result["pilot_ready"]
    assert len(requests) == 1
    assert len(read_jsonl(out / "reservations.jsonl")) == 1
    run_evaluation(out, dataset, client_factory=factory, max_requests=1)
    assert len(requests) == 1


def test_interrupted_task_is_not_silently_retried(dataset, prepared_protocol, monkeypatch):
    protocol, out, _ = prepared_protocol
    first = task_plan(protocol, protocol["pilot_case_ids"])[0]
    (out / "traces").mkdir()
    (out / "traces" / (digest(first) + ".jsonl")).write_text('{"kind":"task_started"}\n')
    factory, requests = fake_model(monkeypatch)
    with pytest.raises(ValueError, match="Interrupted task"):
        run_evaluation(out, dataset, client_factory=factory)
    assert requests == []


def test_missing_key_does_not_create_scored_failure_or_poison_resume(dataset, prepared_protocol, monkeypatch):
    _, out, _ = prepared_protocol
    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    with pytest.raises(MetaAPIError, match="missing_or_invalid_api_key"):
        run_evaluation(out, dataset)
    assert not (out / "results.jsonl").exists()
    assert not list((out / "traces").glob("*.jsonl"))
    factory, _ = fake_model(monkeypatch)
    assert run_evaluation(out, dataset, client_factory=factory)["pilot_ready"]


def test_cli_freeze_analyze_and_no_overwrite(dataset, prepared_protocol, tmp_path, capsys):
    _, _, split_path = prepared_protocol
    out = tmp_path / "cli-output"
    args = ["prepare", "--dataset", str(dataset), "--split", str(split_path), "--out", str(out),
            "--expected-test-incidents", "2", "--pilot-cases", "1"]
    assert main(args) == 0
    output = capsys.readouterr().out
    assert '"api_requests":0' in output
    assert main(args) == 2
    capsys.readouterr()
    assert main(["analyze", "--out", str(out)]) == 0
    assert (out / "report.json").exists()
    assert not (out / "reservations.jsonl").exists()
