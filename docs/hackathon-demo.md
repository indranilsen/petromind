> Optional live v3: [prepare, verify and run instructions](live-investigation-verification.md). First demonstrate the unchanged captured cases. Additional sensor summaries are available only when explicitly queried under the shared five-sensor budget; never describe viewer scrubbing as new Muse evidence. Active sensor selection efficacy and physical correctness remain unestablished.

# Three-minute platform demo

Use captured replay for a reliable recording. It contains real past Muse executions,
not a live simulation. If using live, configure a fresh capped protocol first and
explicitly select live mode. Do not claim a new live call while showing replay.

| Time | Page / action | Narration |
|---|---|---|
| 0:00–0:20 | Home → Open historical incident replay | “This production well has pressure, temperature, flow and equipment-state measurements. Some readings are missing or constant. Similar measurements can have different causes.” |
| 0:20–0:55 | Monitoring at sample 0 → Play or scrub | “We start at the first recorded observation. Values, relative trends, the sample counter and chart cursor follow the same sample. Raw mode replays actual samples; without the local dataset, this is an explicitly labeled two-endpoint comparison.” |
| 0:55–1:15 | Reach the marked checkpoint | “The replay has reached the end of the diagnostic window. This is a demo investigation checkpoint, not a historical alarm. The saved classifier needs full-window summaries, so we do not show it as an earlier prediction.” |
| 1:15–1:35 | Diagnosis expands automatically | “The statistical classifier suggests service-line hydrate: ice-like material that can restrict flow. These pressure increases are observations; a statistical pattern does not establish the cause. The stronger claim was constructed for evaluation.” |
| 1:35–2:05 | Click Investigate with Muse Spark → advance actual captured events | “Only now do we ask Muse to investigate. In this recording, these are genuine captured tool responses, not a new API call. Muse checks measurements, source-backed knowledge and restricted training analogues.” |
| 2:05–2:35 | Inside Muse → inspect a source, then Console assessment | “The evidence graph records actual requests and citations. A generic description of hydrate obstruction does not establish a necessary or specific pressure response. Muse distinguishes the supported pressure changes from the unsupported causal premise.” |
| 2:35–2:50 | Rewind/forward or briefly show the second case | “Rewinding hides the diagnosis and preserves the audit; returning does not call the model again. In the second example, a published-pattern comparison has a narrow supported scope, not proof of root cause.” |
| 2:50–3:00 | Technology | “Python enforces evidence budgets, provenance and validation. Statistical methods performed better at fault classification in our earlier benchmark. Muse's role here is evidence assessment, not certified root-cause determination.” |

For live mode, first prepare a fresh capped protocol after installing the current
code. Reaching the checkpoint does not spend money: only the explicitly selected
live investigation action invokes Meta. Actual events stream as they happen. V3
can request up to two additional sensor summaries within the original total of
five; v2 cannot. Knowledge is generic/source-scoped, not exact well topology.
Replay never silently substitutes for a failed live run. Synthetic Challenge
remains deferred. [Run and real-data verification commands](monitoring-workflow.md).


# Submission description

**PetroMind — when a diagnosis outruns its evidence**

PetroMind uses Meta Muse Spark to investigate industrial diagnostic claims. It
separates measured observations from causal assertions, retrieves provenance-tagged
engineering context, identifies unsupported premises, and names the evidence
needed for a stronger conclusion—or explicitly says no verified discriminating
test is available.

Our demonstration uses actual Petrobras 3W development measurements and two real
captured Muse audits. In one, recorded pressures increased, but that did not
establish the claimed service-line hydrate diagnosis. Muse accepted the numerical
observations while identifying the missing necessity/specificity premise. In the
other, Muse recognized a match to a published pressure-pattern example while
preserving the distinction between example consistency and proof of root cause.

Muse performs the substantive decomposition, evidence lookup and claim analysis.
Python enforces observation budgets, source provenance, exact numeric checks,
bounded repairs and API spending reservations. The interface makes each premise,
source, uncertainty and next-evidence request inspectable. Captured replay is
explicitly labeled; a separate versioned live integration remains available.

We did not pursue a claim that an LLM outperforms statistical fault diagnosis.
On our frozen 33-incident benchmark, conventional adaptive diagnosis achieved
60.6%, while direct Muse sensor-only and GraphRAG achieved 12.1% and 15.2%.
Graph-only Muse achieved 3.0%. These results are preserved. The claim-auditing
pilot completed four investigations; its two constructed tasks are not a general
accuracy benchmark, and independent engineering review remains pending.

The graph is documented only within the scope of its sources. Generic locations
are not verified individual-well topology, published examples are not universal
fault laws, and historical similarity is not causal confirmation. PetroMind is
a decision-support prototype—not a safety-certified operational decision system,
root-cause verifier, or autonomous equipment controller. No models were fine-tuned.

# Architecture in one paragraph

A trusted loader verifies the original capture and projects only already charged
sensor summaries, the statistical prediction, constructed claim and public source
context. In replay, the UI displays the original validated Muse output unchanged
and separately labeled source/logic review. In live v2, Muse chooses documented
knowledge topics/history tools and submits scope-specific findings through the
existing bounded Responses runner. Deterministic Python validation checks numbers,
received IDs, recommendation catalog targets and limits; it does not establish
physical entailment. A loopback HTTP server delivers static HTML/CSS/JS and keeps
credentials, private metadata and capture files out of the browser.
