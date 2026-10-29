# Three-minute demo: a fact is not yet a cause

Open case **01 · Two pressures rise**. This is a replay of a genuine captured Muse
audit, not a new API execution. The main story takes two clicks. Do not begin in
the evidence drawer or narrate every implementation detail.

| Time | Scene and action | Suggested narration |
|---|---|---|
| 0:00–0:30 | **What happened?** Show the well and its two sensor indicators. Optionally scrub. | “Two pressure sensors in a production well ended higher than they started. One is deep down; the ‘tree’ is equipment near the top. These changes are real.” If raw loading is verified, Play runs real samples at 10×. Otherwise say: “These are captured start/end values; raw replay isn’t loaded.” |
| 0:30–0:55 | Click **See the diagnosis**. | “The statistical engine suggests service-line hydrate: ice-like material that can restrict flow. We constructed a plausible claim to test: both pressures rose, so that establishes this cause. Does it?” |
| 0:55–1:30 | Click **Ask Muse to investigate**. Pause on the verdict. | “The pressures really rose. But that doesn’t prove the cause. Muse accepted the measurements, consulted the documented context, and found no supplied verified rule establishing that these pressure increases are necessary or specific to hydrate.” The large story is editorial explanation; the quoted finding is exact captured Muse output. Do not imply a new live call or staged tool chronology. |
| 1:30–1:55 | Read the missing-evidence sentence; optionally open **Explore evidence**. | “The missing piece is the causal rule—not another decimal place. We would request the applicable well documentation and a validated way to distinguish causes. We don’t invent a discriminating test that our sources don’t supply.” The drawer contains original claims, measured values, documents and exact model findings. |
| 1:55–2:25 | Close the drawer. Select **02 · A pattern matches**; use the same two actions. | “The auditor can also accept a narrow supported claim. One pressure rose, the other fell, matching a published valve-closure example. Muse supports the comparison, without treating it as proof of valve closure.” |
| 2:25–2:45 | Optional: **Explore evidence**, actual grounded/ungrounded output. | “These are genuine captured outputs, with citations and historical overlap preserved. Raw replay is for the viewer; Muse received fixed sensor summaries. Moving a slider never changes its verdict.” |
| 2:45–3:00 | Return attention to the verdict. | “PetroMind catches the moment when a convincing diagnosis says more than its evidence establishes. It supports engineering judgment; it does not certify root cause or control equipment.” |

Before recording, verify the dataset and private protocol locally if you intend
to show Play. Do not replace missing raw data with generated samples. Only open a
sensor chart if asked; the story should be understandable without it. Exact well
geometry is illustrative. Independent engineering review is pending. Live Muse
integration is separate, opt-in and cost-bounded; do not run it during this replay
without an explicitly authorized fresh execution.

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
