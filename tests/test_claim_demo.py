"""Synthetic contract/security tests; real-capture review is recorded separately."""

import json
import threading
from dataclasses import asdict

import httpx
import pytest

from petromind.audit import canonical, verify_audit
from petromind.claim_auditor import ClaimAuditSession
from petromind.claim_demo import DemoApp, freeze_live, make_server
from petromind.claim_review import TASKS, demo_cases, review_capture
from petromind.eval_protocol import digest
from petromind.measurements import summarize
from petromind.meta_api import MetaResponsesClient
from petromind.scope_auditor import (
    VERSION,
    ScopeAuditSession,
    scope_tools,
)


def packet():
    return {
        "claim": "Recorded endpoints rose, which does not prove a cause.",
        "constructed_evaluation_claim": True,
        "observations": {
            s: summarize([1, 2, 3]).to_dict() for s in ["ABER-CKGL", "P-PDG", "P-TPT"]
        },
        "baseline": {
            "prediction": 9,
            "confidence_calibrated": False,
            "probabilities": [
                {"fault_type": 9, "probability": 0.9, "represented_in_fit": True}
            ],
        },
        "claimed_values": [],
        "claim_citations": [],
        "scope": "Synthetic software test fixture",
    }


def finding(scope="measured_observation", verdict="SUPPORTED"):
    return {
        "statement": "The recorded P-TPT endpoint increased.",
        "premises": ["First 1, last 3."],
        "basis": "measurement",
        "verdict": verdict,
        "citations": ["measurement:P-TPT"],
        "missing_premise": "",
        "next_evidence": {"kind": "none", "target": "", "purpose": ""},
        "justification": "Endpoint difference is positive.",
        "scope": scope,
    }


def submit(f=None):
    f = f or finding()
    return {
        "verdict": f["verdict"],
        "findings": [f],
        "numeric_observations": [{"sensor": "P-TPT", "metric": "delta", "value": 2}],
    }


def test_v2_scope_preserves_supported_comparison_without_stronger_gaps():
    s = ScopeAuditSession(packet())
    r = s.dispatch("submit_audit", submit(finding("documented_comparison")))
    assert (
        r["contract_version"] == VERSION
        and s.result == r
        and verify_audit(s.audit_trail)
    )
    assert r["physical_correctness_verified"] is False
    assert r["findings"][0]["missing_premise"] == ""
    assert s.remaining_budget == 2


def test_supported_finding_cannot_require_stronger_claim_evidence():
    s = ScopeAuditSession(packet())
    f = finding()
    f["missing_premise"] = "Need generalizability."
    assert s.dispatch("submit_audit", submit(f))["error"]["code"] == "scope_mismatch"
    assert s.result is None


@pytest.mark.parametrize(
    "kind,target",
    [
        ("sensor", "ESTADO-DHSV"),
        ("document", "well:tag_map"),
        ("descriptive_test", "paired_pressure_trends"),
        ("no_verified_discriminating_test", "fault:9"),
    ],
)
def test_concrete_recommendation_paths_are_proposals_not_measurements(kind, target):
    s = ScopeAuditSession(packet())
    f = finding("diagnostic_conclusion", "NOT_ESTABLISHED")
    f["missing_premise"] = "No documented discriminating criterion."
    f["next_evidence"] = {
        "kind": kind,
        "target": target,
        "purpose": "Check this scoped premise; not proof of root cause.",
    }
    r = s.dispatch("submit_audit", submit(f))
    assert r["verdict"] == "NOT_ESTABLISHED" and s.remaining_budget == 2
    assert "ESTADO-DHSV" not in s.packet["observations"]


def test_invented_tests_and_missing_next_steps_are_rejected_with_bounded_repairs():
    s = ScopeAuditSession(packet())
    f = finding("diagnostic_conclusion", "NOT_ESTABLISHED")
    f["missing_premise"] = "Unknown physical rule."
    f["next_evidence"] = {
        "kind": "descriptive_test",
        "target": "magic_hydrate_proof",
        "purpose": "Prove fault.",
    }
    a = submit(f)
    assert s.dispatch("submit_audit", a)["error"]["code"] == "unknown_next_target"
    s.dispatch("submit_audit", a)
    assert s.stop == "assessment_repeated_invalid_submission"
    s = ScopeAuditSession(packet())
    f["next_evidence"] = {"kind": "none", "target": "", "purpose": ""}
    assert (
        s.dispatch("submit_audit", submit(f))["error"]["code"]
        == "missing_next_evidence"
    )


def test_old_contract_unchanged_and_v2_no_label_or_encoding_inference():
    from petromind.claim_auditor import VERSION as V1
    from petromind.claim_auditor import tools

    assert V1 == "claim-auditor-v1"
    assert (
        "scope"
        not in tools()[-1]["parameters"]["properties"]["findings"]["items"][
            "properties"
        ]
    )
    assert (
        "scope"
        in scope_tools()[-1]["parameters"]["properties"]["findings"]["items"][
            "properties"
        ]
    )
    s = ScopeAuditSession(packet())
    r = s.dispatch("lookup_knowledge", {"topic": "valve_codes"})
    assert next(f for f in r["facts"] if f["id"] == "valve:1")["object"] == "open"
    assert "ESTADO-DHSV" not in s.packet["observations"]
    assert (
        s.dispatch("get_sensor_history", {"sensor_name": "ESTADO-DHSV"})["error"][
            "code"
        ]
        == "tool_not_available"
    )


@pytest.fixture
def capture(tmp_path, monkeypatch):
    root = tmp_path / "capture"
    root.mkdir()
    tasks = []
    rows = []
    counts = {
        ("fault_expectation", "ungrounded"): 4,
        ("fault_expectation", "grounded"): 5,
        ("published_example_consistency", "ungrounded"): 4,
        ("published_example_consistency", "grounded"): 4,
    }
    for tid in TASKS:
        tasks.append({"task_id": tid, "source_case_id": "a" * 32, "packet": packet()})
        for method in ("checker", "ungrounded", "grounded"):
            if method == "checker":
                from petromind.claim_auditor import citation_checker

                result = citation_checker(packet())
                audit = []
            else:
                s = ClaimAuditSession(packet())
                a = submit()
                f = a["findings"][0]
                f.pop("scope")
                f["next_evidence"] = ""
                a["findings"] = [dict(f) for _ in range(counts[(tid, method)])]
                result = s.dispatch("submit_audit", a)
                audit = [asdict(x) for x in s.audit_trail]
            rows.append(
                {
                    "task_id": tid,
                    "method": method,
                    "status": "completed",
                    "reason": "synthetic_test_only",
                    "result": result,
                    "audit": audit,
                    "new_sensor_queries": 0,
                    "sensor_queries_inherited": 3,
                    "requests": 0,
                    "usage": {"estimated_cost_usd": 0},
                    "latency_seconds": 0,
                }
            )
    p = {
        "study": "claim-auditor-v1",
        "tasks": tasks,
        "histories": {},
        "pilot_task_ids": list(TASKS),
    }
    p["protocol_id"] = digest(p)
    for row in rows:
        row["protocol_id"] = p["protocol_id"]
    (root / "protocol.json").write_text(canonical(p))
    (root / "results.jsonl").write_text("".join(canonical(r) + "\n" for r in rows))
    monkeypatch.setattr("petromind.claim_review.CAPTURE_PROTOCOL", p["protocol_id"])
    monkeypatch.setattr("petromind.claim_review.CAPTURE_ROWS_DIGEST", digest(rows))
    return root


def test_capture_review_preserves_outputs_and_no_self_certification(capture):
    before = (capture / "results.jsonl").read_bytes()
    r = review_capture(capture)
    cases = demo_cases(capture)
    assert len(r["findings"]) == 17 and r["independent_engineering_review"] is False
    assert all(f["physical_correctness"] is None for f in r["findings"])
    assert (capture / "results.jsonl").read_bytes() == before
    assert cases[0]["remaining_budget"] == 2
    assert all(
        "true_event" not in canonical(c) and "review_target" not in canonical(c)
        for c in cases
    )
    rows = [json.loads(l) for l in before.splitlines()]
    rows[1]["result"]["verdict"] = "CONTRADICTED"
    (capture / "results.jsonl").write_text("".join(canonical(r) + "\n" for r in rows))
    with pytest.raises(ValueError):
        demo_cases(capture)


@pytest.fixture
def server(capture):
    app = DemoApp(capture)
    server = make_server(app, 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield app, f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
    server.server_close()
    thread.join()


def test_end_to_end_http_replay_assets_privacy_and_no_live_by_default(server):
    app, url = server
    with httpx.Client(trust_env=False) as client:
        page = client.get(url + "/")
        assert page.status_code == 200 and "A well has dozens of sensors." in page.text
        for asset in ("app.js", "style.css"):
            assert client.get(url + "/" + asset).status_code == 200
        result = client.get(url + "/api/cases").json()
        assert len(result["cases"]) == 2
        assert "true_event" not in canonical(
            result
        ) and "review_target" not in canonical(result)
        assert client.get(url + "/api/status").json()["live_enabled"] is False
        assert client.get(url + "/api/review").json()["api_requests"] == 0
        assert client.get(url + "/../../protocol.json").status_code == 404
        assert (
            client.get(url + "/", headers={"Host": "evil.example"}).status_code == 403
        )
        assert (
            client.post(
                url + "/api/live", json={"case_id": TASKS[0], "request_id": "a" * 32}
            ).status_code
            == 403
        )
        headers = {"Origin": url, "X-PetroMind-Token": app.token}
        assert (
            client.post(
                url + "/api/live",
                headers=headers,
                json={"case_id": TASKS[0], "request_id": "a" * 32},
            ).status_code
            == 400
        )
        assert "frame-ancestors" in page.headers["Content-Security-Policy"]


def test_live_requires_fresh_versioned_protocol_and_does_not_call_on_start(
    capture, tmp_path
):
    out = tmp_path / "live"
    r = freeze_live(capture, out)
    assert r["api_requests"] == 0 and r["contract_version"] == VERSION

    def forbidden(**kw):
        raise AssertionError("No API client on start")

    app = DemoApp(capture, out, client_factory=forbidden)
    assert app.live_directory == out
    with pytest.raises(ValueError):
        freeze_live(capture, out)
    p = json.loads((out / "protocol.json").read_text())
    p["prompt_digest"] = "old"
    p.pop("protocol_id")
    p["protocol_id"] = digest(p)
    (out / "protocol.json").write_text(canonical(p))
    with pytest.raises(ValueError):
        DemoApp(capture, out)


def test_mock_live_v2_execution_is_separate_idempotent_and_budgeted(
    capture, tmp_path, monkeypatch
):
    out = tmp_path / "live"
    freeze_live(capture, out)
    monkeypatch.setenv("MODEL_API_KEY", "unit-test-not-real")
    calls = []

    def callback(request):
        body = json.loads(request.content)
        calls.append(body)
        assert "true_event" not in canonical(body) and "review_target" not in canonical(
            body
        )
        assert "viewer_series" not in canonical(
            body
        ) and "present_in_incident" not in canonical(body)
        assert body["instructions"].find("SCOPE REFINEMENT v2") >= 0
        return httpx.Response(
            200,
            json={
                "status": "completed",
                "error": None,
                "output": [
                    {
                        "type": "function_call",
                        "name": "submit_audit",
                        "call_id": "call1",
                        "arguments": canonical(submit()),
                    }
                ],
                "usage": {
                    "input_tokens": 10,
                    "output_tokens": 10,
                    "input_tokens_details": {"cached_tokens": 0},
                },
            },
        )

    def factory(**kw):
        return MetaResponsesClient(**kw, transport=httpx.MockTransport(callback))

    app = DemoApp(capture, out, client_factory=factory)
    old = (capture / "results.jsonl").read_bytes()
    row = app.live(TASKS[0], "a" * 32)
    assert (
        row["status"] == "completed"
        and row["output"]["contract_version"] == VERSION
        and row["new_sensor_queries"] == 0
    )
    assert app.live(TASKS[0], "a" * 32) == row and len(calls) == 1
    assert len((out / "reservations.jsonl").read_text().splitlines()) == 1
    assert (capture / "results.jsonl").read_bytes() == old
    with pytest.raises(ValueError):
        app.live(TASKS[1], "a" * 32)


def test_three_pages_and_tool_scope_are_explicit(server):
    _, url = server
    with httpx.Client(trust_env=False) as client:
        for path in ("/", "/demo", "/technology"):
            response = client.get(url + path)
            assert response.status_code == 200
            assert "Main navigation" in response.text
        status = client.get(url + "/api/status").json()
        assert status["capabilities"]["new_sensor_queries"] is False
        assert status["capabilities"]["well_topology_traversal"] is False
        assert status["capabilities"]["tools"] == [
            "lookup_knowledge",
            "search_history",
            "submit_audit",
        ]
        assert client.get(url + "/simulation").status_code == 404
        assert client.post(url + "/api/live/stream", json={}).status_code == 403


def test_public_projection_omits_rejected_text_and_preserves_real_facts():
    from petromind.investigation_events import received_event, tool_event

    s = ScopeAuditSession(packet())
    s.dispatch("lookup_knowledge", {"topic": "fault:9"})
    event = tool_event(asdict(s.audit_trail[-1]), "live")
    assert event["facts"] and all(f["provenance"] for f in event["facts"])
    assert event["topic"] == "fault:9"
    s.dispatch("submit_audit", {"secret-rejected-text": "do not export"})
    rejected = tool_event(asdict(s.audit_trail[-1]), "live")
    assert "do not export" not in canonical(rejected)
    assert rejected["validation"]["code"]
    assert received_event(s.packet, "live")["observations"] == packet()["observations"]


def test_live_stream_uses_real_mocked_events_before_completion_and_no_viewer_inputs(
    capture, tmp_path, monkeypatch
):
    from petromind.investigation_events import captured_events

    out = tmp_path / "live-stream"
    freeze_live(capture, out, max_cost=0.5)
    monkeypatch.setenv("MODEL_API_KEY", "unit-test-not-real")
    calls = []

    def callback(request):
        body = json.loads(request.content)
        assert "viewer_series" not in canonical(body) and "true_event" not in canonical(
            body
        )
        calls.append(body)
        name, args = (
            ("lookup_knowledge", {"topic": "fault:9"})
            if len(calls) == 1
            else ("submit_audit", submit())
        )
        return httpx.Response(
            200,
            json={
                "status": "completed",
                "error": None,
                "output": [
                    {
                        "type": "function_call",
                        "name": name,
                        "call_id": "call" + str(len(calls)),
                        "arguments": canonical(args),
                    }
                ],
                "usage": {
                    "input_tokens": 10,
                    "output_tokens": 10,
                    "input_tokens_details": {"cached_tokens": 0},
                },
            },
        )

    def factory(**kw):
        return MetaResponsesClient(**kw, transport=httpx.MockTransport(callback))

    app = DemoApp(capture, out, client_factory=factory)
    # A real runner invokes the observer synchronously while each tool completes.
    observed = []
    row = app.live(
        TASKS[0], "d" * 32, on_public_event=lambda e: observed.append((len(calls), e))
    )
    assert [e["kind"] for _, e in observed] == [
        "evidence_received",
        "tool_result",
        "tool_result",
    ]
    assert observed[1][0] == 1 and observed[2][0] == 2
    assert observed[1][1]["facts"] and observed[2][1]["assessment"] == row["output"]
    assert row["new_sensor_queries"] == 0 and len(calls) == 2
    assert captured_events(packet(), row)[-1]["status"] == "completed"
    # Streaming cached request is idempotent: it returns completion, no new calls.
    server = make_server(app, 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{server.server_port}"
    try:
        with httpx.Client(trust_env=False) as client:
            with client.stream(
                "POST",
                url + "/api/live/stream",
                headers={"Origin": url, "X-PetroMind-Token": app.token},
                json={"case_id": TASKS[0], "request_id": "d" * 32},
            ) as response:
                assert response.headers["content-type"].startswith(
                    "application/x-ndjson"
                )
                events = [json.loads(l) for l in response.iter_lines() if l]
            assert events[-1]["row"]["output"] == row["output"] and len(calls) == 2
            assert (
                client.get(url + "/api/status").json()["live_limits"]["estimated_usd"]
                == 0.5
            )
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
