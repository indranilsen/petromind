# Frozen scoring protocol — synthetic-physics-v1.1

Register this protocol and case/input/answer-key digests before running any model.
The seven cases are dependent variants of ONE incident. Report case and atomic
results; do not claim population accuracy or seven independent trials. Do not
select cases, thresholds, verdicts or retrieval policies using model outcomes.

The model receives only a public packet and serialized tool results. Evaluators
receive the immutable transcript and separate answer key after the run. Scoring
never sends reference verdicts, numeric simulation parameters or private metadata
to a model. Agent processes must not mount the repository, private archive or
trusted host process. An adapter object alone is not a security sandbox.

| Dimension | Points | Full / partial / zero credit |
|---|---:|---|
| Measurement correctness | 12 | Two correct, time-aligned endpoint observations with units and error bounds / one / none or fabricated measurement |
| Availability | 5 | Correctly treats missing, frozen and unverified-calibration channels / one material omission / invents availability or treats missing as zero |
| Citation accuracy | 8 | 4 mechanical points: all cited IDs actually received and citations nonempty; 4 review points: cited statements are entailed at their stated scope / half for minor imprecision / fabricated citation or material misattribution |
| Document scope | 8 | Separates an example, generic meaning and model premise from incident truth / states limit without applying it / transfers example as proof |
| Atomic verdicts | 20 | Macro recall over the three reference labels, weighted equally across labels; exact literal atomic statement mapping; missing or invalid submissions are wrong |
| Causal leaps | 8 | All causal propositions bounded by evidence / incomplete qualification / unsupported certainty |
| Missing premises | 6 | Names a concrete missing measurement, calibration or material premise and its inferential role / concrete premise without role / generic review request |
| Historical analogue | 5 | Names overlap and missing discriminators and avoids identity inference / warns about similarity only / treats similarity score as causal probability |
| Hypothesis comparison | 6 | At least two mechanisms compared against actual evidence, including a counterprediction / two named only / one asserted cause |
| Sensor acquisition | 8 | Requests a discriminating sensor when required, cites its role, no unavailable/frozen/unneeded request / relevant redundant request or recommendation without acquisition / wastes all remaining slots or fails required acquisition |
| Necessity and sufficiency | 6 | Distinguishes fixed-condition implication, converse and material non-identifiability / only compatibility language / invalid converse or universal signature |
| Structured output | 5 | First valid submission / valid after at most two repairs earns 2.5 / none or limit exceeded |
| Cost/tool efficiency | 3 | Within 24 tool calls, <=2 repairs and declared pre-reserved API cap / 1.5 if bounded but redundant / overrun or missing accounting |

Review dimensions use fractions 0, 0.5, 1 only, with transcript receipt/sequence
references and a written justification. Two reviewers independently grade without
seeing model/method identity; resolve disagreements by documented adjudication.
The evaluator script computes atomic and structural metrics, then requires review
fractions for semantic dimensions. A missing review produces an incomplete total,
never automatic full credit. It verifies receipt membership but does not claim to
verify prose entailment. Deterministic evidence tests are necessary, not sufficient.

Atomic labels: SUPPORTED, NOT_ESTABLISHED, CONTRADICTED. The overall conjunction
is CONTRADICTED if any atom is contradicted, SUPPORTED if all supported,
NOT_ESTABLISHED if all unestablished, otherwise PARTIALLY_SUPPORTED. This overall
value is not a probability or partial identification of material.

Penalties (deduct after weighting, floor at zero): each distinct invented reading
or fabricated citation -15; unsupported causal certainty -10; ignoring a supplied
contradiction -10; transferring generic topology to a real well -10; correlation
as causation -10; each unavailable/frozen or irrelevant new sensor request -2.
Apply each distinct error once within a category; several categories can apply.
Invalid final structure scores zero atomic/structure points. Blanket abstention
has zero recall on supported and contradicted atoms and is capped at 40/100.
Always report supported and contradicted recall separately; a method is not a
successful reasoner unless each is >=0.8 and no fabricated evidence occurs.
A reference finding is wrong if required evidence was not acquired, even when its
verdict accidentally matches the answer key. Report these unsupported matches.

Freeze sensor thresholds, endpoint windows, error intervals and required evidence
in the private key. Use worst-case simultaneous intervals, not significance tests
or standard errors. Calibration-unverified measurements cannot establish a numeric
resistance even if their latent values happen to fit it.

For model comparisons, use paired identical cases, initial sensors, tool limits
and seeds. Log exact documents/edges returned, retrieval failures, sensor choices,
raw submissions, repairs, provider tokens and estimated cost. Separate retrieval
recall (needed evidence actually returned), verdict accuracy conditional on evidence,
and end-to-end performance. No model run has been made in this release.

Optional paid runs require a separate ledger with a $2 aggregate ceiling,
conservative input+maximum-output reservation BEFORE each request, bounded turns,
no uncontrolled parallel calls and <=2 repairs. No reservation can be reclaimed
without observed usage or a confirmed non-billable failure. Report provider billing
as unavailable unless obtained from provider records. Evaluation code here has no
API client or credential access; the baseline is offline and costs $0.
