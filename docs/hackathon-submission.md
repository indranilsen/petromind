# PetroMind — Beyond Prediction, Toward Understanding

**Can a reasoning model move beyond recognizing anomalies to investigating the
physical causes behind them?**

PetroMind explores this frontier using **real industrial sensor measurements and
recorded failure incidents from Petrobras oil wells**. Traditional anomaly
detection tells an operator something changed. PetroMind investigates what the
available evidence supports about why.

Industrial faults can produce overlapping sensor patterns, critical measurements
may be unavailable, and statistical confidence does not establish causality.
Built with Meta Muse Spark, PetroMind combines budgeted sensor investigation,
source-scoped engineering knowledge, generic physical relationships and auditable
assessments. It distinguishes observed measurements from hypotheses and can
explicitly conclude **root cause not established**.

The primary demonstration follows a real Petrobras 3W incident. A statistical
classifier suspects service-line hydrate obstruction. Muse confirms increases in
two measured pressures but identifies the missing causal basis: the supplied
measurements and context do not establish hydrate as the cause. The stronger
causal claim was constructed for evaluation, not presented as an expert operator
diagnosis. Original findings and source citations remain inspectable.

The experience moves from recorded telemetry and a measurement alert to a
statistical hypothesis, actual Muse tool records and a clear final finding. The
next-evidence section leads into the existing focused evidence map and optional
supporting details. Recorded playback is labeled as a previous investigation;
only separately configured live execution makes a new paid request. Viewer-only
telemetry never silently becomes evidence supplied to Muse.

## What the experiments actually establish

The exploratory comparison used **33 Petrobras 3W incidents** and measured correct
fault classifications, not verified causal diagnoses:

| Configuration | Correct / total | Correct rate |
| --- | --- | --- |
| Sensor-only | 4/33 | 12.1% |
| Sensor + Equipment Graph | 1/33 | 3.0% |
| GraphRAG | 5/33 | 15.2% |
| Fixed Investigation — statistical | 13/33 | 39.4% |
| Adaptive Investigation — statistical | 20/33 | 60.6% |

**The evaluated fixed and adaptive methods are statistical sensor-selection
baselines; neither uses Muse or GraphRAG.** The adaptive baseline's correct rate
was 5× sensor-only Muse and 4× the tested GraphRAG configuration. These compare
whole configurations and do not isolate a causal benefit of knowledge, adaptivity
or reasoning quality. The separate claim-auditing work explores what a structured
investigation can establish; the 60.6% result must not be attributed to that work.
Non-correct cases are not uniformly correct abstentions.

## Separate synthetic extension

**Demo Extension · Synthetic Physics Scenario** demonstrates evidence-based
physical reasoning through pressure, flow and hydraulic resistance. In a
previously recorded controlled hydraulic investigation, additional measurements
support increased effective resistance under the supplied model while leaving
the specific obstruction material unidentified. These simulated measurements
are not Petrobras telemetry and do not validate the real-data results.

## Vision and limits

Industrial failures are physical events, not just patterns. PetroMind explores
AI that connects physical principles with measurements, investigates competing
explanations, identifies missing evidence and recognizes when causality cannot
be established. Source-backed context is not verified installed-well topology or
a complete digital twin. Small, correlated claim audits and a synthetic showcase
are not independent engineering certification or production diagnostic reliability.

**PetroMind — moving beyond predicting failures, toward understanding them.**

## Short description

PetroMind uses Meta Muse Spark to investigate the physical evidence behind an
industrial diagnosis using real Petrobras oil-well sensor data. It separates
statistical predictions, observed measurements and source-scoped engineering
context, presents traceable findings, and can conclude that the root cause is
not established. A separate, clearly labeled synthetic extension illustrates
model-scoped hydraulic reasoning.

## Delivery and attribution

The supported runtime is a local Python app with separately supplied authorized
capture/data bundles. The public repository does not bundle those inputs or
establish public judge access. No final deployment or video URL is recorded here.
Confirm delivery links and the authenticated portal's requirements before submission;
do not claim submission without a receipt.

[Project overview](../README.md) · [Setup](hackathon-readiness.md) ·
[Architecture](architecture.md) · [Recording plan](hackathon-demo.md) ·
[Delivery checklist](submission-checklist.md) · [Configuration definitions](evaluation.md#compared-configurations)

Credit Petrobras and the 3W authors for the dataset and published context, and
Meta for Muse Spark. Retain source scope, data-license requirements and the
original recordings. New interactive live history suppresses training-event
labels; frozen captures retain their original training-label metadata and are
not retroactively label-free. Neither exposes hidden held-out target labels to Muse.
