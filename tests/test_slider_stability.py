"""Real pointer scrubbing with fabricated monitoring telemetry; no model calls."""

import os
import threading

import numpy as np
import pytest

from petromind.audit import canonical
from petromind.claim_demo import DemoApp, make_server
from petromind.measurements import summarize
from petromind.monitoring_replay import project


@pytest.mark.skipif(
    os.getenv("PETROMIND_BROWSER_CHECK") != "1", reason="Opt-in browser regression"
)
@pytest.mark.parametrize("width,height", [(1440, 900), (390, 844)])
def test_manual_slider_drag_preserves_position_and_evidence_gates(
    tmp_path, monkeypatch, width, height
):
    import test_claim_demo
    from playwright.sync_api import sync_playwright
    from test_monitoring_replay import fixture

    original_packet = test_claim_demo.packet
    values = np.linspace(1, 3, 600)

    def packet():
        p = original_packet()
        p["observations"] = {s: summarize(values).to_dict() for s in p["observations"]}
        return p

    monkeypatch.setattr(test_claim_demo, "packet", packet)
    capture = test_claim_demo.capture.__wrapped__(tmp_path, monkeypatch)
    app = DemoApp(capture)
    frame, _, entry = fixture()
    for sensor in entry["present_sensor_ids"]:
        frame.loc[:399, sensor] = [0.01 + 0.001 * (i % 7) for i in range(400)]
        frame.loc[400:999, sensor] = values
        frame.loc[1000, sensor] = 3
    replay = project(frame, entry, app.cases[0], 400)
    app.cases[0]["replay"] = replay
    first = next(
        i
        for i, p in enumerate(replay["workflow"]["monitor"]["trace"])
        if p["new_alert"]
    )
    checkpoint = replay["workflow"]["checkpoint"]["index"]
    last = replay["workflow"]["positions"] - 1
    assert 60 < first < checkpoint - 60
    before = canonical(app.cases)
    server = make_server(app, 0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    errors, paid = [], []
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                executable_path=os.getenv("PETROMIND_CHROMIUM"),
                args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
            )
            page = browser.new_page(
                viewport={"width": width, "height": height}, reduced_motion="reduce"
            )
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.on(
                "request",
                lambda r: paid.append(r.url) if "/api/live" in r.url else None,
            )
            page.goto(
                f"http://127.0.0.1:{server.server_port}/demo", wait_until="networkidle"
            )
            slider = page.locator("#slider")
            slider.evaluate(
                "e=>window.scrollBy(0,e.getBoundingClientRect().top-innerHeight/2)"
            )
            # Catch deferred automatic scrolling as well as visible scroll movement.
            page.evaluate(
                """()=>{window.scrubScrollCalls=0;window.scrubPositions=[];document.getElementById('slider').addEventListener('input',()=>requestAnimationFrame(()=>{const b=document.getElementById('slider').getBoundingClientRect();window.scrubPositions.push({x:b.x,y:b.y,width:b.width,height:b.height,scrollY})}));const original=Element.prototype.scrollIntoView;Element.prototype.scrollIntoView=function(...a){window.scrubScrollCalls++;return original.apply(this,a)}}"""
            )
            box = slider.bounding_box()
            scroll = page.evaluate("scrollY")
            y = box["y"] + box["height"] / 2
            start_x = box["x"] + 8
            page.mouse.move(start_x, y)
            page.mouse.down()
            stages = []
            for target in [
                first - 60,
                first + 60,
                checkpoint - 60,
                last,
                checkpoint - 60,
                first + 60,
                first - 60,
            ]:
                page.mouse.move(
                    start_x + (box["width"] - 16) * target / last, y, steps=6
                )
                page.evaluate(
                    "()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))"
                )
                position = int(slider.input_value())
                actual_box = slider.bounding_box()
                assert abs(page.evaluate("scrollY") - scroll) <= 1, (
                    target,
                    "unexpected page scroll",
                )
                for coordinate in ("x", "y", "width", "height"):
                    assert abs(actual_box[coordinate] - box[coordinate]) <= 1, (
                        target,
                        coordinate,
                        box,
                        actual_box,
                    )
                assert page.evaluate("scrubScrollCalls") == 0
                alerted, ready = position >= first, position >= checkpoint
                assert page.locator("#checkpointAlert").is_visible() == alerted
                assert page.locator("#diagnosisCard").is_visible() == ready
                assert page.locator("#nextScene").is_visible() == ready
                assert page.locator("#pressureOverview svg").first.get_attribute(
                    "data-index"
                ) == str(position)
                sensor = page.locator('[data-sensor="P-PDG"]').first
                assert sensor.get_attribute("data-index") == str(position)
                assert (
                    float(sensor.get_attribute("data-value"))
                    == replay["series"]["P-PDG"]["samples"][position]["value"]
                )
                stages.append((alerted, ready))
            page.mouse.up()
            snapshots = page.evaluate("scrubPositions")
            assert len(snapshots) >= len(stages)
            for snapshot in snapshots:
                assert abs(snapshot["scrollY"] - scroll) <= 1, snapshot
                for coordinate in ("x", "y", "width", "height"):
                    assert abs(snapshot[coordinate] - box[coordinate]) <= 1, snapshot
            # Guided navigation is an explicit scroll opt-in; evidence gates remain.
            page.locator("#journeyAction").click()
            page.evaluate(
                "()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))"
            )
            assert int(slider.input_value()) == first
            assert page.locator("#checkpointAlert").is_visible()
            assert page.locator("#diagnosisCard").is_hidden()
            assert page.evaluate("scrubScrollCalls") > 0
            assert stages == [
                (False, False),
                (True, False),
                (True, False),
                (True, True),
                (True, False),
                (True, False),
                (False, False),
            ]
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            assert not errors, errors
            assert not paid, paid
            assert canonical(app.cases) == before
            browser.close()
    finally:
        server.shutdown()
        server.server_close()
