"""Requête canary : prompt/schéma gelés Phase 4A, max_output canary, 0 POST ici."""

from __future__ import annotations

import json
from typing import Any

from app.ai.contracts import AIRequest
from app.ai.providers._anthropic_schema import prepare_anthropic_json_schema
from app.ai.providers.anthropic_engine import AnthropicEngine
from app.ai.thinking import THINKING_MODE_PROVIDER_DEFAULT
from app.editorial_planner_canary_4a1.constants import (
    AUTHORIZATION_SCOPE,
    CANARY_MAX_OUTPUT_TOKENS,
    CANARY_READ_TIMEOUT_SECONDS,
    MODEL,
    PROMPT_VERSION,
    PROVIDER,
    STAGE_CANARY,
    TRANSPORT_VERSION,
)
from app.editorial_planner_canary_4a1.guard import (
    assert_no_technical_windows,
    assert_synthetic_only_payload,
    assert_synthetic_source_map,
)
from app.editorial_planning.digest import render_digest
from app.editorial_planning.prompt import (
    prompt_bundle,
    prompt_fingerprint,
    render_user_prompt,
    system_prompt,
)
from app.editorial_planning.schema import build_editorial_plan_transport_schema
from app.editorial_planning.settings import PlannerSettings
from app.file_utils import content_hash
from app.source_analysis.models import SourceMap


def canary_settings() -> PlannerSettings:
    return PlannerSettings(
        provider=PROVIDER,
        model=MODEL,
        thinking_mode=THINKING_MODE_PROVIDER_DEFAULT,
        effort=None,
        max_output_tokens=CANARY_MAX_OUTPUT_TOKENS,
        temperature=None,
    )


def build_canary_request(source_map: SourceMap) -> AIRequest:
    assert_synthetic_source_map(source_map)
    settings = canary_settings()
    digest = render_digest(source_map)
    assert_no_technical_windows(digest)
    user = render_user_prompt(digest)
    schema = build_editorial_plan_transport_schema()
    return AIRequest(
        prompt=user,
        system_prompt=system_prompt(),
        model=settings.model,
        temperature=settings.temperature,
        max_output_tokens=settings.max_output_tokens,
        response_schema=schema,
        timeout_seconds=CANARY_READ_TIMEOUT_SECONDS,
        thinking_mode=settings.thinking_mode,
        effort=settings.effort,
        thinking_budget_tokens=None,
        metadata={
            "stage": STAGE_CANARY,
            "prompt_version": PROMPT_VERSION,
            "transport_version": TRANSPORT_VERSION,
            "authorization_scope": AUTHORIZATION_SCOPE,
            "production_source_map_sent": False,
            "canary": True,
            "schema_sha256": content_hash(
                json.dumps(schema, ensure_ascii=False, sort_keys=True)
            ),
        },
    )


def strip_secrets(payload: dict[str, Any]) -> dict[str, Any]:
    cleaned = dict(payload)
    for key in ("x-api-key", "api_key", "authorization", "Authorization"):
        cleaned.pop(key, None)
    return cleaned


def build_safe_anthropic_payload(request: AIRequest) -> dict[str, Any]:
    engine = AnthropicEngine(model=MODEL, api_key="offline-canary-4a1-unused")
    payload = strip_secrets(engine.build_payload(request, MODEL))
    return payload


def payload_audit(source_map: SourceMap) -> dict[str, Any]:
    request = build_canary_request(source_map)
    payload = build_safe_anthropic_payload(request)
    digest = render_digest(source_map)
    assert_synthetic_only_payload(
        payload,
        user_text=request.prompt,
        system_text=request.system_prompt or "",
        digest_text=digest,
    )
    system = request.system_prompt or ""
    user = request.prompt
    schema = build_editorial_plan_transport_schema()
    adapted = prepare_anthropic_json_schema(schema)
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    prompt = prompt_bundle()
    format_node = (payload.get("output_config") or {}).get("format") or {}
    return {
        "secrets_included": False,
        "model": payload.get("model"),
        "max_tokens": payload.get("max_tokens"),
        "thinking_present": "thinking" in payload,
        "thinking_value": payload.get("thinking"),
        "effort_present": "effort" in (payload.get("output_config") or {}),
        "temperature_present": "temperature" in payload,
        "structured_output": format_node.get("type"),
        "adapted_schema_in_payload": adapted == format_node.get("schema"),
        "prompt_fingerprint_system_plus_user": prompt_fingerprint(system, user),
        "frozen_prompt_sha256": prompt["prompt_sha256"],
        "digest_chars": len(digest),
        "digest_bytes": len(digest.encode("utf-8")),
        "user_prompt_chars": len(user),
        "system_prompt_chars": len(system),
        "payload_chars": len(encoded),
        "payload_bytes": len(encoded.encode("utf-8")),
        "payload_sha256": content_hash(encoded),
        "payload_keys": sorted(payload.keys()),
        "stage": STAGE_CANARY,
        "authorization_scope": AUTHORIZATION_SCOPE,
        "production_data_sent": False,
        "request_thinking_mode": request.thinking_mode,
        "request_effort": request.effort,
        "request_thinking_budget_tokens": request.thinking_budget_tokens,
        "payload": payload,
    }


__all__ = [
    "build_canary_request",
    "build_safe_anthropic_payload",
    "canary_settings",
    "payload_audit",
    "strip_secrets",
]
