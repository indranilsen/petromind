"""Versioned atomic propositions and composite aggregation for future live runs.

Structural scope checks are not an independent physical entailment verifier.
Legacy captured results are never passed through this contract for regrading.
"""

from . import reliable_auditor as v4
from .reliable_auditor import DOCUMENTS, run_active_auditor, run_scope_auditor  # noqa: F401

VERSION = "claim-auditor-v5-active-atomic"
SCOPE_VERSION = "claim-auditor-v5-scope-atomic"
ATOMIC_VERDICTS = ["SUPPORTED", "NOT_ESTABLISHED", "CONTRADICTED"]
GUIDANCE = """
ATOMIC SCOPE CONTRACT v5: Each finding evaluates ONE independently testable proposition.
Use measured_observation for a measured fact; documented_comparison for what a specific
source example establishes; diagnostic_conclusion for the inference to a physical cause.
Do not combine a pressure observation and a claimed cause in one finding. Atomic verdicts
are SUPPORTED, NOT_ESTABLISHED or CONTRADICTED. PARTIALLY_SUPPORTED is OVERALL ONLY.
Supported measurements and an unestablished cause yield overall PARTIALLY_SUPPORTED;
this does not mean partial proof of that cause. All supported => SUPPORTED; all
unestablished => NOT_ESTABLISHED; any contradicted conjunct => CONTRADICTED.
The schema has no declared disjunctions: overall verdict summarizes the conjunction
of the listed propositions, not the probability of a fault or the true incident label.
A published fault-8 production-line example can support a limited pressure-pattern
comparison. It is NOT evidence establishing fault-9 service-line hydrate. Match only
features actually observed; do not imply an unobserved downstream response was checked.
Necessity (fault implies pattern) is distinct from sufficiency (pattern implies fault).
No verified fault-discriminating causal rules are supplied in the current registry.
Therefore this registry cannot substantiate a SUPPORTED diagnostic_conclusion. State
the specific missing premise instead of upgrading similarity or a mechanism description
to proof. CONTRADICTED still requires actual contrary evidence; absence is not falsity.
Never change findings to match a desired overall verdict; use the aggregation rule.
"""
INSTRUCTIONS = v4.INSTRUCTIONS + GUIDANCE
SCOPE_INSTRUCTIONS = v4.SCOPE_INSTRUCTIONS + GUIDANCE


def _tools(result):
    finding = result[-1]["parameters"]["properties"]["findings"]["items"]
    finding["properties"]["verdict"]["enum"] = ATOMIC_VERDICTS[:]
    finding["properties"]["statement"]["description"] = (
        "One atomic proposition within the stated scope; separate observations from cause."
    )
    result[-1]["parameters"]["properties"]["verdict"]["description"] = (
        "Composite conjunction: any CONTRADICTED => CONTRADICTED; all SUPPORTED => SUPPORTED; "
        "all NOT_ESTABLISHED => NOT_ESTABLISHED; otherwise PARTIALLY_SUPPORTED."
    )
    return result


def active_tools():
    return _tools(v4.active_tools())


def scope_tools(grounded=True):
    return _tools(v4.scope_tools(grounded))


def aggregate_verdict(verdicts):
    """Explicit conjunction policy over nonempty atomic verdicts, not physics."""
    if not verdicts or any(v not in ATOMIC_VERDICTS for v in verdicts):
        raise ValueError("Expected nonempty atomic verdicts")
    if "CONTRADICTED" in verdicts:
        return "CONTRADICTED"
    if all(v == "SUPPORTED" for v in verdicts):
        return "SUPPORTED"
    if all(v == "NOT_ESTABLISHED" for v in verdicts):
        return "NOT_ESTABLISHED"
    return "PARTIALLY_SUPPORTED"


class AtomicContract:
    def _validate_overall(self, args):
        for i, f in enumerate(args["findings"]):
            if f["verdict"] not in ATOMIC_VERDICTS:
                return (
                    "atomic_verdict_required",
                    f"findings[{i}].verdict",
                    (
                        "Assess one proposition as SUPPORTED, NOT_ESTABLISHED or CONTRADICTED. "
                        "Split a composite finding into observations, source comparisons and causal conclusions; "
                        "PARTIALLY_SUPPORTED is an overall verdict only."
                    ),
                )
        expected = aggregate_verdict([f["verdict"] for f in args["findings"]])
        if args["verdict"] != expected:
            return (
                "inconsistent_overall_verdict",
                "verdict",
                (
                    f"For this conjunction of atomic findings use {expected}. "
                    "Do not change individual findings to match an overall label."
                ),
            )
        return None

    def _validate(self, args):
        error = super()._validate(args)
        if error:
            return error
        for i, f in enumerate(args["findings"]):
            field = f"findings[{i}]"
            if f["verdict"] == "SUPPORTED":
                if f["scope"] == "diagnostic_conclusion":
                    return (
                        "verified_causal_rule_unavailable",
                        field + ".verdict",
                        (
                            "The supplied registry has no verified fault-discriminating causal rule. "
                            "A measurement, mechanism description, example from any fault (including fault 8), "
                            "or historical analogue cannot establish fault 9 or another root cause. "
                            "Separate supported facts from the unestablished causal conclusion."
                        ),
                    )
                expected = {
                    "measured_observation": "measurement",
                    "documented_comparison": "documented",
                }[f["scope"]]
                if f["basis"] != expected:
                    return (
                        "scope_basis_mismatch",
                        field + ".basis",
                        f"Use {expected} basis for a supported {f['scope']}; keep hypotheses and correlations separate.",
                    )
        return None


class ScopeAuditSession(AtomicContract, v4.ScopeAuditSession):
    contract_version = SCOPE_VERSION
    model_instructions = SCOPE_INSTRUCTIONS

    def model_tools(self):
        return scope_tools(self.grounded)


class ActiveAuditSession(AtomicContract, v4.ActiveAuditSession):
    contract_version = VERSION
    model_instructions = INSTRUCTIONS

    def model_tools(self):
        return active_tools()
