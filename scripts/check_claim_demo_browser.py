#!/usr/bin/env python3
"""Check the guided real-capture UI at desktop/mobile sizes. Never calls live Muse."""

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
        errors = []
        requests = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("request", lambda r: requests.append(r.url))
        page.goto(a.url, wait_until="networkidle")
        page.wait_for_function("document.querySelectorAll('.sensor-hit').length>=3")
        payload = page.request.get(a.url + "/api/cases").json()
        for case_index, case in enumerate(payload["cases"]):
            page.locator("#caseSelect").select_option(str(case_index))
            page.wait_for_function(
                'document.querySelectorAll("#progress button").length===5'
            )
            assert page.locator("#progress button").count() == 5
            assert page.locator("#well [role=button]").count() >= 3
            # Every displayed sensor can be selected; no additional queries occur.
            page.locator('#well [aria-label^="Tree pressure"]').click()
            assert (
                "Canonical recorded value" in page.locator("#context").inner_text()
                or "No measurement" in page.locator("#context").inner_text()
            )
            mode = case["replay"]["mode"]
            maximum = 599 if mode == "raw" else 1
            assert page.locator("#play").is_disabled() == (mode == "endpoints")
            page.locator("#slider").fill("0")
            page.locator("#slider").fill(str(maximum))
            assert (
                "viewer" in page.locator("#visibility").inner_text().lower()
                or "captured" in page.locator("#visibility").inner_text().lower()
            )
            page.locator("#progress button").nth(2).click()
            assert ("Hydrate" if case_index == 0 else "safety valve") in page.locator(
                "#context"
            ).inner_text()
            if a.screenshots:
                a.screenshots.mkdir(parents=True, exist_ok=True)
                page.screenshot(
                    path=str(a.screenshots / f"case{case_index + 1}-desktop-system.png")
                )
            page.locator("#progress button").nth(3).click()
            assert page.locator(".tool-step").count() == len(
                case["captured_activity"]["grounded"]
            )
            page.locator("#progress button").nth(4).click()
            verdict = page.locator("#verdictTitle").inner_text()
            assert "ROOT CAUSE IS NOT ESTABLISHED" in verdict
            page.locator("#slider").fill("0")
            assert page.locator("#verdictTitle").inner_text() == verdict
            page.locator("#slider").fill(str(maximum))
            assert page.locator("#verdictTitle").inner_text() == verdict
            if a.screenshots:
                page.screenshot(
                    path=str(
                        a.screenshots / f"case{case_index + 1}-desktop-verdict.png"
                    ),
                    full_page=True,
                )
            page.locator("#inspectDetails").click()
            raw = json.loads(page.locator("#raw").text_content())
            assert raw["output"] == case["audits"]["grounded"]["output"]
            page.locator("#ungrounded").click()
            assert (
                json.loads(page.locator("#raw").text_content())["output"]
                == case["audits"]["ungrounded"]["output"]
            )
            page.locator("#grounded").click()
            page.locator("#closeDetails").click()
            page.set_viewport_size({"width": 390, "height": 844})
            page.locator("#progress button").nth(0).click()
            page.evaluate("window.scrollTo(0,0)")
            assert page.evaluate(
                "document.documentElement.scrollWidth<=window.innerWidth"
            )
            assert page.locator("#nextScene").is_visible()
            if a.screenshots:
                page.screenshot(
                    path=str(a.screenshots / f"case{case_index + 1}-mobile.png"),
                    full_page=True,
                )
            page.locator("#progress button").nth(4).click()
            if a.screenshots:
                page.screenshot(
                    path=str(
                        a.screenshots / f"case{case_index + 1}-mobile-verdict.png"
                    ),
                    full_page=True,
                )
            page.set_viewport_size({"width": 1440, "height": 900})
            page.evaluate("window.scrollTo(0,0)")
        if a.test_synthetic_raw_controls:
            # Explicit synthetic UI fixture: does not pass through the production
            # adapter and is never saved as a screenshot or reported as 3W data.
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
                for stream in r["series"].values():
                    stream["samples"] = [
                        {
                            "value": None if i in (2, 3) else float(i + 1),
                            "quality": "missing"
                            if i == 2
                            else "invalid"
                            if i == 3
                            else "valid",
                        }
                        for i in range(600)
                    ]
                    stream["reference"] = 1
            testpage = browser.new_page(viewport={"width": 1440, "height": 900})
            testpage.on("pageerror", lambda e: errors.append(str(e)))
            testpage.route("**/api/cases", lambda route: route.fulfill(json=toy))
            testpage.goto(a.url, wait_until="networkidle")
            testpage.locator("#sensors [role=button]").nth(2).wait_for()
            assert not testpage.locator("#play").is_disabled()
            testpage.locator("#slider").fill("2")
            assert testpage.locator("#sensors .missing").count() == 3
            testpage.locator("#slider").fill("3")
            assert testpage.locator("#sensors .invalid").count() == 3
            testpage.locator("#slider").fill("0")
            testpage.locator("#play").click()
            testpage.wait_for_timeout(1250)
            assert int(testpage.locator("#slider").input_value()) > 0
            testpage.locator("#play").click()
            position = testpage.locator("#slider").input_value()
            testpage.wait_for_timeout(1100)
            assert testpage.locator("#slider").input_value() == position
            assert (
                testpage.locator(".chart-line").first.get_attribute("d").count("M") >= 2
            )
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
                    "unchanged_captured_outputs": True,
                }
            )
        )


if __name__ == "__main__":
    main()
