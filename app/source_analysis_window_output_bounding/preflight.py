"""Préflight offline WIN001 avec 1.0 vs 1.1. 0 appel provider."""

from __future__ import annotations

import json
from typing import Any

from app.ai.estimation import estimate_tokens
from app.ai.providers._anthropic_schema import prepare_anthropic_json_schema
from app.source_analysis.ultra_compact_schema import (
    build_ultra_compact_response_schema,
    ultra_compact_schema_fingerprint,
)
from app.source_analysis.window_analyzer import build_window_ai_request
from app.source_analysis.window_granularity import (
    HARD_CEILINGS,
    TOTAL_HARD_CEILING,
    granularity_policy,
)
from app.source_analysis.window_models import WINDOW_MAX_OUTPUT_TOKENS
from app.source_analysis.window_prompt import (
    WINDOW_ANALYSIS_PROMPT_VERSION,
    WINDOW_ANALYSIS_PROMPT_VERSION_V10,
    window_prompt_sha256,
)
from app.source_analysis_execution_strategy.windows import load_clean_transcript
from app.source_analysis_hybrid.planner import plan_windows_v2
from app.source_analysis_window_output_bounding.constants import WINDOW_ID


def _payload_bytes(request) -> int:
    from app.ai.providers.anthropic_engine import AnthropicEngine
    from app.ai.settings import resolve_stage_settings
    from app.source_analysis.window_models import STAGE_WINDOW

    settings = resolve_stage_settings(STAGE_WINDOW)
    engine = AnthropicEngine(
        model=settings.model or "claude-sonnet-5",
        api_key="offline-preflight-not-a-key",
    )
    payload = engine.build_payload(request, request.model or "claude-sonnet-5")
    return len(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


def rebuild_win001_pair(project_name: str, *, sortie_dir=None) -> dict[str, Any]:
    transcript = load_clean_transcript(project_name, sortie_dir=sortie_dir)
    plan = plan_windows_v2(transcript)
    window = next(item for item in plan.windows if item.window_id == WINDOW_ID)
    old = build_window_ai_request(
        window, transcript, prompt_version=WINDOW_ANALYSIS_PROMPT_VERSION_V10
    )
    new = build_window_ai_request(
        window, transcript, prompt_version=WINDOW_ANALYSIS_PROMPT_VERSION
    )
    schema = build_ultra_compact_response_schema()
    schema_text = json.dumps(schema, ensure_ascii=False, sort_keys=True)
    adapted = json.dumps(
        prepare_anthropic_json_schema(schema), ensure_ascii=False, sort_keys=True
    )
    old_system = old.system_prompt or ""
    new_system = new.system_prompt or ""
    user = new.request.prompt
    old_est = int(old.token_estimate["total_tokens"])
    new_est = int(new.token_estimate["total_tokens"])
    return {
        "window_id": window.window_id,
        "owned_src_count": window.owned_src_count,
        "word_count": window.word_count,
        "plan_window_count": plan.window_count,
        "old_prompt_version": WINDOW_ANALYSIS_PROMPT_VERSION_V10,
        "new_prompt_version": WINDOW_ANALYSIS_PROMPT_VERSION,
        "old_prompt_sha256": window_prompt_sha256(old_system),
        "new_prompt_sha256": window_prompt_sha256(new_system),
        "old_system_chars": len(old_system),
        "new_system_chars": len(new_system),
        "system_char_delta": len(new_system) - len(old_system),
        "user_chars": len(user),
        "old_local_estimate": old_est,
        "new_local_estimate": new_est,
        "local_estimate_delta": new_est - old_est,
        "old_signature": old.signature,
        "new_signature": new.signature,
        "signatures_differ": old.signature != new.signature,
        "payload_bytes_new": _payload_bytes(new.request),
        "schema_bytes": len(schema_text.encode("utf-8")),
        "adapted_schema_bytes": len(adapted.encode("utf-8")),
        "response_schema_sha256": ultra_compact_schema_fingerprint(schema),
        "schema_unchanged_generation_c": True,
        "max_output": WINDOW_MAX_OUTPUT_TOKENS,
        "hard_semantic_limits": {
            "per_kind": dict(HARD_CEILINGS),
            "total": TOTAL_HARD_CEILING,
        },
        "policy": granularity_policy(),
        "real_calls": 0,
        "win001_retried": False,
        "old_system_tokens": estimate_tokens(old_system).tokens,
        "new_system_tokens": estimate_tokens(new_system).tokens,
    }


__all__ = ["rebuild_win001_pair"]
