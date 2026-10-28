# M4 v2: alternative-field failure and contract disclosure

Offline inspection of the user-supplied archive made zero API requests and changed
no protocol, result or trace. Protocol:
`f7b5f8fd388a0e791e270b76199828ce16edbb58b007251cd1d51aef02118b2b`.
Archive SHA-256:
`81b5228a5b470d47b883868e3a1b07afc2900b069b19c41a7519e14dd52f6bc7`.
All eight supplied audit snapshots independently verify.

## What the records establish

All six Muse investigations failed; both local baseline conditions completed.
Known usage totals $0.3207402 across 34 requests. The bounded repair behavior
terminated all runs within five or six requests. There were 15 rejected assessment
attempts: nine `invalid_alternative`, three `alternative_requires_support`, and
three `repeated_invalid_submission`.

Every first assessment failed `alternative_fault_type` validation. Three runs
repeated an invalid submission; three changed their submission and eventually
reached the missing-support check for an alternative, then exhausted repairs.
That later code occurs after citation checks, so at least those submissions
progressed past basic claim/source validation. It does not prove physical merit.

There were **zero graph and zero retrieval calls**. This run cannot establish any
equipment-graph or historical-retrieval contribution. It also produces no accepted
assessment on which to judge fault-challenging capability.

## What the records do not establish

The original `invalid_alternative` code conflates an alternative on a non-CHALLENGE
decision, wrong Python type, out-of-range value and equality to the baseline.
Rejected payloads were intentionally not retained. We cannot reconstruct which
of those conditions occurred, the proposed value, or the model's private intent.
Do not describe a particular branch as the proven cause of all six failures.

## Two independently reproducible framework problems

First, the enforced alternative-support condition was not adequately disclosed
before submission: the `alternative_fault_type` schema had no description of the
requirement for a separate supporting claim targeting that alternative. The
main instructions allowed an alternative but did not spell out that structural
rule. Models could discover it only after other validation errors were resolved.
This is a model-facing contract gap, not a need to increase repair limits.

Second, Python `type(value) is int` rejected `2.0` and `1.0` as fault identifiers,
although the tool schema declares JSON Schema `integer`, which accepts integral
numeric representations. This mismatch is reproducible offline. The saved traces
do NOT establish that Muse used these representations in the historical runs.
See the [JSON Schema numeric definition](https://json-schema.org/understanding-json-schema/reference/numeric).

## Focused correction: contract v2.1

- Describe decision constraints, optional JSON null, baseline contradiction,
  separate alternative support, and conflicting evidence directly in the tool
  schema BEFORE a submission. This is contract disclosure, not new diagnostic
  domain knowledge. The original diagnostic instruction text remains unchanged.
- Split alternative failures into decision incompatibility, wrong type, range,
  fractional number and baseline equality codes with specific correction text.
- Preserve only safe type/predicate diagnostics: JSON type, integrality,
  public-taxonomy range, decision compatibility and equality to the public
  baseline prediction. No raw alternative value, target truth, rejected prose
  or unqueried measurement is exported.
- On an invalid repeat, preserve the underlying safe validation code and field,
  not just a generic duplicate code.
- Accept and normalize whole-number fault IDs such as `2.0` to integer `2`.
  Strings, booleans, fractional values, nonfinite values and IDs outside 1–9
  remain invalid. Measured sensor readings are not normalized or rounded.
- Retain exact citation, provenance, alternative-support, consistency and
  two-repair rules. No failure is relabeled INSUFFICIENT_EVIDENCE and no baseline
  prediction is overridden.
- New source/contract version requires a NEW protocol. Preserve both prior runs;
  do not rescore them as if they had used this correction, selectively retry a
  condition or copy old outcomes into a new protocol.

The correction is covered by offline regression and mocked-transport tests. No
post-fix live experiment has run and no diagnostic improvement is claimed. Review
this correction before authorizing further spending. The domain grounding gaps
and required expert review documented in the v1 analysis remain unresolved.
