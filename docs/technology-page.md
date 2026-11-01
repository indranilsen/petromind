# Visual Technology walkthrough

The Technology page is a buildless HTML/CSS/JavaScript explanation of the existing
system. Home and Demo retain their operator journey and captured/live modes.
No prompt, validation contract, classifier, detector, retrieval policy or saved
experiment is changed by this page.

## Run

From the repository, with Python 3.12 and the existing private demo artifacts:

```bash
python -m pip install -e '.[test,agent,audit]'
python scripts/demo_claim_audit.py serve \
  --capture .petromind/claim-audit-v1 \
  --dataset ../3W/dataset \
  --science-protocol .petromind/science-m5-v1/protocol.json \
  --monitoring .petromind/monitoring-demo-v1
```

Open **http://127.0.0.1:8765/technology** and hard-refresh after pulling changes.
This does not enable live calls. The dataset and capture are not in the public
repository; see [the setup runbook](hackathon-readiness.md) for prerequisites.
For a Technology-only review with an unchanged original claim capture, omit the
three dataset/protocol/monitoring flags. Its dots will show captured endpoints,
not a continuous raw replay. It does not replace raw monitoring verification.

## A 60–90 second tour

1. Follow the six-stage software pipeline. Click Muse, then Python safeguards:
   inputs, outputs, actual interfaces and boundaries appear beneath the diagram.
2. Explore the seven investigation capabilities. Additional sensor requests are
   optional and share the five-sensor limit with the initial evidence. This is
   a capability map, not an invented chronology of model actions.
3. Switch the curated graph from documented sensor locations to comparison,
   claim and gap. Click a source to inspect its provenance. These are generic
   source-scoped facts, not installed-well topology or a new traversal engine.
4. Inspect the atomic assessment. Measured increases and a narrow fault-8
   comparison can be supported while fault-9 sufficiency and necessity remain
   unestablished. The composite PARTIALLY_SUPPORTED does not partly prove a cause.
5. Read the frozen classification chart. The adaptive statistical baseline
   outperformed Muse variants. Muse's demonstrated role is evidence auditing;
   this page makes no new accuracy or physical-verification claim.

## Data and illustration boundaries

- Sensor-location nodes use the existing public `sensor_definitions` returned
  by `/api/cases`, including the dataset.ini source and its per-well scope limit.
- The Figure 5 text is a caption summary of the registry's two fault-8 pressure
  comparisons. The complete published example also has a downstream pressure
  decrease. No universal rule or fault-9 causal edge is asserted.
- The v5 assessment and necessity/sufficiency diagrams are **explanatory
  illustrations**, not edited saved findings or a newly executed investigation.
- The signal preview uses only existing public replay samples. At most 20
  recorded indices per channel are drawn as dots on independent channel scales.
  Missing/invalid samples are skipped, never filled. X is sample index, not a
  claim about continuous or synchronized timing. Endpoint mode shows only actual
  captured first/last valid values; their timestamps are unavailable and may
  differ across channels. The preview does not add evidence to Muse's packet.
- The missing/zero symbols, hypothesis branches and 3-vs-1 overlap are explicitly
  illustrative. They are not fabricated signals or new retrieval results.
- The bar chart reads the unchanged results table and uses a full 0–100% scale.
  Counts remain 20, 13, 4, 1 and 5 out of 33.
- All new styles are scoped to `#technologyPage`; chart point attributes are
  namespaced so they cannot enter Demo's sensor selectors.

## Reproduce verification

```bash
python -m pytest -q
python -m pip install playwright
python -m playwright install chromium
python scripts/verify_technology_browser.py \
  --capture .petromind/claim-audit-v1 \
  --screenshots .petromind/technology-screenshots
```

Use `--browser /absolute/path/to/chromium` for an existing browser executable.
The verifier starts a temporary loopback server, checks all six architecture
components, seven workflow stages, source inspectors, chart counts and widths,
exact plotted sample values, keyboard focus, reduced motion, text containment
and horizontal overflow at 1440×900, 900×900 and 390×844. It refuses to count a
live request as a passing frontend check. No Meta credentials are required.

The existing broader regression can be run against your already running server:

```bash
python scripts/check_claim_demo_browser.py \
  --url http://127.0.0.1:8765 \
  --mock-live-capture .petromind/claim-audit-v1
```

The raw-widget regression uses a constructed software fixture, and live HTTP
responses in this test are mocked. Neither is real-data or paid-API validation.
Review the screenshots as well as the assertions. No new claim of independent
physical correctness is established by these checks.

### Implementation verification receipt — 2026-11-01

- Full offline suite: **547 passed, 1 opt-in browser test skipped**.
- Technology browser verifier: passed at **1440×900, 900×900 and 390×844**;
  screenshots visually inspected, no horizontal overflow or clipped button text.
- Existing three-page browser regression: passed on both recorded cases at
  desktop/mobile; seven mocked live HTTP requests, zero paid requests, zero
  JavaScript errors. Completion, active-sensor and failure paths passed.
- The environment had the unchanged public capture but not the raw local 3W
  dataset. The screenshots show six actual endpoint dots across three channels;
  this is not a new real-dataset replay certification. The broader raw-widget
  regression remains a constructed software fixture.
- Zero paid Meta calls. No frozen records, knowledge records, model prompts,
  validation contracts or scientific backend files changed.
