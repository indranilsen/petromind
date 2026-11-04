> **Historical implementation snapshot.** This document records an earlier UI
> iteration; references to three pages or a deferred synthetic mode are not current.
> Use the [project README](../README.md), [documentation index](README.md) and
> [current setup runbook](hackathon-readiness.md). Original implementation and
> verification details below are retained for provenance.

# Classifier result and guided Muse investigation

This refines the existing Home / Demo / Technology product. It retains the
prefix-only monitoring work and the original classifier/Muse evidence boundary.
No paid call, new classifier experiment, model prompt change or schema relaxation
was made. The graph is an **evidence-use graph**, never a verified well topology.

## Run locally

From the repository root, with your existing Python 3.12 environment:

```bash
python -m pip install -e '.[test,agent,audit]'
python scripts/demo_claim_audit.py serve \
  --capture .petromind/claim-audit-v1 \
  --dataset ../3W/dataset \
  --science-protocol .petromind/science-m5-v1/protocol.json \
  --monitoring .petromind/monitoring-demo-v1
```

Open **http://127.0.0.1:8765/demo**. This command enables no paid mode. If you have
not prepared the monitoring bundle, follow [these exact commands](monitoring/run.md)
first. Alternatively omit `--monitoring` for the original 600-sample / endpoint
checkpoint demonstration; it is not relabeled as anomaly detection.

The recorded clips' computed alerts remain 14:32 and 31:02. Original diagnosis
readiness remains 39:59. These are unchanged software-feasibility findings, not
validated industrial alarm performance. The first substantially pre-annotation
alert remains a specificity warning. [Evidence and limits](monitoring/feasibility-v1.md).

1. Start at the first observation and play/scrub. No diagnosis or Muse action
   appears before the existing evidence gate. An anomaly, fault category and
   established physical cause remain separate concepts.
2. Read **Statistical machine-learning classifier → Suspected failure**. The
   actual recorded prediction supplies the fault name. “Ranked highest” appears
   only if that category has the highest recorded score among represented trained
   categories. No numeric score is promoted as a calibrated probability.
3. The two pressure comparisons use the **original 600-sample audit summaries**,
   not the slider's broader viewer reference. They show recorded endpoints and
   endpoint differences. These differences are not mislabeled as feature importance.
4. Click **Investigate with Muse Spark**. Inside Muse opens and the captured
   public records unfold automatically, in original order, every 1.4 seconds.
   This is deliberate **presentation pacing**, not original API token timing.
5. Pause/resume, restart the investigation replay, or show its completed
   assessment. These controls do not rerun a model or manufacture events. Rewind
   or navigate away to pause; no future assessment or source fact appears early.
6. Click an event to highlight its actual evidence links. Click a graph node or
   a returned fact to inspect the underlying record, source and locator. Mobile
   prioritizes the conversation; expand the evidence-graph disclosure as needed.

## What the classifier presentation establishes

The captured initial prediction comes from the existing diagonal Gaussian
statistical evidence model. Its implementation uses median, standard deviation
and the difference of half-window medians. The endpoint differences shown in the
UI are descriptive recorded observations, not necessarily that last feature.

The claim capture preserves the initial prediction and later audit observations,
**not the exact per-prediction classifier sensor list**. We do not assert that
all three inherited Muse summaries were used to make that initial prediction.
The input disclosure says this explicitly. No feature attribution, training
coefficient, calibrated confidence, early classification timestamp or new
posterior is fabricated. Public `classifier_context` remains outside the agent
packet; it contains implementation descriptions, not new telemetry.

## What Muse actually retrieves

`lookup_knowledge` selects predefined vetted source-scoped facts by public topic
(subject, object or documented example). It is **not** unrestricted traversal of
a well's installed equipment. No new topology query tool was added: the present
knowledge does not justify pretending to discover well-specific piping.

Only actual returned facts become document/entity/equipment nodes. Their exact
subject–relation–object triples become documented edges, with their provenance
and scope. Sensor-to-document links require that the returned triple actually
names that sensor. A document mentioning an unqueried sensor creates a source
reference, never an observed measurement node or free sensor reading.

Historical edges show the returned `matched_sensors`, shared-sensor count and
empirical distance. Unequal overlap is visible. A one-sensor analogue is not
promoted to equally corroborated causal evidence. Assessment edges show **Muse
cites**, not Python proves. Supported/unsupported findings and missing premises
arrive only with the corresponding actual accepted submission.

The physical-explanation disclosure contains returned mechanism/equipment facts,
published example directions where supplied, actual available summaries, and
submitted public premises/gaps/next-evidence requests. It distinguishes a narrow
example comparison from necessary/sufficient physical rules. If no verified
fault-specific expectation or discriminating test was returned, it says so.
Missing measurements and unobserved example components are explicit. No flow
paths, pressure differences, equations or causal propagation are invented.

## Live v3 remains explicit and capped

The model-facing contract is unchanged: `lookup_knowledge`, restricted
`search_history`, `submit_audit`, plus opt-in v3 `request_sensor`. Active queries
still require verified original raw 600-sample windows; initial and additional
summaries share five sensors, missing requests cost a query and cache hits are free.
Viewer history, reference statistics and alert scores never enter that packet.

An optional pre-dispatch observer now emits **actual tool-request metadata** and
then the existing completed-tool event. It is opt-in for interactive live runs;
ordinary evaluation events are unchanged. Known lookup topics may be shown;
submission arguments, rejected text and private reasoning are not persisted or
projected by this observer. Waiting indicators reflect an actual outstanding run,
not invented messages. A terminal failure is never converted to captured success.

Public event projection is versioned `public-investigation-v2`. Source/runtime
pinning and the new event-version pin require a **fresh** live protocol after this
update. Existing protocols/results are never edited. Use the existing
[explicit live instructions](live-investigation-verification.md) when authorizing
future paid execution. No paid experiment or smoke call was performed for this PR.

## Verify and capture screenshots

```bash
python -m pytest -q
python -m pip install playwright
python -m playwright install chromium
python scripts/verify_guided_investigation.py \
  --capture .petromind/claim-audit-v1 \
  --monitoring .petromind/monitoring-demo-v1 \
  --screenshots .petromind/guided-muse-review-v1
```

Use a fresh screenshot directory. Optional `--browser /absolute/path/to/chromium`
uses an existing browser executable. The script starts/stops an offline-only
loopback server, checks both cases at 1440×900 and 390×844, and creates classifier,
retrieval and final-assessment PNGs for each. Screenshots contain real measurements
and remain local rather than being published in GitHub.

Checks cover original event order, no premature facts/assessment, automatic
progression, pause/resume/restart/skip, query-linked highlights, actual source
inspection, classifier attribution, rewind gating, mobile layout and zero live
endpoint requests. The separate existing browser suite exercises v2/v3 incremental
streaming and failures using mocked HTTP, not paid Meta verification.

Actual verification here used the two user-supplied 3,001-position recorded
projections, with unchanged original summary checks. The full source dataset was
not available here; this is not independent dataset authenticity verification.
Frozen M3/M4/M5 results and captured claim audits remain unchanged. Root cause,
physical entailment and an accuracy benefit from Muse remain unestablished.
