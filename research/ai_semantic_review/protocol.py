"""Immutable AI-only intake and bounded provider configuration. No reviewer grades."""

from __future__ import annotations

import re
from datetime import date
from decimal import ROUND_CEILING, Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import urlsplit

from research.semantic_review.workflow import parse, row_template

from .contract import (
    LABEL,
    PROMPTS,
    ROLES,
    SCHEMA,
    VERSION,
    fail,
    read,
    scan,
    sha,
    write,
)

ROOT = Path(__file__).parent
CONFIG_KEYS = {
    "provider",
    "model",
    "max_output_tokens",
    "temperature",
    "reasoning_effort",
    "input_ceiling_usd_per_million",
    "output_ceiling_usd_per_million",
    "rate_source",
    "rate_checked_at",
}


def nano(value):
    try:
        d = Decimal(str(value))
    except InvalidOperation:
        fail("invalid_decimal_rate_or_budget")
    if not d.is_finite() or d <= 0:
        fail("positive_finite_rate_or_budget_required")
    return int((d * 1_000_000_000).to_integral_value(rounding=ROUND_CEILING))


def cost(config, input_tokens, output_tokens):
    return (
        input_tokens * nano(config["input_ceiling_usd_per_million"])
        + output_tokens * nano(config["output_ceiling_usd_per_million"])
        + 999_999
    ) // 1_000_000


def code_commitment():
    files = list(ROOT.glob("*.py")) + [
        ROOT.parents[1] / "scripts/ai_semantic_review.py",
        ROOT.parent / "semantic_review/workflow.py",
    ]
    return sha(
        {
            p.name if p.parent == ROOT else str(p.relative_to(ROOT.parents[1])): sha(
                p.read_bytes()
            )
            for p in sorted(files)
        }
    )


def validate_config(config):
    if not isinstance(config, dict) or set(config) != set(ROLES) | {
        "same_family_reason",
        "execution_mode",
        "pricing_confirmation",
    }:
        fail("ai_configuration_contract")
    if config["execution_mode"] not in ("live_external", "offline_contract_check"):
        fail("ai_execution_mode_required")
    expected_pricing = (
        "OWNER_VERIFIED_PRICE_CEILINGS"
        if config["execution_mode"] == "live_external"
        else "OFFLINE_FIXTURE_NOT_A_QUOTE"
    )
    if config["pricing_confirmation"] != expected_pricing:
        fail("ai_price_ceiling_confirmation_required")
    for role in ROLES:
        c = config[role]
        if not isinstance(c, dict) or set(c) != CONFIG_KEYS:
            fail("ai_provider_configuration_contract")
        if c["provider"] not in ("openai", "anthropic"):
            fail("unsupported_external_reviewer_provider")
        if (
            not isinstance(c["model"], str)
            or not re.fullmatch(r"[a-zA-Z0-9._:-]{1,100}", c["model"])
            or any(
                x in c["model"].lower()
                for x in ("muse", "spark", "replace", "your_", "set_")
            )
        ):
            fail("explicit_external_model_required")
        if (
            type(c["max_output_tokens"]) is not int
            or not 256 <= c["max_output_tokens"] <= 16384
        ):
            fail("ai_output_limit_required")
        parsed_url = urlsplit(c["rate_source"])
        if (
            parsed_url.query
            or parsed_url.fragment
            or parsed_url.username
            or parsed_url.password
        ):
            fail("ai_price_source_must_not_contain_credentials")
        try:
            date.fromisoformat(c["rate_checked_at"])
        except (ValueError, TypeError):
            fail("ai_rate_date_invalid")
        if c["provider"] == "anthropic" and not c["model"].startswith("claude-"):
            fail("ai_provider_model_family_mismatch")
        if c["provider"] == "openai" and not re.fullmatch(
            r"(gpt-[A-Za-z0-9._:-]+|o[0-9][A-Za-z0-9._:-]*)", c["model"]
        ):
            fail("ai_provider_model_family_mismatch")
        if c["temperature"] is not None and (
            type(c["temperature"]) not in (int, float) or not 0 <= c["temperature"] <= 1
        ):
            fail("ai_temperature_invalid")
        if (
            c["reasoning_effort"] not in (None, "low", "medium", "high")
            or c["provider"] == "anthropic"
            and c["reasoning_effort"] is not None
        ):
            fail("ai_reasoning_parameter_invalid")
        for k in ("input_ceiling_usd_per_million", "output_ceiling_usd_per_million"):
            if not isinstance(c[k], str) or nano(c[k]) > nano("1000"):
                fail("verified_string_price_ceiling_required")
        hosts = (
            ("https://openai.com/", "https://developers.openai.com/")
            if c["provider"] == "openai"
            else ("https://platform.claude.com/", "https://www.anthropic.com/")
        )
        if (
            not isinstance(c["rate_source"], str)
            or not c["rate_source"].startswith(hosts)
            or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", c["rate_checked_at"])
        ):
            fail("owner_verified_rate_source_and_date_required")
    if not isinstance(config["same_family_reason"], str):
        fail("same_family_disclosure_required")
    if (
        config["reviewer_a"]["provider"] == config["reviewer_b"]["provider"]
        and not config["same_family_reason"].strip()
    ):
        fail("different_families_or_explicit_limitation_required")
    return config


def inspect_input(folder, expected_sha):
    folder = Path(folder)
    raw = (folder / "packets.json").read_bytes()
    if sha(raw) != expected_sha:
        fail("ai_blinded_packet_file_commitment_mismatch")
    packets = parse(raw)
    form = read(folder / "review-form.json")
    if not isinstance(packets, list) or len(packets) != 70:
        fail("ai_requires_original_70_packets")
    if not isinstance(form, dict) or set(form) != {
        "version",
        "bundle_id",
        "reviewer_code",
        "attestation",
        "reviews",
    }:
        fail("ai_requires_original_blank_human_form")
    if form["version"] != "sprint-c-human-semantic-review-v2" or form[
        "reviewer_code"
    ] not in ("R-A", "R-B"):
        fail("ai_unknown_source_human_contract")
    if (
        not isinstance(form["attestation"], dict)
        or not form["attestation"]
        or any(v is not False for v in form["attestation"].values())
    ):
        fail("human_attestations_must_remain_false")
    if (
        len(form["reviews"]) != 70
        or len({r["review_id"] for r in form["reviews"]}) != 70
    ):
        fail("ai_original_form_coverage")
    rows = {r["review_id"]: r for r in form["reviews"]}
    for p in packets:
        if not isinstance(p, dict) or set(p) != {
            "review_id",
            "initial",
            "events",
            "submission",
            "projection_notice",
        }:
            fail("ai_projection_contract")
        if not re.fullmatch("[0-9a-f]{24}", p["review_id"]) or rows.get(
            p["review_id"]
        ) != row_template(p):
            fail("ai_packet_changed_or_human_fields_not_blank")
        scan(p)
    if len({p["review_id"] for p in packets}) != 70:
        fail("ai_duplicate_original_ids")
    return packets


def prepare(folder, expected_sha, config_path, out, cap="20"):
    out = Path(out)
    if out.exists():
        fail("fresh_ai_protocol_directory_required")
    packets = inspect_input(folder, expected_sha)
    config = validate_config(read(config_path))
    cap_nano = nano(cap)
    if cap_nano > nano("20"):
        fail("ai_authorized_cap_exceeded")
    record = {
        "version": VERSION,
        "label": LABEL,
        "packet_file_sha256": expected_sha,
        "packet_hashes": {p["review_id"]: sha(p) for p in packets},
        "source_form_sha256": sha((Path(folder) / "review-form.json").read_bytes()),
        "config": config,
        "prompt_sha256": {r: sha(PROMPTS[r].encode()) for r in ROLES},
        "schema_sha256": sha(SCHEMA),
        "code_sha256": code_commitment(),
        "max_cost_nano_usd": cap_nano,
        "max_requests": 210,
        "max_attempts_per_role_packet": 1,
        "input_reservation_rule": "UTF8 serialized entire request bytes + 4096 tokens; charge all usage at frozen ceiling prices, no cache discount",
        "pricing_limitation": "Hard local request/reservation cap under owner-verified price ceilings; not a provider invoice guarantee.",
        "human_semantic_fields": "UNGRADED",
        "independence_limit": "Fresh one-packet contexts isolate inputs, not model training, correlated errors or implicit source recognition.",
        "custody_limit": "Source matched original blank-form commitments and owner-supplied file SHA; owner must compare this with the prior verification receipt, not a newly self-computed hash.",
    }
    record["protocol_id"] = sha(record)
    out.mkdir(mode=0o700, parents=True)
    source_raw = (Path(folder) / "packets.json").read_bytes()
    form_raw = (Path(folder) / "review-form.json").read_bytes()
    if sha(source_raw) != expected_sha or sha(form_raw) != record["source_form_sha256"]:
        fail("ai_source_changed_during_preparation")
    write(out / "protocol.json", record)
    with (out / "packets.json").open("xb") as stream:
        stream.write(source_raw)
    with (out / "source-human-form.UNMODIFIED.json").open("xb") as stream:
        stream.write(form_raw)
    for role in ROLES:
        (out / role).mkdir(mode=0o700)
    write(out / "prompts.json", PROMPTS)
    write(out / "schema.json", SCHEMA)
    from .runner import initialize

    initialize(out)
    return {
        "status": "ai_protocol_frozen",
        "label": LABEL,
        "packets": 70,
        "protocol_id": record["protocol_id"],
        "api_requests": 0,
        "max_cost_usd": cap_nano / 1e9,
    }


def load(root):
    root = Path(root)
    p = read(root / "protocol.json")
    if (
        p.get("version") != VERSION
        or p.get("label") != LABEL
        or p.get("protocol_id")
        != sha({k: v for k, v in p.items() if k != "protocol_id"})
    ):
        fail("ai_protocol_digest_changed")
    if (
        p["code_sha256"] != code_commitment()
        or p["schema_sha256"] != sha(SCHEMA)
        or p["prompt_sha256"] != {r: sha(PROMPTS[r].encode()) for r in ROLES}
    ):
        fail("ai_code_prompt_or_schema_changed")
    if read(root / "prompts.json") != PROMPTS or read(root / "schema.json") != SCHEMA:
        fail("ai_frozen_prompt_or_schema_file_changed")
    if (
        sha((root / "packets.json").read_bytes()) != p["packet_file_sha256"]
        or sha((root / "source-human-form.UNMODIFIED.json").read_bytes())
        != p["source_form_sha256"]
    ):
        fail("ai_source_bytes_changed")
    packets = read(root / "packets.json")
    if (
        len(packets) != 70
        or len({x["review_id"] for x in packets}) != 70
        or {x["review_id"]: sha(x) for x in packets} != p["packet_hashes"]
    ):
        fail("ai_frozen_packet_changed")
    form = read(root / "source-human-form.UNMODIFIED.json")
    # Original packet/form bytes and null human fields remain unchanged.
    if {r["review_id"]: r for r in form["reviews"]} != {
        x["review_id"]: row_template(x) for x in packets
    } or any(v is not False for v in form["attestation"].values()):
        fail("human_semantic_fields_changed")
    validate_config(p["config"])
    if (
        not 0 < p["max_cost_nano_usd"] <= nano("20")
        or p["max_requests"] != 210
        or p["max_attempts_per_role_packet"] != 1
    ):
        fail("ai_limits_changed")
    return p, {x["review_id"]: x for x in packets}
