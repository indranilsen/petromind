#!/usr/bin/env python3
"""Optional real-browser replay checks; never clicks a paid live action.

Install playwright separately. Point at a running local demo and optionally a
Chromium executable. Screenshots are local development artifacts, not model data.
"""

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
    a = p.parse_args()
    parsed = urlparse(a.url)
    if parsed.hostname not in {"127.0.0.1", "localhost"}:
        raise ValueError("Local demo URL required")
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            executable_path=str(a.browser.resolve()) if a.browser else None,
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
        )
        page = browser.new_page(
            viewport={"width": 1440, "height": 1080}, device_scale_factor=1
        )
        errors = []
        requests = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("request", lambda r: requests.append(r.url))
        page.goto(a.url, wait_until="networkidle")
        page.locator("#claim").wait_for()
        page.wait_for_function(
            "document.querySelector('#claim').textContent.length > 20"
        )
        payload = page.request.get(a.url + "/api/cases").json()
        assert page.locator("#liveMode").is_disabled()
        page.locator("#inspect").click()
        page.locator("#auditArea").wait_for(state="visible")
        assert page.locator("#verdictBadge").inner_text() == "PARTIALLY SUPPORTED"
        page.locator("#tabKnowledge").click()
        assert "service_line" in page.locator("#evidence").inner_text()
        page.locator("#tabHistory").click()
        assert "1 of 3" in page.locator("#evidence").inner_text()
        page.locator("#tabMeasurements").click()
        assert "291,760" in page.locator("#evidence").inner_text()
        raw = json.loads(page.locator("#raw").text_content())
        assert raw["output"] == payload["cases"][0]["audits"]["grounded"]["output"]
        if a.screenshots:
            a.screenshots.mkdir(parents=True, exist_ok=True)
            page.screenshot(
                path=str(a.screenshots / "fault9-desktop.png"), full_page=True
            )
        page.locator(".case-button").nth(1).click()
        page.locator("#inspect").click()
        assert page.locator("#verdictBadge").inner_text() == "SUPPORTED"
        page.locator("#tabKnowledge").click()
        assert "Figure 3 caption" in page.locator("#evidence").inner_text()
        page.locator("#ungrounded").click()
        assert page.locator("#verdictBadge").inner_text() == "PARTIALLY SUPPORTED"
        page.locator("#grounded").click()
        raw = json.loads(page.locator("#raw").text_content())
        assert raw["output"] == payload["cases"][1]["audits"]["grounded"]["output"]
        if a.screenshots:
            page.screenshot(
                path=str(a.screenshots / "fault2-desktop.png"), full_page=True
            )
        page.set_viewport_size({"width": 390, "height": 844})
        page.evaluate("window.scrollTo(0,0)")
        assert page.evaluate(
            "document.documentElement.scrollWidth <= window.innerWidth"
        )
        if a.screenshots:
            page.screenshot(
                path=str(a.screenshots / "fault2-mobile.png"), full_page=True
            )
        assert not errors, errors
        assert not any("/api/live" in url or "api.meta.ai" in url for url in requests)
        browser.close()
        print(
            json.dumps(
                {
                    "status": "passed",
                    "cases": 2,
                    "viewports": ["1440x1080", "390x844"],
                    "javascript_errors": 0,
                    "paid_requests": 0,
                    "original_outputs_unchanged": True,
                }
            )
        )


if __name__ == "__main__":
    main()
