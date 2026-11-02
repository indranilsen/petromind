# Monitoring → classifier → Muse handoff

The Demo's post-alert Operator Console has four blocks, in order:

1. **Alert summary.** Plain-language measured deviation, explicitly not fault
   identification. A capture without monitoring history remains a labeled review
   checkpoint; it is never presented as a historical operational alarm.
2. **Statistical classifier result.** A prominent suspected failure, its plain-
   English meaning, the top three captured candidate scores and two observed
   pressure changes. Score bars are relative to the top supplied score, not
   calibrated probabilities. No scores, categories or certainty are fabricated.
3. **Muse investigation.** The causal limitation and Muse's reasoning-based
   audit purpose precede the existing mode selector and Investigate action.
4. **Details.** The unchanged constructed claim, input-attribution limitations,
   detector rule, capture record, tools and spending limits remain inspectable.

Exact classifier sensor attribution is absent from the original capture. The
pressure cards are therefore labeled **observed pressure changes**, not feature
importance or proof of which sensors caused the model's prediction. Direction
uses each supplied summary's first-to-last-valid change; it does not assert a
monotonic trend. The second case correctly shows tree pressure decreasing.

The selector retains the original captured, verified saved and configured live
modes. Live remains disabled without server configuration. Selecting a mode
makes no API call; the existing explicit investigation action and backend caps
remain unchanged. Details collapse on incident changes.

## Run locally

After pulling the PR, use Python 3.12 and your existing private artifacts:

```bash
python -m pip install -e '.[test,agent,audit]'
python scripts/demo_claim_audit.py serve \
  --capture .petromind/claim-audit-v1 \
  --dataset ../3W/dataset \
  --science-protocol .petromind/science-m5-v1/protocol.json \
  --monitoring .petromind/monitoring-demo-v1
```

Open **http://127.0.0.1:8765/demo** and hard-refresh. Advance the timeline:
monitoring → recorded detector alert → completed diagnosis evidence → four-block
handoff. Choose a replay mode and click **Investigate with Muse Spark**. No live
API calls are enabled by this command. Keep your existing `--saved-run` argument
if you have imported a verified saved run. See [setup prerequisites](hackathon-readiness.md)
if the private monitoring bundle or original capture is missing.

## Verify

```bash
python -m pytest -q
python -m pip install playwright
python -m playwright install chromium
python scripts/check_claim_demo_browser.py \
  --url http://127.0.0.1:8765 \
  --mock-live-capture .petromind/claim-audit-v1 \
  --screenshots .petromind/handoff-screenshots
```

Use `--browser /absolute/path/to/chromium` for an existing executable. Mocked
live paths exercise the real runner/UI with HTTP mocked; no paid model calls.
The browser checks the four-block order, collapsed keyboard-accessible details,
source packet preservation, exact captured score ranking/bar widths, both cases'
pressure directions, disabled/configured live modes, and the replay action.
The constructed monitoring fixture verifies that an alert does not reveal the
classifier or Muse controls before the complete measurement window. It is a
software regression, not a new real-data detector validation.

The existing separate saved-mode browser regression remains opt-in:

```bash
PETROMIND_BROWSER_CHECK=1 python -m pytest tests/test_saved_investigation.py -q
```

Set `PETROMIND_CHROMIUM=/absolute/path/to/chromium` if needed. Its recording is a
clearly labeled software fixture, not a newly captured Meta run.

Verification for this change: full offline suite **549 passed, 1 skipped**;
opt-in saved browser suite **24 passed**; three-page browser regression passed
at **1440×900** and **390×844**, both captured incidents, seven mocked live HTTP
requests, zero paid requests and zero JavaScript errors. Screenshots were
inspected. Raw 3W files are unavailable in this environment; actual screenshots
use captured endpoints, and history-gating checks use a labeled software fixture.
No classifier, detector, diagnostic window, prompt, tool schema, retrieval policy,
validation contract, budget or captured result changed.
