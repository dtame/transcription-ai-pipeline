"""Exact future 1.0.2 production request. Built twice. Never sent."""

from __future__ import annotations

import json
from dataclasses import replace
from typing import Any

from app.ai.estimation import estimate_tokens
from app.ai.thinking import THINKING_MODE_PROVIDER_DEFAULT
from app.editorial_planner_forensics_4a34.constants import (
    AUTHORIZATION_SCOPE,
    MAX_OUTPUT_TOKENS,
    MODEL,
    SUCCESSOR_PROMPT,
    THINKING_MODE,
)
from app.editorial_planner_forensics_4a34.guard import (
    redact_secrets,
    scan_technical_chunks,
)
from app.editorial_planning.digest import build_planner_digest_v101, render_digest_v101
from app.editorial_planning.language_policy import normalize_language_code
from app.editorial_planning.payload_v102 import (
    build_future_anthropic_payload_v102,
    build_planner_request_v102,
)
from app.editorial_planning.prompt_v102 import instruction_prompt, prompt_fingerprint
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
    return build_planner_request_v102(
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
    payload = build_future_anthropic_payload_v102(
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
    user = request.prompt
    system = request.system_prompt or ""
    idea_ids = [idea.idea_id for idea in source_map.ideas]
    expected_count = len(idea_ids)
    language_in_user = f"\nCANONICAL_DOCUMENT_LANGUAGE\n{language}\n" in user
    count_in_user = f"\nEXPECTED_IDEA_COUNT\n{expected_count}\n" in user
    return {
        "model": first.get("model"),
        "max_tokens": first.get("max_tokens"),
        "selected_max_output": int(max_output_tokens),
        "thinking_present": "thinking" in first,
        "effort_present": "effort" in (first.get("output_config") or {}),
        "temperature_present": "temperature" in first,
        "thinking_mode": request.thinking_mode,
        "effort": request.effort,
        "prompt_version": SUCCESSOR_PROMPT,
        "canonical_document_language": language,
        "expected_idea_count": expected_count,
        "expected_idea_count_dynamic": True,
        "expected_idea_count_in_user": count_in_user,
        "full_id_manifest_duplicated": False,
        "request_explicitly_requires_language": (
            language_in_user
            and digest_obj.get("canonical_document_language") == language
            and f"code « {language} »" in system
        ),
        "structured_output": (
            ((first.get("output_config") or {}).get("format") or {}).get("type")
        ),
        "request_sha256": sha_first,
        "request_sha256_repeat": sha_second,
        "request_determinism": sha_first == sha_second,
        "request_chars": len(encoded_first),
        "request_utf8_bytes": len(encoded_first.encode("utf-8")),
        "system_prompt_chars": len(system),
        "user_prompt_chars": len(user),
        "digest_chars": len(digest),
        "digest_bytes": len(digest.encode("utf-8")),
        "local_input_token_estimate": estimate_tokens(
            system + "\n" + user, model=MODEL
        ).to_dict(),
        "prompt_fingerprint_system_plus_user": prompt_fingerprint(system, user),
        "technical_chunks_in_digest": scan_technical_chunks(digest),
        "technical_chunks_in_user": scan_technical_chunks(user),
        "no_technical_chunks": not scan_technical_chunks(digest)
        and not scan_technical_chunks(user),
        "secrets_included": False,
        "authorization_scope_note": AUTHORIZATION_SCOPE,
        "engine_generate_called": False,
        "payload": first,
        "thinking_mode_frozen": THINKING_MODE,
        "model_frozen": MODEL,
        "instruction_chars": len(instruction_prompt(language)),
        "idea_ids_in_user": sum(1 for idea_id in idea_ids if idea_id in user),
        "hardening_in_system": "COMPLETUDE EXHAUSTIVE DES IDEA" in system,
        "self_check_in_system": "AUTO-VERIFICATION DE SORTIE" in system,
        "idea_specific_prompting": any(
            token in system for token in ("IDEA007", "IDEA008")
        ),
    }


__all__ = [
    "build_production_payload",
    "build_production_request",
    "encode_payload",
    "production_settings",
    "request_identity",
]
