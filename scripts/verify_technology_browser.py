#!/usr/bin/env python3
"""Check the visual Technology explorer against a local capture. No live API calls."""

import argparse
import json
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from petromind.claim_demo import DemoApp, make_server


def verify(page, url, cases, out, label):
    errors, paid = [], []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.on(
        "request",
        lambda request: (
            paid.append(request.url)
            if "/api/live" in request.url or "api.meta.ai" in request.url
            else None
        ),
    )
    page.goto(url + "/technology")
    page.locator("#techPipeline .tech-stage").last.wait_for()
    assert page.locator("#techPipeline .tech-stage").count() == 6
    assert page.locator("#architectureNodes button").count() == 6
    assert page.locator("#techWorkflow [role=tab]").count() == 7
    for i in range(6):
        button = page.locator("#architectureNodes button").nth(i)
        button.click()
        assert button.get_attribute("aria-pressed") == "true"
        for word in ("INPUT", "OUTPUT", "INTERFACE", "BOUNDARY"):
            assert word in page.locator("#architectureDetail").inner_text()
        assert page.locator("#techPipeline .active, #techResources .active").count() > 0
    # Roving focus and the corresponding panel label follow selection.
    first = page.locator("#architectureNodes button").first
    first.focus()
    first.press("ArrowRight")
    assert (
        page.locator("#architectureNodes button")
        .nth(1)
        .evaluate("(e)=>e===document.activeElement")
    )
    tabs = page.locator("#techWorkflow [role=tab]")
    for i in range(7):
        tabs.nth(i).click()
        assert tabs.nth(i).get_attribute("aria-selected") == "true"
        assert page.locator("#techWorkflowDetail").get_attribute(
            "aria-labelledby"
        ) == tabs.nth(i).get_attribute("id")
    tabs.nth(0).focus()
    tabs.nth(0).press("End")
    assert tabs.nth(6).evaluate("(e)=>e===document.activeElement")
    tabs.nth(4).click()
    assert page.locator(".tech-budget span").count() == 5
    assert (
        "missing reading costs a query"
        in page.locator("#techWorkflowDetail").inner_text()
    )
    page.locator("#techLocations").click()
    for node in page.locator("#techEvidenceDiagram button").all():
        node.click()
        assert (
            page.locator("#techSourceDetail a")
            .get_attribute("href")
            .startswith("https://")
        )
        assert (
            "per well" in page.locator("#techSourceDetail").inner_text()
            or "per-well" in page.locator("#techSourceDetail").inner_text()
        )
    page.locator("#techClaims").click()
    assert "not captured calls" in page.locator("#techGraphScope").inner_text()
    for node in page.locator("#techEvidenceDiagram button").all():
        node.click()
        assert page.locator("#techSourceDetail").inner_text()
    assert (
        "fault 9" in page.locator("#techSourceDetail").inner_text()
        or "verified test" in page.locator("#techSourceDetail").inner_text()
    )
    expected = [(20, "60.6%"), (13, "39.4%"), (4, "12.1%"), (1, "3.0%"), (5, "15.2%")]
    rows = page.locator("#techScoreChart button")
    assert rows.count() == 5
    for i, (count, percent) in enumerate(expected):
        row = rows.nth(i)
        assert row.get_attribute("data-correct") == str(count)
        assert row.get_attribute("data-total") == "33"
        assert row.get_attribute("data-accuracy") == percent
        assert (
            abs(
                float(row.locator(".tech-bar-value").get_attribute("width"))
                - 100 * count / 33
            )
            < 1e-10
        )
        assert row.locator(".tech-bar-track").get_attribute("width") == "100"
        row.click()
        assert f"{count}/33" in page.locator("#techScoreDetail").inner_text()
    # Every displayed dot is an exact selected sample, with no interpolation.
    replay = cases[0]["replay"]
    for dot in page.locator("#techSignalPreview circle").all():
        sensor = dot.get_attribute("data-tech-sensor")
        index = int(dot.get_attribute("data-sample-index"))
        series = replay["series"].get(sensor) or replay.get("viewer_series", {}).get(
            sensor
        )
        sample = series["samples"][index]
        assert sample["quality"] == "valid"
        assert float(dot.get_attribute("data-recorded-value")) == sample["value"]
    assert page.locator("#techSignalPreview circle").count() > 0
    assert (
        "no continuous trace" in page.locator("#techSignalScope").inner_text().lower()
        if replay["mode"] == "endpoints"
        else "no interpolation" in page.locator("#techSignalScope").inner_text().lower()
    )
    # No document overflow or clipped button text, at each tested width.
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), label
    clipped = page.locator("#technologyPage button").evaluate_all(
        """(els)=>els.filter(e=>{const box=e.getBoundingClientRect();const walker=document.createTreeWalker(e,NodeFilter.SHOW_TEXT);let text;while(text=walker.nextNode()){if(!text.textContent.trim())continue;const range=document.createRange();range.selectNodeContents(text);for(const r of range.getClientRects()){if(r.right>box.right+1||r.left<box.left-1)return true;}}return false;}).map(e=>e.textContent)"""
    )
    assert not clipped, (label, clipped)
    page.emulate_media(reduced_motion="reduce")
    assert (
        page.locator(".tech-stage").first.evaluate(
            "(e)=>getComputedStyle(e).transitionDuration"
        )
        == "0s"
    )
    # Restore a readable, deliberately selected state before capturing.
    page.locator("#architectureNodes button").nth(2).click()
    tabs.nth(2).click()
    page.locator("#techLocations").click()
    page.evaluate("scrollTo(0,0)")
    page.mouse.move(1, 1)
    if out:
        page.screenshot(path=str(out / f"{label}-architecture.png"))
        for title, name in [
            ("techWorkflowTitle", "workflow"),
            ("techGraphTitle", "knowledge"),
            ("techChallengesTitle", "challenges"),
            ("techVerdictTitle", "assessment"),
            ("techResultsTitle", "results"),
        ]:
            page.locator("#" + title).evaluate(
                "(e)=>scrollTo(0,scrollY+e.getBoundingClientRect().top-115)"
            )
            page.screenshot(path=str(out / f"{label}-{name}.png"))
        page.locator("#techClaims").click()
        page.locator("#techGraphTitle").evaluate(
            "(e)=>scrollTo(0,scrollY+e.getBoundingClientRect().top-115)"
        )
        page.screenshot(path=str(out / f"{label}-claim-graph.png"))
    assert not errors, errors
    assert not paid, paid
    return {
        "viewport": label,
        "components": 6,
        "workflow_steps": 7,
        "chart_rows": 5,
        "recorded_points": page.locator("#techSignalPreview circle").count(),
        "horizontal_overflow": False,
        "api_requests": 0,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture", type=Path, required=True)
    parser.add_argument("--browser", type=Path)
    parser.add_argument("--screenshots", type=Path)
    args = parser.parse_args()
    app = DemoApp(args.capture)
    if args.screenshots:
        args.screenshots.mkdir(parents=True, exist_ok=True)
    server = make_server(app, 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                headless=True,
                executable_path=str(args.browser.resolve()) if args.browser else None,
                args=["--no-sandbox", "--disable-dev-shm-usage"],
            )
            try:
                results = []
                for width, height in [(1440, 900), (900, 900), (390, 844)]:
                    page = browser.new_page(viewport={"width": width, "height": height})
                    results.append(
                        verify(
                            page,
                            f"http://127.0.0.1:{server.server_port}",
                            app.cases,
                            args.screenshots,
                            f"{width}x{height}",
                        )
                    )
                    page.close()
            finally:
                browser.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
    print(
        json.dumps(
            {
                "status": "technology_browser_verified",
                "checks": results,
                "scope": "Local captured measurements and frontend interactions; no raw-dataset, paid API or physical-correctness verification.",
            }
        )
    )


if __name__ == "__main__":
    main()
