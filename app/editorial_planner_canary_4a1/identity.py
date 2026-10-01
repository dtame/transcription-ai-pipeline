"""Identités pré-appel : schéma, prompt, transport vs gel Phase 4A."""

from __future__ import annotations

from typing import Any

from app.ai.thinking import (
    THINKING_MODE_PROVIDER_DEFAULT,
    is_historical_thinking_default,
)
from app.editorial_planner_canary_4a1.constants import (
    CANARY_MAX_OUTPUT_TOKENS,
    MODEL,
    PHASE_4A_ADAPTED_SCHEMA_BYTES,
    PHASE_4A_ADAPTED_SCHEMA_SHA256,
    PHASE_4A_INSTRUCTIONS_SHA256,
    PHASE_4A_PROMPT_SHA256,
    PHASE_4A_RAW_SCHEMA_BYTES,
    PHASE_4A_RAW_SCHEMA_SHA256,
    PHASE_4A_SYSTEM_SHA256,
    PRODUCTION_PROPOSED_MAX_OUTPUT,
    PROMPT_VERSION,
    PROVIDER,
    TRANSPORT_VERSION,
)
from app.editorial_planner_canary_4a1.guard import PlannerCanaryError
from app.editorial_planning.prompt import prompt_bundle
from app.editorial_planning.schema import schema_identity
from app.editorial_planning.settings import thinking_recommendation


def live_schema_identity() -> dict[str, Any]:
    return schema_identity()


def live_prompt_identity() -> dict[str, Any]:
    bundle = prompt_bundle()
    return {
        "version": bundle["version"],
        "system_sha256": bundle["system_sha256"],
        "instructions_sha256": bundle["instructions_sha256"],
        "prompt_sha256": bundle["prompt_sha256"],
    }


def compare_schema(live: dict[str, Any] | None = None) -> dict[str, Any]:
    live = dict(live or live_schema_identity())
    expected = {
        "transport_version": TRANSPORT_VERSION,
        "raw_schema_sha256": PHASE_4A_RAW_SCHEMA_SHA256,
        "adapted_schema_sha256": PHASE_4A_ADAPTED_SCHEMA_SHA256,
        "raw_schema_bytes": PHASE_4A_RAW_SCHEMA_BYTES,
        "adapted_schema_bytes": PHASE_4A_ADAPTED_SCHEMA_BYTES,
    }
    mismatches: list[str] = []
    if live.get("transport_version") != expected["transport_version"]:
        mismatches.append("transport_version")
    if live.get("raw_schema_sha256") != expected["raw_schema_sha256"]:
        mismatches.append("raw_schema_sha256")
    if live.get("adapted_schema_sha256") != expected["adapted_schema_sha256"]:
        mismatches.append("adapted_schema_sha256")
    if live.get("raw_schema_bytes") != expected["raw_schema_bytes"]:
        mismatches.append("raw_schema_bytes")
    if live.get("adapted_schema_bytes") != expected["adapted_schema_bytes"]:
        mismatches.append("adapted_schema_bytes")
    return {
        "expected": expected,
        "live": {
            "transport_version": live.get("transport_version"),
            "raw_schema_sha256": live.get("raw_schema_sha256"),
            "adapted_schema_sha256": live.get("adapted_schema_sha256"),
            "raw_schema_bytes": live.get("raw_schema_bytes"),
            "adapted_schema_bytes": live.get("adapted_schema_bytes"),
            "anthropic_known_incompatibilities": live.get(
                "anthropic_known_incompatibilities"
            ),
            "additional_properties_false_on_adapted": live.get(
                "additional_properties_false_on_adapted"
            ),
        },
        "mismatches": mismatches,
        "identity": "MATCH" if not mismatches else "MISMATCH",
        "full_live": live,
    }


def compare_prompt(live: dict[str, Any] | None = None) -> dict[str, Any]:
    live = dict(live or live_prompt_identity())
    expected = {
        "version": PROMPT_VERSION,
        "system_sha256": PHASE_4A_SYSTEM_SHA256,
        "instructions_sha256": PHASE_4A_INSTRUCTIONS_SHA256,
        "prompt_sha256": PHASE_4A_PROMPT_SHA256,
    }
    mismatches = [key for key, value in expected.items() if live.get(key) != value]
    return {
        "expected": expected,
        "live": live,
        "mismatches": mismatches,
        "identity": "MATCH" if not mismatches else "MISMATCH",
    }


def thinking_precall() -> dict[str, Any]:
    rec = thinking_recommendation()
    default_ok = is_historical_thinking_default(
        THINKING_MODE_PROVIDER_DEFAULT, None, None
    )
    return {
        "thinking_mode": THINKING_MODE_PROVIDER_DEFAULT,
        "effort": None,
        "budget_tokens": None,
        "sonnet5_thinking_disabled_copied": False,
        "historical_provider_default": default_ok,
        "recommendation": rec,
        "canary_max_output_tokens": CANARY_MAX_OUTPUT_TOKENS,
        "production_proposed_max_output": PRODUCTION_PROPOSED_MAX_OUTPUT,
        "canary_max_is_not_production_max": (
            CANARY_MAX_OUTPUT_TOKENS != PRODUCTION_PROPOSED_MAX_OUTPUT
        ),
        "provider": PROVIDER,
        "model": MODEL,
    }


def precall_identity() -> dict[str, Any]:
    schema = compare_schema()
    prompt = compare_prompt()
    thinking = thinking_precall()
    blocked = (
        schema["identity"] != "MATCH"
        or prompt["identity"] != "MATCH"
        or schema["live"].get("anthropic_known_incompatibilities") not in (0, None)
    )
    return {
        "schema": schema,
        "prompt": prompt,
        "thinking": thinking,
        "transport_version": TRANSPORT_VERSION,
        "prompt_version": PROMPT_VERSION,
        "schema_identity": schema["identity"],
        "prompt_identity": prompt["identity"],
        "blocked_precall": blocked,
        "block_reason": (
            None
            if not blocked
            else "schema/prompt identity mismatch with Phase 4A freeze"
        ),
    }


def require_precall_identity(identity: dict[str, Any] | None = None) -> dict[str, Any]:
    identity = identity or precall_identity()
    if identity.get("blocked_precall"):
        raise PlannerCanaryError(
            "BLOCKED_PRECALL: " + str(identity.get("block_reason"))
        )
    return identity


__all__ = [
    "compare_prompt",
    "compare_schema",
    "live_prompt_identity",
    "live_schema_identity",
    "precall_identity",
    "require_precall_identity",
    "thinking_precall",
]
