"""Construction exacte de la requête production 3.0. 0 POST. build_payload only."""

from __future__ import annotations

import json
from typing import Any

from app.ai.contracts import AIRequest
from app.ai.estimation import estimate_tokens
from app.ai.providers._anthropic_schema import prepare_anthropic_json_schema
from app.ai.providers.anthropic_engine import AnthropicEngine
from app.file_utils import content_hash
from app.source_analysis_v31_global_real_consolidation.guard import (
    reject_raw_transcript_payload,
)
from app.source_analysis_v31_global_real_consolidation.input_contract import compact_text
from app.source_analysis_v31_global_reuse_output.prompt_v30 import prompt_v30_bundle
from app.source_analysis_v31_global_reuse_output.transport_v30 import (
    build_global_consolidation_schema_v30,
)
from app.source_analysis_v31_global_v30_exact_preflight.constants import (
    CONNECT_TIMEOUT_SECONDS,
    FUTURE_AUTHORIZATION_SCOPE,
    MODEL,
    PRODUCTION_MAX_OUTPUT_TOKENS,
    PROJECT_NAME,
    PROMPT_VERSION,
    PROVIDER,
    READ_TIMEOUT_SECONDS,
    READY_WINDOWS,
    SECRET_KEY_NAMES,
    SECRET_SUBSTRINGS,
    STAGE_PREFLIGHT,
    THINKING_CONTRACT,
    THINKING_MODE,
    TRANSPORT_VERSION,
)
from app.source_analysis_v31_global_v30_exact_preflight.identity import (
    canonical_json,
    request_identity,
    request_identity_payload,
    verify_schema_identity,
)
from app.source_analysis_v31_global_v30_exact_preflight.offline import (
    GlobalExactPreflightError,
)


def user_prompt_for_normalized(normalized: dict[str, Any]) -> str:
    prompt = prompt_v30_bundle()
    compact = compact_text(normalized)
    return prompt["instructions"] + "\n" + compact + "\n"


def build_production_request(normalized: dict[str, Any]) -> AIRequest:
    prompt = prompt_v30_bundle()
    schema = build_global_consolidation_schema_v30()
    return AIRequest(
        prompt=user_prompt_for_normalized(normalized),
        system_prompt=prompt["system"],
        model=MODEL,
        temperature=None,
        max_output_tokens=PRODUCTION_MAX_OUTPUT_TOKENS,
        response_schema=schema,
        timeout_seconds=READ_TIMEOUT_SECONDS,
        thinking_mode=THINKING_MODE,
        effort=None,
        thinking_budget_tokens=None,
        metadata={
            "stage": STAGE_PREFLIGHT,
            "window_id": "GLOBAL",
            "prompt_version": PROMPT_VERSION,
            "transport_version": TRANSPORT_VERSION,
            "thinking_contract": THINKING_CONTRACT,
            "authorization_scope": FUTURE_AUTHORIZATION_SCOPE,
            "canary": False,
            "preflight_only": True,
            "ready_windows": list(READY_WINDOWS),
            "schema_sha256": content_hash(
                json.dumps(schema, ensure_ascii=False, sort_keys=True)
            ),
            "prompt_sha256": prompt["combined_sha256"],
            "input_sha256": normalized.get("compact_sha256"),
        },
    )


def _payload_engine() -> AnthropicEngine:
    return AnthropicEngine(
        model=MODEL,
        api_key="cle-de-test",
        timeout_seconds=READ_TIMEOUT_SECONDS,
        connect_timeout_seconds=CONNECT_TIMEOUT_SECONDS,
    )


def build_anthropic_payload(request: AIRequest) -> dict[str, Any]:
    return _payload_engine().build_payload(request, MODEL)


def sanitize_provider_visible(payload: dict[str, Any]) -> dict[str, Any]:
    def _clean(value: Any) -> Any:
        if isinstance(value, dict):
            return {
                str(key): _clean(item)
                for key, item in value.items()
                if str(key) not in SECRET_KEY_NAMES
            }
        if isinstance(value, list):
            return [_clean(item) for item in value]
        return value

    return _clean(payload)


def provider_visible_bytes(payload: dict[str, Any]) -> bytes:
    sanitized = sanitize_provider_visible(payload)
    text = canonical_json(sanitized)
    return text.encode("utf-8")


def secrets_present(blob: Any) -> list[str]:
    hits: list[str] = []

    def _walk(value: Any, key_name: str = "") -> None:
        lowered_key = key_name.lower()
        if lowered_key in {item.lower() for item in SECRET_KEY_NAMES} and lowered_key not in {
            "headers",
            "authorization",
        }:
            hits.append(key_name)
        if isinstance(value, dict):
            for key, item in value.items():
                _walk(item, str(key))
            return
        if isinstance(value, list):
            for item in value:
                _walk(item, key_name)
            return
        text = str(value)
        for token in SECRET_SUBSTRINGS:
            if token.lower() in text.lower():
                hits.append(token)

    if isinstance(blob, str):
        lowered = blob.lower()
        for token in SECRET_SUBSTRINGS:
            if token.lower() in lowered:
                hits.append(token)
        if '"api_key"' in lowered or '"x-api-key"' in lowered or '"anthropic_api_key"' in lowered:
            hits.append("api_key")
        return sorted(set(hits))
    _walk(blob)
    return sorted(set(hits))


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
    window_set_sha256: str,
) -> dict[str, Any]:
    sanitized = sanitize_provider_visible(payload)
    visible = provider_visible_bytes(sanitized)
    output_config = sanitized.get("output_config")
    format_block = output_config.get("format") if isinstance(output_config, dict) else None
    schema = format_block.get("schema") if isinstance(format_block, dict) else None
    thinking = sanitized.get("thinking")
    thinking_type = thinking.get("type") if isinstance(thinking, dict) else None
    effort_present = isinstance(output_config, dict) and "effort" in output_config
    prompt = prompt_v30_bundle()
    local_est = estimate_tokens(
        (request.system_prompt or "") + "\n" + request.prompt,
        model=MODEL,
    )
    payload_est = estimate_tokens(visible.decode("utf-8"), model=MODEL)
    identity_fields = request_identity_payload(
        schema_hash=str(schema_metrics.get("hash") or ""),
        prompt_hash=prompt["combined_sha256"],
        normalized_input_hash=input_hash,
        provider_visible_hash=content_hash(visible.decode("utf-8")),
        window_set_sha256=window_set_sha256,
        max_output=int(request.max_output_tokens or PRODUCTION_MAX_OUTPUT_TOKENS),
    )
    identity = request_identity(
        schema_hash=str(schema_metrics.get("hash") or ""),
        prompt_hash=prompt["combined_sha256"],
        normalized_input_hash=input_hash,
        provider_visible_hash=content_hash(visible.decode("utf-8")),
        window_set_sha256=window_set_sha256,
        max_output=int(request.max_output_tokens or PRODUCTION_MAX_OUTPUT_TOKENS),
    )
    secret_hits = secrets_present(sanitized)
    request_chars = len((request.system_prompt or "") + request.prompt)
    return {
        "model": sanitized.get("model"),
        "max_tokens": sanitized.get("max_tokens"),
        "thinking_type": thinking_type,
        "thinking": thinking,
        "effort_present": effort_present,
        "budget_tokens_present": _nested_has(sanitized, "budget_tokens"),
        "task_budget_present": _nested_has(sanitized, "task_budget"),
        "temperature_present": "temperature" in sanitized,
        "output_config_present": isinstance(output_config, dict),
        "format_present": isinstance(format_block, dict) and "schema" in format_block,
        "format_type": format_block.get("type") if isinstance(format_block, dict) else None,
        "schema_version": TRANSPORT_VERSION,
        "schema_hash": schema_metrics.get("hash"),
        "raw_bytes": schema_metrics.get("raw_bytes"),
        "adapted_bytes": schema_metrics.get("adapted_bytes"),
        "prompt_version": PROMPT_VERSION,
        "prompt_hash": prompt["combined_sha256"],
        "message_count": len(sanitized.get("messages") or []),
        "system_present": bool(sanitized.get("system")),
        "normalized_input_hash": input_hash,
        "provider_visible_hash": content_hash(visible.decode("utf-8")),
        "request_identity": identity,
        "identity_fields": identity_fields,
        "window_set_sha256": window_set_sha256,
        "authorization_scope": FUTURE_AUTHORIZATION_SCOPE,
        "provider": PROVIDER,
        "local_input_estimate_tokens": local_est.tokens,
        "local_input_estimate_method": local_est.method,
        "payload_local_estimate_tokens": payload_est.tokens,
        "payload_local_estimate_method": payload_est.method,
        "request_prompt_chars": request_chars,
        "request_prompt_bytes": len(
            ((request.system_prompt or "") + request.prompt).encode("utf-8")
        ),
        "provider_visible_chars": len(visible.decode("utf-8")),
        "provider_visible_bytes": len(visible),
        "compact_chars": len(compact),
        "production_max_output_unchanged": PRODUCTION_MAX_OUTPUT_TOKENS == 48000,
        "secrets_included": False,
        "secret_hits": secret_hits,
        "raw_transcript_included": False,
        "ready_windows": list(READY_WINDOWS),
        "http_timeouts_excluded_from_body": {
            "connect_timeout_seconds": CONNECT_TIMEOUT_SECONDS,
            "read_timeout_seconds": READ_TIMEOUT_SECONDS,
            "note": (
                "HTTP timeouts are engine configuration, not Anthropic JSON body. "
                "They are recorded in request identity metadata but excluded from "
                "the provider-visible semantic hash of build_payload()."
            ),
        },
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
    if audit.get("max_tokens") != PRODUCTION_MAX_OUTPUT_TOKENS:
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
    if audit.get("secret_hits"):
        failures.append(f"secrets={audit.get('secret_hits')}")
    if not audit.get("production_max_output_unchanged"):
        failures.append("production max_output mutated")
    if failures:
        raise GlobalExactPreflightError(
            "Payload conditions failed — STOP WITHOUT PROVIDER CALL: "
            + "; ".join(failures)
        )


def build_audited_request(
    normalized: dict[str, Any],
    *,
    window_set_sha256: str,
    project_name: str | None = None,
    sortie_dir: Any = None,
) -> dict[str, Any]:
    schema_metrics = verify_schema_identity(
        project_name or PROJECT_NAME,
        sortie_dir=sortie_dir,
    )
    request = build_production_request(normalized)
    payload = build_anthropic_payload(request)
    compact = compact_text(normalized)
    reject_raw_transcript_payload(request.prompt, compact_text=compact)
    audit = inspect_safe_payload(
        request,
        payload,
        input_hash=str(normalized.get("compact_sha256") or ""),
        schema_metrics=schema_metrics,
        compact=compact,
        window_set_sha256=window_set_sha256,
    )
    assert_payload_conditions(audit)
    adapted = prepare_anthropic_json_schema(build_global_consolidation_schema_v30())
    audit["adapted_bytes_recomputed"] = len(
        json.dumps(adapted, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    )
    return {
        "request": request,
        "payload": sanitize_provider_visible(payload),
        "audit": audit,
        "schema_metrics": schema_metrics,
        "compact": compact,
    }


def dry_run_identity_tuple(audit: dict[str, Any]) -> tuple[Any, ...]:
    return (
        audit.get("normalized_input_hash"),
        audit.get("provider_visible_hash"),
        audit.get("prompt_version"),
        audit.get("schema_version"),
        audit.get("schema_hash"),
        audit.get("model"),
        audit.get("thinking_type"),
        audit.get("max_tokens"),
        audit.get("request_identity"),
        audit.get("window_set_sha256"),
    )


__all__ = [
    "assert_payload_conditions",
    "build_anthropic_payload",
    "build_audited_request",
    "build_production_request",
    "dry_run_identity_tuple",
    "inspect_safe_payload",
    "provider_visible_bytes",
    "sanitize_provider_visible",
    "secrets_present",
    "user_prompt_for_normalized",
]
