"""Construction et audit sûr du payload Anthropic canary. 0 POST ici."""

from __future__ import annotations

import json
from typing import Any

from app.ai.contracts import AIRequest
from app.ai.providers._anthropic_schema import prepare_anthropic_json_schema
from app.ai.providers.anthropic_engine import AnthropicEngine
from app.file_utils import content_hash
from app.source_analysis_local_v2.schema import (
    build_semantic_transport_v2_schema,
    measure_schema_pair,
    semantic_transport_v2_fingerprint,
)
from app.source_analysis_v2_grammar_canary.constants import (
    CANARY_MAX_OUTPUT_TOKENS,
    CANARY_READ_TIMEOUT_SECONDS,
    EXPECTED_ADAPTED_SCHEMA_BYTES,
    EXPECTED_RAW_SCHEMA_BYTES,
    MODEL,
    PRODUCTION_MAX_OUTPUT_TOKENS,
    PROVIDER,
    SEMANTIC_TRANSPORT_VERSION_V2,
    STAGE_CANARY,
    THINKING_CONTRACT,
    THINKING_MODE,
    WINDOW_ANALYSIS_PROMPT_VERSION_V12,
)
from app.source_analysis_v2_grammar_canary.fixture import SyntheticCanaryFixture
from app.source_analysis_v2_grammar_canary.guard import (
    GrammarCanaryError,
    assert_synthetic_only_payload,
)
from app.source_analysis_v2_grammar_canary.identity import (
    canary_identity_payload,
    canary_request_identity,
)
from app.source_analysis_v2_grammar_canary.wrapper import (
    build_canary_system_prompt,
    build_canary_user_prompt,
    wrapper_hash,
)


def measure_v2_schema_bytes() -> dict[str, Any]:
    schema = build_semantic_transport_v2_schema()
    measured = measure_schema_pair(schema)
    return {
        "raw_bytes": measured["raw_bytes"],
        "adapted_bytes": measured["adapted_bytes"],
        "raw_hash": semantic_transport_v2_fingerprint(schema),
        "adapted_hash": content_hash(
            json.dumps(
                prepare_anthropic_json_schema(schema),
                ensure_ascii=False,
                sort_keys=True,
            )
        ),
        "expected_raw_bytes": EXPECTED_RAW_SCHEMA_BYTES,
        "expected_adapted_bytes": EXPECTED_ADAPTED_SCHEMA_BYTES,
        "matches_expected": (
            measured["raw_bytes"] == EXPECTED_RAW_SCHEMA_BYTES
            and measured["adapted_bytes"] == EXPECTED_ADAPTED_SCHEMA_BYTES
        ),
        "production_max_output_unchanged": PRODUCTION_MAX_OUTPUT_TOKENS == 32000,
    }


def assert_schema_metrics(metrics: dict[str, Any] | None = None) -> dict[str, Any]:
    measured = metrics or measure_v2_schema_bytes()
    if not measured["matches_expected"]:
        raise GrammarCanaryError(
            "V2 schema bytes materially different from A.12/A.11 baseline "
            f"({measured['raw_bytes']}/{measured['adapted_bytes']} vs "
            f"{EXPECTED_RAW_SCHEMA_BYTES}/{EXPECTED_ADAPTED_SCHEMA_BYTES}). "
            "STOP WITHOUT PROVIDER CALL."
        )
    return measured


def build_canary_request(fixture: SyntheticCanaryFixture) -> AIRequest:
    system = build_canary_system_prompt(fixture.transcript.primary_language)
    user = build_canary_user_prompt(fixture)
    schema = build_semantic_transport_v2_schema()
    return AIRequest(
        prompt=user,
        system_prompt=system,
        model=MODEL,
        temperature=None,
        max_output_tokens=CANARY_MAX_OUTPUT_TOKENS,
        response_schema=schema,
        timeout_seconds=CANARY_READ_TIMEOUT_SECONDS,
        thinking_mode=THINKING_MODE,
        effort=None,
        thinking_budget_tokens=None,
        metadata={
            "stage": STAGE_CANARY,
            "window_id": fixture.window.window_id,
            "prompt_version": WINDOW_ANALYSIS_PROMPT_VERSION_V12,
            "transport_version": SEMANTIC_TRANSPORT_VERSION_V2,
            "thinking_contract": THINKING_CONTRACT,
            "canary": True,
            "schema_sha256": semantic_transport_v2_fingerprint(schema),
            "wrapper_sha256": wrapper_hash(system, user),
            "fixture_sha256": fixture.fixture_hash,
        },
    )


def _payload_engine() -> AnthropicEngine:
    return AnthropicEngine(model=MODEL, api_key="cle-de-test")


def build_anthropic_payload(request: AIRequest) -> dict[str, Any]:
    return _payload_engine().build_payload(request, MODEL)


def _nested_has(payload: Any, key: str) -> bool:
    if isinstance(payload, dict):
        if key in payload:
            return True
        return any(_nested_has(value, key) for value in payload.values())
    if isinstance(payload, list):
        return any(_nested_has(item, key) for item in payload)
    return False


def inspect_safe_payload(
    request: AIRequest,
    payload: dict[str, Any],
    *,
    fixture_hash: str,
) -> dict[str, Any]:
    output_config = payload.get("output_config")
    format_block = output_config.get("format") if isinstance(output_config, dict) else None
    schema = format_block.get("schema") if isinstance(format_block, dict) else None
    thinking = payload.get("thinking")
    thinking_type = thinking.get("type") if isinstance(thinking, dict) else None
    effort_present = isinstance(output_config, dict) and "effort" in output_config
    schema_hash = (
        content_hash(json.dumps(schema, ensure_ascii=False, sort_keys=True))
        if schema is not None
        else None
    )
    wrapper = wrapper_hash(request.system_prompt or "", request.prompt)
    identity = canary_request_identity(
        schema_hash=str(request.metadata.get("schema_sha256") or ""),
        wrapper_hash=wrapper,
        fixture_hash=fixture_hash,
        max_output=int(request.max_output_tokens or CANARY_MAX_OUTPUT_TOKENS),
    )
    return {
        "model": payload.get("model"),
        "max_tokens": payload.get("max_tokens"),
        "thinking_type": thinking_type,
        "thinking": thinking,
        "effort_present": effort_present,
        "budget_tokens_present": _nested_has(payload, "budget_tokens"),
        "task_budget_present": _nested_has(payload, "task_budget"),
        "temperature_present": "temperature" in payload,
        "output_config_present": isinstance(output_config, dict),
        "format_present": isinstance(format_block, dict) and "schema" in format_block,
        "format_type": format_block.get("type") if isinstance(format_block, dict) else None,
        "schema_hash": schema_hash,
        "raw_schema_hash": request.metadata.get("schema_sha256"),
        "message_count": len(payload.get("messages") or []),
        "system_present": bool(payload.get("system")),
        "synthetic_input_hash": fixture_hash,
        "wrapper_hash": wrapper,
        "request_identity": identity,
        "identity_fields": canary_identity_payload(
            schema_hash=str(request.metadata.get("schema_sha256") or ""),
            wrapper_hash=wrapper,
            fixture_hash=fixture_hash,
            max_output=int(request.max_output_tokens or CANARY_MAX_OUTPUT_TOKENS),
        ),
        "provider": PROVIDER,
        "secrets_included": False,
        "pastoral_content": False,
    }


def assert_payload_conditions(audit: dict[str, Any]) -> None:
    failures: list[str] = []
    if audit.get("model") != MODEL:
        failures.append(f"model={audit.get('model')!r}")
    if audit.get("thinking_type") != "disabled":
        failures.append(f"thinking.type={audit.get('thinking_type')!r}")
    if audit.get("effort_present"):
        failures.append("effort present")
    if audit.get("budget_tokens_present"):
        failures.append("budget_tokens present")
    if audit.get("task_budget_present"):
        failures.append("task_budget present")
    if not audit.get("format_present"):
        failures.append("output_config.format missing")
    if audit.get("format_type") != "json_schema":
        failures.append(f"format.type={audit.get('format_type')!r}")
    if audit.get("temperature_present"):
        failures.append("temperature present")
    if audit.get("max_tokens") != CANARY_MAX_OUTPUT_TOKENS:
        failures.append(f"max_tokens={audit.get('max_tokens')!r}")
    if audit.get("message_count") != 1:
        failures.append(f"message_count={audit.get('message_count')!r}")
    if not audit.get("system_present"):
        failures.append("system missing")
    if failures:
        raise GrammarCanaryError(
            "Payload conditions failed — STOP WITHOUT PROVIDER CALL: "
            + "; ".join(failures)
        )


def build_audited_request(fixture: SyntheticCanaryFixture) -> dict[str, Any]:
    schema_metrics = assert_schema_metrics()
    request = build_canary_request(fixture)
    payload = build_anthropic_payload(request)
    assert_synthetic_only_payload(
        payload,
        user_text=request.prompt,
        system_text=request.system_prompt or "",
    )
    audit = inspect_safe_payload(request, payload, fixture_hash=fixture.fixture_hash)
    assert_payload_conditions(audit)
    return {
        "request": request,
        "payload": payload,
        "audit": audit,
        "schema_metrics": schema_metrics,
    }


__all__ = [
    "assert_payload_conditions",
    "assert_schema_metrics",
    "build_anthropic_payload",
    "build_audited_request",
    "build_canary_request",
    "inspect_safe_payload",
    "measure_v2_schema_bytes",
]
