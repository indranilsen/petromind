#!/usr/bin/env python3
"""Verify the operator/finding/evidence UX against authorized local replay artifacts.

No live mode or model client is enabled. A fixture caller must label its images.
"""

import argparse
import json
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from petromind.audit import canonical
from petromind.claim_demo import DemoApp, make_server


def verify(browser, app, url, screenshots=None, *, fixture=False):
    errors, paid = [], []
    before = canonical(app.cases)
    checks = 0
    for width, height, label in [
        (1440, 900, "desktop"),
        (1024, 768, "tablet"),
        (390, 844, "mobile"),
    ]:
        for number, case in enumerate(app.cases):
            page = browser.new_page(
                viewport={"width": width, "height": height}, reduced_motion="reduce"
            )
            page.set_default_timeout(6000)
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.on(
                "request",
                lambda r: (
                    paid.append(r.url)
                    if "/api/live" in r.url or "api.meta.ai" in r.url
                    else None
                ),
            )
            page.goto(url + "/demo", wait_until="networkidle")
            if fixture:
                page.evaluate(
                    """()=>{let n=document.createElement('div');n.textContent='SYNTHETIC UI FIXTURE · NOT THE OWNER’S SAVED INVESTIGATION';n.style='position:fixed;bottom:0;left:0;right:0;z-index:9999;background:#e3c58e;color:#091923;padding:6px;text-align:center;font-size:11px';document.body.append(n)}"""
                )
            page.clock.install(time=0)
            page.clock.pause_at(1000)
            page.locator("#caseSelect").select_option(str(number))
            saved = case.get("saved_investigation")
            events = (
                saved["events"] if saved else case["investigation_events"]["grounded"]
            )
            expected = next(
                e["assessment"] for e in reversed(events) if e.get("assessment")
            )
            page.locator("#slider").fill(
                str(case["replay"]["workflow"]["checkpoint"]["index"])
            )
            page.locator("#nextScene").click()
            assert not page.locator("#insideAssessment").inner_text()
            for count in range(2, len(events) + 1):
                page.clock.run_for(1400)
                if not any(
                    e["kind"] == "completion" and e.get("status") == "completed"
                    for e in events[:count]
                ):
                    assert not page.locator("#insideAssessment").inner_text()
            page.clock.run_for(32)

            def shot(name, page=page, number=number, label=label):
                if screenshots:
                    page.screenshot(
                        path=str(screenshots / f"case-{number + 1}-{label}-{name}.png")
                    )

            assert page.locator("#insideAssessment .root-cause-status").is_visible()
            assert (
                "What should be verified next?"
                in page.locator("#insideAssessment").inner_text()
            )
            shot("finding")
            for _ in range(3):
                page.locator("#operatorView").click()
                assert page.locator(
                    "#operatorResult .operator-investigation-summary"
                ).is_visible()
                assert page.locator("#operatorResult .full-receipt").count() == 0
                assert page.locator("#operatorResult .operator-next-steps").count() == 0
                assert page.locator("#classifierHandoff").is_hidden()
                box = page.locator("#operatorResult").bounding_box()
                assert box["width"] <= width and box["x"] + box["width"] <= width
                page.locator("#operatorResult [data-open-finding]").click()
                page.clock.run_for(32)
            page.locator("#operatorView").click()
            page.locator("#operatorResult").scroll_into_view_if_needed()
            shot("operator-complete")
            page.locator("#operatorResult [data-open-finding]").click()
            page.clock.run_for(32)
            term = page.locator("#insideAssessment .sensor-term").first
            if term.count():
                term.focus()
                term.press("Enter")
                assert term.locator("[role=tooltip]").is_visible()
                term.press("Escape")
            page.locator("#insideAssessment .full-receipt>summary").click()
            assert (
                json.loads(
                    page.locator("#insideAssessment .raw-assessment pre").text_content()
                )
                == expected
            )
            indices = page.locator(
                "#insideAssessment [data-finding-index]"
            ).evaluate_all("els=>els.map(e=>e.dataset.findingIndex)")
            for index in indices:
                if not page.locator("#insideAssessment .full-receipt").evaluate(
                    "e=>e.open"
                ):
                    page.locator("#insideAssessment .full-receipt>summary").click()
                page.locator(
                    f'#insideAssessment [data-finding-index="{index}"]'
                ).click()
                page.clock.run_for(32)
                assert page.locator("#completionEvidence").evaluate("e=>e.open")
                assert page.locator("#graphPanel").evaluate("e=>e.open")
                assert (
                    page.locator(".evidence-node.selected-finding").get_attribute(
                        "data-node-id"
                    )
                    == "finding:" + index
                )
                assert page.locator("#findingEvidenceContext").inner_text()
                assert page.locator(".evidence-node.selected-finding").evaluate(
                    "e=>e===document.activeElement"
                )
            shot("selected-evidence")
            page.locator("[data-expand-graph]").click()
            assert page.locator(".evidence-node").count() == page.evaluate(
                "PublicInvestigation.graph(visibleEvents()).nodes.length"
            )
            assert page.locator(
                "#evidenceGraph .evidence-edge"
            ).count() == page.evaluate(
                "PublicInvestigation.graph(visibleEvents()).edges.length"
            )
            page.locator("#graphControls").get_by_role(
                "button", name="Zoom in", exact=True
            ).click()
            assert "125%" in page.locator("#graphControls").inner_text()
            page.locator("#graphControls").get_by_role(
                "button", name="Reset view", exact=True
            ).click()
            page.locator("#graphPanel").scroll_into_view_if_needed()
            shot("full-graph")
            page.locator(".evidence-node.type-measurement").first.click()
            assert page.locator("#nodeDialog").is_visible()
            page.locator("#closeNode").click()
            assert (
                page.locator(".physical-evidence-diagram .physical-card").count() == 3
            )
            page.locator("#physicalHypotheses").scroll_into_view_if_needed()
            shot("evidence-explanation")
            assert page.evaluate("document.documentElement.scrollWidth<=innerWidth")
            page.locator("#captureRestart").click()
            assert not page.locator("#insideAssessment").inner_text()
            page.locator("#operatorView").click()
            page.locator("#slider").fill("0")
            assert not page.locator("#operatorResult").inner_text()
            page.close()
            checks += 1
    assert not errors, errors
    assert not paid, paid
    assert canonical(app.cases) == before
    return {
        "viewports": 3,
        "case_viewport_journeys": checks,
        "javascript_errors": 0,
        "paid_requests": 0,
        "exact_outputs_unchanged": True,
        "saved_v5": "synthetic fixture"
        if fixture
        else "actual imported run"
        if any(c.get("saved_investigation") for c in app.cases)
        else "not available; original capture only",
    }


def main():
    from playwright.sync_api import sync_playwright

    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--capture", type=Path, required=True)
    p.add_argument("--saved-run", type=Path)
    p.add_argument("--monitoring", type=Path)
    p.add_argument("--browser", type=Path)
    p.add_argument("--screenshots", type=Path)
    a = p.parse_args()
    if a.screenshots:
        a.screenshots.mkdir(parents=True, exist_ok=False)
    app = DemoApp(
        a.capture, saved_directory=a.saved_run, monitoring_directory=a.monitoring
    )
    server = make_server(app, 0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                executable_path=str(a.browser) if a.browser else None,
                args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
            )
            try:
                report = verify(
                    browser,
                    app,
                    f"http://127.0.0.1:{server.server_port}",
                    a.screenshots,
                )
            finally:
                browser.close()
        print(json.dumps({"status": "passed", **report}))
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
