#!/usr/bin/env python3
"""Verify supplied real frozen development windows; never silently pass endpoints."""

import argparse
import json
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from petromind.claim_demo import DemoApp, make_server
from petromind.replay_verification import verify_browser, verify_case


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--capture", type=Path, required=True)
    p.add_argument("--dataset", type=Path, required=True)
    p.add_argument("--science-protocol", type=Path, required=True)
    p.add_argument("--browser-check", action="store_true")
    p.add_argument("--browser", type=Path)
    a = p.parse_args()
    try:
        if not a.dataset.is_dir():
            raise ValueError("dataset_required")
        source = json.loads(a.science_protocol.read_text())
        app = DemoApp(a.capture, dataset=a.dataset, science_protocol=source)
        rows = [verify_case(c, app.protocol, a.dataset, source) for c in app.cases]
        browser_check = None
        if a.browser_check:
            from playwright.sync_api import sync_playwright

            server = make_server(app, 0)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                with sync_playwright() as pw:
                    browser = pw.chromium.launch(
                        headless=True,
                        executable_path=str(a.browser.resolve()) if a.browser else None,
                        args=["--no-sandbox", "--disable-dev-shm-usage"],
                    )
                    try:
                        browser_check = verify_browser(
                            browser,
                            f"http://127.0.0.1:{server.server_port}",
                            {"cases": app.cases},
                        )
                    finally:
                        browser.close()
            finally:
                server.shutdown()
                server.server_close()
                thread.join()
        print(
            json.dumps(
                {
                    "status": "supplied_dataset_verified",
                    "cases": rows,
                    "browser": browser_check,
                    "api_requests": 0,
                    "scope": "Against frozen protocol file hashes, not independent dataset authenticity or physical certification.",
                }
            )
        )
        return 0
    except (ValueError, OSError, KeyError, TypeError, AssertionError, ImportError):
        print(
            json.dumps(
                {
                    "status": "verification_failed",
                    "api_requests": 0,
                    "instruction": "Supply the unchanged dataset and matching private M5 protocol. Browser check additionally needs Playwright/Chromium. Endpoint fallback does not pass.",
                }
            )
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
