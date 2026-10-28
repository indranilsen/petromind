import json
from functools import partial

import httpx
import pytest

from petromind.audit import AuditEntry, verify_audit
from petromind.challenge_cli import main
from petromind.challenge_protocol import freeze_development, validate_development
from petromind.challenge_runner import plan_tasks, run_challenge_evaluation
from petromind.challenger import ChallengeSession
from petromind.eval_protocol import digest
from petromind.eval_runner import read_jsonl
from petromind.meta_api import MetaAPIError, MetaResponsesClient
from petromind.retrieval import IncidentRetriever


@pytest.fixture
def development(dataset, prepared_protocol, tmp_path):
    _, _, split_path = prepared_protocol
    protocol = freeze_development(dataset, split_path, n_cases=12, pilot_cases=1)
    out = tmp_path / "challenger"
    out.mkdir()
    (out / "protocol.json").write_text(json.dumps(protocol))
    return protocol, out


def test_frozen_development_uses_original_training_wells_only(dataset, development):
    protocol, _ = development
    split, by_id = validate_development(protocol, dataset)
    assert set(protocol["development_wells"]) <= set(protocol["original_split"]["train_wells"])
    assert not set(protocol["development_wells"]) & set(split.train_wells)
    assert not set(protocol["original_split"]["test_wells"]) & set(split.train_wells)
    fit = [by_id[r["case_id"]] for r in protocol["records"] if r["role"] == "fit"]
    index = IncidentRetriever(fit, split)
    assert not index.index_wells & set(protocol["development_wells"])
    assert protocol["selection"]["population_accuracy_claim_allowed"] is False
    assert protocol["gate"]["false_challenge_rate_max"] == .2
    assert all(by_id[r["case_id"]].well in protocol["development_wells"] for r in protocol["selected"])
    assert {r["true_event"] for r in protocol["selected"]} <= {2, 8}


def test_freeze_is_deterministic_except_opaque_ids(dataset, development, prepared_protocol):
    protocol, _ = development
    again = freeze_development(dataset, prepared_protocol[2], n_cases=12, pilot_cases=1)
    assert again["retrieval_split"] == protocol["retrieval_split"]
    assert [r["locator_hash"] for r in again["selected"]] == [r["locator_hash"] for r in protocol["selected"]]
    assert again["gate"] == protocol["gate"]


def test_protocol_and_data_drift_rejected(dataset, development):
    protocol, _ = development
    protocol["gate"]["false_challenge_rate_max"] = .9
    with pytest.raises(ValueError, match="modified"):
        validate_development(protocol, dataset)


def factory(monkeypatch):
    monkeypatch.setenv("MODEL_API_KEY", "synthetic-test-placeholder")
    seen = []
    def respond(request):
        body = json.loads(request.content)
        seen.append(body)
        text = json.dumps(body)
        assert all(s not in text for s in ("true_event", "WELL-", ".parquet", "development_pool", "baseline_correct"))
        context = json.loads(body["input"][0]["content"][0]["text"])
        obs = context["observations"]
        assert len(obs) == 2 and context["remaining_budget"] == 3
        sensor = next(s for s, q in obs.items() if q["available"])
        tool_names = {t["name"] for t in body["tools"]}
        done = sum(i.get("type") == "function_call_output" for i in body["input"])
        steps = [("get_sensor_history", {"sensor_name": "T-TPT"})]
        if "get_equipment_neighbors" in tool_names:
            steps.append(("get_equipment_neighbors", {"sensor_name": "P-TPT"}))
        if "search_similar_incidents" in tool_names:
            steps.append(("search_similar_incidents", {"top_k": 3}))
        steps.append(("submit_assessment", {"decision": "INSUFFICIENT_EVIDENCE", "confidence": .4,
            "alternative_fault_type": None, "relationships": [], "uncertainty": "Synthetic test only.",
            "claims": [{"category": "uncertainty", "sensor_name": sensor, "field": "median",
                        "value": obs[sensor]["median"], "interpretation": "Requires review.",
                        "source_id": next(k for k,v in context["evidence_sources"].items() if v.get("sensor_name") == sensor),
                        "hypothesis_fault_type": context["hypothesis"]["prediction"], "expected_if_hypothesis_true": None}]}))
        name, args = steps[done]
        return httpx.Response(200, json={"status": "completed", "error": None,
            "usage": {"input_tokens": 100, "output_tokens": 20}, "output": [{"type": "function_call",
                "call_id": f"call{done}", "name": name, "arguments": json.dumps(args)}]})
    return partial(MetaResponsesClient, transport=httpx.MockTransport(respond)), seen


def test_end_to_end_pilot_full_resume_and_pairing(dataset, development, monkeypatch):
    protocol, out = development
    client, requests = factory(monkeypatch)
    with pytest.raises(ValueError, match="pilot"):
        run_challenge_evaluation(out, dataset, "full", client_factory=client)
    pilot = run_challenge_evaluation(out, dataset, client_factory=client)
    assert pilot["pilot_ready"] and pilot["stage_complete"]
    assert len(read_jsonl(out / "results.jsonl")) == 4
    count = len(requests)
    run_challenge_evaluation(out, dataset, client_factory=client)
    assert len(requests) == count
    report = run_challenge_evaluation(out, dataset, "full", client_factory=client)
    assert report["stage_complete"]
    rows = read_jsonl(out / "results.jsonl")
    assert len(rows) == 4 * len(protocol["selected"])
    for case in protocol["selected"]:
        paired = [r for r in rows if r["case_id"] == case["case_id"]]
        assert all(r["initial_sensor_sequence"] == case["initial_sensor_sequence"] for r in paired)
        assert all(r["baseline_prediction"] == case["baseline_prediction"] for r in paired)
        assert all(len(r["sensor_sequence"]) <= 5 and r["audit_valid"] for r in paired)
    train_ids = {r["case_id"] for r in protocol["records"] if r["role"] == "fit"}
    for row in rows:
        for event in row["retrieval_events"]:
            assert all(m["case_id"] in train_ids for m in event["result"].get("matches", []))
    assert all(r.get("recommendation") in {None, "PENDING"} for r in report["summary"])
    assert len(read_jsonl(out / "reservations.jsonl")) == len(requests)
    assert (out / "review-template.json").exists()
    packets = json.loads((out / "review-packets.json").read_text())
    assert "true_event" not in json.dumps(packets) and "baseline_correct" not in json.dumps(packets)
    for trace in (out / "traces").glob("*.jsonl"):
        entries = next(e["entries"] for e in read_jsonl(trace) if e["kind"] == "audit_snapshot")
        assert verify_audit(tuple(AuditEntry(**a) for a in entries))


def test_missing_key_fails_before_any_task_or_reservation(dataset, development, monkeypatch):
    _, out = development
    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    with pytest.raises(MetaAPIError, match="missing_or_invalid_api_key"):
        run_challenge_evaluation(out, dataset)
    assert not (out / "results.jsonl").exists()
    assert not list((out / "traces").glob("*.jsonl"))


def test_durable_spending_cap_and_interruption(dataset, development, monkeypatch):
    protocol, out = development
    client, requests = factory(monkeypatch)
    report = run_challenge_evaluation(out, dataset, client_factory=client, max_requests=1)
    assert not report["pilot_ready"] and len(requests) == 1
    run_challenge_evaluation(out, dataset, client_factory=client, max_requests=1)
    assert len(requests) == 1


def test_interrupted_task_not_retried(dataset, development, monkeypatch):
    protocol, out = development
    task = plan_tasks(protocol, protocol["pilot_case_ids"])[0]
    (out / "traces").mkdir()
    (out / "traces" / (digest(task) + ".jsonl")).write_text('{}\n')
    client, requests = factory(monkeypatch)
    with pytest.raises(ValueError, match="Interrupted"):
        run_challenge_evaluation(out, dataset, client_factory=client)
    assert not requests


def test_cli_requires_fresh_output_and_explicit_full_review(dataset, prepared_protocol, tmp_path, capsys):
    out = tmp_path / "cli-challenge"
    args = ["prepare", "--dataset", str(dataset), "--split", str(prepared_protocol[2]), "--out", str(out)]
    assert main(args) == 0
    assert '"api_requests":0' in capsys.readouterr().out
    before = (out / "protocol.json").read_bytes()
    assert main(args) == 2
    assert (out / "protocol.json").read_bytes() == before
    with pytest.raises(SystemExit):
        main(["full", "--dataset", str(dataset), "--out", str(out)])
    assert main(["analyze", "--out", str(out)]) == 0


def test_validation_revision_preserves_cohort_ids_pilot_settings_and_gate(dataset, development, prepared_protocol):
    parent, _ = development
    parent = json.loads(json.dumps(parent))
    parent.pop("assessment_repair_limit")
    parent.pop("assessment_contract_version")  # The real original protocol predates this operational bound.
    parent["protocol_id"] = digest({k: v for k, v in parent.items() if k != "protocol_id"})
    revised = freeze_development(dataset, prepared_protocol[2], n_cases=12, pilot_cases=1, cohort_from=parent)
    assert revised["parent_protocol_id"] == parent["protocol_id"]
    for key in ("records", "selected", "pilot_case_ids", "gate", "agent_config", "prompt_digest", "retrieval_split"):
        assert digest(revised[key]) == digest(parent[key])
    assert revised["assessment_repair_limit"] == 2
    assert revised["assessment_contract_version"] == "assessment-contract-v2"
    assert revised["protocol_id"] != parent["protocol_id"]
    with pytest.raises(ValueError, match="preserve"):
        freeze_development(dataset, prepared_protocol[2], n_cases=16, pilot_cases=1, cohort_from=parent)
    parent["gate"]["false_challenge_rate_max"] = .9
    with pytest.raises(ValueError, match="modified"):
        freeze_development(dataset, prepared_protocol[2], n_cases=12, pilot_cases=1, cohort_from=parent)
