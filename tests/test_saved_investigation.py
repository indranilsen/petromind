"""Synthetic saved-run software fixtures; never represented as actual Meta runs."""

import json
from copy import deepcopy
from pathlib import Path

import httpx
import pytest
from test_claim_demo import capture as capture_fixture
from test_claim_demo import finding, submit

from petromind.audit import canonical
from petromind.claim_demo import DemoApp, freeze_live
from petromind.meta_api import MetaResponsesClient
from petromind.saved_investigation import import_saved, load_saved, verify_saved


@pytest.fixture
def capture(tmp_path, monkeypatch):
    return capture_fixture.__wrapped__(tmp_path, monkeypatch)


@pytest.fixture
def saved(capture, tmp_path, monkeypatch):
    run = tmp_path / "synthetic-live"
    freeze_live(capture, run, max_cost=2)
    monkeypatch.setenv("MODEL_API_KEY", "mock-only")
    a = submit()
    f = finding("diagnostic_conclusion", "NOT_ESTABLISHED")
    f.update(
        statement="Constructed causal claim; not a real expert diagnosis.",
        missing_premise="No applicable discriminating criterion supplied.",
        next_evidence={
            "kind": "no_verified_discriminating_test",
            "target": "fault:9",
            "purpose": "No verified fault-discriminating test is supplied.",
        },
    )
    a["findings"].append(f)
    a["verdict"] = "PARTIALLY_SUPPORTED"
    actions = [
        ("lookup_knowledge", {"topic": "P-PDG"}),
        ("lookup_knowledge", {"topic": "P-TPT"}),
        ("search_history", {}),
        ("submit_audit", a),
    ]
    calls = []

    def response(request):
        name, args = actions[len(calls)]
        calls.append(name)
        return httpx.Response(
            200,
            json={
                "status": "completed",
                "error": None,
                "output": [
                    {
                        "type": "function_call",
                        "name": name,
                        "call_id": str(len(calls)),
                        "arguments": canonical(args),
                    }
                ],
                "usage": {"input_tokens": 10, "output_tokens": 10},
            },
        )

    def factory(**kw):
        return MetaResponsesClient(**kw, transport=httpx.MockTransport(response))

    app = DemoApp(capture, run, client_factory=factory)
    row = app.live("fault_expectation", "a" * 32)
    assert row["status"] == "completed" and len(calls) == 4
    return capture, run, row, tmp_path / "bundle"


def hashes(root):
    import hashlib

    return {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in root.iterdir()
        if p.is_file()
    }


def test_readonly_import_and_replay_do_not_call_model_or_expose_private_metadata(saved):
    capture, run, row, bundle = saved
    before = hashes(run)
    info = import_saved(capture, run, bundle)
    assert (
        info["api_requests"] == 0 and info["status"] == "saved_v5_verified_and_imported"
    )
    public = load_saved(capture, bundle)
    assert public["events"][-2]["assessment"] == row["output"]
    assert [e["tool"] for e in public["events"] if e["kind"] == "tool_request"] == [
        "lookup_knowledge",
        "lookup_knowledge",
        "search_history",
        "submit_audit",
    ]
    assert public["events"][-1]["status"] == "completed"
    text = canonical(public)
    for private in [
        str(run),
        "source_directory",
        "agent_config",
        "arguments_json",
        "training_event",
        "true_event",
        "prompt_digest",
    ]:
        assert private not in text
    assert hashes(run) == before
    app = DemoApp(capture, saved_directory=bundle)
    assert app.live_directory is None and "saved_investigation" in app.cases[0]
    assert "saved_investigation" not in app.cases[1]
    with pytest.raises(ValueError):
        import_saved(capture, run, bundle)


@pytest.mark.parametrize(
    "mutation",
    [
        lambda r: r.update(status="failed"),
        lambda r: r.update(case_id="unrelated_case"),
        lambda r: r.update(protocol_id="0" * 64),
        lambda r: r.update(remaining_budget=5),
        lambda r: r["audit"][0].update(digest="0" * 64),
        lambda r: r["output"]["findings"][0].update(
            citations=["measurement:UNQUERIED"]
        ),
        lambda r: r["output"].update(private_path="/private/secret"),
    ],
)
def test_mismatched_incomplete_or_modified_results_rejected(saved, mutation):
    capture, run, row, _ = saved
    mutation(row)
    (run / "results.jsonl").write_text(canonical(row) + "\n")
    with pytest.raises(ValueError):
        verify_saved(capture, run)


def test_source_changes_after_import_are_rejected(saved):
    capture, run, _, bundle = saved
    import_saved(capture, run, bundle)
    path = run / ("a" * 32 + ".jsonl")
    path.write_text(path.read_text() + "\n")
    with pytest.raises(ValueError):
        load_saved(capture, bundle)


def test_missing_request_events_are_disclosed_without_invention(saved):
    capture, run, _, _ = saved
    path = run / ("a" * 32 + ".jsonl")
    trace = [json.loads(l) for l in path.read_text().splitlines()]
    path.write_text(
        "".join(canonical(e) + "\n" for e in trace if e["kind"] != "tool_request")
    )
    public, _, _ = verify_saved(capture, run)
    assert "No request events were saved" in public["disclosure"]
    assert not any(e["kind"] == "tool_request" for e in public["events"])
    assert len([e for e in public["events"] if e["kind"] == "tool_result"]) == 4


def test_partial_request_trace_and_missing_final_result_are_rejected(saved):
    capture, run, _, _ = saved
    path = run / ("a" * 32 + ".jsonl")
    original = path.read_text()
    trace = [json.loads(l) for l in original.splitlines()]
    index = next(i for i, e in enumerate(trace) if e["kind"] == "tool_request")
    trace.pop(index)
    path.write_text("".join(canonical(e) + "\n" for e in trace))
    with pytest.raises(ValueError):
        verify_saved(capture, run)
    path.unlink()
    with pytest.raises(ValueError):
        verify_saved(capture, run)


def test_ambiguous_run_requires_request_selection(saved):
    capture, run, row, _ = saved
    path = run / "results.jsonl"
    other = deepcopy(row)
    other["request_id"] = "b" * 32
    path.write_text(canonical(row) + "\n" + canonical(other) + "\n")
    with pytest.raises(ValueError, match="Select exactly one"):
        verify_saved(capture, run)
    assert (
        verify_saved(capture, run, request_id="a" * 32)[0]["case_id"] == row["case_id"]
    )


def test_saved_bundle_tampering_and_symlinked_sources_rejected(saved):
    capture, run, _, bundle = saved
    import_saved(capture, run, bundle)
    (bundle / "replay.json").write_text("{}")
    with pytest.raises(ValueError):
        load_saved(capture, bundle)
    p = run / "protocol.json"
    real = run / "private-copy.json"
    p.rename(real)
    p.symlink_to(real)
    with pytest.raises(ValueError):
        verify_saved(capture, run)


def test_focused_graph_never_adds_edges_or_future_findings():
    import shutil
    import subprocess

    node = shutil.which("node")
    if not node:
        pytest.skip("Node needed for graph projection check")
    script = r"""
const assert=require('node:assert/strict'), p=require('./petromind/web/investigation.js');
const received={kind:'evidence_received',hypothesis:9,claim:'fixture',observations:{'P-PDG':{available:true},'P-TPT':{available:true}}};
const facts=Array.from({length:14},(_,i)=>({citation_id:'knowledge:'+i,subject:'sensor:'+i,relation:'measures',object:'quantity:'+i,scope:'documented generic',provenance:{locator:'fixture'}}));
const lookup={kind:'tool_result',tool:'lookup_knowledge',facts};
const assessment={kind:'tool_result',tool:'submit_audit',assessment:{findings:[{scope:'diagnostic_conclusion',verdict:'NOT_ESTABLISHED',statement:'fixture causal claim',citations:['measurement:P-PDG','measurement:P-TPT','knowledge:0'],missing_premise:'fixture gap'}]}};
const events=[received,lookup,assessment], full=p.graph(events), focus=p.focusedGraph(events,2);
assert(focus.nodes.length<=10);assert(focus.nodes.some(n=>n.id==='finding:0'));assert(focus.nodes.some(n=>n.id==='gap:0'));
for(const e of focus.edges)assert(full.edges.some(x=>JSON.stringify(x)===JSON.stringify(e)));
assert(!p.focusedGraph(events.slice(0,2),1).nodes.some(n=>n.kind==='finding'||n.kind==='gap'));
assert(full.nodes.length>focus.nodes.length);
const summary=p.takeaway({findings:[{scope:'measured_observation',verdict:'SUPPORTED'},{scope:'measured_observation',verdict:'NOT_ESTABLISHED'},{scope:'documented_comparison',verdict:'SUPPORTED'},{scope:'diagnostic_conclusion',verdict:'NOT_ESTABLISHED'}]});
assert.equal(summary.find(x=>x.kind==='measured').count,1);assert.equal(summary.find(x=>x.kind==='causal').count,1);
assert(!JSON.stringify(summary).includes('fault:9'));
"""
    subprocess.run(
        [node, "-e", script], cwd=Path(__file__).resolve().parents[1], check=True
    )


@pytest.mark.skipif(
    __import__("os").getenv("PETROMIND_BROWSER_CHECK") != "1",
    reason="Explicit local Chromium check; no paid API",
)
def test_saved_browser_progression_and_graph(saved, monkeypatch):
    import os
    import threading

    from playwright.sync_api import sync_playwright

    from petromind.claim_demo import make_server

    capture, run, _row, bundle = saved
    import_saved(capture, run, bundle)
    app = DemoApp(capture, saved_directory=bundle)
    server = make_server(app, 0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    screenshots = Path(
        os.getenv("PETROMIND_SCREENSHOTS", str(bundle.parent / "screenshots"))
    )
    screenshots.mkdir(parents=True, exist_ok=True)
    errors, paid = [], []
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                executable_path=os.getenv("PETROMIND_CHROMIUM"),
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage"],
            )
            for width, height, label in [(1440, 900, "desktop"), (390, 844, "mobile")]:
                page = browser.new_page(
                    viewport={"width": width, "height": height}, reduced_motion="reduce"
                )
                page.on("pageerror", lambda e: errors.append(str(e)))
                page.on(
                    "request",
                    lambda r: paid.append(r.url) if "/api/live" in r.url else None,
                )
                page.goto(
                    f"http://127.0.0.1:{server.server_port}/demo",
                    wait_until="networkidle",
                )
                page.evaluate(
                    """() => {const b=document.createElement('div');b.textContent='SYNTHETIC SOFTWARE FIXTURE · NO RECORDED META RUN';Object.assign(b.style,{position:'fixed',bottom:'0',left:'0',right:'0',padding:'8px',background:'#e3c58e',color:'#091923',zIndex:'100',textAlign:'center',fontSize:'12px'});document.body.append(b);} """
                )
                page.clock.install(time=0)
                page.clock.pause_at(1000)
                assert page.locator("#executionSelect").input_value() == "saved"
                assert page.locator("#slider").input_value() == "0"
                assert page.locator("#insideAssessment").inner_text() == ""
                page.locator("#slider").fill(
                    page.locator("#slider").get_attribute("max")
                )
                page.screenshot(path=str(screenshots / f"{label}-diagnosis.png"))
                page.locator("#nextScene").click()
                assert page.locator("#eventFeed li").count() == 1
                page.locator("#capturePause").click()
                page.clock.run_for(3000)
                assert page.locator("#eventFeed li").count() == 1
                page.locator("#capturePause").click()
                expected = app.cases[0]["saved_investigation"]["events"]
                for count in range(2, len(expected) + 1):
                    page.clock.run_for(1400)
                    assert page.locator("#eventFeed li").count() == count
                    assert page.locator(".evidence-node").count() <= 10
                    if not any(
                        e.get("kind") == "completion" and e.get("status") == "completed"
                        for e in expected[:count]
                    ):
                        assert page.locator("#insideAssessment").inner_text() == ""
                assert (
                    "not verified" in page.locator("#insideAssessment").text_content()
                )
                assert page.locator("#insideAssessment details").count() > 0
                page.locator("#insideAssessment [data-inspect-evidence]").click()
                if not page.locator("#graphPanel").evaluate("(e)=>e.open"):
                    page.locator("#graphPanel>summary").click()
                page.locator("#graphToggle").click()
                assert page.locator(".evidence-node").count() > 10
                page.locator(".evidence-node.type-fact").first.click()
                assert page.locator("#nodeDialog").is_visible()
                page.locator("#closeNode").click()
                page.locator("#graphPanel").evaluate(
                    '(e)=>window.scrollTo({top:scrollY+e.getBoundingClientRect().top-160,behavior:"instant"})'
                )
                page.screenshot(path=str(screenshots / f"{label}-full-graph.png"))
                page.locator("#insideAssessment .full-receipt > summary").click()
                page.locator('#insideAssessment [data-finding-index="1"]').click()
                assert page.locator(".evidence-node").count() <= 10
                page.locator("#insideAssessment").evaluate(
                    '(e)=>window.scrollTo({top:scrollY+e.getBoundingClientRect().top-200,behavior:"instant"})'
                )
                page.screenshot(path=str(screenshots / f"{label}-assessment.png"))
                page.locator("#graphPanel").evaluate(
                    '(e)=>window.scrollTo({top:scrollY+e.getBoundingClientRect().top-160,behavior:"instant"})'
                )
                page.screenshot(path=str(screenshots / f"{label}-focused-graph.png"))
                page.locator("#operatorView").click()
                page.locator("#handoffDetails > summary").click()
                page.locator("#inspectDetails").click()
                assert (
                    "Verified saved v5 public output"
                    in page.locator("#raw").text_content()
                )
                assert (
                    "Constructed causal claim"
                    in page.locator("#detailFindings").text_content()
                )
                assert page.locator("#ungrounded").is_disabled()
                page.locator("#closeDetails").click()
                page.locator("#insideView").click()
                page.locator("#captureRestart").click()
                assert page.locator("#eventFeed li").count() == 1
                assert page.locator("#insideAssessment").inner_text() == ""
                page.locator("#captureSkip").click()
                assert (
                    "PARTIALLY SUPPORTED"
                    in page.locator("#insideAssessment").text_content()
                )
                page.locator("#operatorView").click()
                page.locator("#executionSelect").select_option("captured")
                page.locator("#nextScene").click()
                page.locator("#captureSkip").click()
                assert (
                    "ORIGINAL CAPTURED"
                    in page.locator("#insideAssessment").text_content()
                )
                page.locator("#caseSelect").select_option("1")
                assert not errors, errors
                assert page.locator("#savedExecution").evaluate("e=>e.disabled")
                assert page.locator("#slider").input_value() == "0"
                assert page.evaluate(
                    "()=>document.documentElement.scrollWidth<=innerWidth"
                )
                page.close()
            browser.close()
    finally:
        server.shutdown()
        server.server_close()
    assert not errors, errors
    assert not paid, paid


def test_optional_public_stream_verified_and_hashed(saved):
    from dataclasses import asdict

    from test_claim_demo import packet

    from petromind.audit import AuditEntry
    from petromind.investigation_events import received_event, tool_event

    capture, run, row, _ = saved
    trace = [
        json.loads(l)
        for l in (run / (row["request_id"] + ".jsonl")).read_text().splitlines()
    ]
    requests = [e["details"] for e in trace if e["kind"] == "tool_request"]
    events = [received_event(packet(), "live")]
    for i, e in enumerate(row["audit"]):
        events += [requests[i], tool_event(asdict(AuditEntry(**e)), "live")]
    events += [{"kind": "completion", "status": "completed", "row": row}]
    path = run / (row["request_id"] + ".public.jsonl")
    path.write_text(
        "".join(
            canonical({"elapsed_seconds": i, "event": e}) + "\n"
            for i, e in enumerate(events)
        )
    )
    _, hashes, _ = verify_saved(capture, run)
    assert path.name in hashes
    events[0]["observations"]["P-TPT"]["delta"] = 999
    path.write_text("".join(canonical({"event": e}) + "\n" for e in events))
    with pytest.raises(ValueError, match="input packet mismatch"):
        verify_saved(capture, run)


@pytest.mark.parametrize("content", ["[]", "null", "{}", '{"protocol_id":"invalid"}'])
def test_invalid_protocol_has_safe_failure(saved, content):
    capture, run, _, _ = saved
    (run / "protocol.json").write_text(content)
    with pytest.raises(ValueError):
        verify_saved(capture, run)


def test_active_run_binds_original_window_and_missing_sensor_query(
    capture, tmp_path, monkeypatch
):
    import numpy as np
    import pandas as pd

    import petromind.claim_review as review
    from petromind.eval_protocol import digest
    from petromind.measurements import summarize

    frame = pd.DataFrame(
        {s: np.linspace(1, 3, 600) for s in ["ABER-CKGL", "P-PDG", "P-TPT"]},
        index=pd.date_range("2020", periods=600, freq="s"),
    )
    frame["QGL"] = None
    parent = json.loads((capture / "protocol.json").read_text())
    rows = [json.loads(l) for l in (capture / "results.jsonl").read_text().splitlines()]
    for task in parent["tasks"]:
        task["packet"]["observations"] = {
            s: summarize(frame[s]).to_dict() for s in ["ABER-CKGL", "P-PDG", "P-TPT"]
        }
    parent.pop("protocol_id")
    parent["protocol_id"] = digest(parent)
    for r in rows:
        r["protocol_id"] = parent["protocol_id"]
    (capture / "protocol.json").write_text(canonical(parent))
    (capture / "results.jsonl").write_text("".join(canonical(r) + "\n" for r in rows))
    monkeypatch.setattr(review, "CAPTURE_PROTOCOL", parent["protocol_id"])
    monkeypatch.setattr(review, "CAPTURE_ROWS_DIGEST", digest(rows))
    monkeypatch.setattr(
        "petromind.claim_demo.active_windows",
        lambda *a: (
            {t["task_id"]: frame for t in parent["tasks"]},
            "synthetic-window-digest",
        ),
    )
    run = tmp_path / "synthetic-active"
    freeze_live(capture, run, max_cost=2, active_sensors=True)
    actions = [
        ("lookup_knowledge", {"topic": "QGL"}),
        (
            "request_sensor",
            {
                "sensor_name": "QGL",
                "source_id": "knowledge:location:QGL",
                "purpose": "Check this measurement; not a verified fault discriminator.",
            },
        ),
        ("submit_audit", submit()),
    ]
    calls = []

    def response(request):
        name, a = actions[len(calls)]
        calls.append(name)
        return httpx.Response(
            200,
            json={
                "status": "completed",
                "error": None,
                "output": [
                    {
                        "type": "function_call",
                        "name": name,
                        "call_id": str(len(calls)),
                        "arguments": canonical(a),
                    }
                ],
                "usage": {"input_tokens": 10, "output_tokens": 10},
            },
        )

    monkeypatch.setenv("MODEL_API_KEY", "mock-only")
    app = DemoApp(
        capture,
        run,
        client_factory=lambda **kw: MetaResponsesClient(
            **kw, transport=httpx.MockTransport(response)
        ),
    )
    row = app.live("fault_expectation", "c" * 32)
    assert (
        row["status"] == "completed"
        and row["new_sensor_queries"] == 1
        and row["remaining_budget"] == 1
    )
    public, _, _ = verify_saved(capture, run)
    query = next(e for e in public["events"] if e.get("sensor") == "QGL")
    assert query["summary"]["available"] is False
    monkeypatch.setattr(
        "petromind.claim_demo.active_windows", lambda *a: ({}, "wrong-window")
    )
    with pytest.raises(ValueError, match="window mismatch"):
        verify_saved(capture, run)


def test_rehashed_private_fact_and_unpermitted_history_still_rejected(saved):
    from dataclasses import asdict

    from petromind.audit import AuditEntry

    capture, run, row, _ = saved
    original = deepcopy(row)
    trace_path = run / (row["request_id"] + ".jsonl")
    original_trace = [json.loads(l) for l in trace_path.read_text().splitlines()]
    for kind in ["fact", "history"]:
        row = deepcopy(original)
        trace = deepcopy(original_trace)
        chain = []
        for e in row["audit"]:
            result = json.loads(e["result_json"])
            if kind == "fact" and e["sequence"] == 1:
                result["facts"][0]["provenance"]["url"] = "/private/well/path"
            if kind == "history" and e["tool"] == "search_history":
                result["matches"] = [{"case_id": "unpermitted", "training_event": 9}]
            chain.append(
                AuditEntry.create(
                    e["sequence"],
                    e["tool"],
                    json.loads(e["arguments_json"]),
                    result,
                    chain[-1].digest if chain else "0" * 64,
                )
            )
        row["audit"] = [asdict(e) for e in chain]
        for e in trace:
            if e["kind"] == "tool_result":
                a = chain[e["details"]["audit_sequence"] - 1]
                e["details"]["audit_digest"] = a.digest
                e["details"]["result"] = json.loads(a.result_json)
        (run / "results.jsonl").write_text(canonical(row) + "\n")
        trace_path.write_text("".join(canonical(e) + "\n" for e in trace))
        with pytest.raises(ValueError):
            verify_saved(capture, run)


def test_cli_import_and_check_are_offline(saved, monkeypatch, capsys):
    import runpy
    import sys

    capture, run, _, bundle = saved
    args = [
        "--capture",
        str(capture),
        "--dataset",
        str(bundle.parent / "absent-data"),
        "--science-protocol",
        str(bundle.parent / "absent-science"),
    ]
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "demo_claim_audit.py",
            "import-saved",
            *args,
            "--run",
            str(run),
            "--out",
            str(bundle),
        ],
    )
    with pytest.raises(SystemExit) as end:
        runpy.run_path("scripts/demo_claim_audit.py", run_name="__main__")
    assert (
        end.value.code == 0 and json.loads(capsys.readouterr().out)["api_requests"] == 0
    )
    monkeypatch.setattr(
        "petromind.claim_demo.make_server",
        lambda *a: (_ for _ in ()).throw(AssertionError("Check must not bind server")),
    )
    monkeypatch.setattr(
        sys, "argv", ["demo_claim_audit.py", "check", *args, "--saved-run", str(bundle)]
    )
    with pytest.raises(SystemExit) as end:
        runpy.run_path("scripts/demo_claim_audit.py", run_name="__main__")
    report = json.loads(capsys.readouterr().out)
    assert (
        end.value.code == 0
        and report["saved_replays"] == 1
        and report["api_requests"] == 0
        and report["live_configured"] is False
    )


def test_import_never_writes_inside_original_run(saved):
    capture, run, _, _ = saved
    before = hashes(run)
    with pytest.raises(ValueError, match="outside the original"):
        import_saved(capture, run, run / "derived")
    assert hashes(run) == before and not (run / "derived").exists()
