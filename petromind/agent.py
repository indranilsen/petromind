"""Muse chooses tools; DiagnosticSession remains the authority for all evidence.

Model text and encrypted reasoning stay out of exported traces. The runner never
receives an evaluator, a source path, a well identifier, or a target event label.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import time
from dataclasses import asdict, dataclass

from .agent_tools import INSTRUCTIONS, PROMPT_VERSION, tool_definitions
from .audit import canonical
from .meta_api import MetaAPIError
from .variants import VARIANT_TOOLS


@dataclass(frozen=True)
class AgentConfig:
    model: str = "muse-spark-1.3"
    max_turns: int = 20
    max_tool_calls: int = 40
    max_output_tokens: int = 2048
    reasoning_effort: str = "medium"
    run_timeout: float = 300
    variant: str = "graphrag"

    def __post_init__(self):
        if self.variant not in VARIANT_TOOLS:
            raise ValueError("Unknown agent variant")
        if not isinstance(self.model, str) or not re.fullmatch(r"muse-spark-[0-9]+\.[0-9]+", self.model):
            raise ValueError("Invalid Muse Spark model identifier")
        for value, low, high in ((self.max_turns, 1, 40), (self.max_tool_calls, 1, 80),
                                 (self.max_output_tokens, 16, 8192)):
            if type(value) is not int or not low <= value <= high:
                raise ValueError("Invalid agent limits")
        if (self.reasoning_effort not in {"low", "medium", "high"}
                or not isinstance(self.run_timeout, (float, int)) or isinstance(self.run_timeout, bool)
                or not math.isfinite(self.run_timeout) or not 0 < self.run_timeout <= 600):
            raise ValueError("Invalid reasoning/deadline configuration")


@dataclass(frozen=True)
class RunEvent:
    sequence: int
    kind: str
    details_json: str


@dataclass(frozen=True)
class AgentResult:
    status: str
    reason: str
    diagnosis_json: str | None
    events: tuple[RunEvent, ...]
    requests: int
    reserved_output_tokens: int


def _reject_constant(_):
    raise ValueError("Nonfinite JSON constant")


def _unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate argument keys")
        result[key] = value
    return result


def _arguments(value):
    if not isinstance(value, str) or len(value) > 8192:
        return None
    try:
        parsed = json.loads(value, parse_constant=_reject_constant, object_pairs_hook=_unique_keys)
        return parsed if isinstance(parsed, dict) else None
    except (ValueError, RecursionError):
        return None


def _replay_items(output):
    """Only supported Responses input fields; opaque reasoning never gets logged."""
    replay = []
    has_call = any(item.get("type") == "function_call" for item in output)
    if not any(item.get("type") in {"function_call", "message"} for item in output):
        raise MetaAPIError("invalid_model_output")
    for item in output:
        kind = item.get("type")
        if kind == "reasoning":
            encrypted = item.get("encrypted_content")
            if not isinstance(encrypted, str) or not encrypted:
                raise MetaAPIError("missing_encrypted_reasoning")
            replay.append({"type": "reasoning", "summary": [], "encrypted_content": encrypted})
        elif kind == "function_call":
            replay.append({k: item[k] for k in ("type", "call_id", "name", "arguments")})
        elif kind == "message":
            if item.get("role") != "assistant" or not isinstance(item.get("content"), list):
                raise MetaAPIError("invalid_assistant_message")
            if any(not isinstance(c, dict) or c.get("type") != "output_text"
                   or not isinstance(c.get("text"), str) for c in item["content"]):
                raise MetaAPIError("model_refused_or_invalid_content")
            message = {"type": "message", "role": "assistant",
                       "content": [{"type": "output_text", "text": c["text"]} for c in item["content"]]}
            if has_call or item.get("phase") == "commentary":
                message["phase"] = "commentary"
            replay.append(message)
        else:
            raise MetaAPIError("unsupported_output_item")
    return replay


def run_agent(session, client, config: AgentConfig | None = None, *, on_event=None,
              clock=time.monotonic) -> AgentResult:
    config = config or AgentConfig()
    if session.variant != config.variant:
        raise ValueError("Session capabilities must match agent variant")
    if session.audit_trail or session.diagnosis is not None:
        raise ValueError("Muse requires a fresh investigation session")
    initial_history = [{"role": "user", "content": [{"type": "input_text", "text": canonical({
        "task": "Investigate this historical case and submit a supported fault-type diagnosis",
        "case_id": session.case_id, "sensor_budget": session.budget,
        "known_transient_onset": True})}]}]
    return run_tool_agent(session, client, config, instructions=INSTRUCTIONS,
        tools=tool_definitions(config.variant), initial_history=initial_history,
        prompt_version=PROMPT_VERSION, on_event=on_event, clock=clock)


def run_tool_agent(session, client, config, *, instructions, tools, initial_history,
                   prompt_version, on_event=None, clock=time.monotonic, submission_reason="diagnosis_submitted", is_complete=None, stop_reason=None, decode_arguments=None):
    """Trusted composition hook; only the supplied dispatcher reaches model tools.

    Reuses bounded transport/replay/usage safeguards. Callers must construct a
    label-blinded context and enforce their own terminal submission schema.
    """
    is_complete = is_complete or (lambda: session.diagnosis is not None)
    events = []
    def emit(kind, details):
        event = RunEvent(len(events) + 1, kind, canonical(details))
        events.append(event)
        if on_event:
            on_event(event)
    def finish(reason, diagnosis=None):
        status = "completed" if diagnosis is not None else "failed"
        emit("stop", {"status": status, "reason": reason, "requests": client.requests,
                      "reserved_output_tokens": client.reserved_output_tokens})
        return AgentResult(status, reason, canonical(diagnosis) if diagnosis else None,
                           tuple(events), client.requests, client.reserved_output_tokens)
    emit("configuration", {**asdict(config), "prompt_version": prompt_version,
         "prompt_sha256": hashlib.sha256(instructions.encode()).hexdigest(),
         "sensor_budget": session.budget, "stateless_replay": True,
         "confidence_calibrated": False})
    history = list(initial_history)
    deadline = clock() + config.run_timeout
    seen_ids, n_calls, stalls = set(), 0, 0
    for turn in range(1, config.max_turns + 1):
        payload = {"model": config.model, "instructions": instructions, "input": history,
                   "tools": tools, "tool_choice": "auto", "parallel_tool_calls": False,
                   "store": False, "include": ["reasoning.encrypted_content"],
                   "reasoning": {"effort": config.reasoning_effort},
                   "max_output_tokens": config.max_output_tokens}
        if len(canonical(payload).encode()) > 512_000:
            return finish("request_context_too_large")
        emit("request", {"turn": turn, "remaining_budget": session.remaining_budget})
        try:
            response = client.create(payload, deadline=deadline, on_retry=lambda d: emit("retry", d))
            usage = response.get("usage")
            usage = usage if isinstance(usage, dict) else {}
            counts = {k: usage[k] for k in ("input_tokens", "output_tokens", "total_tokens")
                      if type(usage.get(k)) is int and usage[k] >= 0}
            for field, detail, key in (("cached_tokens", "input_tokens_details", "cached_tokens"),
                                       ("reasoning_tokens", "output_tokens_details", "reasoning_tokens")):
                nested = usage.get(detail)
                if isinstance(nested, dict) and type(nested.get(key)) is int and nested[key] >= 0:
                    counts[field] = nested[key]
            emit("usage", {"turn": turn, **counts})
            if clock() >= deadline:
                return finish("run_deadline_exceeded")
            incomplete = response.get("incomplete_details")
            if (response.get("status") == "incomplete" and isinstance(incomplete, dict)
                    and incomplete.get("reason") == "max_output_tokens"):
                return finish("model_output_token_limit")
            if response.get("status") != "completed" or response.get("error") is not None:
                return finish("model_response_not_completed")
            output = response.get("output")
            if not isinstance(output, list) or not output or not all(isinstance(x, dict) for x in output):
                return finish("invalid_model_output")
            calls = [item for item in output if item.get("type") == "function_call"]
            if len(calls) > 8 or n_calls + len(calls) > config.max_tool_calls:
                return finish("tool_call_limit")
            current_ids = set()
            for call in calls:
                identifier = call.get("call_id")
                if (not isinstance(identifier, str) or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,64}", identifier)
                        or identifier in seen_ids or identifier in current_ids
                        or not isinstance(call.get("name"), str)
                        or not isinstance(call.get("arguments"), str)
                        or call.get("status", "completed") != "completed"):
                    return finish("invalid_function_call")
                current_ids.add(identifier)
            # Validate the full response before executing ANY side effects.
            replay = _replay_items(output)
        except MetaAPIError as exc:
            emit("api_error", {"code": exc.code, "status": exc.status})
            return finish(exc.code)
        history.extend(replay)
        # Token counts only; vendor bodies, reasoning and free-form text are not trace content.
        usage = response.get("usage") or {}
        emit("response", {"turn": turn, "function_calls": len(calls),
             "usage": {k: usage[k] for k in ("input_tokens", "output_tokens", "total_tokens")
                       if isinstance(usage, dict) and type(usage.get(k)) is int and usage[k] >= 0}})
        if not calls:
            stalls += 1
            if stalls >= 3:
                return finish("no_submitted_diagnosis" if submission_reason == "diagnosis_submitted"
                              else "no_submitted_assessment")
            history.append({"role": "user", "content": [{"type": "input_text", "text":
                ("No diagnosis has been submitted. Use the registered tools to gather evidence, "
                 "then call submit_diagnosis. Plain text is not a submission."
                 if submission_reason == "diagnosis_submitted" else
                 "No terminal assessment has been submitted. Use one of the registered assessment submission tools; plain text is not a submission.")}]})
            continue
        stalls = 0
        seen_ids.update(current_ids)
        for call in calls:
            n_calls += 1
            arguments = (decode_arguments(call["name"], call["arguments"]) if decode_arguments
                         else _arguments(call["arguments"]))
            # Invalid JSON is routed through the normal sanitized session audit too.
            result = session.dispatch(call["name"], arguments)
            audit = session.audit_trail[-1]
            emit("tool_result", {"turn": turn, "tool": audit.tool,
                 "arguments": json.loads(audit.arguments_json), "result": result,
                 "audit_sequence": audit.sequence, "audit_digest": audit.digest})
            reason = stop_reason() if stop_reason else None
            if reason is not None:
                return finish(reason)
            if is_complete():
                return finish(submission_reason, result)
            history.append({"type": "function_call_output", "call_id": call["call_id"],
                            "output": canonical(result)})
    return finish("turn_limit")
