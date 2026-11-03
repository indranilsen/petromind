#!/usr/bin/env python3
"""Offline browser layout check: unchanged recorded v4 and constructed v5 inputs.

No model calls, no rewrite of captures, no replay of invented tool chronology.
The fixture is inserted into browser memory solely to inspect final presentation.
"""

import argparse
import hashlib
import json
import sys
import threading
from copy import deepcopy
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from petromind.claim_demo import DemoApp, make_server


def main():
    from playwright.sync_api import sync_playwright

    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--capture", type=Path, required=True)
    p.add_argument("--browser", type=Path)
    p.add_argument("--screenshots", type=Path, required=True)
    args = p.parse_args()
    args.screenshots.mkdir(parents=True, exist_ok=False)
    fixture_path = (
        Path(__file__).resolve().parents[1]
        / "tests/fixtures/live006-public-assessment.json"
    )
    fixture = json.loads(fixture_path.read_text())
    original = fixture["recorded_assessment"]
    expected = deepcopy(original)
    expected["findings"][-1]["verdict"] = "NOT_ESTABLISHED"
    expected["contract_version"] = "claim-auditor-v5-scope-atomic"
    before = {
        name: hashlib.sha256((args.capture / name).read_bytes()).hexdigest()
        for name in ["protocol.json", "results.jsonl"]
    }
    server = make_server(DemoApp(args.capture), 0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    errors, paid = [], []
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                executable_path=str(args.browser.resolve()) if args.browser else None,
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage"],
            )
            for width, height, label in [(1440, 900, "desktop"), (390, 844, "mobile")]:
                page = browser.new_page(
                    viewport={"width": width, "height": height}, reduced_motion="reduce"
                )
                page.on("pageerror", lambda e: errors.append(str(e)))
                page.on(
                    "request",
                    lambda r: paid.append(r.url) if "/api/live" in r.url else None,
                )
                page.goto(
                    f"http://127.0.0.1:{server.server_port}/demo",
                    wait_until="networkidle",
                )
                page.locator("#slider").fill(
                    page.locator("#slider").get_attribute("max")
                )
                for mode, assessment in [
                    ("recorded-v4", original),
                    ("constructed-v5", expected),
                ]:
                    page.evaluate(
                        """({assessment, mode}) => {
                        execution = 'captured'; workspaceView = 'inside';
                        const r = investigation(); r.phase = 2; r.playing = false;
                        r.events = [
                          {kind:'evidence_received',hypothesis:c().packet.baseline.prediction,observations:c().observations},
                          {kind:'tool_result',tool:'submit_audit',assessment},
                          {kind:'completion',status:'completed',reason:'offline_ui_fixture_only'}
                        ]; r.cursor = r.events.length; r.row = null;
                        renderPlatform();
                        let banner = document.getElementById('offlineFixtureBanner');
                        if (!banner) {banner = document.createElement('div'); banner.id = 'offlineFixtureBanner'; document.body.append(banner);}
                        banner.textContent = 'OFFLINE UI CHECK · ' + mode + ' fixture · NO NEW MODEL RUN';
                        Object.assign(banner.style, {position:'fixed',bottom:'0',left:'0',right:'0',background:'#e3c58e',color:'#091923',padding:'8px',zIndex:'100',fontSize:'12px',textAlign:'center'});
                    }""",
                        {"assessment": assessment, "mode": mode},
                    )
                    root = page.locator("#insideAssessment")
                    assert (
                        root.locator('[data-scope="measured"] .scoped-finding').count()
                        == 2
                    )
                    assert (
                        root.locator(
                            '[data-scope="documented"] .scoped-finding'
                        ).count()
                        == 1
                    )
                    assert (
                        root.locator('[data-scope="causal"] .scoped-finding').count()
                        == 1
                    )
                    root.locator(".full-receipt > summary").click()
                    assert (
                        "Legacy recorded label" in root.inner_text()
                        if mode == "recorded-v4"
                        else "Recorded verdict: NOT ESTABLISHED" in root.inner_text()
                    )
                    for section in ["measured", "documented", "causal"]:
                        target = root.locator(f'[data-scope="{section}"]')
                        target.evaluate(
                            "(el) => window.scrollTo({top: scrollY + el.getBoundingClientRect().top - (innerWidth < 740 ? 200 : 160), behavior: 'instant'})"
                        )
                        box = target.bounding_box()
                        assert (
                            box
                            and box["x"] >= 0
                            and box["x"] + box["width"] <= width + 1
                        )
                        page.screenshot(
                            path=str(args.screenshots / f"{mode}-{label}-{section}.png")
                        )
                    assert page.evaluate(
                        "() => document.documentElement.scrollWidth <= innerWidth"
                    )
                    # Compare immutable displayed input rather than a computed regrade.
                    assert (
                        page.evaluate("() => PublicInvestigation.completedResult(visibleEvents())") == assessment
                    )
                page.close()
            browser.close()
        assert not errors, errors
        assert not paid, paid
        assert all(
            hashlib.sha256((args.capture / n).read_bytes()).hexdigest() == h
            for n, h in before.items()
        )
        assert fixture["recorded_assessment"] == original
    finally:
        server.shutdown()
        server.server_close()
    print(
        json.dumps(
            {
                "status": "passed",
                "viewports": ["1440x900", "390x844"],
                "fixtures": [
                    "unchanged recorded v4 public assessment",
                    "constructed v5 expected-contract input, not a model result",
                ],
                "screenshots": 12,
                "paid_requests": 0,
                "captures_unchanged": True,
                "javascript_errors": len(errors),
            }
        )
    )


if __name__ == "__main__":
    main()
