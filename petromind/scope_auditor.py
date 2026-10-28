"""Scope-aware v2 contract. v1 prompts, sessions and captured outputs stay intact."""

from __future__ import annotations

from copy import deepcopy

from .agent import AgentConfig, _arguments, run_tool_agent
from .audit import canonical
from .claim_auditor import INSTRUCTIONS as V1_INSTRUCTIONS
from .claim_auditor import ClaimAuditSession, tools
from .diagnostic_tests import REGISTRY
from .knowledge import SENSORS

VERSION = "claim-auditor-v2-scope"
DOCUMENTS = {
    "authors:figure3": {
        "source": "https://arxiv.org/html/2507.01048v1",
        "locator": "Figure 3 caption",
        "available": "public documented example, not a universal rule",
    },
    "authors:table3": {
        "source": "https://arxiv.org/html/2507.01048v1",
        "locator": "Table 3",
        "available": "public generic ESTADO valve-code semantics; not an actual valve reading",
    },
    "well:tag_map": {
        "source": None,
        "locator": "Approved well-specific schematic and sensor tag mapping",
        "available": "not supplied; request from operator",
    },
    "well:DHSV_log": {
        "source": None,
        "locator": "Time-aligned DHSV instrument-state and operating log",
        "available": "not supplied; must not substitute dataset class/state labels",
    },
    "well:service_line_layout": {
        "source": None,
        "locator": "Approved well-specific service-line schematic",
        "available": "not supplied; request from operator",
    },
    "well:differential_procedure": {
        "source": None,
        "locator": "Validated well-specific fault-isolation procedure",
        "available": "not supplied; existence and adequacy unverified",
    },
}
INSTRUCTIONS = (
    V1_INSTRUCTIONS
    + """
SCOPE REFINEMENT v2: Each finding has scope measured_observation, documented_comparison, or
 diagnostic_conclusion. Keep a comparison to a published example separate from proof of its cause.
SUPPORTED means supported at the stated scope. Do not demand generalizability to establish a
limited example comparison. For a supported finding, leave missing_premise empty and next_evidence
kind none; put premises needed for a stronger causal claim in a separate diagnostic_conclusion finding.
Compatible with is not established by. A rule absent from retrieved documents is not proved false
or proved absent from all engineering knowledge. Do not count analogues with unequal sensor overlap
as equivalent corroboration; name matched_sensors/shared_sensors explicitly.
Choose a concrete next_evidence target from the supplied document, sensor or descriptive-test catalog.
A proposed document is not an existing verified document. A descriptive computation is not a verified
discriminating test. No fault-discriminating tests are verified in this registry: say
no_verified_discriminating_test when no documented test resolves the diagnostic uncertainty.
ESTADO code semantics describe encoded readings, not confirmed actuator positions. No unobserved
valve state, operational label or future measurement may be inferred. Recommendations are proposals,
not tool executions, and do not override the baseline. Return concise public justifications only."""
)


def scope_tools(grounded=True):
    result = deepcopy(tools(grounded))
    finding = result[-1]["parameters"]["properties"]["findings"]["items"]
    finding["properties"]["scope"] = {
        "type": "string",
        "enum": [
            "measured_observation",
            "documented_comparison",
            "diagnostic_conclusion",
        ],
    }
    finding["required"].append("scope")
    finding["properties"]["next_evidence"] = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "kind": {
                "type": "string",
                "enum": [
                    "none",
                    "document",
                    "sensor",
                    "descriptive_test",
                    "no_verified_discriminating_test",
                ],
            },
            "target": {"type": "string", "maxLength": 120},
            "purpose": {"type": "string", "maxLength": 350},
        },
        "required": ["kind", "target", "purpose"],
    }
    return result


class ScopeAuditSession(ClaimAuditSession):
    def _validate(self, a):
        if not isinstance(a.get("findings"), list):
            return super()._validate(a)
        translated = deepcopy(a)
        for i, f in enumerate(a["findings"]):
            field = f"findings[{i}]"
            if not isinstance(f, dict) or f.get("scope") not in [
                "measured_observation",
                "documented_comparison",
                "diagnostic_conclusion",
            ]:
                return (
                    "invalid_scope",
                    field + ".scope",
                    "Choose an observation, documented comparison or diagnostic conclusion scope.",
                )
            n = f.get("next_evidence")
            if (
                not isinstance(n, dict)
                or set(n) != {"kind", "target", "purpose"}
                or any(not isinstance(v, str) for v in n.values())
            ):
                return (
                    "invalid_next_evidence",
                    field + ".next_evidence",
                    "Use kind, target and purpose from the small recommendation schema.",
                )
            kind, target, purpose = n["kind"], n["target"], n["purpose"]
            if len(target) > 120 or len(purpose) > 350:
                return (
                    "invalid_next_evidence",
                    field + ".next_evidence",
                    "Keep target and purpose concise.",
                )
            allowed = {
                "document": DOCUMENTS,
                "sensor": SENSORS,
                "descriptive_test": REGISTRY,
            }
            valid = (
                (kind in allowed and target in allowed[kind] and bool(purpose.strip()))
                or (
                    kind == "no_verified_discriminating_test"
                    and target in {"fault:" + str(i) for i in range(1, 10)}
                    and bool(purpose.strip())
                )
                or (kind == "none" and target == "" and purpose == "")
            )
            if not valid:
                return (
                    "unknown_next_target",
                    field + ".next_evidence",
                    "Use a catalog target, or explicitly state no_verified_discriminating_test for a public fault ID.",
                )
            if f.get("verdict") == "SUPPORTED" and (
                f.get("missing_premise") != "" or kind != "none"
            ):
                return (
                    "scope_mismatch",
                    field,
                    "For this supported scope no evidence is missing. Put the stronger unestablished conclusion in a separate finding.",
                )
            if (
                f.get("verdict") in ["NOT_ESTABLISHED", "PARTIALLY_SUPPORTED"]
                and kind == "none"
            ):
                return (
                    "missing_next_evidence",
                    field + ".next_evidence",
                    "Name a concrete target or state no verified discriminating test.",
                )
            translated["findings"][i].pop("scope")
            translated["findings"][i]["next_evidence"] = (
                purpose if kind != "none" else ""
            )
        return super()._validate(translated)

    def _record(self, tool, args, result):
        if tool == "submit_audit" and "error" not in result:
            result = {**result, "contract_version": VERSION}
            self.result = deepcopy(result)
        return super()._record(tool, args, result)


def run_scope_auditor(session, client, config=None, on_event=None):
    config = config or AgentConfig(
        max_turns=6, max_tool_calls=8, max_output_tokens=4096, variant="sensor_only"
    )
    context = {
        **session.packet,
        "remaining_budget": session.remaining_budget,
        "sensor_budget": 5,
        "measurement_citation_ids": {
            s: "measurement:" + s for s in session.packet["observations"]
        },
        "recommendation_documents": DOCUMENTS,
        "recommendation_sensors": list(SENSORS),
        "descriptive_tests": [
            {
                **r.public(False),
                "interpretation": "Descriptive computation only; no verified fault-discriminating test.",
            }
            for r in REGISTRY.values()
        ],
        "verified_discriminating_tests": [],
    }
    if session.grounded:
        context["knowledge_topics"] = session.topics()
    return run_tool_agent(
        session,
        client,
        config,
        instructions=INSTRUCTIONS,
        tools=scope_tools(session.grounded),
        initial_history=[
            {
                "role": "user",
                "content": [{"type": "input_text", "text": canonical(context)}],
            }
        ],
        prompt_version=VERSION,
        on_event=on_event,
        submission_reason="claim_audit_submitted",
        is_complete=lambda: session.result is not None,
        stop_reason=lambda: session.stop,
        decode_arguments=lambda _, s: _arguments(s),
    )
