"""Offline AIRequest builder. Consumes AIResponse.parsed later. No POST."""

from __future__ import annotations

import json
from typing import Any

from app.ai.contracts import AIRequest
from app.ai.estimation import estimate_tokens
from app.ai.providers._anthropic_schema import prepare_anthropic_json_schema
from app.ai.providers.anthropic_engine import AnthropicEngine
from app.book_generation.constants import (
    BOOK_GENERATION_TRANSPORT_VERSION,
    BOOK_GENERATOR_PROMPT_VERSION,
    STAGE_BOOK_GENERATION,
)
from app.book_generation.evidence import render_evidence_json
from app.book_generation.prompt import prompt_fingerprint
from app.book_generation.prompt_select import resolve_prompt_module
from app.book_generation.schema import build_book_generation_transport_schema
from app.book_generation.settings import GeneratorSettings, frozen_production_settings
from app.file_utils import content_hash


def build_chapter_request(
    evidence: dict[str, Any],
    *,
    settings: GeneratorSettings | None = None,
    max_output_tokens: int | None = None,
    prompt_version: str | None = None,
) -> AIRequest:
    settings = settings or frozen_production_settings()
    version = prompt_version or BOOK_GENERATOR_PROMPT_VERSION
    prompt = resolve_prompt_module(version)
    user = prompt.render_user_prompt(render_evidence_json(evidence))
    schema = build_book_generation_transport_schema()
    output = max_output_tokens if max_output_tokens is not None else settings.max_output_tokens
    return AIRequest(
        prompt=user,
        system_prompt=prompt.system_prompt(),
        model=settings.model,
        temperature=settings.temperature,
        max_output_tokens=output,
        response_schema=schema,
        thinking_mode=settings.thinking_mode,
        effort=settings.effort,
        thinking_budget_tokens=None,
        metadata={
            "stage": STAGE_BOOK_GENERATION,
            "prompt_version": version,
            "transport_version": BOOK_GENERATION_TRANSPORT_VERSION,
            "authorization_scope": "phase4b1-offline-payload-only",
            "chapter_id": (evidence.get("chapter") or {}).get("id"),
            "schema_sha256": content_hash(
                json.dumps(schema, ensure_ascii=False, sort_keys=True)
            ),
        },
    )


def build_future_anthropic_payload(
    evidence: dict[str, Any],
    *,
    settings: GeneratorSettings | None = None,
    max_output_tokens: int | None = None,
    prompt_version: str | None = None,
) -> dict[str, Any]:
    settings = settings or frozen_production_settings()
    request = build_chapter_request(
        evidence,
        settings=settings,
        max_output_tokens=max_output_tokens,
        prompt_version=prompt_version,
    )
    engine = AnthropicEngine(model=settings.model, api_key="offline-phase4b1-unused")
    payload = engine.build_payload(request, settings.model)
    for key in ("x-api-key", "api_key", "authorization"):
        payload.pop(key, None)
    return payload


def payload_audit(
    evidence: dict[str, Any],
    *,
    settings: GeneratorSettings | None = None,
    max_output_tokens: int | None = None,
    prompt_version: str | None = None,
) -> dict[str, Any]:
    settings = settings or frozen_production_settings()
    version = prompt_version or BOOK_GENERATOR_PROMPT_VERSION
    prompt = resolve_prompt_module(version)
    request = build_chapter_request(
        evidence,
        settings=settings,
        max_output_tokens=max_output_tokens,
        prompt_version=version,
    )
    payload = build_future_anthropic_payload(
        evidence,
        settings=settings,
        max_output_tokens=max_output_tokens,
        prompt_version=version,
    )
    system = request.system_prompt or ""
    user = request.prompt
    schema = build_book_generation_transport_schema()
    adapted = prepare_anthropic_json_schema(schema)
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return {
        "secrets_included": False,
        "model": payload.get("model"),
        "max_tokens": payload.get("max_tokens"),
        "thinking_present": "thinking" in payload,
        "effort_present": "effort" in (payload.get("output_config") or {}),
        "temperature_present": "temperature" in payload,
        "structured_output": (
            ((payload.get("output_config") or {}).get("format") or {}).get("type")
        ),
        "prompt_fingerprint": prompt_fingerprint(system, user),
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
        "prompt": prompt.prompt_bundle(),
        "prompt_version": version,
        "stage": STAGE_BOOK_GENERATION,
        "chapter_id": request.metadata.get("chapter_id"),
        "http_sent": False,
    }
