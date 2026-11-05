# PetroMind — Beyond Prediction, Toward Understanding: recording plan

The three-minute edit below is an editorial target, **not a verified contest
video-duration rule**. Confirm the signed-in submission form's limit before
recording/exporting the final version. No final video is included in this PR.

Record at 1440×900 with browser notifications off and readable page zoom. Keep the
replay badge visible when establishing the mode. Record one uninterrupted
investigation pass before editing; do not splice evidence from different runs.
Use only the actual imported/captured findings in narration. The early setup
belongs off camera. Reserve about half the video for the investigation and its
payoff. Export in the format accepted by the actual submission form, then check
video playback and link access in a signed-out browser.

Use the [readiness runbook](hackathon-readiness.md) to prepare the recorded bundle,
check inputs, and start the app before recording. The recommended presentation
uses the [verified saved v5 investigation](saved-v5-replay.md) when explicitly imported.
Otherwise use the original frozen captured recording and identify it accurately. Declare that mode once and keep its badge
visible. Do not call captured activity a new live execution.

| Time | Action | Suggested narration |
| --- | --- | --- |
| 0:00–0:20 | Home → Demo. Begin with the first recorded sample. | “PetroMind explores whether AI can move beyond recognizing anomalies to investigating their physical causes. Our primary demo uses real Petrobras oil-well sensor measurements and Meta Muse Spark. A prediction is not a proven cause.” |
| 0:20–0:40 | Play briefly, then click Jump to recorded alert. | “This is real Petrobras 3W telemetry. Sensors update from recorded samples, including missing readings. Our fixed monitor detected sustained pressure deviation against its earlier measured reference. It is a demonstration heuristic, not a validated industrial alarm.” |
| 0:40–0:55 | Show evidence accumulation, then click Continue to classifier. | “An anomaly does not identify a fault. The original 600-sample diagnosis window must finish; we have not moved it to manufacture an early prediction.” |
| 0:55–1:15 | Show the four handoff cards: alert, classifier, why investigate, and continue. | “The statistical machine-learning classifier proposed service-line hydrate—ice-like material that can restrict flow. The recorded pressures rose. That still does not establish what caused the change.” |
| 1:15–1:45 | Choose the recorded mode, then click Investigate with Muse Spark. Let automatic replay unfold. | “This is a genuine previously recorded Muse investigation. Muse received its fixed, budgeted summaries—not all the telemetry the viewer can explore. These are actual public tool records, not a private reasoning transcript.” |
| 1:45–2:10 | Pause on returned facts; show the focused graph and inspect one source. Use Show all evidence only if asked. | “Muse queried documented engineering context and compared permitted training incidents. The graph shows the actual returned facts and cited evidence. Generic equipment associations are not the installed topology of this particular well. Similarity is not causal proof.” |
| 2:10–2:40 | Resume; read the concise measured/documented/causal takeaway. Expand one missing premise. | “Muse accepts the measured increases but identifies the unsupported step: no supplied verified criterion establishes that this pressure pattern specifically proves hydrate. We need applicable documentation or validated discriminating evidence, not a more confident explanation.” |
| 2:40–3:00 | Briefly show the second captured case or Technology results. | “The second audit supports a narrow comparison with a published pressure-pattern example, without turning that match into root cause. The adaptive statistical sensor-selection baseline achieved 20/33; it did not use Muse or GraphRAG. Muse’s role here is auditable evidence investigation and uncertainty, not a claimed classification improvement.” |

A 50-minute historical clip cannot play in full during a three-minute walkthrough.
Scrubbing is honest navigation through recorded samples, not invented time-series
behavior. Replay speed is 10×; model-record pacing is editorial and labeled.
Sensor colors show relative change, not danger. The first clip's monitor fires
well before the annotation, so **do not describe it as verified early fault detection**.

## Network or API failure fallback (15 seconds)

Show the actual failure notice; never replace it silently. Say:

> “The live call did not complete. I’m switching to a previously recorded Muse run
> over these same fixed inputs. This is captured playback, not a new live answer.”

Select Saved verified v5 investigation if imported, otherwise Original captured investigation, and click Investigate. The original captured events
and verdict remain unchanged. Do not imitate live token timing or manufacture a
successful tool call. Do not initiate another paid attempt during a recorded demo
unless separately authorized and cost-capped. The reliable submission recording
can use captured mode throughout. After the authorized bundles and app are
installed locally, replay needs no Meta API connection.

## Before pressing Record

- Validate the full recorded journey with `demo_claim_audit.py check --capture ...
  --monitoring ...`; the runbook supplies complete commands.
- Confirm the chosen mode. Keep Home / Demo / Extension / Technology and Operator Console /
  Inside Muse, not a debug console, as the visible product.
- Know the two computed alert positions (14:32 / 31:02) and original diagnosis
  readiness (39:59). Do not show private annotation labels or incident paths.
- Check the source dialog and final assessment on the actual recording machine.
- Keep screenshots / a recorded walkthrough available as fallback, clearly labeled.
- Never expose the API key, private source protocol, hidden target label or raw
  evaluator filename in the video or public repository.

For a verified saved v5 run, explain the two causal questions in one sentence:
“A pattern can fit an example without identifying its cause; whether that fault
always produces the pattern is a separate question.” Only report the verdicts
actually recorded for those questions. Never advertise the expected five-finding
example as verified until the local import and inspection succeed.

## Optional Extension shot

Show `/extension` only as a separate **Demo Extension · Synthetic Physics Scenario**.
Its controlled pressure/flow/resistance example illustrates reasoning under the
supplied model, not real Petrobras telemetry or validation of the 33-incident study.
Keep its recorded mode and material-identity limitation visible. The primary
industrial story remains the real-data `/demo`.

Use the [current submission copy](hackathon-submission.md) for names and claims.
The 20/33 result must not be narrated as “Muse with Sensors + GraphRAG”; its
statistical implementation is documented in the [evaluation definitions](evaluation.md#compared-configurations).
