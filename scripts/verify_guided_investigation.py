#!/usr/bin/env python3
"""Offline automatic-replay/browser checks; no live server or paid API enabled."""

import argparse
import json
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from petromind.claim_demo import DemoApp, make_server


def main():
    from playwright.sync_api import sync_playwright

    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--capture", type=Path, required=True)
    p.add_argument("--monitoring", type=Path)
    p.add_argument("--browser", type=Path)
    p.add_argument("--screenshots", type=Path)
    a = p.parse_args()
    app = DemoApp(a.capture, monitoring_directory=a.monitoring)
    server = make_server(app, 0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    if a.screenshots:
        a.screenshots.mkdir(parents=True, exist_ok=False)
    errors, live_requests = [], []
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                executable_path=str(a.browser.resolve()) if a.browser else None,
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage"],
            )
            for w, h, label in [(1440, 900, "desktop"), (390, 844, "mobile")]:
                page = browser.new_page(viewport={"width": w, "height": h})
                page.on("pageerror", lambda e: errors.append(str(e)))
                page.on(
                    "request",
                    lambda r: (
                        live_requests.append(r.url) if "/api/live" in r.url else None
                    ),
                )
                page.goto(
                    f"http://127.0.0.1:{server.server_port}/demo",
                    wait_until="networkidle",
                )
                page.clock.install(time=0)
                page.clock.pause_at(1000)
                for i, case in enumerate(app.cases):
                    page.locator("#caseSelect").select_option(str(i))
                    assert page.locator("#diagnosisCard").is_hidden()
                    assert page.locator("#nextScene").is_hidden()
                    ready = case["replay"]["workflow"]["checkpoint"]["index"]
                    page.locator("#slider").fill(str(ready))
                    assert (
                        "Statistical classifier result"
                        in page.locator("#diagnosisCard").inner_text()
                    )
                    assert (
                        page.locator("#cause")
                        .inner_text()
                        .startswith("Suspected failure:")
                    )
                    assert (
                        "calibrated"
                        in page.locator("#classifierStatement").inner_text()
                    )

                    def shot(name, target, page=page, i=i, label=label):
                        if a.screenshots:
                            page.locator(target).scroll_into_view_if_needed()
                            page.screenshot(
                                path=str(
                                    a.screenshots / f"case-{i + 1}-{label}-{name}.png"
                                )
                            )

                    shot("classifier", "#diagnosisCard")
                    page.locator("#nextScene").click()
                    assert page.locator("#insidePanel").is_visible()
                    assert page.locator("#eventFeed li").count() == 1
                    assert page.locator(".evidence-node.type-fact").count() == 0
                    assert page.locator("#insideAssessment").inner_text() == ""
                    page.clock.run_for(1400)
                    assert page.locator("#eventFeed li").count() == 2
                    page.locator("#capturePause").click()
                    page.clock.run_for(7000)
                    assert page.locator("#eventFeed li").count() == 2
                    expected = case["investigation_events"]["grounded"]
                    assert page.locator(".evidence-node.type-fact").count() == len(
                        expected[1]["facts"]
                    )
                    if label == "mobile":
                        assert not page.locator("#graphPanel").evaluate("e=>e.open")
                        page.locator("#graphPanel>summary").click()
                    page.locator(".evidence-node.type-fact").first.click()
                    assert (
                        expected[1]["facts"][0]["locator"]
                        in page.locator("#nodeData").inner_text()
                    )
                    assert page.locator("#nodeLinks a").count() == 1
                    shot("provenance", "#nodeDialog")
                    page.locator("#closeNode").click()
                    page.locator("#eventFeed .event-title").first.click()
                    assert page.locator(".evidence-node.current-node").count() > 0
                    page.locator("#eventFeed .event-title").nth(1).click()
                    shot("retrieval", "#eventFeed li:last-child")
                    page.locator("#capturePause").click()
                    page.clock.run_for(1400)
                    assert page.locator("#eventFeed li").count() == 3
                    page.locator("#captureRestart").click()
                    assert page.locator("#eventFeed li").count() == 1
                    assert page.locator(".evidence-node.type-fact").count() == 0
                    # Complete the entire captured journey automatically, not through Skip.
                    for count in range(2, len(expected) + 1):
                        page.clock.run_for(1400)
                        assert page.locator("#eventFeed li").count() == count
                        kinds = page.locator("#eventFeed li").evaluate_all(
                            "ns=>ns.map(n=>n.dataset.kind)"
                        )
                        assert kinds == [e["kind"] for e in expected[:count]]
                        supplied = {
                            f["citation_id"]
                            for e in expected[:count]
                            for f in e.get("facts", [])
                        }
                        shown = set(
                            page.locator(".evidence-node.type-fact").evaluate_all(
                                "ns=>ns.map(n=>n.dataset.nodeId)"
                            )
                        )
                        assert shown <= supplied
                        assert page.locator(".evidence-node").count() <= 10
                        page.locator("#graphToggle").click()
                        assert (
                            set(
                                page.locator(".evidence-node.type-fact").evaluate_all(
                                    "ns=>ns.map(n=>n.dataset.nodeId)"
                                )
                            )
                            == supplied
                        )
                        page.locator("#graphToggle").click()
                        if not any(e.get("assessment") for e in expected[:count]):
                            assert page.locator("#insideAssessment").inner_text() == ""
                    page.clock.run_for(
                        500
                    )  # Finish the restrained scroll/reveal animation.
                    heading = page.locator("#insideAssessment h3").first.bounding_box()
                    assert heading and 0 <= heading["y"] < h - 35
                    assert page.locator("#capturePause").is_disabled()
                    assert (
                        case["audits"]["grounded"]["output"]["verdict"].replace(
                            "_", " "
                        )
                        in page.locator("#insideAssessment").inner_text()
                    )
                    assert page.locator("#physicalHypotheses").inner_text()
                    shot("assessment", "#insideAssessment")
                    page.emulate_media(reduced_motion="reduce")
                    page.locator("#captureRestart").click()
                    assert page.locator("#eventFeed li").count() == 1
                    assert (
                        page.locator("#eventFeed li").first.evaluate(
                            "e=>getComputedStyle(e).animationName"
                        )
                        == "none"
                    )
                    page.locator("#captureSkip").click()
                    assert page.locator("#eventFeed li").count() == len(expected)
                    page.emulate_media(reduced_motion="no-preference")
                    page.locator("#operatorView").click()
                    page.locator("#slider").fill("0")
                    page.clock.run_for(7000)
                    assert page.locator("#diagnosisCard").is_hidden()
                    assert page.locator("#nextScene").is_hidden()
                    assert page.evaluate(
                        "document.documentElement.scrollWidth<=innerWidth"
                    )
                page.close()
            browser.close()
        assert not errors, errors
        assert not live_requests, live_requests
    finally:
        server.shutdown()
        server.server_close()
    print(
        json.dumps(
            {
                "status": "passed",
                "cases": 2,
                "viewports": ["1440x900", "390x844"],
                "automatic_order_pause_resume_restart_skip": True,
                "full_automatic_completion_and_visible_verdict": True,
                "reduced_motion_verified": True,
                "actual_returned_graph_and_provenance": True,
                "paid_requests": 0,
                "recording_mode": app.cases[0]["replay"]["mode"],
            }
        )
    )


if __name__ == "__main__":
    main()
