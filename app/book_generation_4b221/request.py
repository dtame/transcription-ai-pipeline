"""Build the isolated CH018 request with prompt 1.1. No fallback."""

from __future__ import annotations

import json
from typing import Any

from app.ai.contracts import AIRequest
from app.ai.estimation import estimate_tokens
from app.ai.providers._anthropic_schema import prepare_anthropic_json_schema
from app.ai.providers.anthropic_engine import AnthropicEngine
from app.ai.thinking import THINKING_MODE_DISABLED
from app.book_generation.constants import BOOK_GENERATION_TRANSPORT_VERSION
from app.book_generation.evidence import render_evidence_json
from app.book_generation.prompt import prompt_fingerprint
from app.book_generation.prompt_select import resolve_prompt_module
from app.book_generation.schema import build_book_generation_transport_schema
from app.book_generation.settings import GeneratorSettings, frozen_production_settings
from app.book_generation_4b221.constants import (
    AUTHORIZATION_SCOPE,
    EXPECTED_PROMPT_1_1_INSTRUCTIONS_SHA256,
    EXPECTED_PROMPT_1_1_SHA256,
    EXPECTED_PROMPT_1_1_SYSTEM_SHA256,
    FORBIDDEN_PROMPT_CLAUSES,
    FORBIDDEN_PROMPTS,
    MODEL,
    PHASE,
    PROMPT_VERSION,
    PROVIDER,
    STAGE_CANARY,
    TARGET_CHAPTER_ID,
    THINKING_MODE,
)
from app.book_generation_4b221.guard import BookGeneration4221Error, assert_prompt_allowed
from app.book_scale_up_preparation_4b220.prompt_select import (
    prompt_1_1_registered_in_production,
    resolve_isolated_prompt,
)
from app.file_utils import content_hash


def load_isolated_prompt_1_1():
    assert_prompt_allowed(PROMPT_VERSION)
    if prompt_1_1_registered_in_production():
        raise BookGeneration4221Error(
            "Prompt 1.1 must remain unregistered in production prompt_select."
        )
    return resolve_isolated_prompt(PROMPT_VERSION, activate=False)


def assert_prompt_1_1_isolated() -> dict[str, Any]:
    module = load_isolated_prompt_1_1()
    bundle = module.prompt_bundle()
    if bundle.get("version") != PROMPT_VERSION:
        raise BookGeneration4221Error(
            f"Prompt candidate version is {bundle.get('version')!r}, not {PROMPT_VERSION}."
        )
    system = bundle["system"]
    for clause in FORBIDDEN_PROMPT_CLAUSES:
        if clause in system:
            raise BookGeneration4221Error(
                f"Prompt 1.1 still contains forbidden clause: {clause!r}"
            )
    for forbidden in FORBIDDEN_PROMPTS:
        try:
            resolve_prompt_module(forbidden)
        except ValueError:
            if forbidden == "book-generator-1.0.1":
                raise BookGeneration4221Error(
                    "Historical production prompt 1.0.1 disappeared from prompt_select."
                )
        else:
            if forbidden == PROMPT_VERSION:
                raise BookGeneration4221Error("Prompt 1.1 registered in production.")
    try:
        resolve_prompt_module(PROMPT_VERSION)
    except ValueError:
        unregistered = True
    else:
        unregistered = False
    if not unregistered:
        raise BookGeneration4221Error(
            "Prompt 1.1 must remain unregistered in prompt_select."
        )
    if bundle.get("prompt_sha256") != EXPECTED_PROMPT_1_1_SHA256:
        raise BookGeneration4221Error(
            "Prompt 1.1 hash diverged from the 4B.2.20 isolated candidate."
        )
    if bundle.get("system_sha256") != EXPECTED_PROMPT_1_1_SYSTEM_SHA256:
        raise BookGeneration4221Error("Prompt 1.1 system hash diverged.")
    if bundle.get("instructions_sha256") != EXPECTED_PROMPT_1_1_INSTRUCTIONS_SHA256:
        raise BookGeneration4221Error("Prompt 1.1 instructions hash diverged.")
    if not bundle.get("idea_handle_instruction_present"):
        raise BookGeneration4221Error(
            "Prompt 1.1 is missing the paras[].e IDEA-handle instruction."
        )
    return {
        "phase": PHASE,
        "version": bundle["version"],
        "activated_in_production": False,
        "registered_in_prompt_select": False,
        "replaces_historical_prompt": False,
        "replaces_faithful_prompt_1_0_candidate": False,
        "used_for_isolated_ch018_only": True,
        "selected_by": "app.book_scale_up_preparation_4b220.prompt_select",
        "fallback": None,
        "fallback_forbidden": True,
        "system": bundle["system"],
        "instructions": bundle["instructions"],
        "system_sha256": bundle["system_sha256"],
        "instructions_sha256": bundle["instructions_sha256"],
        "prompt_sha256": bundle["prompt_sha256"],
        "fundamental_rule_present": bundle["fundamental_rule_present"],
        "authorial_voice_present": bundle["authorial_voice_present"],
        "idea_handle_instruction_present": bundle["idea_handle_instruction_present"],
        "forbids_invented_idea_correspondence": bundle[
            "forbids_invented_idea_correspondence"
        ],
        "rejects_stylistic_expansion_as_a_license": bundle[
            "rejects_stylistic_expansion_as_a_license"
        ],
        "rejects_high_stylistic_freedom_slogan": bundle[
            "rejects_high_stylistic_freedom_slogan"
        ],
        "secrets_included": False,
    }


def render_faithful_user_prompt(bundle_json: str, *, instructions: str) -> str:
    return instructions + "\nEVIDENCE_BUNDLE_JSON\n" + bundle_json + "\n"


def build_ch018_request(
    evidence: dict[str, Any],
    *,
    max_output_tokens: int,
    settings: GeneratorSettings | None = None,
) -> AIRequest:
    settings = settings or frozen_production_settings()
    if settings.provider != PROVIDER or settings.model != MODEL:
        raise BookGeneration4221Error(
            "Configured book_generation model is not "
            f"{PROVIDER}/{MODEL}: {settings.provider}/{settings.model}."
        )
    snapshot = assert_prompt_1_1_isolated()
    module = load_isolated_prompt_1_1()
    user = render_faithful_user_prompt(
        render_evidence_json(evidence),
        instructions=module.instruction_prompt(),
    )
    schema = build_book_generation_transport_schema()
    if THINKING_MODE != THINKING_MODE_DISABLED:
        raise BookGeneration4221Error(
            "Thinking is not the verified budgeted configuration. STOP."
        )
    return AIRequest(
        prompt=user,
        system_prompt=module.system_prompt(),
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
            "thinking_mode": THINKING_MODE_DISABLED,
        },
    )


def build_anthropic_payload(request: AIRequest) -> dict[str, Any]:
    engine = AnthropicEngine(model=MODEL, api_key="offline-4b221-unused")
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
    snapshot = assert_prompt_1_1_isolated()
    request = build_ch018_request(
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
            build_ch018_request(
                evidence, max_output_tokens=max_output_tokens, settings=settings
            )
        ),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    sha = content_hash(encoded)
    thinking = payload.get("thinking")
    thinking_type = thinking.get("type") if isinstance(thinking, dict) else None
    thinking_disabled = thinking_type == "disabled"
    if thinking is not None and not thinking_disabled:
        raise BookGeneration4221Error(
            "Thinking is enabled in the Anthropic payload. Cost cannot be bounded. STOP."
        )
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
        "thinking_present": thinking is not None,
        "thinking_disabled": thinking_disabled,
        "thinking_type": thinking_type,
        "thinking_mode": THINKING_MODE_DISABLED,
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
    "assert_prompt_1_1_isolated",
    "build_anthropic_payload",
    "build_ch018_request",
    "load_isolated_prompt_1_1",
    "render_faithful_user_prompt",
    "request_identity",
]
