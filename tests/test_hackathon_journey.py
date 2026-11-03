"""Opt-in judge walkthrough checks with synthetic software inputs only."""

import os
import sys
import threading
from pathlib import Path

import pytest
from test_saved_investigation import capture as capture_fixture
from test_saved_investigation import saved as saved_fixture

from petromind.audit import canonical
from petromind.claim_demo import DemoApp, make_server
from petromind.saved_investigation import import_saved


@pytest.fixture
def capture(tmp_path, monkeypatch):
    return capture_fixture.__wrapped__(tmp_path, monkeypatch)


@pytest.fixture
def saved(capture, tmp_path, monkeypatch):
    return saved_fixture.__wrapped__(capture, tmp_path, monkeypatch)


@pytest.mark.skipif(
    os.getenv("PETROMIND_BROWSER_CHECK") != "1", reason="Opt-in browser check"
)
def test_guided_journey_preserves_replay_and_evidence_gates(saved):
    from playwright.sync_api import sync_playwright

    capture_dir, run, _row, bundle = saved
    import_saved(capture_dir, run, bundle)
    app = DemoApp(capture_dir, saved_directory=bundle)
    before = canonical(app.cases)
    server = make_server(app, 0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    screenshots = Path(
        os.getenv("PETROMIND_SCREENSHOTS", str(bundle.parent / "screenshots"))
    )
    screenshots.mkdir(parents=True, exist_ok=True)
    errors, live = [], []
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                executable_path=os.getenv("PETROMIND_CHROMIUM"),
                args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
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
                    lambda r: live.append(r.url) if "/api/live" in r.url else None,
                )
                page.goto(
                    f"http://127.0.0.1:{server.server_port}/", wait_until="networkidle"
                )
                page.evaluate(
                    """()=>{const n=document.createElement('div');n.textContent='SYNTHETIC UI TEST FIXTURE · NOT AN ACTUAL MUSE RUN';n.style='position:fixed;bottom:0;left:0;right:0;z-index:9999;background:#e3c58e;color:#091923;padding:5px;text-align:center;font-size:11px';document.body.append(n)}"""
                )
                page.screenshot(
                    path=str(screenshots / f"journey-{label}-home.png"), full_page=False
                )
                page.locator('.home-hero a[href="/demo"]').click()
                assert (
                    page.locator('#journeySteps [aria-current="step"]').inner_text()
                    == "Monitor"
                )
                assert page.locator("#nextScene").is_hidden()
                page.screenshot(
                    path=str(screenshots / f"journey-{label}-monitor.png"),
                    full_page=False,
                )
                page.locator("#journeyAction").click()
                assert page.locator("#slider").input_value() == "1"
                assert (
                    page.locator('#journeySteps [aria-current="step"]').inner_text()
                    == "Classifier"
                )
                assert page.locator("#classifierHandoff > section").count() == 4
                assert (
                    page.locator("#executionControl").locator("..").get_attribute("id")
                    == "investigationLaunch"
                )
                assert (
                    "no new api call"
                    in page.locator("#journeyMode").inner_text().lower()
                )
                page.locator("#journeyAction").click()
                page.screenshot(
                    path=str(screenshots / f"journey-{label}-handoff.png"),
                    full_page=False,
                )
                page.locator("#nextScene").click()
                page.locator("#capturePause").click()
                assert page.locator("#insideAssessment").inner_text() == ""
                assert page.locator("#investigationBrief").is_visible()
                assert (
                    page.locator("#investigationQuestion").inner_text()
                    == app.cases[0]["packet"]["claim"]
                )
                page.screenshot(
                    path=str(screenshots / f"journey-{label}-investigation.png"),
                    full_page=False,
                )
                page.locator("#captureSkip").click()
                assert (
                    page.locator('#journeySteps [aria-current="step"]').inner_text()
                    == "Findings"
                )
                assert (
                    "PARTIALLY SUPPORTED"
                    in page.locator("#insideAssessment").text_content()
                )
                assert page.locator("#insideAssessment .full-receipt").count() == 1
                page.locator("#journeyAction").click()
                heading = page.locator("#insideAssessment h3").first.bounding_box()
                controls = page.locator("#captureControls").bounding_box()
                assert heading["y"] >= controls["y"] + controls["height"]
                page.screenshot(
                    path=str(screenshots / f"journey-{label}-findings.png"),
                    full_page=False,
                )
                assert page.evaluate("document.documentElement.scrollWidth<=innerWidth")
                page.locator('.site-nav a[href="/technology"]').click()
                page.go_back()
                assert page.locator("#insideAssessment").inner_text()
                page.locator("#captureRestart").click()
                assert page.locator("#insideAssessment").inner_text() == ""
                page.locator("#operatorView").click()
                page.locator("#slider").fill("0")
                assert page.locator("#nextScene").is_hidden()
                assert page.locator("#insideAssessment").inner_text() == ""
                page.close()
            sys.path.insert(0, str(Path("scripts").resolve()))
            from verify_technology_browser import verify

            for width, height, label in [
                (1440, 900, "desktop"),
                (1024, 768, "tablet"),
                (390, 844, "mobile"),
            ]:
                page = browser.new_page(viewport={"width": width, "height": height})
                verify(
                    page,
                    f"http://127.0.0.1:{server.server_port}",
                    app.cases,
                    None,
                    label,
                )
                page.close()
            browser.close()
        assert not errors, errors
        assert not live
        assert canonical(app.cases) == before
    finally:
        server.shutdown()
        server.server_close()


@pytest.mark.skipif(
    os.getenv("PETROMIND_BROWSER_CHECK") != "1", reason="Opt-in browser check"
)
def test_recorded_alert_jump_does_not_reveal_classifier_early(tmp_path, monkeypatch):
    """Use fabricated telemetry with a known alert; never modify a real capture."""
    import numpy as np
    import test_claim_demo
    from playwright.sync_api import sync_playwright
    from test_monitoring_replay import fixture

    from petromind.measurements import summarize
    from petromind.monitoring_replay import project

    original_packet = test_claim_demo.packet
    values = np.linspace(1, 3, 600)

    def packet():
        p = original_packet()
        p["observations"] = {s: summarize(values).to_dict() for s in p["observations"]}
        return p

    monkeypatch.setattr(test_claim_demo, "packet", packet)
    capture_dir = test_claim_demo.capture.__wrapped__(tmp_path, monkeypatch)
    app = DemoApp(capture_dir)
    frame, _, entry = fixture()
    for sensor in entry["present_sensor_ids"]:
        frame.loc[:399, sensor] = [0.01 + 0.001 * (i % 7) for i in range(400)]
        frame.loc[400:999, sensor] = values
        frame.loc[1000, sensor] = 3
    app.cases[0]["replay"] = project(frame, entry, app.cases[0], 400)
    replay = app.cases[0]["replay"]
    first = next(
        i
        for i, p in enumerate(replay["workflow"]["monitor"]["trace"])
        if p["new_alert"]
    )
    assert first < replay["workflow"]["checkpoint"]["index"]
    before = canonical(app.cases[0])
    server = make_server(app, 0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                executable_path=os.getenv("PETROMIND_CHROMIUM"),
                args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
            )
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            page.goto(
                f"http://127.0.0.1:{server.server_port}/demo", wait_until="networkidle"
            )
            assert (
                "Jump to recorded alert" in page.locator("#journeyAction").inner_text()
            )
            page.locator("#journeyAction").click()
            assert page.locator("#slider").input_value() == str(first)
            assert page.locator("#checkpointAlert").is_visible()
            assert page.locator("#diagnosisCard").is_hidden()
            assert page.locator("#nextScene").is_hidden()
            assert (
                page.locator('#journeySteps [aria-current="step"]').inner_text()
                == "Alert"
            )
            # Plot coordinates are derived from revealed measurements only.
            assert page.locator("#pressureOverview svg").first.get_attribute(
                "data-index"
            ) == str(first)
            page.locator("#journeyAction").click()
            assert page.locator("#slider").input_value() == "999"
            assert page.locator("#diagnosisCard").is_visible()
            page.locator("#slider").fill(str(first - 1))
            assert page.locator("#diagnosisCard").is_hidden()
            assert page.locator("#checkpointAlert").is_hidden()
            assert canonical(app.cases[0]) == before
            browser.close()
    finally:
        server.shutdown()
        server.server_close()


@pytest.mark.skipif(
    os.getenv("PETROMIND_BROWSER_CHECK") != "1", reason="Opt-in browser check"
)
def test_judge_flow_mocked_live_success_failure_and_active_sensors(capture):
    from playwright.sync_api import sync_playwright

    sys.path.insert(0, str(Path("scripts").resolve()))
    from check_claim_demo_browser import mock_active_browser, mock_live_browser

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            executable_path=os.getenv("PETROMIND_CHROMIUM"),
            args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
        )
        try:
            assert mock_live_browser(browser, capture) == 2
            assert mock_live_browser(browser, capture, fail=True) == 2
            assert mock_active_browser(browser, capture) == 3
        finally:
            browser.close()
