"""Exact production request via the frozen planner builder. 0 POST."""

from __future__ import annotations

import json
from dataclasses import replace
from typing import Any

from app.ai.estimation import estimate_tokens
from app.ai.thinking import THINKING_MODE_PROVIDER_DEFAULT
from app.editorial_planner_preflight_4a2.constants import (
    AUTHORIZATION_SCOPE,
    MODEL,
    OLD_PROPOSED_MAX_OUTPUT,
    THINKING_MODE,
)
from app.editorial_planner_preflight_4a2.guard import (
    redact_secrets,
    scan_technical_chunks,
)
from app.editorial_planning.digest import build_planner_digest, render_digest
from app.editorial_planning.payload import (
    build_future_anthropic_payload,
    build_planner_request,
)
from app.editorial_planning.prompt import instruction_prompt, prompt_fingerprint
from app.editorial_planning.settings import PlannerSettings, frozen_production_settings
from app.file_utils import content_hash
from app.source_analysis.models import SourceMap


def production_settings(*, max_output_tokens: int) -> PlannerSettings:
    base = frozen_production_settings()
    if base.thinking_mode != THINKING_MODE_PROVIDER_DEFAULT:
        raise RuntimeError("frozen thinking_mode is no longer provider_default")
    if base.effort is not None:
        raise RuntimeError("frozen effort is no longer none")
    return replace(base, max_output_tokens=int(max_output_tokens))


def build_production_request(
    source_map: SourceMap,
    *,
    max_output_tokens: int,
) -> Any:
    settings = production_settings(max_output_tokens=max_output_tokens)
    return build_planner_request(source_map, settings=settings)


def build_production_payload(
    source_map: SourceMap,
    *,
    max_output_tokens: int,
) -> dict[str, Any]:
    settings = production_settings(max_output_tokens=max_output_tokens)
    payload = build_future_anthropic_payload(source_map, settings=settings)
    return redact_secrets(payload)


def encode_payload(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def request_identity(
    source_map: SourceMap,
    *,
    max_output_tokens: int,
) -> dict[str, Any]:
    first = build_production_payload(source_map, max_output_tokens=max_output_tokens)
    second = build_production_payload(source_map, max_output_tokens=max_output_tokens)
    encoded_first = encode_payload(first)
    encoded_second = encode_payload(second)
    sha_first = content_hash(encoded_first)
    sha_second = content_hash(encoded_second)
    request = build_production_request(
        source_map, max_output_tokens=max_output_tokens
    )
    digest = render_digest(source_map)
    digest_hits = scan_technical_chunks(digest)
    instruction_len = len(instruction_prompt())
    user = request.prompt
    digest_in_user = user[instruction_len:] if user.startswith(instruction_prompt()) else user
    user_digest_hits = scan_technical_chunks(digest_in_user)
    compact_ok = _compact_by_reference(source_map, digest)
    return {
        "model": first.get("model"),
        "max_tokens": first.get("max_tokens"),
        "old_proposed_max_output": OLD_PROPOSED_MAX_OUTPUT,
        "selected_max_output": int(max_output_tokens),
        "thinking_present": "thinking" in first,
        "thinking_value": first.get("thinking"),
        "effort_present": "effort" in (first.get("output_config") or {}),
        "temperature_present": "temperature" in first,
        "thinking_mode": request.thinking_mode,
        "effort": request.effort,
        "thinking_budget_tokens": request.thinking_budget_tokens,
        "payload_keys": sorted(first.keys()),
        "structured_output": (
            ((first.get("output_config") or {}).get("format") or {}).get("type")
        ),
        "request_sha256": sha_first,
        "request_sha256_repeat": sha_second,
        "request_determinism": sha_first == sha_second,
        "request_chars": len(encoded_first),
        "request_utf8_bytes": len(encoded_first.encode("utf-8")),
        "system_prompt_chars": len(request.system_prompt or ""),
        "user_prompt_chars": len(request.prompt),
        "digest_chars": len(digest),
        "digest_bytes": len(digest.encode("utf-8")),
        "prompt_fingerprint_system_plus_user": prompt_fingerprint(
            request.system_prompt or "", request.prompt
        ),
        "technical_chunks_in_digest": digest_hits,
        "technical_chunks_in_user_digest": user_digest_hits,
        "no_technical_chunks": not digest_hits and not user_digest_hits,
        "compact_by_reference": compact_ok,
        "secrets_included": False,
        "authorization_scope_note": AUTHORIZATION_SCOPE,
        "engine_generate_called": False,
        "payload": first,
        "thinking_mode_frozen": THINKING_MODE,
        "model_frozen": MODEL,
    }


def _compact_by_reference(source_map: SourceMap, digest_text: str) -> dict[str, Any]:
    digest = json.loads(digest_text)
    idea_keys: set[str] = set()
    for idea in digest.get("ideas") or []:
        idea_keys.update(idea.keys())
    src_tables_omitted = "sources" not in digest and "source_segments" not in digest
    relations_omitted = all(
        "relations" not in idea for idea in (digest.get("ideas") or [])
    )
    ideas_have_source_refs = any(
        "source_refs" in idea for idea in (digest.get("ideas") or [])
    )
    _ = source_map
    return {
        "src_tables_omitted": src_tables_omitted,
        "idea_relations_omitted": relations_omitted,
        "idea_source_refs_omitted": not ideas_have_source_refs,
        "idea_fields": sorted(idea_keys),
        "full_source_text_not_required": True,
        "pass": src_tables_omitted
        and relations_omitted
        and not ideas_have_source_refs,
    }


def local_input_estimate(system: str, user: str, *, model: str) -> dict[str, Any]:
    estimate = estimate_tokens(system + "\n" + user, model=model)
    return estimate.to_dict()


__all__ = [
    "build_production_payload",
    "build_production_request",
    "encode_payload",
    "local_input_estimate",
    "production_settings",
    "request_identity",
]
