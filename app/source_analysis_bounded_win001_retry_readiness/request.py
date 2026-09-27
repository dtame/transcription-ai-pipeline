"""Reconstruction offline de la requête bornée WIN001 1.1. 0 appel provider."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.ai.timeouts import diagnose_stage_timeout
from app.source_analysis.ultra_compact_schema import SEMANTIC_TRANSPORT_VERSION
from app.source_analysis.window_analyzer import build_window_ai_request
from app.source_analysis.window_granularity import POLICY_VERSION
from app.source_analysis.window_models import STAGE_WINDOW
from app.source_analysis.window_prompt import (
    WINDOW_ANALYSIS_PROMPT_VERSION,
    WINDOW_ANALYSIS_PROMPT_VERSION_V10,
    window_prompt_sha256,
)
from app.source_analysis_bounded_win001_retry_readiness.constants import (
    AUTHORIZATION_SCOPE,
    HARD_MAX_LOCAL_ESTIMATE,
    MAX_ATTEMPTS_REQUIRED,
    PROJECT_NAME,
    WINDOW_ID,
)
from app.source_analysis_execution_strategy.windows import load_clean_transcript
from app.source_analysis_hybrid.planner import plan_windows_v2
from app.source_analysis_hybrid_readiness.constants import (
    TARGET_MODEL,
    TARGET_PROVIDER,
)
from app.source_analysis_window_output_bounding.preflight import _payload_bytes


def rebuild_bounded_win001_request(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> dict[str, Any]:
    transcript = load_clean_transcript(project_name, sortie_dir=sortie_dir)
    plan = plan_windows_v2(transcript)
    window = next(item for item in plan.windows if item.window_id == WINDOW_ID)
    historical = build_window_ai_request(
        window, transcript, prompt_version=WINDOW_ANALYSIS_PROMPT_VERSION_V10
    )
    future = build_window_ai_request(
        window, transcript, prompt_version=WINDOW_ANALYSIS_PROMPT_VERSION
    )
    timeout = diagnose_stage_timeout(STAGE_WINDOW)
    system = future.system_prompt or ""
    user = future.request.prompt or ""
    local = int(future.token_estimate["total_tokens"])
    return {
        "window_id": window.window_id,
        "plan_window_count": plan.window_count,
        "owned_src_count": window.owned_src_count,
        "word_count": window.word_count,
        "stage": future.request.stage,
        "provider": TARGET_PROVIDER,
        "model": TARGET_MODEL,
        "prompt_version": future.signature_inputs.prompt_version,
        "prompt_sha256": window_prompt_sha256(system),
        "schema_version": SEMANTIC_TRANSPORT_VERSION,
        "schema_sha256": future.response_schema_sha256,
        "window_signature": future.signature,
        "historical_prompt_version": historical.signature_inputs.prompt_version,
        "historical_prompt_sha256": window_prompt_sha256(historical.system_prompt or ""),
        "historical_signature": historical.signature,
        "signatures_differ": future.signature != historical.signature,
        "system_chars": len(system),
        "user_chars": len(user),
        "combined_chars": len(system) + len(user),
        "local_estimated_input": local,
        "local_estimated_input_is_planner_units": True,
        "hard_max_is_local_planner_estimate_only": True,
        "hard_max_is_not_provider_billing_ceiling": True,
        "within_hard_max": local <= HARD_MAX_LOCAL_ESTIMATE,
        "hard_max_local": HARD_MAX_LOCAL_ESTIMATE,
        "payload_bytes": _payload_bytes(future.request),
        "temperature": future.request.temperature,
        "output_language": transcript.primary_language,
        "max_output": future.request.max_output_tokens,
        "connect_timeout_seconds": timeout["connect_seconds"],
        "read_timeout_seconds": timeout["read_seconds"],
        "max_attempts": MAX_ATTEMPTS_REQUIRED,
        "authorization_scope": AUTHORIZATION_SCOPE,
        "granularity_policy_version": POLICY_VERSION,
        "transport_version": SEMANTIC_TRANSPORT_VERSION,
        "real_calls": 0,
        "win001_retried": False,
    }
