# PetroMind — investigate the evidence behind an industrial diagnosis

A production well has dozens of measurements. Knowing what failed is harder:
readings may be incomplete and different faults may have overlapping symptoms.
PetroMind combines conventional statistical diagnosis with Meta Muse Spark to
investigate the evidential basis of industrial diagnostic claims.

The statistical engine proposes a fault. Muse decomposes the diagnostic claim,
consults source-backed engineering facts and restricted historical analogues,
and identifies which observations are supported and which causal premises remain
unestablished. Python validates exact measurements, received citations and
submission structure while enforcing observation and API-spending limits.

Our defining example uses actual Petrobras 3W development measurements: both
pressures increased, and a classifier suggested service-line hydrate. Muse
accepted the numerical changes but found no supplied verified rule establishing
that particular cause. In a second captured case, Muse supported a comparison to
a published fault example without treating the match as proof of root cause.
The diagnostic claims were constructed for evaluation, not presented as real
expert diagnoses. Original model outputs are inspectable and unchanged.

The guided demo makes that progression understandable without petroleum expertise.
Home explains the industrial problem. Demo combines an instrumented Operator
Console and an interactive Inside Muse evidence graph. The graph follows actual
received measurements, tool results, documented relationships, historical overlap,
public findings and missing premises. Explicit live Muse runs stream observable
activity; clearly labeled captured replay supports a reliable demonstration.
No private chain of thought, fictitious tool chronology or invented telemetry is
shown. The current live auditor exposes source-topic knowledge lookup, restricted
history and structured submission. Opt-in live v3 can request additional
source-motivated sensor summaries within the same total five-sensor budget. It
cannot traverse verified well-specific topology. Viewer-only telemetry remains
separate; additional queries are not forced or claimed to improve diagnosis.

The distinctive product interaction is an evidence handoff: an alert becomes a
ranked hypothesis, and Muse checks the stronger constructed diagnostic claim
against the information actually received. Engineers can inspect each source and
see where an explanation outruns its evidence. We do not claim novelty for graph
retrieval or tool calling in isolation.

We preserve the uncomfortable results: conventional adaptive diagnosis achieved
60.6% on the frozen 33-incident benchmark; direct Muse sensor-only, graph and
GraphRAG variants achieved 12.1%, 3.0% and 15.2%. GraphRAG did not demonstrate a
classification advantage. The claim-auditing pilots are small and correlated;
physical interpretations have not completed independent engineering validation.
Accurate citations alone do not certify physical truth.

The graph is documented only within source scope, not exact individual-well
configuration. Historical similarity is not causal evidence. Synthetic Challenge
is deferred; no validated physics simulator or synthetic success is claimed.
PetroMind is a decision-support prototype, not an autonomous controller,
safety-certified operational recommendation or general root-cause verifier.
No fine-tuning or new infrastructure was introduced.


## Short description

PetroMind uses Meta Muse Spark to investigate whether an industrial diagnosis is
justified by real sensor measurements and documented engineering knowledge. A
statistical classifier proposes a fault; Muse inspects budgeted evidence, source
facts and permitted historical analogues, then identifies supported observations,
unsupported causal premises and the evidence needed next. A recorded-data
Operator Console and evolving evidence graph make that investigation inspectable.

## Submission delivery

The supported demonstration runs locally with separately supplied authorized
data/capture artifacts; the public clone does not bundle the incidents or private
protocols. Captured mode is genuine prior model activity, explicitly labeled.
Public cloud hosting and a real paid readiness smoke test were not verified here.
Use the [runbook](hackathon-readiness.md), [three-minute script](hackathon-demo.md)
and the current verification receipt before recording. No general diagnostic
verification, prospective alarm efficacy or physically certified reasoning claim
is made.

New interactive live history suppresses training-event labels under a fresh pinned
projection version. Original captured audits retain their original training-label
metadata and must not be described as retrospectively label-free. Neither route
exposes hidden held-out target labels or private well/source paths to the agent.

## Portal preparation

Suggested tagline: **A classifier proposes a fault. Muse investigates the evidence.**

Use the short description above for a compact project field, and the main copy
for a longer field, subject to the actual portal's character limits. Technical
architecture is in [architecture.md](architecture.md); recording script and shot
plan are in [hackathon-demo.md](hackathon-demo.md). [Submission requirements](submission-checklist.md)
separate verified rules from signed-in form fields still needing confirmation.
Do not mark the project submitted until its receipt is available.
