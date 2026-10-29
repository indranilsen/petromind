# Three-minute guided demo flow

Start on **See the well**. The badge identifies a real captured Muse audit replay.
Check the data badge before recording: raw data must be privately mapped and
verified to enable Play. Otherwise show only the actual captured endpoints and
say so. Never stage a continuous replay with generated readings.

| Time | Scene and action | Suggested narration |
|---|---|---|
| 0:00–0:25 | See the well; click Tree pressure, then Downhole pressure | “This is a production well. These sensors record pressure at the wellhead and downhole. The equipment associations are documented; this simplified layout is illustrative, not an exact well piping diagram.” |
| 0:25–0:50 | Replay the change; if verified raw data is loaded, Play at 10× and drag the cursor | “The values come from real timestamped measurements. Color means change from the first valid sample—not dangerous pressure. Missing and invalid readings stay distinct.” **If endpoint mode:** “The raw dataset is not loaded here. These are the actual recorded first/last valid values, not a simulated time series.” |
| 0:50–1:10 | The diagnosis | “Both recorded pressures increased. The statistical model suggests hydrate blockage in the service line. Here is our constructed claim: those increases establish that cause.” |
| 1:10–1:45 | Audit this diagnosis | “Muse separates the measured facts from the physical inference. The document describes hydrate obstruction, but supplies no necessary or sufficiently specific joint-pressure rule. Here is the missing premise.” Show actual captured tool order; do not present the editorial guide as a live model transcript. |
| 1:45–2:10 | The verdict | “The pressure changes are real. The claimed root cause is not established. Moving the slider changes the viewer, not what Muse saw or concluded. There is no verified discriminating test in this registry; request the applicable tag map and validated differential procedure instead of inventing one.” |
| 2:10–2:40 | Select example 02; go to The verdict / optional provenance | “A careful auditor also accepts a limited valid comparison. These two directions match a documented fault-2 example. Muse supports that comparison without upgrading it into proof of valve closure.” |
| 2:40–3:00 | Evidence & provenance; briefly show source and overlap | “These are genuine captured model outputs. Analogue matches have unequal overlap, and source citations do not certify physical truth. Live integration is separate and cost-bounded; independent engineering review remains pending.” |

Judges should understand the well, sensor meaning, observed change, suggested
failure and missing causal premise without knowing the original sensor IDs.
Friendly names are primary; identifiers, units and source provenance remain
inspectable. Keep the original statistical diagnosis unchanged. Do not present
the constructed claims as real expert diagnoses or the endpoint chart as a full
sensor timeline. See [the inventory and mapping guarantees](guided-investigation.md).

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
