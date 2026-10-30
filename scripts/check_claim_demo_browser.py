#!/usr/bin/env python3
"""Check the three-scene story with real captures. Never calls live Muse."""

import argparse
import json
from pathlib import Path
from urllib.parse import urlparse


def main():
    from playwright.sync_api import sync_playwright

    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--url", default="http://127.0.0.1:8765")
    p.add_argument("--browser", type=Path)
    p.add_argument("--screenshots", type=Path)
    p.add_argument(
        "--test-synthetic-raw-controls",
        action="store_true",
        help="Separate synthetic widget check; never saved as real-data screenshots",
    )
    a = p.parse_args()
    if urlparse(a.url).hostname not in {"127.0.0.1", "localhost"}:
        raise ValueError("Loopback URL required")
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            executable_path=str(a.browser.resolve()) if a.browser else None,
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
        )
        page = browser.new_page(
            viewport={"width": 1440, "height": 900}, device_scale_factor=1
        )
        errors, requests = [], []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("request", lambda r: requests.append(r.url))
        page.goto(a.url, wait_until="networkidle")
        page.locator(".sensor-hit").nth(1).wait_for()
        payload = page.request.get(a.url + "/api/cases").json()
        if a.screenshots:
            a.screenshots.mkdir(parents=True, exist_ok=True)
        for case_index, case in enumerate(payload["cases"]):
            for width, height, viewport in (
                (1440, 900, "desktop"),
                (390, 844, "mobile"),
            ):
                page.set_viewport_size({"width": width, "height": height})
                page.locator("#caseSelect").select_option(str(case_index))
                page.evaluate("window.scrollTo(0,0)")
                assert page.locator("#experience").get_attribute("data-scene") == "0"
                assert page.locator(".sensor-hit").count() == 12
                assert page.locator("#inspectDetails").is_hidden()
                assert page.locator(".chart-svg:visible").count() == 0
                assert page.locator("#details").is_hidden()
                assert page.locator("#progress").count() == 0
                # Friendly values and a limited secondary set, without a dashboard.
                visible = page.locator("body").inner_text()
                for excluded in ("P-PDG", "P-TPT", "ABER-CKGL", "API", "provenance"):
                    assert excluded not in visible
                assert page.locator("#play").is_disabled() == (
                    case["replay"]["mode"] == "endpoints"
                )
                maximum = 599 if case["replay"]["mode"] == "raw" else 1
                for position in (0, maximum):
                    page.locator("#slider").fill(str(position))
                assert page.locator(".claim-sensor").count() == 2
                assert page.locator(".secondary-sensor").count() == 10
                assert (
                    "Not observed in audit"
                    in page.locator('[data-sensor="T-TPT"]').inner_text()
                )
                # Endpoints visibly change both numbers and marker colors.
                page.locator("#slider").fill("0")
                first = page.locator(".tree .sensor-reading").inner_text()
                assert "stable" in page.locator("#treePoint").get_attribute("class")
                if a.screenshots and case_index == 0:
                    page.mouse.move(0, 0)
                    page.screenshot(
                        path=str(a.screenshots / f"replay-start-{viewport}.png")
                    )
                page.locator("#slider").fill(str(maximum))
                assert page.locator(".tree .sensor-reading").inner_text() != first
                assert ("rising" if case_index == 0 else "falling") in page.locator(
                    "#treePoint"
                ).get_attribute("class")
                assert page.locator(
                    '[data-sensor="ABER-CKGL"] .sensor-reading'
                ).count() == (1 if case_index == 0 else 0)
                assert "not danger" in page.locator("#trendLegend").inner_text()
                # A measured secondary uses its actual unit; an unobserved one has no chart.
                page.locator('[data-sensor="ABER-CKGL"]').click()
                assert ("53 %" if case_index == 0 else "Not observed") in page.locator(
                    "#sensorValue"
                ).inner_text()
                page.keyboard.press("Escape")
                page.locator('[data-sensor="T-TPT"]').click()
                assert page.locator("#sensorChart .chart-svg").count() == 0
                assert (
                    "No measurements were supplied"
                    in page.locator("#sensorChart").inner_text()
                )
                page.keyboard.press("Escape")
                page.locator("#allSensors").click()
                assert page.locator(".inventory-row").count() == 27
                assert page.locator(".inventory-section").count() == 4
                assert (
                    "Unknown without raw data"
                    in page.locator("#inventoryGroups").inner_text()
                )
                assert (
                    "not observed in audit"
                    in page.locator("#inventoryGroups").inner_text()
                )
                if a.screenshots and case_index == 0:
                    page.mouse.move(0, 0)
                    page.screenshot(
                        path=str(a.screenshots / f"all-sensors-{viewport}.png")
                    )
                page.keyboard.press("Escape")
                assert page.locator("#allSensors").evaluate(
                    "e => e === document.activeElement"
                )
                # Sensor is optional. Its modal contains one chart and real units.
                page.locator(".sensor-hit.tree").click()
                assert "MPa" in page.locator("#sensorValue").inner_text()
                assert page.locator("#sensorChart .chart-svg").count() == 1
                assert "viewer-only" in page.locator("#sensorNotes").inner_text()
                page.keyboard.press("Escape")
                assert page.locator("#sensorDialog").is_hidden()
                for scene in range(3):
                    page.mouse.move(0, 0)
                    page.wait_for_timeout(450)  # capture after editorial fade
                    assert page.evaluate(
                        "document.documentElement.scrollWidth<=innerWidth"
                    )
                    if width == 1440:
                        assert page.evaluate(
                            "document.documentElement.scrollHeight<=innerHeight"
                        ), (
                            case_index,
                            viewport,
                            scene,
                            page.evaluate("document.documentElement.scrollHeight"),
                        )
                    action = page.locator(
                        "#inspectDetails" if scene == 2 else "#nextScene"
                    ).bounding_box()
                    assert action["height"] >= 44
                    assert action["y"] + action["height"] <= height, (
                        case_index,
                        viewport,
                        scene,
                        action,
                    )
                    if a.screenshots:
                        page.screenshot(
                            path=str(
                                a.screenshots
                                / f"case{case_index + 1}-{viewport}-{scene + 1}.png"
                            )
                        )
                        if width < 741 and scene == 2:
                            page.evaluate(
                                "window.scrollTo(0,document.body.scrollHeight)"
                            )
                            page.screenshot(
                                path=str(
                                    a.screenshots
                                    / f"case{case_index + 1}-mobile-verdict-next.png"
                                )
                            )
                            page.evaluate("window.scrollTo(0,0)")
                    if scene < 2:
                        page.locator("#nextScene").click()
                # Exactly two main-action clicks reached the fixed verdict.
                assert page.locator("#experience").get_attribute("data-scene") == "2"
                assert "Audit result" in page.locator("#headline").inner_text()
                assert (
                    page.locator("#museQuote").text_content()
                    in case["audits"]["grounded"]["output"]["findings"][2][
                        "justification"
                    ]
                )
                assert page.locator("#museChecks li").count() == 3
                assert (
                    "rule" in page.locator("#nextEvidence").inner_text()
                    if case_index == 0
                    else "comparison is supported"
                    in page.locator("#nextEvidence").inner_text()
                )
                headline = page.locator("#headline").inner_text()
                page.locator("#inspectDetails").click()
                raw = json.loads(page.locator("#raw").text_content())
                assert raw["output"] == case["audits"]["grounded"]["output"]
                page.locator("#ungrounded").click()
                assert (
                    json.loads(page.locator("#raw").text_content())["output"]
                    == (case["audits"]["ungrounded"]["output"])
                )
                page.locator("#grounded").click()
                page.keyboard.press("Escape")
                assert page.locator("#details").is_hidden()
                assert page.locator("#inspectDetails").evaluate(
                    "e => e === document.activeElement"
                )
                assert page.locator("#headline").inner_text() == headline
                # Replaying endpoints/samples and returning does not alter output.
                page.locator("#back").click()
                page.locator("#back").click()
                page.locator("#slider").fill("0")
                page.locator("#nextScene").click()
                page.locator("#nextScene").click()
                assert page.locator("#headline").inner_text() == headline
        if a.test_synthetic_raw_controls:
            from copy import deepcopy

            toy = deepcopy(payload)
            for case in toy["cases"]:
                r = case["replay"]
                r.update(
                    mode="raw",
                    can_play=True,
                    elapsed_seconds=list(range(600)),
                    timestamps=[f"synthetic test {i}" for i in range(600)],
                    timing="Synthetic software test only",
                    visibility="Synthetic UI-test samples, not 3W data",
                )
                for sensor, stream in r["series"].items():
                    # Synthetic fixture only: zero is valid, one pressure rises,
                    # the other falls, choke stays constant; gaps stay explicit.
                    stream["samples"] = [
                        {
                            "value": None
                            if i in (2, 3)
                            else (
                                53.0
                                if sensor == "ABER-CKGL"
                                else (float(i) if sensor == "P-PDG" else float(600 - i))
                                * 1e6
                            ),
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
                            {"value": float(10 + i / 10), "quality": "valid"}
                            for i in range(600)
                        ],
                        "reference": 10.0,
                    }
                }
                for row in r["inventory"]:
                    if row["sensor"] == "T-TPT":
                        row.update(present_in_incident=True, availability="available")
            testpage = browser.new_page(viewport={"width": 1440, "height": 900})
            testpage.on("pageerror", lambda e: errors.append(str(e)))
            testpage.route("**/api/cases", lambda route: route.fulfill(json=toy))
            testpage.goto(a.url, wait_until="networkidle")
            testpage.locator(".sensor-hit").nth(1).wait_for()
            assert not testpage.locator("#play").is_disabled()
            testpage.locator("#slider").fill("2")
            assert testpage.locator(".claim-sensor.missing").count() == 2
            testpage.locator("#slider").fill("3")
            assert testpage.locator(".claim-sensor.invalid").count() == 2
            testpage.locator("#slider").fill("0")
            assert "0 MPa" in testpage.locator(".down .sensor-reading").inner_text()
            assert "stable" in testpage.locator("#downPoint").get_attribute("class")
            testpage.locator("#slider").fill("10")
            assert (
                testpage.locator('[data-sensor="T-TPT"] .sensor-reading').inner_text()
                == "11 °C"
            )
            assert (
                "Viewer only" in testpage.locator('[data-sensor="T-TPT"]').inner_text()
            )
            testpage.locator("#allSensors").click()
            assert "11 °C" in testpage.locator("#inventoryGroups").inner_text()
            testpage.keyboard.press("Escape")
            assert testpage.locator(".down .sensor-reading").inner_text() == "10 MPa"
            assert testpage.locator(".tree .sensor-reading").inner_text() == "590 MPa"
            assert (
                testpage.locator("#downPoint").evaluate("e => getComputedStyle(e).fill")
                == "rgb(255, 177, 122)"
            )
            assert (
                testpage.locator("#treePoint").evaluate("e => getComputedStyle(e).fill")
                == "rgb(139, 199, 255)"
            )
            testpage.locator("#play").click()
            testpage.wait_for_timeout(1250)
            assert int(testpage.locator("#slider").input_value()) > 0
            testpage.locator("#play").click()
            position = testpage.locator("#slider").input_value()
            testpage.wait_for_timeout(1100)
            assert testpage.locator("#slider").input_value() == position
            testpage.locator(".sensor-hit.tree").click()
            assert testpage.locator(".chart-line").get_attribute("d").count("M") >= 2
            testpage.close()
        assert not errors, errors
        assert not any("/api/live" in x or "api.meta.ai" in x for x in requests)
        browser.close()
        print(
            json.dumps(
                {
                    "status": "passed",
                    "cases": 2,
                    "viewports": ["1440x900", "390x844"],
                    "javascript_errors": 0,
                    "paid_requests": 0,
                    "main_action_clicks_to_verdict": 2,
                    "unchanged_captured_outputs": True,
                }
            )
        )


if __name__ == "__main__":
    main()
