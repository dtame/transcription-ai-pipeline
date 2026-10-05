"""Build the isolated CH012 request with the 4B.2.16 faithful prompt."""

from __future__ import annotations

import json
from typing import Any

from app.ai.contracts import AIRequest
from app.ai.estimation import estimate_tokens
from app.ai.providers._anthropic_schema import prepare_anthropic_json_schema
from app.ai.providers.anthropic_engine import AnthropicEngine
from app.ai.thinking import THINKING_MODE_DISABLED
from app.book_editorial_alignment_4b216.prompt_candidate import (
    instruction_prompt,
    prompt_bundle,
    system_prompt,
)
from app.book_generation.constants import BOOK_GENERATION_TRANSPORT_VERSION
from app.book_generation.evidence import render_evidence_json
from app.book_generation.prompt import prompt_fingerprint
from app.book_generation.prompt_select import resolve_prompt_module
from app.book_generation.schema import build_book_generation_transport_schema
from app.book_generation.settings import GeneratorSettings, frozen_production_settings
from app.book_generation_4b217.constants import (
    AUTHORIZATION_SCOPE,
    FORBIDDEN_PROMPT_CLAUSES,
    MODEL,
    PHASE,
    PROMPT_VERSION,
    PROVIDER,
    STAGE_CANARY,
    TARGET_CHAPTER_ID,
)
from app.book_generation_4b217.guard import BookGeneration4217Error
from app.file_utils import content_hash


def render_faithful_user_prompt(bundle_json: str) -> str:
    return instruction_prompt() + "\nEVIDENCE_BUNDLE_JSON\n" + bundle_json + "\n"


def assert_faithful_prompt_isolated() -> dict[str, Any]:
    bundle = prompt_bundle()
    system = bundle["system"]
    for clause in FORBIDDEN_PROMPT_CLAUSES:
        if clause in system:
            raise BookGeneration4217Error(
                f"Faithful prompt still contains forbidden clause: {clause!r}"
            )
    try:
        resolve_prompt_module(PROMPT_VERSION)
    except ValueError:
        unregistered = True
    else:
        unregistered = False
    if not unregistered:
        raise BookGeneration4217Error(
            "Faithful prompt must remain unregistered in prompt_select."
        )
    return {
        "phase": PHASE,
        "version": bundle["version"],
        "activated_in_production": False,
        "registered_in_prompt_select": False,
        "replaces_historical_prompt": False,
        "used_for_isolated_ch012_only": True,
        "system": bundle["system"],
        "instructions": bundle["instructions"],
        "system_sha256": bundle["system_sha256"],
        "instructions_sha256": bundle["instructions_sha256"],
        "prompt_sha256": bundle["prompt_sha256"],
        "fundamental_rule_present": bundle["fundamental_rule_present"],
        "rejects_stylistic_expansion_as_a_license": bundle[
            "rejects_stylistic_expansion_as_a_license"
        ],
        "rejects_high_stylistic_freedom_slogan": bundle[
            "rejects_high_stylistic_freedom_slogan"
        ],
        "secrets_included": False,
    }


def build_ch012_request(
    evidence: dict[str, Any],
    *,
    max_output_tokens: int,
    settings: GeneratorSettings | None = None,
) -> AIRequest:
    settings = settings or frozen_production_settings()
    if settings.provider != PROVIDER or settings.model != MODEL:
        raise BookGeneration4217Error(
            "Configured book_generation model is not "
            f"{PROVIDER}/{MODEL}: {settings.provider}/{settings.model}."
        )
    snapshot = assert_faithful_prompt_isolated()
    user = render_faithful_user_prompt(render_evidence_json(evidence))
    schema = build_book_generation_transport_schema()
    return AIRequest(
        prompt=user,
        system_prompt=system_prompt(),
        model=settings.model,
        temperature=None,
        max_output_tokens=max_output_tokens,
        response_schema=schema,
        thinking_mode=THINKING_MODE_DISABLED,
        effort=None,
        thinking_budget_tokens=None,
        metadata={
            "stage": STAGE_CANARY,
            "prompt_version": PROMPT_VERSION,
            "prompt_sha256": snapshot["prompt_sha256"],
            "transport_version": BOOK_GENERATION_TRANSPORT_VERSION,
            "authorization_scope": AUTHORIZATION_SCOPE,
            "chapter_id": TARGET_CHAPTER_ID,
            "schema_sha256": content_hash(
                json.dumps(schema, ensure_ascii=False, sort_keys=True)
            ),
            "historical_prompt_used": False,
        },
    )


def build_anthropic_payload(request: AIRequest) -> dict[str, Any]:
    engine = AnthropicEngine(model=MODEL, api_key="offline-4b217-unused")
    payload = engine.build_payload(request, MODEL)
    for key in ("x-api-key", "api_key", "authorization"):
        payload.pop(key, None)
    return payload


def request_identity(
    evidence: dict[str, Any],
    *,
    max_output_tokens: int,
    settings: GeneratorSettings | None = None,
) -> dict[str, Any]:
    settings = settings or frozen_production_settings()
    snapshot = assert_faithful_prompt_isolated()
    request = build_ch012_request(
        evidence, max_output_tokens=max_output_tokens, settings=settings
    )
    payload = build_anthropic_payload(request)
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    system = request.system_prompt or ""
    user = request.prompt
    schema = build_book_generation_transport_schema()
    adapted = prepare_anthropic_json_schema(schema)
    repeat = json.dumps(
        build_anthropic_payload(
            build_ch012_request(
                evidence, max_output_tokens=max_output_tokens, settings=settings
            )
        ),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    sha = content_hash(encoded)
    return {
        "phase": PHASE,
        "chapter_id": TARGET_CHAPTER_ID,
        "provider": PROVIDER,
        "model": payload.get("model"),
        "prompt_version": PROMPT_VERSION,
        "prompt_snapshot": snapshot,
        "request_sha256": sha,
        "request_sha256_repeat": content_hash(repeat),
        "deterministic": sha == content_hash(repeat),
        "max_tokens": payload.get("max_tokens"),
        "thinking_present": "thinking" in payload,
        "temperature_present": "temperature" in payload,
        "structured_output": (
            ((payload.get("output_config") or {}).get("format") or {}).get("type")
        ),
        "prompt_fingerprint": prompt_fingerprint(system, user),
        "system_prompt_chars": len(system),
        "user_prompt_chars": len(user),
        "payload_chars": len(encoded),
        "payload_bytes": len(encoded.encode("utf-8")),
        "payload_sha256": sha,
        "local_input_token_estimate": estimate_tokens(
            system + "\n" + user, model=MODEL
        ).to_dict(),
        "adapted_schema_in_payload": adapted
        == ((payload.get("output_config") or {}).get("format") or {}).get("schema"),
        "payload": payload,
        "ai_request": request,
        "secrets_included": False,
        "http_sent": False,
        "historical_prompt_used": False,
    }


__all__ = [
    "assert_faithful_prompt_isolated",
    "build_anthropic_payload",
    "build_ch012_request",
    "render_faithful_user_prompt",
    "request_identity",
]
