"""Fresh live-only v4 recommendation contract; frozen v1/v2/v3 remain unchanged."""

from copy import deepcopy

from .active_auditor import INSTRUCTIONS as V3_INSTRUCTIONS
from .active_auditor import ActiveAuditSession as V3Session
from .active_auditor import active_tools as v3_tools
from .agent import AgentConfig, _arguments, run_tool_agent
from .audit import canonical
from .claim_auditor import ClaimAuditSession
from .diagnostic_tests import REGISTRY
from .knowledge import SENSORS
from .scope_auditor import DOCUMENTS
from .scope_auditor import INSTRUCTIONS as V2_INSTRUCTIONS
from .scope_auditor import ScopeAuditSession as V2Session
from .scope_auditor import scope_tools as v2_tools

VERSION = "claim-auditor-v4-active-recommendations"
SCOPE_VERSION = "claim-auditor-v4-scope-recommendations"
TARGETS = {
    "none": [""],
    "document": sorted(DOCUMENTS),
    "sensor": sorted(SENSORS),
    "descriptive_test": sorted(REGISTRY),
    "no_verified_discriminating_test": [f"fault:{i}" for i in range(1, 10)],
}
EXAMPLES = {
    "none": {"kind": "none", "target": "", "purpose": ""},
    "document": {
        "kind": "document",
        "target": "well:tag_map",
        "purpose": "Request the approved well-specific sensor tag mapping; it is not supplied.",
    },
    "sensor": {
        "kind": "sensor",
        "target": "P-TPT",
        "purpose": "Inspect tree pressure; this recommendation is not a measurement or a fault-specific test.",
    },
    "descriptive_test": {
        "kind": "descriptive_test",
        "target": "paired_pressure_trends",
        "purpose": "Compare measured trends; this does not establish a physical cause.",
    },
    "no_verified_discriminating_test": {
        "kind": "no_verified_discriminating_test",
        "target": "fault:9",
        "purpose": "No verified discriminating test is supplied for this proposed fault.",
    },
}
GUIDANCE = """
RECOMMENDATION CONTRACT v4: next_evidence is exactly {kind, target, purpose}.
Use the exact catalog IDs supplied in recommendation_targets, not citation IDs, URLs or prose.
For kind none, BOTH target and purpose must be empty strings. A SUPPORTED finding
has missing_premise empty and next_evidence {"kind":"none","target":"","purpose":""}.
For every other kind, purpose must be nonempty and target must belong to that kind's catalog.
For no_verified_discriminating_test, target is a public fault ID such as fault:9.
Examples are syntax illustrations, not prescribed findings or evidence. Choose only what your
assessment justifies. Validation errors identify the field and allowed syntax; repair the submission
without inventing evidence or changing the scientific conclusion to satisfy the interface.
"""
INSTRUCTIONS = V3_INSTRUCTIONS + GUIDANCE
SCOPE_INSTRUCTIONS = V2_INSTRUCTIONS + GUIDANCE


def _tools(result):
    n = result[-1]["parameters"]["properties"]["findings"]["items"]["properties"][
        "next_evidence"
    ]
    n["properties"]["target"]["enum"] = sorted(
        {t for values in TARGETS.values() for t in values}
    )
    n["properties"]["target"]["description"] = (
        "Exact ID from the selected kind's recommendation_targets catalog; empty only for none."
    )
    n["properties"]["purpose"]["description"] = (
        "Empty only for kind none; otherwise a concise public purpose (not an executed test)."
    )
    return result


def active_tools():
    return _tools(v3_tools())


def scope_tools(grounded=True):
    return _tools(v2_tools(grounded))


def _recommendation_error(f, field):
    n = f.get("next_evidence")
    if not isinstance(n, dict) or set(n) != {"kind", "target", "purpose"}:
        return (
            "invalid_next_evidence_shape",
            field,
            "Supply exactly kind, target and purpose, each a string.",
        )
    for key in ("kind", "target", "purpose"):
        if not isinstance(n[key], str):
            return "invalid_next_evidence_type", field + "." + key, "Supply a string."
    kind, target, purpose = (n[k] for k in ("kind", "target", "purpose"))
    if kind not in TARGETS:
        return (
            "invalid_next_kind",
            field + ".kind",
            "Choose one of: " + ", ".join(TARGETS),
        )
    if len(target) > 120:
        return (
            "next_target_too_long",
            field + ".target",
            "Use an exact catalog ID of at most 120 characters.",
        )
    if len(purpose) > 350:
        return (
            "next_purpose_too_long",
            field + ".purpose",
            "Keep the public purpose within 350 characters.",
        )
    if kind == "none":
        if target != "":
            return (
                "none_target_must_be_empty",
                field + ".target",
                'For kind none, set target to "".',
            )
        if purpose != "":
            return (
                "none_purpose_must_be_empty",
                field + ".purpose",
                'For kind none, set purpose to "".',
            )
    elif target not in TARGETS[kind]:
        return (
            "unknown_next_target",
            field + ".target",
            "For kind "
            + kind
            + ", choose an exact target: "
            + ", ".join(TARGETS[kind]),
        )
    elif not purpose.strip():
        return (
            "missing_next_purpose",
            field + ".purpose",
            "State a nonempty public purpose for this recommendation; do not claim it was executed.",
        )
    return None


class RecommendationContract:
    """Structural validation only, with no echoed rejected text or implicit repair."""

    def _validate(self, args):
        findings = args.get("findings")
        if isinstance(findings, list):
            for i, f in enumerate(findings):
                if isinstance(f, dict):
                    error = _recommendation_error(f, f"findings[{i}].next_evidence")
                    if error:
                        return error
        return super()._validate(args)

    def _error(self, tool, args, code, field, correction):
        # Only fixed vocabulary, types, lengths and membership flags. Never echo
        # target/purpose/statement text, private paths, labels or model reasoning.
        self._safe_rejection = None
        if tool == "submit_audit" and isinstance(args, dict):
            findings = args.get("findings")
            if isinstance(findings, list) and field.startswith("findings["):
                index = int(field.split("[", 1)[1].split("]", 1)[0])
                if index < len(findings) and isinstance(findings[index], dict):
                    n = findings[index].get("next_evidence")
                    if isinstance(n, dict):
                        kind = n.get("kind")
                        known = isinstance(kind, str) and kind in TARGETS
                        self._safe_rejection = {
                            "kind": kind if known else "unrecognized",
                            "target_is_string": isinstance(n.get("target"), str),
                            "target_in_kind_catalog": known
                            and n.get("target") in TARGETS[kind],
                            "purpose_is_string": isinstance(n.get("purpose"), str),
                            "purpose_nonempty": isinstance(n.get("purpose"), str)
                            and bool(n["purpose"].strip()),
                        }
        try:
            return super()._error(tool, args, code, field, correction)
        finally:
            self._safe_rejection = None

    def _record(self, tool, args, result):
        if tool == "submit_audit":
            if "error" not in result:
                result = {**result, "contract_version": self.contract_version}
                self.result = deepcopy(result)
                return ClaimAuditSession._record(self, tool, args, result)
            if getattr(self, "_safe_rejection", None) is not None:
                result = deepcopy(result)
                result["error"]["diagnostics"] = self._safe_rejection
                kind = self._safe_rejection["kind"]
                if kind in EXAMPLES:
                    result["error"]["syntax_example"] = EXAMPLES[kind]
        return super()._record(tool, args, result)


class ActiveAuditSession(RecommendationContract, V3Session):
    contract_version = VERSION


class ScopeAuditSession(RecommendationContract, V2Session):
    contract_version = SCOPE_VERSION


def _run(session, client, config, on_event, on_tool_request, active):
    context = {
        **session.packet,
        "sensor_budget": 5,
        "remaining_budget": session.remaining_budget,
        "measurement_citation_ids": {
            s: "measurement:" + s for s in session.packet["observations"]
        },
        "recommendation_documents": DOCUMENTS,
        "recommendation_sensors": list(SENSORS),
        "recommendation_targets": TARGETS,
        "recommendation_syntax_examples": EXAMPLES,
        "verified_discriminating_tests": [],
        "descriptive_tests": [
            {
                **r.public(False),
                "interpretation": "Descriptive only; no verified fault-discriminating test.",
            }
            for r in REGISTRY.values()
        ],
        "history_scope": "Frozen training-only snapshot using initial observations; not reranked by additional queries.",
    }
    if session.grounded:
        context["knowledge_topics"] = session.topics()
    return run_tool_agent(
        session,
        client,
        config
        or AgentConfig(
            max_turns=6, max_tool_calls=8, max_output_tokens=4096, variant="sensor_only"
        ),
        instructions=getattr(
            session,
            "model_instructions",
            INSTRUCTIONS if active else SCOPE_INSTRUCTIONS,
        ),
        tools=(
            session.model_tools()
            if hasattr(session, "model_tools")
            else active_tools()
            if active
            else scope_tools(session.grounded)
        ),
        initial_history=[
            {
                "role": "user",
                "content": [{"type": "input_text", "text": canonical(context)}],
            }
        ],
        prompt_version=session.contract_version,
        on_event=on_event,
        on_tool_request=on_tool_request,
        submission_reason="claim_audit_submitted",
        is_complete=lambda: session.result is not None,
        stop_reason=lambda: session.stop,
        decode_arguments=lambda _, s: _arguments(s),
    )


def run_active_auditor(
    session, client, config=None, on_event=None, on_tool_request=None
):
    return _run(session, client, config, on_event, on_tool_request, True)


def run_scope_auditor(
    session, client, config=None, on_event=None, on_tool_request=None
):
    return _run(session, client, config, on_event, on_tool_request, False)
