#!/usr/bin/env python3
"""Exercise three-page PetroMind, captured events and optional mocked live streaming."""

import argparse
import json
from pathlib import Path
from urllib.parse import urlparse


def mock_live_browser(browser, capture, *, fail=False):
    """Real server/runner/client path, HTTP mocked. No screenshots or paid calls."""
    import os
    import tempfile
    import threading

    import httpx

    from petromind.audit import canonical
    from petromind.claim_demo import DemoApp, freeze_live, make_server
    from petromind.meta_api import MetaResponsesClient

    gate = threading.Event()
    calls = []
    args = {
        "verdict": "SUPPORTED",
        "findings": [
            {
                "statement": "Software-test measurement assertion.",
                "premises": ["The received summary has this exact delta."],
                "basis": "measurement",
                "verdict": "SUPPORTED",
                "citations": ["measurement:P-TPT"],
                "missing_premise": "",
                "next_evidence": {"kind": "none", "target": "", "purpose": ""},
                "justification": "Numeric transport test only, not physical validation.",
                "scope": "measured_observation",
            }
        ],
        "numeric_observations": [],
    }

    def callback(request):
        body = json.loads(request.content)
        assert "viewer_series" not in canonical(body) and "true_event" not in canonical(
            body
        )
        calls.append(body)
        if len(calls) == 1:
            name, payload = "lookup_knowledge", {"topic": "fault:9"}
        else:
            if not gate.wait(20):
                raise AssertionError("Browser did not release streaming test gate")
            if fail:
                return httpx.Response(
                    200,
                    json={
                        "status": "incomplete",
                        "error": None,
                        "output": [],
                        "incomplete_details": {"reason": "max_output_tokens"},
                        "usage": {"input_tokens": 10, "output_tokens": 10},
                    },
                )
            name, payload = "submit_audit", args
        return httpx.Response(
            200,
            json={
                "status": "completed",
                "error": None,
                "output": [
                    {
                        "type": "function_call",
                        "name": name,
                        "call_id": "mock" + str(len(calls)),
                        "arguments": canonical(payload),
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

    old = os.environ.get("MODEL_API_KEY")
    os.environ["MODEL_API_KEY"] = "software-test-only"
    with tempfile.TemporaryDirectory(prefix="petromind-mock-") as temp:
        live = Path(temp) / "live"
        freeze_live(capture, live, max_cost=0.5)
        app = DemoApp(capture, live, client_factory=factory)
        server = make_server(app, 0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        try:
            page.goto(
                f"http://127.0.0.1:{server.server_port}/demo", wait_until="networkidle"
            )
            page.locator(".sensor-hit").nth(11).wait_for()
            page.locator("#caseSelect").select_option("1")
            page.locator("#executionSelect").select_option("live")
            page.locator("#nextScene").click()
            page.locator("#nextScene").click()
            page.get_by_text(
                "Muse retrieves source-backed graph facts", exact=True
            ).wait_for()
            # The real tool response is visible while the next request is blocked.
            assert (
                "NEW LIVE ASSESSMENT"
                not in page.locator("#operatorResult").inner_text()
            )
            page.locator(".site-nav a").first.click()
            page.locator(".home-hero .primary").click()
            assert page.locator("#caseSelect").input_value() == "1"
            page.locator("#insideView").click()
            assert page.locator(".evidence-node.layer-2").count() > 0
            assert page.locator("#caseSelect").is_disabled()
            gate.set()
            page.locator("#operatorView").click()
            if fail:
                page.get_by_text(
                    "Investigation stopped · no completed audit", exact=True
                ).wait_for()
                assert "response limit" in page.locator("#operatorResult").inner_text()
                assert (
                    "NEW LIVE ASSESSMENT"
                    not in page.locator("#operatorResult").inner_text()
                )
            else:
                page.get_by_text("NEW LIVE ASSESSMENT", exact=True).wait_for()
                assert (
                    "Software-test measurement assertion."
                    in page.locator("#operatorResult").inner_text()
                )
            assert len(calls) == 2
        finally:
            gate.set()
            page.close()
            server.shutdown()
            server.server_close()
            thread.join()
            if old is None:
                os.environ.pop("MODEL_API_KEY", None)
            else:
                os.environ["MODEL_API_KEY"] = old
    return len(calls)


def mock_active_browser(browser, capture):
    """Constructed telemetry + mocked Meta; real active session/HTTP/UI path.

    No screenshots: this fixture must never be presented as a real 3W run.
    """
    import os
    import tempfile
    import threading
    from copy import deepcopy
    from unittest.mock import patch

    import httpx
    import numpy as np
    import pandas as pd

    from petromind.audit import canonical
    from petromind.claim_demo import DemoApp, freeze_live, make_server
    from petromind.claim_review import demo_cases
    from petromind.incident_replay import raw_payload
    from petromind.measurements import summarize
    from petromind.meta_api import MetaResponsesClient

    cases = demo_cases(capture)
    window = pd.DataFrame(
        {s: np.linspace(1, 3, 600) for s in ["P-PDG", "P-TPT", "ABER-CKGL"]},
        index=pd.date_range("2020", periods=600, freq="s"),
    )
    window["T-TPT"] = 55.0
    for c in cases:
        c["observations"] = json.loads(
            canonical(
                {
                    s: summarize(window[s]).to_dict()
                    for s in ["P-PDG", "P-TPT", "ABER-CKGL"]
                }
            )
        )
        c["packet"]["observations"] = deepcopy(c["observations"])
    calls, gate = [], threading.Event()
    assessment = {
        "verdict": "SUPPORTED",
        "findings": [
            {
                "statement": "Software fixture: temperature summary is constant.",
                "premises": ["The queried summary has median 55."],
                "basis": "measurement",
                "verdict": "SUPPORTED",
                "citations": ["measurement:T-TPT"],
                "missing_premise": "",
                "next_evidence": {"kind": "none", "target": "", "purpose": ""},
                "justification": "Software test only; no physical inference.",
                "scope": "measured_observation",
            }
        ],
        "numeric_observations": [
            {"sensor": "T-TPT", "metric": "median", "value": 55.0}
        ],
    }
    actions = [
        ("lookup_knowledge", {"topic": "T-TPT"}),
        (
            "request_sensor",
            {
                "sensor_name": "T-TPT",
                "source_id": "knowledge:location:T-TPT",
                "purpose": "Inspect documented tree temperature.",
            },
        ),
        ("submit_audit", assessment),
    ]

    def callback(request):
        body = json.loads(request.content)
        assert "viewer_series" not in canonical(body) and "true_event" not in canonical(
            body
        )
        if len(calls) < 2:
            # Temperature itself remains unavailable until its query returns.
            assert "measurement:T-TPT" not in canonical(body["input"][0])
        name, args = actions[len(calls)]
        calls.append(body)
        if len(calls) == 3:
            assert gate.wait(20)
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
        return MetaResponsesClient(**kw, transport=httpx.MockTransport(callback))

    with (
        tempfile.TemporaryDirectory(prefix="petromind-active-mock-") as directory,
        patch.dict(os.environ, {"MODEL_API_KEY": "software-test-only"}),
        patch("petromind.claim_demo.demo_cases", side_effect=lambda _: deepcopy(cases)),
        patch(
            "petromind.claim_demo.active_windows",
            return_value=({c["id"]: window for c in cases}, "constructed-fixture"),
        ),
    ):
        out = Path(directory) / "live"
        freeze_live(capture, out, max_cost=0.5, active_sensors=True)
        app = DemoApp(capture, out, client_factory=factory)
        for c in app.cases:
            c["replay"] = raw_payload(window, c)
        server = make_server(app, 0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        try:
            page.goto(
                f"http://127.0.0.1:{server.server_port}/demo", wait_until="networkidle"
            )
            page.locator("#executionSelect").select_option("live")
            page.locator("#nextScene").click()
            page.locator("#nextScene").click()
            page.get_by_text(
                "Muse requests a documented sensor summary", exact=True
            ).wait_for()
            assert (
                "Muse requested summary"
                in page.locator('[data-sensor="T-TPT"]').inner_text()
            )
            assert "1 queries left" in page.locator("#eventFeed").inner_text()
            page.locator("#insideView").click()
            assert (
                page.get_by_role("button", name="Tree temperature", exact=True).count()
                > 0
            )
            assert (
                "NEW LIVE ASSESSMENT"
                not in page.locator("#operatorResult").inner_text()
            )
            gate.set()
            page.locator("#operatorView").click()
            page.get_by_text("NEW LIVE ASSESSMENT", exact=True).wait_for()
            assert (
                "Tree temperature (charged)"
                in page.locator("#operatorResult").inner_text()
            )
            assert "Software fixture" in page.locator("#operatorResult").inner_text()
            assert len(calls) == 3
        finally:
            gate.set()
            page.close()
            server.shutdown()
            server.server_close()
            thread.join()
    return len(calls)


def raw_widget_browser(browser, url, payload):
    """Synthetic widget-only fixture. Never captured as a real telemetry image."""
    from copy import deepcopy

    fixture = deepcopy(payload)
    for case in fixture["cases"]:
        r = case["replay"]
        r.update(
            mode="raw",
            can_play=True,
            timestamps=["SOFTWARE TEST " + str(i) for i in range(600)],
            elapsed_seconds=list(range(600)),
        )
        for sensor, stream in r["series"].items():
            stream["samples"] = [
                {
                    "value": None
                    if i in (2, 3)
                    else (53.0 if sensor == "ABER-CKGL" else float(i) * 1e6),
                    "quality": "missing"
                    if i == 2
                    else "invalid"
                    if i == 3
                    else "valid",
                }
                for i in range(600)
            ]
            stream["reference"] = stream["samples"][0]["value"]
        r["viewer_series"] = {
            "T-TPT": {
                "samples": [
                    {"value": 10 + i / 10, "quality": "valid"} for i in range(600)
                ],
                "reference": 10,
            }
        }
        for row in r["inventory"]:
            row["present_in_incident"] = (
                row["sensor"] in r["series"] or row["sensor"] == "T-TPT"
            )
        for sensor in case["sensor_definitions"]:
            if sensor not in r["series"] and sensor not in r["viewer_series"]:
                r["viewer_series"][sensor] = {
                    "samples": [
                        {"value": None, "quality": "missing"} for _ in range(600)
                    ],
                    "reference": None,
                }

    page = browser.new_page(viewport={"width": 1440, "height": 900})
    try:
        page.route("**/api/cases", lambda route: route.fulfill(json=fixture))
        page.goto(url + "/demo", wait_until="networkidle")
        page.locator(".sensor-hit").nth(11).wait_for()
        page.locator("#slider").fill("2")
        assert page.locator(".claim-sensor.missing").count() == 2
        page.locator("#slider").fill("3")
        assert page.locator(".claim-sensor.invalid").count() == 2
        page.locator("#slider").fill("0")
        assert "0 MPa" in page.locator(".tree .sensor-reading").inner_text()
        page.locator("#play").click()
        page.wait_for_timeout(1250)
        page.locator("#play").click()
        position = page.locator("#slider").input_value()
        assert int(position) > 0
        page.wait_for_timeout(1100)
        assert page.locator("#slider").input_value() == position
        assert "Viewer only" in page.locator('[data-sensor="T-TPT"]').inner_text()
        page.locator(".sensor-hit.tree").click()
        assert page.locator(".chart-line").get_attribute("d").count("M") >= 2
    finally:
        page.close()
    # Run the exhaustive verifier against an EXPLICITLY CONSTRUCTED route fixture.
    # This checks its browser logic, never certifies real 3W replay.
    from petromind.replay_verification import verify_browser

    class FixtureBrowser:
        def new_page(self, **kwargs):
            p = browser.new_page(**kwargs)
            p.route("**/api/cases", lambda route: route.fulfill(json=fixture))
            return p

    verify_browser(FixtureBrowser(), url, fixture)


def main():
    from playwright.sync_api import sync_playwright

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8765")
    parser.add_argument("--browser", type=Path)
    parser.add_argument("--screenshots", type=Path)
    parser.add_argument("--mock-live-capture", type=Path)
    a = parser.parse_args()
    if urlparse(a.url).hostname not in {"127.0.0.1", "localhost"}:
        raise ValueError("Loopback only")
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            executable_path=str(a.browser.resolve()) if a.browser else None,
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
        )
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        errors = []
        requests = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("request", lambda r: requests.append(r.url))
        page.goto(a.url, wait_until="networkidle")
        page.locator(".sensor-hit").nth(11).wait_for(state="attached")
        payload = page.request.get(a.url + "/api/cases").json()
        if a.screenshots:
            a.screenshots.mkdir(parents=True, exist_ok=True)

        def shot(name):
            page.evaluate("window.scrollTo(0,0)")
            assert page.evaluate("document.documentElement.scrollWidth<=innerWidth"), (
                name,
                page.evaluate("document.documentElement.scrollWidth"),
            )
            if a.screenshots:
                page.mouse.move(0, 0)
                page.screenshot(path=str(a.screenshots / (name + ".png")))

        for width, height, label in [(1440, 900, "desktop"), (390, 844, "mobile")]:
            page.set_viewport_size({"width": width, "height": height})
            page.locator(".site-nav a").nth(0).click()
            assert page.locator(".site-nav a").count() == 3
            assert (
                "A well has dozens of sensors"
                in page.locator("#homePage h1").inner_text()
            )
            shot("home-" + label)
            page.locator(".home-hero .primary").click()
            for i, case in enumerate(payload["cases"]):
                page.locator("#caseSelect").select_option(str(i))
                # Reset an already explored case without changing the source capture.
                if page.locator("#back").is_visible():
                    page.locator("#back").click()
                assert (
                    page.locator(".claim-sensor").count() == 2
                    and page.locator(".secondary-sensor").count() == 10
                )
                assert page.locator("#play").is_disabled() == (
                    case["replay"]["mode"] == "endpoints"
                )
                page.locator("#slider").fill("0")
                first = page.locator(".tree .sensor-reading").inner_text()
                maximum = 599 if case["replay"]["mode"] == "raw" else 1
                page.locator("#slider").fill(str(maximum))
                assert page.locator(".tree .sensor-reading").inner_text() != first
                page.locator("#allSensors").click()
                assert page.locator(".inventory-row").count() == 27
                page.keyboard.press("Escape")
                if i == 0:
                    shot("operator-" + label)
                page.locator("#nextScene").click()
                assert "hypothesis" in page.locator("#plausibility").inner_text()
                if i == 0:
                    shot("diagnosis-" + label)
                page.locator("#nextScene").click()
                assert page.locator("#eventFeed li").count() == 1
                page.locator("#insideView").click()
                assert page.locator(".evidence-node").count() == 5
                assert page.locator("#slider").input_value() == str(maximum)
                for _ in case["investigation_events"]["grounded"][1:]:
                    page.locator("#graphAdvance").click()
                assert page.locator(".evidence-node").count() > 5
                page.locator(".evidence-node.layer-2").first.click()
                assert page.locator("#nodeData").inner_text()
                page.keyboard.press("Escape")
                if i == 0:
                    shot("inside-muse-" + label)
                page.locator("#operatorView").click()
                assert page.locator("#slider").input_value() == str(maximum)
                assert page.locator("#eventFeed li").count() == len(
                    case["investigation_events"]["grounded"]
                )
                if i == 0:
                    shot("assessment-" + label)
                    if a.screenshots:
                        page.locator("#operatorResult").screenshot(path=str(a.screenshots / ("assessment-detail-" + label + ".png")))
                page.locator("#inspectDetails").click()
                assert (
                    json.loads(page.locator("#raw").text_content())["output"]
                    == case["audits"]["grounded"]["output"]
                )
                page.keyboard.press("Escape")
                page.locator("#scenarioSelect").select_option("synthetic")
                assert page.locator("#syntheticNotice").is_visible()
                page.locator("#returnHistorical").click()
            page.locator(".site-nav a").nth(2).click()
            page.locator(".architecture-node").first.click()
            assert "Real replay" in page.locator("#architectureDetail").inner_text()
            assert "60.6%" in page.locator("#technologyPage").inner_text()
            shot("technology-" + label)
            assert page.evaluate("document.documentElement.scrollWidth<=innerWidth")
        assert not errors, errors
        assert not any("/api/live" in r or "api.meta.ai" in r for r in requests)
        raw_widget_browser(browser, a.url, payload)
        mock_calls = (
            mock_live_browser(browser, a.mock_live_capture)
            if a.mock_live_capture
            else 0
        )
        active_calls = (
            mock_active_browser(browser, a.mock_live_capture)
            if a.mock_live_capture
            else 0
        )
        failure_calls = (
            mock_live_browser(browser, a.mock_live_capture, fail=True)
            if a.mock_live_capture
            else 0
        )
        browser.close()
        print(
            json.dumps(
                {
                    "status": "passed",
                    "pages": 3,
                    "cases": 2,
                    "viewports": ["1440x900", "390x844"],
                    "javascript_errors": 0,
                    "paid_requests": 0,
                    "mocked_live_requests": mock_calls + active_calls + failure_calls,
                    "active_sensor_and_failure_paths": bool(a.mock_live_capture),
                    "raw_browser_fixture": "constructed software fixture, not real-data verification",
                    "captured_outputs_unchanged": True,
                }
            )
        )


if __name__ == "__main__":
    main()
