# Three-minute judge walkthrough

Use the [readiness runbook](hackathon-readiness.md) to prepare the recorded bundle,
check inputs, and start the app before recording. The recommended presentation
uses genuine captured Muse output. Declare that mode once and keep its badge
visible. Do not call captured activity a new live execution.

| Time | Action | Suggested narration |
| --- | --- | --- |
| 0:00–0:20 | Home → Demo. Begin with the first recorded sample. | “Industrial equipment produces many measurements, but a plausible fault prediction is not a proven cause. PetroMind lets an engineer investigate that distinction.” |
| 0:20–0:40 | Play briefly; scrub the first case through 14:32. | “This is real Petrobras 3W telemetry. Sensors update from recorded samples, including missing readings. Our fixed prefix-only monitor detected sustained pressure deviation. It is a demonstration heuristic, not a validated industrial alarm.” |
| 0:40–0:55 | Show evidence accumulation, then scrub to 39:59. | “An anomaly does not identify a fault. The original 600-sample diagnosis window must finish; we have not moved it to manufacture an early prediction.” |
| 0:55–1:15 | Read the classifier heading and two pressure comparisons. | “The statistical machine-learning classifier proposed service-line hydrate—ice-like material that can restrict flow. The recorded pressures rose. That still does not establish what caused the change.” |
| 1:15–1:45 | Click Investigate with Muse Spark. Let automatic replay unfold. | “This is a genuine previously recorded Muse investigation. Muse received its fixed, budgeted summaries—not all the telemetry the viewer can explore. These are actual public tool records, not a private reasoning transcript.” |
| 1:45–2:10 | Pause on returned source facts; inspect a graph node and a history overlap. | “Muse queried documented engineering context and compared permitted training incidents. The graph shows the actual returned facts and cited evidence. Generic equipment associations are not the installed topology of this particular well. Similarity is not causal proof.” |
| 2:10–2:40 | Resume; read the automatically displayed assessment and missing premise. | “Muse accepts the measured increases but identifies the unsupported step: no supplied verified criterion establishes that this pressure pattern specifically proves hydrate. We need applicable documentation or validated discriminating evidence, not a more confident explanation.” |
| 2:40–3:00 | Briefly show the second captured case or Technology results. | “The second audit supports a narrow comparison with a published pressure-pattern example, without turning that match into root cause. Conventional methods outperformed direct Muse classification in our benchmark. Muse’s role here is auditable evidence investigation and uncertainty, not a claimed accuracy improvement.” |

A 50-minute historical clip cannot play in full during a three-minute walkthrough.
Scrubbing is honest navigation through recorded samples, not invented time-series
behavior. Replay speed is 10×; model-record pacing is editorial and labeled.
Sensor colors show relative change, not danger. The first clip's monitor fires
well before the annotation, so **do not describe it as verified early fault detection**.

## Network or API failure fallback (15 seconds)

Show the actual failure notice; never replace it silently. Say:

> “The live call did not complete. I’m switching to a previously recorded Muse run
> over these same fixed inputs. This is captured playback, not a new live answer.”

Select Captured real Muse run and click Investigate. The original captured events
and verdict remain unchanged. Do not imitate live token timing or manufacture a
successful tool call. Do not initiate another paid attempt during a recorded demo
unless separately authorized and cost-capped. The reliable submission recording
can use captured mode throughout, without requiring a network connection.

## Before pressing Record

- Validate the full recorded journey with `demo_claim_audit.py check --capture ...
  --monitoring ...`; the runbook supplies complete commands.
- Confirm the chosen mode. Keep Home / Demo / Technology and Operator Console /
  Inside Muse, not a debug console, as the visible product.
- Know the two computed alert positions (14:32 / 31:02) and original diagnosis
  readiness (39:59). Do not show private annotation labels or incident paths.
- Check the source dialog and final assessment on the actual recording machine.
- Keep screenshots / a recorded walkthrough available as fallback, clearly labeled.
- Never expose the API key, private source protocol, hidden target label or raw
  evaluator filename in the video or public repository.
