# PetroMind — Beyond Prediction, Toward Understanding

**Can a reasoning model move beyond recognizing anomalies to investigating the
physical causes behind them?**

PetroMind explores that question with **real industrial sensor measurements and
recorded failure incidents from Petrobras oil wells**, using Meta Muse Spark.
Traditional anomaly detection tells an operator something changed. PetroMind
investigates what the available evidence supports about why.

## Why investigation matters

Different physical faults can produce similar readings, important measurements
may be unavailable, and a confident fault prediction does not establish causality.
PetroMind separates measured observations, statistical hypotheses, engineering
context and evidence-backed conclusions. Its answer can be **root cause not
established**, with an inspectable explanation of the missing evidence.

## Real-world foundation

The primary Demo uses the public [Petrobras 3W dataset](https://github.com/petrobras/3W).
Recorded telemetry, sensor meanings and source-scoped engineering facts support
the investigation. The headline case confirms increases in two pressures while
leaving the suspected service-line hydrate obstruction unverified. The stronger
causal claim was constructed for evaluation; it is not presented as an operator's
expert diagnosis. The separate synthetic Extension is not part of this real-data
comparison.

## What we built

- **Meta Muse Spark investigation:** actual tool requests and returned evidence,
  with a shared maximum of five sensor-summary queries in supported active modes.
- **Physics-aware engineering context:** source-backed sensor descriptions,
  generic equipment relationships and scoped knowledge retrieval. This is not a
  verified per-well digital twin or a guarantee of causal understanding.
- **Auditable findings:** supported observations, unresolved causal premises,
  original verdicts, citations and requirements for further evidence.
- **A visible evidence boundary:** viewer telemetry never becomes extra agent
  evidence merely because it appears on screen. Recorded replay and separately
  enabled paid live execution are explicitly distinguished.

## What the experiments showed

The frozen exploratory comparison covers **33 Petrobras 3W incidents**. Its metric
is correct fault classification, not verified root-cause determination.

| Configuration | Evaluated predictor and evidence | Correct / total | Correct rate |
| --- | --- | --- | --- |
| Sensor-only | Muse with sensor evidence; no added graph retrieval | 4/33 | 12.1% |
| Sensor + Equipment Graph | Muse with sensors and generic equipment context | 1/33 | 3.0% |
| GraphRAG | Muse with sensors, equipment context and train-only similar incidents | 5/33 | 15.2% |
| Fixed Investigation | Statistical classifier; predefined training-ranked sensor order | 13/33 | 39.4% |
| Adaptive Investigation | Statistical classifier; adaptive sensor selection | 20/33 | 60.6% |

**The evaluated fixed and adaptive baselines do not use Muse or GraphRAG.** The
best tested configuration's correct-classification rate was 5× the sensor-only
Muse configuration and 4× the GraphRAG configuration. These descriptive ratios
compare whole configurations; they do not isolate an effect of adaptivity,
GraphRAG or reasoning quality.

The engineering lesson is to investigate the evidence, not assume that more
context establishes a cause. Non-correct cases must not be relabeled as uniformly
correct abstentions. These results do not establish production diagnostic
reliability. See the [configuration definitions](docs/evaluation.md#compared-configurations)
and [unchanged failure analysis](docs/milestone3-failure-analysis.md).

## Explore the product

**HOME | DEMO | EXTENSION | TECHNOLOGY**

- **Home (`/`):** the industrial problem and the distinction between a prediction
  and an explanation supported by evidence.
- **Demo (`/demo`):** real Petrobras measurements → recorded pressure alert →
  statistical hypothesis → Muse investigation → supported findings and uncertainty.
  After completion, next-evidence requirements lead into the focused evidence map.
- **Extension (`/extension`):** a separately labeled, previously recorded synthetic
  hydraulic investigation through pressure, flow and resistance. Its model-scoped
  conclusion does not establish an obstruction material or validate the real-data results.
- **Technology (`/technology`):** bounded tools, engineering context, evidence
  provenance, scientific limits and the unchanged classification comparison.

## Architecture

A local Python server validates evidence, tool budgets and accepted outputs.
The buildless HTML/CSS/JavaScript frontend shows only revealed public records.
The classifier proposes a fault; Muse assesses the stronger diagnostic claim.
Generic graph relationships and historical analogues retain their source scope.

[Architecture](docs/architecture.md) · [Assessment contract](docs/atomic-assessment.md) ·
[Research and development documentation](docs/README.md)

## Local setup and execution

Use Python 3.12. The public clone does **not** include the original claim capture,
private science protocol, 3W data or local monitoring/saved-replay bundles. Obtain
those authorized artifacts separately. A missing capture cannot be fixed by
regenerating its frozen results; use the [setup runbook](docs/hackathon-readiness.md).

```bash
python3.12 -m venv .venv312
source .venv312/bin/activate
python -m pip install -e '.[test,agent,audit]'

python scripts/demo_claim_audit.py check \
  --capture .petromind/claim-audit-v1 \
  --monitoring .petromind/monitoring-demo-v1

python scripts/demo_claim_audit.py serve \
  --capture .petromind/claim-audit-v1 \
  --dataset ../3W/dataset \
  --science-protocol .petromind/science-m5-v1/protocol.json \
  --monitoring .petromind/monitoring-demo-v1
```

Open [the local Demo](http://127.0.0.1:8765/demo). These commands enable replay,
not paid model execution. Stop an old server with Ctrl+C and hard-refresh after
updating. The supported runtime is a trusted local Python process, not a static
site or a validated public multi-user service.

For the preferred saved-v5 recording, [verify and import the original completed
run](docs/saved-v5-replay.md), then append
`--saved-run .petromind/judge-v5-replay-v1` to both commands. To enable Extension,
append `--synthetic-replay .petromind/PetroMind-Synthetic-Showcase` using the unchanged
extracted showcase package. See the [Extension runbook](docs/synthetic-investigation-demo.md).
Live execution needs separate explicit configuration, credentials and spending
limits; replay needs no API key. Never disable the server's access protections to
publish it.

## Limits and reproducibility

The 33-incident classification study is separate from the smaller constructed
claim audits and the controlled synthetic extension. None establishes general
physical correctness. Monitoring is retrospective and heuristic, not a validated
industrial alarm or certified early-warning system. Correct citations and
measurements do not by themselves certify a cause. The graph is not verified
installed-well topology, and independent engineering validation remains pending.

Frozen results, protocols, original accepted outputs and research history remain
unchanged. Research branches are separate from the finished demo; they are not
required to record it. [Research index and preserved records](docs/README.md#research-and-integrity)
cover reproducibility and source boundaries.

## Links and attribution

[Repository](https://github.com/indranilsen/petromind) ·
[Submission description](docs/hackathon-submission.md) ·
[Recording plan](docs/hackathon-demo.md) ·
[Delivery checklist](docs/submission-checklist.md)

No public deployment or final video URL is recorded here; delivery links and
access checks remain owner-controlled. Credit Petrobras and the 3W authors for
the dataset and published context, and Meta for Muse Spark. Follow the dataset's
license and citation requirements. Source versions and provenance are retained
in the knowledge registry and [evidence-coverage report](docs/physical-evidence-coverage.md).
The [archived implementation reference](docs/archive/implementation-history.md)
preserves earlier tool, compatibility and experiment instructions.
