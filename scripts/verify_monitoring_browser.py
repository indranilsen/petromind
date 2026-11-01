#!/usr/bin/env python3
"""Local actual-recorded monitoring UI checks. Starts its own no-live server.

Requires a prepared monitoring bundle, unchanged capture and Playwright Chromium.
No Meta calls. Screenshots contain real derived telemetry; keep them local unless
publication is authorized. This is replay verification, not detector validation.
"""

import argparse
import json
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from petromind.audit import canonical
from petromind.claim_demo import DemoApp, make_server
from petromind.eval_protocol import digest


def verify(browser, app, url, screenshots=None):
    errors, api_calls = [], []
    checked = 0
    for width, height, label in [(1440, 900, "desktop"), (390, 844, "mobile")]:
        page = browser.new_page(viewport={"width": width, "height": height})
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.on(
            "request",
            lambda request: (
                api_calls.append(request.url) if "/api/live" in request.url else None
            ),
        )
        page.goto(url + "/demo", wait_until="networkidle")
        for number, case in enumerate(app.cases, 1):
            page.locator("#caseSelect").select_option(str(number - 1))
            page.locator("#operatorView").click()
            replay = case["replay"]
            workflow = replay["workflow"]
            rows = workflow["monitor"]["trace"]
            first = next((i for i, row in enumerate(rows) if row["new_alert"]), None)
            ready = workflow["checkpoint"]["index"]
            assert page.locator("#slider").input_value() == "0"
            assert page.locator("#nextScene").is_hidden()
            assert page.locator("#checkpointMarker").is_hidden()
            positions = {0, 299, 300, ready - 1, ready, len(rows) - 1}
            if first is not None:
                positions.update({first - 1, first, min(first + 1, len(rows) - 1)})
            for index in sorted(positions):
                page.locator("#slider").fill(str(index))
                alert = rows[index]["alerted"]
                eligible = alert and index >= ready
                assert page.locator("#nextScene").is_visible() == eligible
                assert page.locator("#diagnosisCard").is_visible() == eligible
                assert page.locator("#checkpointMarker").is_visible() == alert
                assert page.locator("#checkpointAlert").is_visible() == alert
                assert (
                    page.locator("#sampleCounter").inner_text()
                    == f"Sample {index + 1} of {len(rows)}"
                )
                nodes = page.locator(".sensor-hit").evaluate_all(
                    "nodes=>nodes.map(n=>({sensor:n.dataset.sensor,value:n.dataset.value,quality:n.dataset.quality,index:n.dataset.index}))"
                )
                assert len(nodes) == 12
                streams = {**replay["series"], **replay["viewer_series"]}
                for node in nodes:
                    p = streams[node["sensor"]]["samples"][index]
                    assert node["index"] == str(index)
                    assert node["quality"] == p["quality"]
                    if p["value"] is None:
                        assert node["value"] == ""
                    else:
                        assert float(node["value"]) == p["value"]
                assert page.evaluate(
                    "document.documentElement.scrollWidth <= innerWidth"
                )
                if screenshots and (index == 0 or index == first or index == ready):
                    target = (
                        "#checkpointAlert"
                        if index == first
                        else "#historicalWorkspace"
                        if label == "desktop"
                        else "#diagnosisCard"
                        if index == ready
                        else "#workflowStatus"
                    )
                    page.locator(target).scroll_into_view_if_needed()
                    page.screenshot(
                        path=str(
                            screenshots
                            / f"case-{number}-{label}-{'monitoring' if index == 0 else 'alert' if index == first else 'diagnosis'}.png"
                        )
                    )
                checked += 1
            # All channels remain discoverable and the chart cursor shares the replay index.
            page.locator("#slider").fill(str(ready))
            page.locator('.sensor-hit[data-sensor="P-TPT"]').click()
            chart = page.locator("#sensorDialog svg[data-index]")
            assert chart.get_attribute("data-index") == str(ready)
            page.locator("#closeSensor").click()
            page.locator("#allSensors").click()
            assert page.locator(".inventory-row").count() == 27
            page.locator("#closeInventory").click()
            if rows[ready]["alerted"]:
                page.locator("#nextScene").click()
                while page.locator("#nextRecord").is_visible():
                    page.locator("#nextRecord").click()
                assert page.locator("#operatorResult").inner_text()
                if screenshots:
                    page.locator("#operatorResult").scroll_into_view_if_needed()
                    page.screenshot(
                        path=str(screenshots / f"case-{number}-{label}-muse.png")
                    )
                page.locator("#slider").fill("0")
                assert page.locator("#nextScene").is_hidden()
                assert page.locator("#activityPanel").is_hidden()
                assert page.locator("#checkpointMarker").is_hidden()
        page.close()
    # Separate software-only no-alert branch. Never screenshot this altered fixture.
    from copy import deepcopy

    from petromind.causal_monitor import monitor_trace

    fixture = {"cases": deepcopy(app.cases)}
    for case in fixture["cases"]:
        r = case["replay"]
        streams = {**r["series"], **r["viewer_series"]}
        for sensor in ("P-PDG", "P-TPT"):
            streams[sensor]["samples"] = [
                {"value": 0, "quality": "valid", "reason": None}
            ] * len(r["elapsed_seconds"])
            streams[sensor]["reference"] = 0
        r["workflow"]["monitor"]["trace"] = monitor_trace(r["elapsed_seconds"], streams)
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.route("**/api/cases", lambda route: route.fulfill(json=fixture))
    page.goto(url + "/demo", wait_until="networkidle")
    page.locator("#slider").fill(page.locator("#slider").get_attribute("max"))
    assert page.locator("#diagnosisCard").is_hidden()
    assert page.locator("#nextScene").is_hidden()
    assert page.locator("#checkpointMarker").is_hidden()
    assert "constant or zero" in page.locator("#monitoringExplanation").inner_text()
    page.close()
    assert not errors, errors
    assert not api_calls, api_calls
    return checked


def main():
    from playwright.sync_api import sync_playwright

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture", type=Path, required=True)
    parser.add_argument("--monitoring", type=Path, required=True)
    parser.add_argument("--browser", type=Path)
    parser.add_argument("--screenshots", type=Path)
    args = parser.parse_args()
    baseline = DemoApp(args.capture)
    app = DemoApp(args.capture, monitoring_directory=args.monitoring)
    for original, extended in zip(baseline.cases, app.cases, strict=True):
        assert digest(original["packet"]) == digest(extended["packet"])
        assert canonical(original["audits"]) == canonical(extended["audits"])
    if args.screenshots:
        args.screenshots.mkdir(parents=True, exist_ok=False)
    server = make_server(app, 0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                executable_path=str(args.browser.resolve()) if args.browser else None,
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage"],
            )
            checked = verify(
                browser, app, f"http://127.0.0.1:{server.server_port}", args.screenshots
            )
            browser.close()
    finally:
        server.shutdown()
        server.server_close()
    print(
        json.dumps(
            {
                "status": "supplied_recorded_clip_browser_verified",
                "viewports": ["1440x900", "390x844"],
                "positions_checked": checked,
                "sensor_nodes_per_position": 12,
                "inventory_channels": 27,
                "no_alert_gate": "software_only_constant_zero_fixture_passed",
                "agent_packets_unchanged": True,
                "captured_audits_unchanged": True,
                "api_requests": 0,
                "scope": "Recorded projection and UI only; not full-dataset authenticity, prospective detection or physical certification.",
            }
        )
    )


if __name__ == "__main__":
    main()
