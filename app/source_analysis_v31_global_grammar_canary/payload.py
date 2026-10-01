"""Construction et audit sûr du payload Anthropic A.35. 0 POST ici."""

from __future__ import annotations

import json
from typing import Any

from app.ai.contracts import AIRequest
from app.ai.estimation import estimate_tokens
from app.ai.providers._anthropic_schema import prepare_anthropic_json_schema
from app.ai.providers.anthropic_engine import AnthropicEngine
from app.file_utils import content_hash
from app.source_analysis_v31_global_grammar_canary.constants import (
    AUTHORIZATION_SCOPE,
    CANARY_MAX_OUTPUT_TOKENS,
    CANARY_READ_TIMEOUT_SECONDS,
    CANARY_WINDOW_ID,
    GLOBAL_PROMPT_VERSION,
    GLOBAL_TRANSPORT_VERSION,
    MODEL,
    PRODUCTION_MAX_OUTPUT_TOKENS,
    PROVIDER,
    STAGE_CANARY,
    THINKING_CONTRACT,
    THINKING_MODE,
)
from app.source_analysis_v31_global_grammar_canary.fixture import (
    SyntheticConsolidationFixture,
)
from app.source_analysis_v31_global_grammar_canary.guard import (
    GlobalGrammarCanaryError,
    assert_synthetic_only_payload,
)
from app.source_analysis_v31_global_grammar_canary.identity import (
    canary_identity_payload,
    canary_request_identity,
    verify_schema_identity,
)
from app.source_analysis_v31_global_preflight.prompt import prompt_bundle
from app.source_analysis_v31_global_preflight.transport import (
    build_global_consolidation_schema,
)


def user_prompt_for_fixture(fixture: SyntheticConsolidationFixture) -> str:
    prompt = prompt_bundle()
    compact = json.dumps(fixture.compact, ensure_ascii=False, separators=(",", ":"))
    return prompt["instructions"] + "\n" + compact + "\n"


def build_canary_request(fixture: SyntheticConsolidationFixture) -> AIRequest:
    prompt = prompt_bundle()
    system = prompt["system"]
    user = user_prompt_for_fixture(fixture)
    schema = build_global_consolidation_schema()
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
            "window_id": CANARY_WINDOW_ID,
            "prompt_version": GLOBAL_PROMPT_VERSION,
            "transport_version": GLOBAL_TRANSPORT_VERSION,
            "thinking_contract": THINKING_CONTRACT,
            "authorization_scope": AUTHORIZATION_SCOPE,
            "canary": True,
            "schema_sha256": content_hash(
                json.dumps(schema, ensure_ascii=False, sort_keys=True)
            ),
            "prompt_sha256": prompt["combined_sha256"],
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
    schema_metrics: dict[str, Any],
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
    prompt = prompt_bundle()
    local_est = estimate_tokens(
        (request.system_prompt or "") + "\n" + request.prompt,
        model=MODEL,
    )
    identity = canary_request_identity(
        schema_hash=str(schema_metrics.get("hash") or ""),
        prompt_hash=prompt["combined_sha256"],
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
        "schema_version": GLOBAL_TRANSPORT_VERSION,
        "schema_hash": schema_metrics.get("hash"),
        "adapted_schema_hash": schema_hash,
        "raw_bytes": schema_metrics.get("raw_bytes"),
        "adapted_bytes": schema_metrics.get("adapted_bytes"),
        "prompt_version": GLOBAL_PROMPT_VERSION,
        "prompt_hash": prompt["combined_sha256"],
        "message_count": len(payload.get("messages") or []),
        "system_present": bool(payload.get("system")),
        "synthetic_input_hash": fixture_hash,
        "request_identity": identity,
        "identity_fields": canary_identity_payload(
            schema_hash=str(schema_metrics.get("hash") or ""),
            prompt_hash=prompt["combined_sha256"],
            fixture_hash=fixture_hash,
            max_output=int(request.max_output_tokens or CANARY_MAX_OUTPUT_TOKENS),
        ),
        "authorization_scope": AUTHORIZATION_SCOPE,
        "provider": PROVIDER,
        "local_input_estimate_tokens": local_est.tokens,
        "local_input_estimate_method": local_est.method,
        "production_max_output_unchanged": PRODUCTION_MAX_OUTPUT_TOKENS == 32000,
        "secrets_included": False,
        "pastoral_content": False,
        "input_ids": [],
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
    if audit.get("schema_version") != GLOBAL_TRANSPORT_VERSION:
        failures.append(f"schema={audit.get('schema_version')!r}")
    if audit.get("schema_hash") != audit.get("identity_fields", {}).get("schema_hash"):
        failures.append("schema hash drifted")
    if audit.get("pastoral_content"):
        failures.append("pastoral content present")
    if not audit.get("production_max_output_unchanged"):
        failures.append("production max_output mutated")
    if failures:
        raise GlobalGrammarCanaryError(
            "Payload conditions failed — STOP WITHOUT PROVIDER CALL: "
            + "; ".join(failures)
        )


def build_audited_request(
    fixture: SyntheticConsolidationFixture,
    *,
    project_name: str | None = None,
    sortie_dir: Any = None,
) -> dict[str, Any]:
    schema_metrics = verify_schema_identity(
        project_name or "pastoral_retreat_v2_validation",
        sortie_dir=sortie_dir,
    )
    request = build_canary_request(fixture)
    payload = build_anthropic_payload(request)
    assert_synthetic_only_payload(
        payload,
        user_text=request.prompt,
        system_text=request.system_prompt or "",
    )
    audit = inspect_safe_payload(
        request,
        payload,
        fixture_hash=fixture.fixture_hash,
        schema_metrics=schema_metrics,
    )
    audit["input_ids"] = list(fixture.idea_input_ids) + sorted(fixture.allowed_input_ids)
    assert_payload_conditions(audit)
    adapted = prepare_anthropic_json_schema(build_global_consolidation_schema())
    audit["adapted_bytes_recomputed"] = len(
        json.dumps(adapted, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    )
    return {
        "request": request,
        "payload": payload,
        "audit": audit,
        "schema_metrics": schema_metrics,
    }


__all__ = [
    "assert_payload_conditions",
    "build_anthropic_payload",
    "build_audited_request",
    "build_canary_request",
    "inspect_safe_payload",
    "user_prompt_for_fixture",
]
