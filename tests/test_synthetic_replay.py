"""Isolated replay compatibility/security checks. No benchmark re-execution."""

import hashlib
import json
import os
import shutil
import threading
from copy import deepcopy
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import urlopen

import pytest
from test_claim_demo import capture as capture_fixture

from petromind import synthetic_replay as adapter
from petromind.claim_demo import DemoApp, make_server


def canonical(v):
    return json.dumps(
        v, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()


@pytest.fixture
def capture(tmp_path, monkeypatch):
    return capture_fixture.__wrapped__(tmp_path, monkeypatch)


@pytest.fixture
def showcase(tmp_path, monkeypatch):
    """Explicitly artificial software fixture; not a captured Muse investigation."""
    root = tmp_path / "synthetic"
    root.mkdir()
    sensors = ["P-TPT", "P-MON-CKP", "T-TPT", "SYN-Q-PROD", "SYN-P-SEP"]

    def measurement(sensor):
        return {
            "id": "measurement:" + sensor,
            "sensor": sensor,
            "unit": "Pa",
            "absolute_error_bound": 1,
            "samples": [
                {"t_s": 0, "value": 1, "quality": "GOOD"},
                {"t_s": 2400, "value": 3, "quality": "GOOD"},
            ],
        }

    finding = {
        "statement": "Software fixture only",
        "premises": [],
        "scope": "diagnostic_conclusion",
        "verdict": "NOT_ESTABLISHED",
        "citations": ["model:M1"],
        "justification": "Software fixture",
        "missing_premise": "Material evidence absent",
        "next_evidence": {"target": "assay", "purpose": "identify material"},
    }
    findings = [deepcopy(finding) for _ in range(3)]
    findings[2]["premises"] = [
        "Pressures plus flow show increased effective R_L with stable separator"
    ]
    assessment = {
        "verdict": "PARTIALLY_SUPPORTED",
        "findings": findings,
        "numeric_observations": [],
    }
    packet = {
        "case_id": "c-7a91",
        "synthetic": True,
        "claim": "Constructed software fixture",
        "initial_measurements": {s: measurement(s) for s in sensors[:3]},
        "model": {
            "id": "model:M1",
            "identifiability": "Software fixture",
            "assumptions": [],
        },
    }
    raw = [
        ("initial_packet", {}, packet),
        ("query_sensor", {"sensor": sensors[3]}, measurement(sensors[3])),
        ("query_sensor", {"sensor": sensors[4]}, measurement(sensors[4])),
        (
            "lookup_graph",
            {"node": "candidate:hydrate", "hops": 1},
            {"edges": [], "truncated": False},
        ),
        (
            "read_document",
            {"id": "doc:limits"},
            {"id": "doc:limits", "summary": "Software limits"},
        ),
        (
            "read_document",
            {"id": "doc:phase"},
            {"id": "doc:phase", "summary": "Software phase"},
        ),
        ("submit_audit", assessment, {"accepted": True, "assessment": assessment}),
    ]
    audit, previous = [], "0" * 64
    for i, (tool, args, result) in enumerate(raw):
        e = {
            "sequence": i,
            "tool": tool,
            "arguments": args,
            "result": result,
            "previous": previous,
        }
        e["digest"] = hashlib.sha256(canonical(e)).hexdigest()
        previous = e["digest"]
        audit.append(e)
    events = [
        {
            **{k: e[k] for k in ("sequence", "tool", "arguments", "result")},
            "model_requested_arguments": {"node": "candidate:hydrate"}
            if e["tool"] == "lookup_graph"
            else e["arguments"],
        }
        for e in audit[1:]
    ]
    contents = {name: b"Software fixture only" for name in adapter.FILES}
    contents.update(
        {
            "original-host-audit.UNCHANGED.json": canonical(audit),
            "captured-investigation.json": canonical(
                {
                    "initial_packet": packet,
                    "events": events,
                    "final_assessment": assessment,
                }
            ),
            "verification.json": canonical(
                {
                    "case_id": "c-7a91",
                    "recorded_requests": 6,
                    "sensor_budget": 5,
                    "recorded_latency_seconds": 0,
                    "recorded_estimated_cost_usd": 0,
                }
            ),
        }
    )
    for name, value in contents.items():
        (root / name).write_bytes(value)
    manifest = canonical(
        {name: hashlib.sha256(v).hexdigest() for name, v in contents.items()}
    )
    (root / "MANIFEST.json").write_bytes(manifest)
    monkeypatch.setattr(
        adapter, "MANIFEST_SHA256", hashlib.sha256(manifest).hexdigest()
    )
    monkeypatch.setattr(
        adapter,
        "HOST_SHA256",
        hashlib.sha256(contents["original-host-audit.UNCHANGED.json"]).hexdigest(),
    )
    return root


def test_record_order_accounting_and_unchanged_final(showcase):
    before = {p.name: p.read_bytes() for p in showcase.iterdir()}
    public = adapter.load_synthetic(showcase)
    assert public["version"] == "synthetic-hydraulic-replay-v1"
    assert len(public["events"]) == 14 and public["sensor_budget"] == 5
    requests = [e for e in public["events"] if e["kind"] == "tool_request"]
    assert [e["tool"] for e in requests] == [
        "query_sensor",
        "query_sensor",
        "lookup_graph",
        "read_document",
        "read_document",
        "submit_audit",
    ]
    assert requests[2]["arguments"] == {"node": "candidate:hydrate"}
    assert [
        e["remaining_budget"] for e in public["events"] if "remaining_budget" in e
    ] == [1, 0]
    assert all(e["recorded_timestamp"] is None for e in public["events"])
    assert "classifier" not in public and "reference" not in public
    assert public["events"][-2]["assessment"] == public["assessment"]
    assert before == {p.name: p.read_bytes() for p in showcase.iterdir()}


@pytest.mark.parametrize(
    "name",
    [
        "original-host-audit.UNCHANGED.json",
        "captured-investigation.json",
        "verification.json",
        "MANIFEST.json",
    ],
)
def test_modified_artifacts_fail_closed(showcase, name):
    (showcase / name).write_bytes((showcase / name).read_bytes() + b" ")
    with pytest.raises(ValueError):
        adapter.load_synthetic(showcase)


def test_symlinks_are_rejected(showcase, tmp_path):
    source = showcase / "STORY.md"
    target = tmp_path / "outside"
    shutil.move(source, target)
    source.symlink_to(target)
    with pytest.raises(ValueError):
        adapter.load_synthetic(showcase)


def test_json_duplicates_and_nonfinite_rejected():
    for value in ['{"x":1,"x":2}', '{"x":NaN}']:
        with pytest.raises(ValueError):
            adapter._json(value)


def test_quality_preserves_zero_constant_missing_and_invalid():
    m = {
        "samples": [
            {"value": 0, "quality": "GOOD"},
            {"value": 0, "quality": "GOOD"},
            {"value": None, "quality": "MISSING"},
            {"value": 100, "quality": "CALIBRATION_UNVERIFIED"},
        ]
    }
    s = adapter._summary(m)
    assert s["available"] and s["count"] == 2 and s["delta"] == 0 and s["total"] == 4
    assert m["samples"][-1]["value"] == 100


def test_optional_endpoint_never_alters_historical_cases(capture, showcase):
    original = DemoApp(capture)
    app = DemoApp(capture, synthetic_directory=showcase)
    assert canonical(original.cases) == canonical(app.cases)
    for instance, code in [(original, 404), (app, 200)]:
        server = make_server(instance, 0)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            url = f"http://127.0.0.1:{server.server_port}"
            with urlopen(url + "/api/status") as response:
                status = json.load(response)
            assert status["synthetic_replay_enabled"] == (code == 200)
            if code == 200:
                with urlopen(url + "/api/synthetic") as response:
                    assert json.load(response)["version"] == adapter.VERSION
            else:
                with pytest.raises(HTTPError) as e:
                    urlopen(url + "/api/synthetic")
                assert e.value.code == 404
                e.value.close()
        finally:
            server.shutdown()
            server.server_close()


@pytest.mark.skipif(
    not os.getenv("PETROMIND_SYNTHETIC_SHOWCASE"),
    reason="Owner-supplied exact showcase required",
)
def test_original_verified_recording():
    public = adapter.load_synthetic(os.environ["PETROMIND_SYNTHETIC_SHOWCASE"])
    assert public["id"] == "c-7a91" and public["recording"]["requests"] == 6
    assert len(public["assessment"]["findings"]) == 3
    original = json.loads(
        (
            Path(os.environ["PETROMIND_SYNTHETIC_SHOWCASE"])
            / "original-host-audit.UNCHANGED.json"
        ).read_text()
    )[-1]["result"]["assessment"]
    assert public["assessment"] == original
    assert public["assessment"]["verdict"] == "PARTIALLY_SUPPORTED"
    assert public["assessment"]["findings"][2]["verdict"] == "NOT_ESTABLISHED"
    assert public["editorial_conclusion"].startswith(
        "Hydraulic evidence supports increased effective resistance"
    )
    assert "upgraded atomic Muse verdict" in public["conclusion_basis"]


@pytest.mark.skipif(
    os.getenv("PETROMIND_BROWSER_CHECK") != "1", reason="Opt-in Chromium journey"
)
def test_browser_synthetic_and_historical_switching(capture, showcase, tmp_path):
    from playwright.sync_api import sync_playwright

    path = os.environ.get("PETROMIND_SYNTHETIC_SHOWCASE") or showcase
    # Real supplied package uses production commitments, not fixture commitments.
    if os.getenv("PETROMIND_SYNTHETIC_SHOWCASE"):
        adapter.MANIFEST_SHA256 = (
            "8e0eba8f09efc4b14fb1ea9e4b2be29b0c394d1aba50f44a006bd4c1b71203b3"
        )
        adapter.HOST_SHA256 = (
            "acc1a8e0ec3ddffda69ebd9f992426fb500d2ba12799a7ff6c56b0b328447f4d"
        )
    app = DemoApp(capture, synthetic_directory=path)
    server = make_server(app, 0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    errors, paid = [], []
    shots = Path(os.environ.get("PETROMIND_SCREENSHOTS", str(tmp_path / "shots")))
    shots.mkdir(parents=True, exist_ok=True)
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                executable_path=os.getenv("PETROMIND_CHROMIUM"),
                args=["--no-sandbox", "--disable-dev-shm-usage"],
            )
            for width, height, label in [
                (1440, 900, "desktop"),
                (1024, 768, "tablet"),
                (390, 844, "mobile"),
            ]:
                page = browser.new_page(
                    viewport={"width": width, "height": height}, reduced_motion="reduce"
                )
                page.on("pageerror", lambda e: errors.append(str(e)))
                page.on(
                    "request",
                    lambda r: (
                        paid.append(r.url)
                        if "/api/live" in r.url or "api.meta.ai" in r.url
                        else None
                    ),
                )
                page.goto(
                    f"http://127.0.0.1:{server.server_port}/demo",
                    wait_until="networkidle",
                )
                assert page.locator("#historicalWorkspace").is_visible()
                historical = page.locator("#caseSelect").input_value()
                page.locator("#scenarioSelect").select_option("synthetic")
                page.get_by_role("button", name="Watch Muse investigate").wait_for()
                assert not page.locator("#historicalWorkspace").is_visible()
                assert not page.locator("#classifierHandoff").is_visible()
                page.screenshot(
                    path=str(shots / f"synthetic-{label}-intro.png"), full_page=True
                )
                # Virtual clock advances ordinary UI pacing; does not alter events.
                page.clock.install()
                page.get_by_role("button", name="Watch Muse investigate").click()
                assert page.locator(".synthetic-sensors button").count() == 3
                page.get_by_role("button", name="Pause investigation replay").click()
                initial_counter = page.locator(".synthetic-controls span").inner_text()
                page.clock.run_for(10000)
                assert (
                    page.locator(".synthetic-controls span").inner_text()
                    == initial_counter
                )
                page.locator("#scenarioSelect").select_option("historical")
                assert page.locator("#historicalWorkspace").is_visible()
                page.locator("#scenarioSelect").select_option("synthetic")
                page.get_by_role("button", name="Resume investigation replay").click()
                page.clock.run_for(1800)  # Requested flow is not returned yet.
                assert page.locator(".synthetic-sensors button").count() == 3
                assert (
                    "production flow"
                    in page.locator("#syntheticCurrentActivity").inner_text()
                )
                page.clock.run_for(1800)
                assert page.locator(".synthetic-sensors button").count() == 4
                page.clock.run_for(1800)  # Separator request alone adds no measurement.
                assert page.locator(".synthetic-sensors button").count() == 4
                page.clock.run_for(1800)
                assert page.locator(".synthetic-sensors button").count() == 5
                assert (
                    page.locator('.synthetic-evidence-nodes [data-kind="fact"]').count()
                    == 0
                )
                page.clock.run_for(1800)  # Graph requested, not returned.
                assert (
                    page.locator('.synthetic-evidence-nodes [data-kind="fact"]').count()
                    == 0
                )
                page.clock.run_for(1800)
                expected_facts = sum(
                    len(e.get("facts", [])) for e in app.synthetic["events"]
                )
                assert (
                    page.locator('.synthetic-evidence-nodes [data-kind="fact"]').count()
                    == expected_facts
                )
                page.clock.run_for(40000)
                page.locator("#syntheticFinal").wait_for()
                assert page.locator(".synthetic-sensors button").count() == 5
                assert (
                    page.locator(".synthetic-conversation")
                    .locator('.synthetic-event[data-kind="tool_request"]')
                    .count()
                    == 6
                )
                assert page.locator(".synthetic-conversation").locator(
                    '.synthetic-event[data-kind="tool_request"]'
                ).evaluate_all("els => els.map(e => e.dataset.tool)") == [
                    "query_sensor",
                    "query_sensor",
                    "lookup_graph",
                    "read_document",
                    "read_document",
                    "submit_audit",
                ]
                expected_sources = {
                    d["id"]
                    for e in app.synthetic["events"]
                    for d in e.get("documents", [])
                }
                expected_sources.update(
                    f["id"] for e in app.synthetic["events"] for f in e.get("facts", [])
                )
                for source_id in expected_sources:
                    assert (
                        page.locator(
                            f'.synthetic-evidence-nodes button[data-evidence-id="{source_id}"]'
                        ).count()
                        == 1
                    )

                assert (
                    "The specific cause remains unidentified"
                    in page.locator("#syntheticFinal").inner_text()
                )
                assert (
                    page.locator(
                        '.synthetic-evidence-nodes button[data-evidence-id="model:M1"]'
                    ).count()
                    == 1
                )
                assert page.locator("#syntheticFinal h2").inner_text() == (
                    "Hydraulic evidence supports increased effective resistance under synthetic model M1. "
                    "The specific cause remains unidentified."
                )
                assert page.locator("#syntheticFinal > h3").all_text_contents() == [
                    "What the hydraulic evidence supports",
                    "What Muse did not establish",
                    "What evidence would help next",
                ]
                page.get_by_text(
                    "Accepted Muse premise · exact wording", exact=True
                ).click()
                assert (
                    app.synthetic["assessment"]["findings"][2]["premises"][0]
                    in page.locator("#syntheticFinal blockquote").inner_text()
                )
                page.get_by_text(
                    "Accepted Muse premise · exact wording", exact=True
                ).click()
                page.get_by_text("Exact scientific assessment", exact=True).click()
                assert (
                    json.loads(
                        page.locator("#syntheticOriginalAssessment").inner_text()
                    )
                    == app.synthetic["assessment"]
                )
                assert (
                    "PARTIALLY_SUPPORTED"
                    in page.locator("#syntheticScientificAssessment").inner_text()
                )
                page.get_by_text("Exact scientific assessment", exact=True).click()

                page.locator(
                    '.synthetic-evidence-nodes button[data-evidence-id="model:M1"]'
                ).click()
                assert (
                    "model:M1"
                    in page.locator("#syntheticSelectedEvidence").inner_text()
                )
                assert page.evaluate(
                    "document.documentElement.scrollWidth <= window.innerWidth"
                )
                page.locator("#syntheticFinal").evaluate(
                    "e => e.scrollIntoView({block: 'start'})"
                )
                page.screenshot(
                    path=str(shots / f"synthetic-{label}-final.png"), full_page=True
                )
                page.screenshot(
                    path=str(shots / f"synthetic-{label}-final-viewport.png")
                )
                page.get_by_role(
                    "button", name="Restart synthetic investigation"
                ).click()
                assert page.locator("#syntheticFinal").count() == 0
                assert page.locator(".synthetic-sensors button").count() == 3
                page.locator("#scenarioSelect").select_option("historical")
                assert page.locator("#historicalWorkspace").is_visible()
                assert page.locator("#caseSelect").input_value() == historical
                page.locator("#scenarioSelect").select_option("synthetic")
                assert page.locator("#syntheticContent").is_visible()
                page.close()
            browser.close()
        assert errors == [] and paid == []
    finally:
        server.shutdown()
        server.server_close()
