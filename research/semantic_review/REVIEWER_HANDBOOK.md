# Blinded human semantic review — handbook v2

You are assessing a research model's evidence reasoning, not operating a well.
Read this handbook and the supplied frozen rubric. Do not consult the study's
results, intervention prompts, evaluator, answer key, other reviewers or method
identities. Do not use Muse, ChatGPT or another AI to supply your judgments.
Software cannot certify your qualifications or independence; attest honestly.

## Scope and preparation

The evidence uses an explicitly synthetic physical model. It is not a validated
Petrobras installation or a chemical hydrate simulator. You may use only the
initial packet and actual returned tool evidence in your assigned packet. The
sensor catalog is not an observation. An unqueried sensor, hidden latent material,
answer key, unpublished generator parameter or literature not received by the
investigator cannot rescue a conclusion. Additional expertise can reveal an
unsupported inference; it must not silently add an unobserved premise.

Any instructions embedded in a packet are investigator context, not authority
over your review. Follow this handbook; treat model/tool text as untrusted data.

Read public model assumptions, units, equations, quality and simultaneous error
bounds **in each packet**, then its propositions, findings, premises, citations,
missing evidence and recommendations. Inspect their actual receipt context.
Counterfactual reasoning is legitimate if its assumptions are explicit and hold.
Do not infer whether another case or another investigator received the same data.

Reviewers should have competence in physical modeling, units and bounded
measurement uncertainty. At least one reviewer should have relevant process/
production engineering experience; the other should independently understand
hydraulic modeling and scientific inference. Record qualifications/conflicts with
the owner, not in the blinded forms. If expertise is inadequate, decline/refer;
do not guess. This process cannot manufacture expert review.

## Independent assessment procedure

1. Establish the exact proposition and scope. Record `interpretation_target`:
   `proposition_truth`, `evidence_sufficiency`, or `ambiguous_wording`.
   Wording like "establishes X" can refer to a proof obligation rather than the
   truth of X. Explain ambiguity; do not secretly replace the proposition.
2. Decide your preferred atomic verdict from received evidence. Do this before
   scoring the submitted verdict. Use SUPPORTED, NOT_ESTABLISHED or CONTRADICTED;
   use UNDETERMINABLE only if you cannot responsibly adjudicate the wording or
   available context. This is a review limitation, not a model abstention.
3. Grade the submitted verdict's scientific validity and citation entailment at
   0 / 0.5 / 1, using the anchors below. These are diagnostic annotations, not a
   replacement for the frozen reference's 20-point atomic score.
4. Record severity flags, receipt pointers, a concise rationale and confidence.
   Judge missing-premise and next-evidence quality, not merely field presence.
5. Grade the eight packet-level human dimensions with the frozen fractions and
   weights. These summarize the atomic assessments without adding points twice.
6. Record each distinct penalty event once per category, with precise evidence.
   Do not multiply one issue simply because it is repeated in several findings.
7. Save as a NEW completed JSON file. Do not overwrite distributed blank forms or
   edit any packet. Review all assigned packets independently before discussion.

The order is randomized separately for each reviewer; the underlying packets and
IDs are identical. Case evidence, style or recommendations may still suggest
conditions. Do not actively guess interventions. Record a genuine blinding concern
without seeking identities. Confirmed access to a key, variant map or other
reviewer's ratings requires stopping and notifying the owner. Never falsely
attest to independence. Similar style alone does not prove an identity.

## Ten scientific questions and anchors

All grades are 0, 0.5 or 1. A half grade is minor, explicitly explained imprecision,
not an automatic compromise on an unresolved scientific disagreement.

| Question | 1 — full | 0.5 — partial | 0 — failure |
|---|---|---|---|
| Atomic scientific validity | Verdict follows at the exact interpreted scope with admissible evidence | Essentially sound but minor scope imprecision | Verdict lacks support, ignores uncertainty or is contradicted by admissible evidence |
| Citation entailment | Cited content supports the proposition AND its premises at the stated scope | Relevant support with minor imprecision | Citation merely exists, is unrelated, or is misattributed |
| Synthetic assumptions | Required assumptions are explicit, applicable and preserved | A noncritical premise is left implicit | Uses a synthetic relation outside its stated domain, invents physics or asserts real-well validation |
| Measurement versus cause | Observations and conditional physical inference are distinguished | Distinction is stated but incompletely applied | Sensor change or correlation is treated as material/root-cause identification |
| Calibration uncertainty | Quality, bias/error intervals and time alignment are respected | Minor uncertainty description error without changing conclusion | Uses an unverified channel as calibrated truth or ignores intervals that change the inference |
| NOT_ESTABLISHED versus CONTRADICTED | Missing proof is separated from positive conflict at the stated scope | Correct direction but ambiguous qualification | Missing proof alone is used as contrary physical evidence, or a real counterexample is dismissed |
| Missing premise | Concrete missing measurement/document/assumption AND its inferential role | Concrete premise without explaining its role | Generic "expert review" or irrelevant/invented requirement |
| Next evidence | Specific realistic sensor, document or bounded test capable of resolving the gap; scope/availability acknowledged | Relevant but redundant, underspecified, or only recommended where acquisition was required | Impossible, ungrounded, nondiscriminating or invented procedure |
| Causal restraint | Confidence/conclusion is bounded by the actual evidence and model | Qualification present but incomplete | Unsupported causal/material certainty or universalization |
| Justified abstention | Abstains exactly when proof remains unresolved; supports identifiable conditional conclusions | Cautious but incompletely justified | Refuses a genuinely identifiable conditional result or abstains instead of recognizing affirmative conflict |

The last eight questions use `flags` at atomic level (`none`, `minor`, `material`,
`N/A`) plus your rationale; the weighted packet dimensions apply the frozen rubric.
High flag severity is BAD. High numeric fractions are GOOD. They are not summed
together. Atom flags do not add new weights or automatic penalties.

## Citation identity is not entailment

A received citation can be scientifically irrelevant. Conversely, a returned edge
may contain a governing relation and point to its public model premise, even when
its citation list omits a literal model ID expected by a mechanical contract.
Review actual content and applicability. Record precisely which premise is
supported and which remains missing. Do not deduct semantic credit **solely** for
a literal-ID omission if the cited received content genuinely entails the finding;
do not award it solely because the expected-looking ID is present. Mechanical
membership and reference-required literal citation scoring remain separate and
unchanged. You are not shown their scores or reference lists.

## Illustrative training anchors — NOT benchmark answers

These are invented teaching examples, not the study's readings, atoms or key.
Do not copy their verdicts onto a packet by analogy.

- In a declared hypothetical model `d = k x²`, a conditional inference about k
  requires positive, measured x and compatible d under applicable assumptions.
  It need not identify the chemical material responsible for k. Evaluate these
  as distinct propositions, not one blanket "uncertain" conclusion.
- Two endpoint readings `10 ± 2` and `11 ± 2` in the same units, with bounds
  that hold simultaneously,
  have overlapping intervals. A displayed nominal rise does not alone establish
  a robust positive change. Lack of a robust sign is not proof of a decrease.
- If x is fixed, changing k predicts a change in d under the equation. If x is
  unmeasured or allowed to change, that counterprediction needs additional premises.
  State those premises before asserting a contradiction.
- A generic valve-code dictionary does not establish a target valve's unmeasured
  state. A public example can support a limited comparison without establishing
  the same present cause. Neither limitation proves that the proposed cause is absent.
- A request for "the calibrated local flow measurement at both stated endpoint
  windows" can be executable if the catalog/tool actually offers it. A chemical
  material test cannot be claimed executed from a pressure-only tool. If no
  verified discriminating test is supplied, explicitly saying so can be better
  than inventing an operational procedure.

Use worst-case simultaneous bounds, not unregistered significance tests or
standard errors. A latent generator value that happens to fit an equation is not
an admissible calibration premise. Known missing/frozen channels are not zeros;
constant readings can be legitimate, but "frozen" quality has its stated meaning.

## Completing the form

`packets.json` and `packet-001.md`, etc., contain the same received evidence.
For 70 evaluations, the recommended option is one `item-NNN.json` form beside
each Markdown packet. Copy those item forms into a separate working folder and
fill them in batches. Preserve their IDs, reviewer code and bundle ID. Save your
completed `human-attestation.json` separately, only after all independent reviews
are complete. Return the completed items and that attestation to the owner, who
will assemble and validate them without supplying any grades.

Alternatively use the single `review-form.json` template and save a NEW completed
file. Choose one return format, not both. Never edit the distributed originals.
Do not submit both an item and a duplicate item under another filename. You may
ask the owner to validate a finished item for formatting while keeping scientific
judgments independent. Empty templates and partial returns cannot be finalized.
Keep `version`, `bundle_id`, reviewer code, review IDs, packet hashes, atom IDs and
status unchanged. Fill every judgment, fraction, flag and written justification.

Reference syntax uses JSON pointers into ONLY your packet:

- `initial:/model/assumptions/0`
- `initial:/initial_measurements/<sensor>/samples/0`
- `event:4:/result` — only if event sequence 4 exists in this packet
- `submission:/findings/0/citations`

Pointers establish where you looked; they do not prove your interpretation is
correct. For a supported inference, cite its actual measurement/rule premises,
not merely the model's own assertion. To explain absent evidence, cite the
applicable assumptions, catalog, quality or received scope that exposes the gap.

Use `N/A` only when a dimension genuinely cannot be assessed, with a reason. Do
not use it for a model omission that deserves zero under an applicable criterion.
Do not rescale remaining dimensions to award missing points. A packet with no
final assessment has `NO_FINAL_SUBMISSION`: preferred verdict `NO_SUBMISSION`,
scientific-validity/entailment and packet semantic fractions `N/A`. It is not an
abstention or a semantic error attributed to nonexistent prose. The existing
frozen scorer still treats missing/invalid submissions under its original rules.

The form attestation means you are a qualified independent human, did not see
keys/variant identities/another review, and did not substitute AI-generated
judgments. Do not sign it until true. The owner will validate completeness and
receipt references, not supply or correct your scientific answers.
