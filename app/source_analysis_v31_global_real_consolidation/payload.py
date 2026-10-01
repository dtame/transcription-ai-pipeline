"""Construction et audit sûr du payload Anthropic A.38. 0 POST ici."""

from __future__ import annotations

import json
from typing import Any

from app.ai.contracts import AIRequest
from app.ai.estimation import estimate_tokens
from app.ai.providers._anthropic_schema import prepare_anthropic_json_schema
from app.ai.providers.anthropic_engine import AnthropicEngine
from app.file_utils import content_hash
from app.source_analysis_v31_global_canary_forensics.prompt_v101 import prompt_v101_bundle
from app.source_analysis_v31_global_canary_forensics.transport_v11 import (
    build_global_consolidation_schema_v11,
)
from app.source_analysis_v31_global_real_consolidation.constants import (
    AUTHORIZATION_SCOPE,
    MAX_OUTPUT_TOKENS,
    MODEL,
    PRODUCTION_MAX_OUTPUT_TOKENS,
    PROJECT_NAME,
    PROMPT_VERSION,
    PROVIDER,
    READ_TIMEOUT_SECONDS,
    READY_WINDOWS,
    STAGE_CANARY,
    THINKING_CONTRACT,
    THINKING_MODE,
    TRANSPORT_VERSION,
)
from app.source_analysis_v31_global_real_consolidation.guard import (
    GlobalRealConsolidationError,
    reject_contract_drift,
    reject_raw_transcript_payload,
)
from app.source_analysis_v31_global_real_consolidation.identity import (
    request_identity,
    request_identity_payload,
    verify_schema_identity,
)
from app.source_analysis_v31_global_real_consolidation.input_contract import compact_text


def user_prompt_for_normalized(normalized: dict[str, Any]) -> str:
    prompt = prompt_v101_bundle()
    compact = compact_text(normalized)
    return prompt["instructions"] + "\n" + compact + "\n"


def build_consolidation_request(normalized: dict[str, Any]) -> AIRequest:
    prompt = prompt_v101_bundle()
    system = prompt["system"]
    user = user_prompt_for_normalized(normalized)
    schema = build_global_consolidation_schema_v11()
    return AIRequest(
        prompt=user,
        system_prompt=system,
        model=MODEL,
        temperature=None,
        max_output_tokens=MAX_OUTPUT_TOKENS,
        response_schema=schema,
        timeout_seconds=READ_TIMEOUT_SECONDS,
        thinking_mode=THINKING_MODE,
        effort=None,
        thinking_budget_tokens=None,
        metadata={
            "stage": STAGE_CANARY,
            "window_id": "GLOBAL",
            "prompt_version": PROMPT_VERSION,
            "transport_version": TRANSPORT_VERSION,
            "thinking_contract": THINKING_CONTRACT,
            "authorization_scope": AUTHORIZATION_SCOPE,
            "canary": True,
            "ready_windows": list(READY_WINDOWS),
            "schema_sha256": content_hash(
                json.dumps(schema, ensure_ascii=False, sort_keys=True)
            ),
            "prompt_sha256": prompt["combined_sha256"],
            "input_sha256": normalized.get("compact_sha256"),
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
    input_hash: str,
    schema_metrics: dict[str, Any],
    compact: str,
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
    prompt = prompt_v101_bundle()
    local_est = estimate_tokens(
        (request.system_prompt or "") + "\n" + request.prompt,
        model=MODEL,
    )
    compact_chars = len(compact)
    identity_fields = request_identity_payload(
        schema_hash=str(schema_metrics.get("hash") or ""),
        prompt_hash=prompt["combined_sha256"],
        input_hash=input_hash,
        max_output=int(request.max_output_tokens or MAX_OUTPUT_TOKENS),
    )
    identity = request_identity(
        schema_hash=str(schema_metrics.get("hash") or ""),
        prompt_hash=prompt["combined_sha256"],
        input_hash=input_hash,
        max_output=int(request.max_output_tokens or MAX_OUTPUT_TOKENS),
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
        "schema_version": TRANSPORT_VERSION,
        "schema_hash": schema_metrics.get("hash"),
        "adapted_schema_hash": schema_hash,
        "raw_bytes": schema_metrics.get("raw_bytes"),
        "adapted_bytes": schema_metrics.get("adapted_bytes"),
        "prompt_version": PROMPT_VERSION,
        "prompt_hash": prompt["combined_sha256"],
        "message_count": len(payload.get("messages") or []),
        "system_present": bool(payload.get("system")),
        "input_hash": input_hash,
        "request_identity": identity,
        "identity_fields": identity_fields,
        "authorization_scope": AUTHORIZATION_SCOPE,
        "provider": PROVIDER,
        "local_input_estimate_tokens": local_est.tokens,
        "local_input_estimate_method": local_est.method,
        "request_prompt_chars": len((request.system_prompt or "") + request.prompt),
        "compact_chars": compact_chars,
        "production_max_output_unchanged": PRODUCTION_MAX_OUTPUT_TOKENS == 32000,
        "secrets_included": False,
        "raw_transcript_included": False,
        "ready_windows": list(READY_WINDOWS),
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
    if audit.get("max_tokens") != MAX_OUTPUT_TOKENS:
        failures.append(f"max_tokens={audit.get('max_tokens')!r}")
    if audit.get("message_count") != 1:
        failures.append(f"message_count={audit.get('message_count')!r}")
    if not audit.get("system_present"):
        failures.append("system missing")
    if audit.get("schema_version") != TRANSPORT_VERSION:
        failures.append(f"schema={audit.get('schema_version')!r}")
    if audit.get("prompt_version") != PROMPT_VERSION:
        failures.append(f"prompt={audit.get('prompt_version')!r}")
    if audit.get("raw_transcript_included"):
        failures.append("raw transcript included")
    if not audit.get("production_max_output_unchanged"):
        failures.append("production max_output mutated")
    if failures:
        raise GlobalRealConsolidationError(
            "Payload conditions failed — STOP WITHOUT PROVIDER CALL: "
            + "; ".join(failures)
        )
    reject_contract_drift(
        prompt_version=audit.get("prompt_version"),
        transport_version=audit.get("schema_version"),
        schema_hash=audit.get("schema_hash"),
        model=audit.get("model"),
        thinking_mode=audit.get("thinking_type"),
        max_output=audit.get("max_tokens"),
    )


def build_audited_request(
    normalized: dict[str, Any],
    *,
    project_name: str | None = None,
    sortie_dir: Any = None,
) -> dict[str, Any]:
    schema_metrics = verify_schema_identity(
        project_name or PROJECT_NAME,
        sortie_dir=sortie_dir,
    )
    request = build_consolidation_request(normalized)
    payload = build_anthropic_payload(request)
    compact = compact_text(normalized)
    reject_raw_transcript_payload(request.prompt, compact_text=compact)
    audit = inspect_safe_payload(
        request,
        payload,
        input_hash=str(normalized.get("compact_sha256") or ""),
        schema_metrics=schema_metrics,
        compact=compact,
    )
    assert_payload_conditions(audit)
    adapted = prepare_anthropic_json_schema(build_global_consolidation_schema_v11())
    audit["adapted_bytes_recomputed"] = len(
        json.dumps(adapted, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    )
    return {
        "request": request,
        "payload": payload,
        "audit": audit,
        "schema_metrics": schema_metrics,
        "compact": compact,
    }


def dry_run_identity_tuple(audit: dict[str, Any]) -> tuple[Any, ...]:
    return (
        audit.get("input_hash"),
        audit.get("prompt_version"),
        audit.get("schema_version"),
        audit.get("schema_hash"),
        audit.get("model"),
        audit.get("thinking_type"),
        audit.get("max_tokens"),
        audit.get("request_identity"),
    )


__all__ = [
    "assert_payload_conditions",
    "build_anthropic_payload",
    "build_audited_request",
    "build_consolidation_request",
    "dry_run_identity_tuple",
    "inspect_safe_payload",
    "user_prompt_for_normalized",
]
