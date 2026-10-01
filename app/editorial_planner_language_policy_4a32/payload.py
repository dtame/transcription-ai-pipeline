"""Exact 1.0.1 production request via the real planner payload path. 0 POST."""

from __future__ import annotations

import json
from dataclasses import replace
from typing import Any

from app.ai.estimation import estimate_tokens
from app.ai.thinking import THINKING_MODE_PROVIDER_DEFAULT
from app.editorial_planner_language_policy_4a32.constants import (
    AUTHORIZATION_SCOPE,
    MAX_OUTPUT_TOKENS,
    MODEL,
    THINKING_MODE,
)
from app.editorial_planner_language_policy_4a32.guard import (
    redact_secrets,
    scan_technical_chunks,
)
from app.editorial_planning.digest import build_planner_digest_v101, render_digest_v101
from app.editorial_planning.language_policy import normalize_language_code
from app.editorial_planning.payload_v101 import (
    build_future_anthropic_payload_v101,
    build_planner_request_v101,
)
from app.editorial_planning.prompt_v101 import instruction_prompt, prompt_fingerprint
from app.editorial_planning.settings import PlannerSettings, frozen_production_settings
from app.file_utils import content_hash
from app.source_analysis.models import SourceMap


def production_settings(*, max_output_tokens: int = MAX_OUTPUT_TOKENS) -> PlannerSettings:
    base = frozen_production_settings()
    if base.thinking_mode != THINKING_MODE_PROVIDER_DEFAULT:
        raise RuntimeError("frozen thinking_mode is no longer provider_default")
    if base.effort is not None:
        raise RuntimeError("frozen effort is no longer none")
    return replace(base, max_output_tokens=int(max_output_tokens))


def build_production_request(
    source_map: SourceMap,
    *,
    canonical_document_language: str,
    max_output_tokens: int = MAX_OUTPUT_TOKENS,
) -> Any:
    settings = production_settings(max_output_tokens=max_output_tokens)
    return build_planner_request_v101(
        source_map,
        canonical_document_language=canonical_document_language,
        settings=settings,
    )


def build_production_payload(
    source_map: SourceMap,
    *,
    canonical_document_language: str,
    max_output_tokens: int = MAX_OUTPUT_TOKENS,
) -> dict[str, Any]:
    settings = production_settings(max_output_tokens=max_output_tokens)
    payload = build_future_anthropic_payload_v101(
        source_map,
        canonical_document_language=canonical_document_language,
        settings=settings,
    )
    return redact_secrets(payload)


def encode_payload(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def request_identity(
    source_map: SourceMap,
    *,
    canonical_document_language: str,
    max_output_tokens: int = MAX_OUTPUT_TOKENS,
) -> dict[str, Any]:
    language = normalize_language_code(canonical_document_language)
    first = build_production_payload(
        source_map,
        canonical_document_language=language,
        max_output_tokens=max_output_tokens,
    )
    second = build_production_payload(
        source_map,
        canonical_document_language=language,
        max_output_tokens=max_output_tokens,
    )
    encoded_first = encode_payload(first)
    encoded_second = encode_payload(second)
    sha_first = content_hash(encoded_first)
    sha_second = content_hash(encoded_second)
    request = build_production_request(
        source_map,
        canonical_document_language=language,
        max_output_tokens=max_output_tokens,
    )
    digest = render_digest_v101(source_map, canonical_document_language=language)
    digest_obj = build_planner_digest_v101(
        source_map, canonical_document_language=language
    )
    digest_hits = scan_technical_chunks(digest)
    user = request.prompt
    system = request.system_prompt or ""
    user_hits = scan_technical_chunks(user)
    encoded = encoded_first
    estimate = estimate_tokens(system + "\n" + user, model=MODEL)
    language_in_user = f"\nCANONICAL_DOCUMENT_LANGUAGE\n{language}\n" in user
    language_in_digest = digest_obj.get("canonical_document_language") == language
    language_in_system = f"code « {language} »" in system
    return {
        "model": first.get("model"),
        "max_tokens": first.get("max_tokens"),
        "selected_max_output": int(max_output_tokens),
        "thinking_present": "thinking" in first,
        "effort_present": "effort" in (first.get("output_config") or {}),
        "temperature_present": "temperature" in first,
        "thinking_mode": request.thinking_mode,
        "effort": request.effort,
        "thinking_budget_tokens": request.thinking_budget_tokens,
        "canonical_document_language": language,
        "request_explicitly_requires_language": (
            language_in_user and language_in_digest and language_in_system
        ),
        "language_in_user_prompt": language_in_user,
        "language_in_digest": language_in_digest,
        "language_in_system": language_in_system,
        "structured_output": (
            ((first.get("output_config") or {}).get("format") or {}).get("type")
        ),
        "request_sha256": sha_first,
        "request_sha256_repeat": sha_second,
        "request_determinism": sha_first == sha_second,
        "request_chars": len(encoded),
        "request_utf8_bytes": len(encoded.encode("utf-8")),
        "system_prompt_chars": len(system),
        "user_prompt_chars": len(user),
        "digest_chars": len(digest),
        "digest_bytes": len(digest.encode("utf-8")),
        "local_input_token_estimate": estimate.to_dict(),
        "prompt_fingerprint_system_plus_user": prompt_fingerprint(system, user),
        "technical_chunks_in_digest": digest_hits,
        "technical_chunks_in_user": user_hits,
        "no_technical_chunks": not digest_hits and not user_hits,
        "secrets_included": False,
        "authorization_scope_note": AUTHORIZATION_SCOPE,
        "engine_generate_called": False,
        "payload": first,
        "thinking_mode_frozen": THINKING_MODE,
        "model_frozen": MODEL,
        "instruction_chars": len(instruction_prompt(language)),
    }


__all__ = [
    "build_production_payload",
    "build_production_request",
    "encode_payload",
    "production_settings",
    "request_identity",
]
