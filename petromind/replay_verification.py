"""Offline verification of supplied frozen windows. No Meta clients or inference."""

import math
from collections import Counter

import pandas as pd

from .audit import canonical
from .incident_replay import raw_payload, resolve_window
from .knowledge import SENSORS
from .measurements import MAX_ABS_RAW


def expected_sample(raw):
    """Independent scalar check of the documented numeric-quality rule."""
    if pd.isna(raw):
        return None, "missing"
    try:
        value = float(raw)
    except (ValueError, TypeError):
        return None, "invalid"
    return (
        (value, "valid")
        if math.isfinite(value) and abs(value) <= MAX_ABS_RAW
        else (None, "invalid")
    )


def verify_case(case, claim_protocol, dataset, science_protocol):
    before = canonical(case["packet"])
    window = resolve_window(case, claim_protocol, dataset, science_protocol)
    replay = raw_payload(window, case)
    assert replay["mode"] == "raw" and replay["interpolation"] == "none"
    assert replay["timestamps"] == [t.isoformat() for t in window.index]
    assert replay["elapsed_seconds"] == list(range(600))
    assert set(replay["series"]) == set(case["packet"]["observations"])
    assert set(replay["series"]) | set(replay["viewer_series"]) == set(SENSORS)
    assert len(replay["inventory"]) == 27
    counts = Counter()
    channels = {**replay["series"], **replay["viewer_series"]}
    for sensor, stream in channels.items():
        values = window.get(sensor, [None] * 600)
        for raw, supplied in zip(values, stream["samples"], strict=True):
            value, quality = expected_sample(raw)
            assert supplied["value"] == value and supplied["quality"] == quality
            counts[quality] += 1
        row = next(r for r in replay["inventory"] if r["sensor"] == sensor)
        assert row["present_in_incident"] == (sensor in window)
        assert row["observed_by_muse"] == (sensor in case["packet"]["observations"])
    assert canonical(case["packet"]) == before
    return {
        "task_id": case["id"],
        "mode": "raw",
        "samples": 600,
        "channels_in_catalog": 27,
        "present_channels": len(window.columns),
        "sample_quality_counts": dict(counts),
        "agent_packet_unchanged": True,
        "interpolation": "none",
    }


def verify_browser(browser, url, payload):
    """Exercise every timestamp in the real served payload, never a route fixture.

    Values/quality/trend, visible labels and chart cursor all share one index.
    Extra channels remain accessible in inventory; no live endpoint is invoked.
    """
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    errors, network = [], []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("request", lambda r: network.append(r.url))
    try:
        page.goto(url + "/demo", wait_until="networkidle")
        page.locator(".sensor-hit").nth(11).wait_for()
        for n, case in enumerate(payload["cases"]):
            if case["replay"]["mode"] != "raw":
                raise ValueError(
                    "Raw replay required; endpoint fallback is not a passing check"
                )
            page.locator("#caseSelect").select_option(str(n))
            page.locator('[data-sensor="P-TPT"]').first.click()
            checked = page.evaluate(
                """replay => {
              const streams = {...replay.series, ...replay.viewer_series};
              let count = 0;
              for(let i=0;i<600;i++) {
                const slider=document.getElementById('slider');
                slider.value=String(i); slider.dispatchEvent(new Event('input'));
                for(const node of document.querySelectorAll('.sensor-hit')) {
                  const s=node.dataset.sensor, p=streams[s].samples[i];
                  const row=replay.inventory.find(r=>r.sensor===s);
                  const quality=row.present_in_incident===false ? 'absent' : p.quality;
                  const expected=p.value===null ? '' : String(p.value);
                  if(node.dataset.value!==expected || node.dataset.quality!==quality || Number(node.dataset.index)!==i)
                    throw Error('Sensor sample/index mismatch: '+s+' / '+i);
                  const ref=streams[s].reference;
                  const trend=quality==='absent'?'missing':quality!=='valid'?quality:ref===null?'missing':p.value===ref?'stable':p.value>ref?'rising':'falling';
                  if(!node.classList.contains(trend)) throw Error('Trend mismatch');
                  if(p.quality==='valid' && row.present_in_incident!==false && !node.querySelector('.sensor-reading')) throw Error('Value label missing');
                  count++;
                }
                const chart=document.querySelector('#sensorChart .chart-svg');
                if(Number(chart.dataset.index)!==i || chart.dataset.timestamp!==replay.timestamps[i]) throw Error('Chart timestamp mismatch');
                const cursor=chart.querySelector('.chart-cursor');
                if(cursor && Math.abs(Number(cursor.getAttribute('x1'))-(48+i/599*493))>1e-6) throw Error('Cursor mismatch');
              }
              return count;
            }""",
                case["replay"],
            )
            assert checked == 12 * 600
            page.keyboard.press("Escape")
            page.locator("#allSensors").click()
            assert page.locator(".inventory-row").count() == 27
            page.keyboard.press("Escape")
            for width, height in ((1440, 900), (390, 844)):
                page.set_viewport_size({"width": width, "height": height})
                assert page.evaluate("document.documentElement.scrollWidth<=innerWidth")
        assert not errors, errors
        assert not any("/api/live" in u or "api.meta.ai" in u for u in network)
        return {
            "timeline_positions_per_case": 600,
            "displayed_sensors": 12,
            "chart_schematic_synchronized": True,
            "inventory_channels": 27,
            "paid_requests": 0,
        }
    finally:
        page.close()
