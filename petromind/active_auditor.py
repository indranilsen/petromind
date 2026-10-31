"""Opt-in v3: two additional, source-motivated summary queries, never raw replay.

The private window is supplied by the frozen development locator. This is a tool
boundary, not a sandbox; the model receives only serialized context/results.
"""

import json
from copy import deepcopy

from .agent import AgentConfig, _arguments, run_tool_agent
from .audit import canonical
from .claim_auditor import ClaimAuditSession
from .diagnostic_tests import REGISTRY
from .incident_replay import raw_payload
from .knowledge import SENSORS
from .scope_auditor import DOCUMENTS, ScopeAuditSession, scope_tools
from .scope_auditor import INSTRUCTIONS as V2_INSTRUCTIONS
from .session import DiagnosticSession

VERSION = "claim-auditor-v3-active-summaries"
INSTRUCTIONS = (
    V2_INSTRUCTIONS
    + """
ACTIVE SUMMARY EXTENSION v3: You may request additional sensor summaries from the
same fixed diagnostic window. Three inherited queries already count; there are
at most two remaining unique queries. Missing measurements cost a query too;
cached requests are free. No future or raw viewer samples are available.
Before requesting a sensor, use lookup_knowledge for that sensor and cite its
returned documented location fact in source_id. State a short public purpose
explaining relevance to a premise, not private reasoning. A generic association
is not verified well topology or proof that a sensor discriminates faults.
New measurement citations are measurement:<sensor>. Original captured evidence
and the statistical prediction remain unchanged. search_history is the frozen
training-only snapshot computed from INITIAL sensors only; added measurements
do not rerank it. You may abstain from additional queries when no defensible
measurement resolves the missing premise. Never force a causal conclusion.
"""
)


def active_tools():
    result = scope_tools()
    result.insert(
        2,
        {
            "type": "function",
            "name": "request_sensor",
            "description": "Query one documented sensor summary within the shared five-sensor budget. Cite its returned location fact and give a public purpose.",
            "strict": True,
            "parameters": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "sensor_name": {"type": "string", "enum": list(SENSORS)},
                    "source_id": {"type": "string"},
                    "purpose": {"type": "string", "minLength": 1, "maxLength": 240},
                },
                "required": ["sensor_name", "source_id", "purpose"],
            },
        },
    )
    return result


class ActiveAuditSession(ScopeAuditSession):
    def __init__(self, packet, window, *, history=()):
        raw_payload(
            window, {"observations": json.loads(canonical(packet["observations"]))}
        )
        super().__init__(packet, history=history)
        self._initial_sensors = tuple(self.packet["observations"])
        self._sensors = DiagnosticSession(
            window, SENSORS, budget=5, variant="sensor_only"
        )
        for sensor, expected in self.packet["observations"].items():
            result = self._sensors.get_sensor_history(sensor)
            if canonical(result["summary"]) != canonical(expected):
                raise ValueError("Initial evidence does not match the verified window")

    @property
    def remaining_budget(self):
        return self._sensors.remaining_budget

    @property
    def new_sensor_queries(self):
        return len(self._sensors.queries) - len(self._initial_sensors)

    def _record(self, tool, args, result):
        if tool == "submit_audit" and "error" not in result:
            # Keep the established result structure; version the tool contract.
            result = {**result, "contract_version": VERSION}
            self.result = deepcopy(result)
            return ClaimAuditSession._record(self, tool, args, result)
        if tool == "search_history" and "error" not in result:
            result = {
                **result,
                "observed_sensors": list(self._initial_sensors),
                "limitation": "Frozen training-only analogues from initial sensors only; additional queries do not rerank these matches. Similarity is not causal proof.",
            }
        return super()._record(tool, args, result)

    def dispatch(self, name, args):
        if name != "request_sensor":
            return super().dispatch(name, args)
        with self._lock:

            def reject(code, field, correction):
                return self._record(
                    name,
                    {},
                    {"error": {"code": code, "field": field, "correction": correction}},
                )

            if self.result is not None or self.stop:
                return reject(
                    "investigation_closed", "tool", "Start a fresh investigation."
                )
            if not isinstance(args, dict) or set(args) != {
                "sensor_name",
                "source_id",
                "purpose",
            }:
                return reject(
                    "invalid_arguments",
                    "arguments",
                    "Use sensor_name, source_id and public purpose.",
                )
            sensor = args["sensor_name"]
            if not isinstance(sensor, str) or sensor not in SENSORS:
                return reject(
                    "unknown_sensor", "sensor_name", "Choose a catalog sensor."
                )
            if (
                not isinstance(args["purpose"], str)
                or not 1 <= len(args["purpose"].strip()) <= 240
            ):
                return reject(
                    "invalid_purpose",
                    "purpose",
                    "Give a concise public measurement purpose.",
                )
            source = "knowledge:location:" + sensor
            if args["source_id"] != source or source not in self._known:
                return reject(
                    "sensor_source_required",
                    "source_id",
                    "First look up this sensor; cite its returned location fact.",
                )
            result = self._sensors.get_sensor_history(sensor)
            if "error" in result:
                return reject(
                    result["error"],
                    "sensor_name",
                    "Use an observed sensor or submit the audit within the remaining budget.",
                )
            self.packet["observations"][sensor] = deepcopy(result["summary"])
            self._known.add("measurement:" + sensor)
            return self._record(
                name,
                args,
                {
                    **result,
                    "citation_id": "measurement:" + sensor,
                    "source_id": source,
                    "purpose": args["purpose"],
                    "scope": "Same fixed 600-sample diagnostic window; summary only, not viewer playback or verified normality.",
                },
            )


def run_active_auditor(session, client, config=None, on_event=None):
    context = {
        **session.packet,
        "sensor_budget": 5,
        "remaining_budget": session.remaining_budget,
        "measurement_citation_ids": {
            s: "measurement:" + s for s in session.packet["observations"]
        },
        "knowledge_topics": session.topics(),
        "recommendation_documents": DOCUMENTS,
        "recommendation_sensors": list(SENSORS),
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
    return run_tool_agent(
        session,
        client,
        config
        or AgentConfig(
            max_turns=6, max_tool_calls=8, max_output_tokens=4096, variant="sensor_only"
        ),
        instructions=INSTRUCTIONS,
        tools=active_tools(),
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
