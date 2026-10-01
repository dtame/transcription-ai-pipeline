"""Production request path for editorial-planner-1.0.1. Offline payload only."""

from __future__ import annotations

import json
from typing import Any

from app.ai.contracts import AIRequest
from app.ai.estimation import estimate_tokens
from app.ai.providers._anthropic_schema import prepare_anthropic_json_schema
from app.ai.providers.anthropic_engine import AnthropicEngine
from app.editorial_planning.constants import (
    EDITORIAL_PLAN_TRANSPORT_VERSION,
    STAGE_EDITORIAL_PLANNING,
)
from app.editorial_planning.digest import render_digest_v101
from app.editorial_planning.language_policy import (
    SUCCESSOR_PROMPT_VERSION,
    normalize_language_code,
)
from app.editorial_planning.prompt_v101 import (
    prompt_bundle,
    prompt_fingerprint,
    render_user_prompt,
    system_prompt,
)
from app.editorial_planning.schema import build_editorial_plan_transport_schema
from app.editorial_planning.settings import PlannerSettings, frozen_production_settings
from app.file_utils import content_hash
from app.source_analysis.models import SourceMap


def build_planner_request_v101(
    source_map: SourceMap,
    *,
    canonical_document_language: str,
    settings: PlannerSettings | None = None,
) -> AIRequest:
    settings = settings or frozen_production_settings()
    language = normalize_language_code(canonical_document_language)
    if not language:
        raise ValueError("canonical_document_language is required")
    digest = render_digest_v101(
        source_map, canonical_document_language=language
    )
    user = render_user_prompt(digest, canonical_document_language=language)
    schema = build_editorial_plan_transport_schema()
    return AIRequest(
        prompt=user,
        system_prompt=system_prompt(language),
        model=settings.model,
        temperature=settings.temperature,
        max_output_tokens=settings.max_output_tokens,
        response_schema=schema,
        thinking_mode=settings.thinking_mode,
        effort=settings.effort,
        thinking_budget_tokens=None,
        metadata={
            "stage": STAGE_EDITORIAL_PLANNING,
            "prompt_version": SUCCESSOR_PROMPT_VERSION,
            "transport_version": EDITORIAL_PLAN_TRANSPORT_VERSION,
            "canonical_document_language": language,
            "authorization_scope": "phase4a32-offline-payload-only",
            "schema_sha256": content_hash(
                json.dumps(schema, ensure_ascii=False, sort_keys=True)
            ),
        },
    )


def build_future_anthropic_payload_v101(
    source_map: SourceMap,
    *,
    canonical_document_language: str,
    settings: PlannerSettings | None = None,
) -> dict[str, Any]:
    settings = settings or frozen_production_settings()
    request = build_planner_request_v101(
        source_map,
        canonical_document_language=canonical_document_language,
        settings=settings,
    )
    engine = AnthropicEngine(model=settings.model, api_key="offline-phase4a32-unused")
    payload = engine.build_payload(request, settings.model)
    for key in ("x-api-key", "api_key", "authorization"):
        payload.pop(key, None)
    return payload


def payload_audit_v101(
    source_map: SourceMap,
    *,
    canonical_document_language: str,
    settings: PlannerSettings | None = None,
) -> dict[str, Any]:
    settings = settings or frozen_production_settings()
    language = normalize_language_code(canonical_document_language)
    request = build_planner_request_v101(
        source_map,
        canonical_document_language=language,
        settings=settings,
    )
    payload = build_future_anthropic_payload_v101(
        source_map,
        canonical_document_language=language,
        settings=settings,
    )
    system = request.system_prompt or ""
    user = request.prompt
    digest = render_digest_v101(source_map, canonical_document_language=language)
    schema = build_editorial_plan_transport_schema()
    adapted = prepare_anthropic_json_schema(schema)
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return {
        "secrets_included": False,
        "model": payload.get("model"),
        "max_tokens": payload.get("max_tokens"),
        "thinking_present": "thinking" in payload,
        "effort_present": "effort" in (payload.get("output_config") or {}),
        "temperature_present": "temperature" in payload,
        "canonical_document_language": language,
        "structured_output": (
            ((payload.get("output_config") or {}).get("format") or {}).get("type")
        ),
        "prompt_fingerprint": prompt_fingerprint(system, user),
        "digest_chars": len(digest),
        "digest_bytes": len(digest.encode("utf-8")),
        "user_prompt_chars": len(user),
        "system_prompt_chars": len(system),
        "payload_chars": len(encoded),
        "payload_bytes": len(encoded.encode("utf-8")),
        "payload_sha256": content_hash(encoded),
        "local_input_token_estimate": estimate_tokens(
            system + "\n" + user, model=settings.model
        ).to_dict(),
        "adapted_schema_in_payload": adapted
        == ((payload.get("output_config") or {}).get("format") or {}).get("schema"),
        "prompt": prompt_bundle(language),
        "stage": STAGE_EDITORIAL_PLANNING,
    }


__all__ = [
    "build_future_anthropic_payload_v101",
    "build_planner_request_v101",
    "payload_audit_v101",
]
