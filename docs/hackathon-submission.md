# PetroMind — when a diagnosis outruns its evidence

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

Home explains the industrial problem. Demo combines an instrumented Operator
Console and an interactive Inside Muse evidence graph. The graph follows actual
received measurements, tool results, documented relationships, historical overlap,
public findings and missing premises. Explicit live Muse runs stream observable
activity; clearly labeled captured replay supports a reliable demonstration.
No private chain of thought, fictitious tool chronology or invented telemetry is
shown. The current live auditor exposes source-topic knowledge lookup, restricted
history and structured submission; it cannot query extra sensors or traverse
verified well-specific topology. Viewer-only telemetry is kept separate.

The innovation we investigate is the model's ability to examine whether a causal
conclusion follows from evidence, rather than generate another classifier label.
We do not claim novelty for graph retrieval or tool calling in isolation.

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
