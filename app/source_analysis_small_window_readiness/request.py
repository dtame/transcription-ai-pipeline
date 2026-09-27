"""Reconstruction offline de la requête small WIN001. 0 appel provider."""

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
from app.source_analysis_execution_strategy.windows import load_clean_transcript
from app.source_analysis_hybrid.planner import plan_windows_v2
from app.source_analysis_hybrid_readiness.constants import TARGET_MODEL, TARGET_PROVIDER
from app.source_analysis_small_window_hierarchy.constants import CANDIDATE_PLANNER_VERSION
from app.source_analysis_small_window_hierarchy.planner import (
    plan_coverage,
    plan_windows_v21_small,
    small_window_planner_config,
    window_plan_metrics,
)
from app.source_analysis_small_window_readiness.constants import (
    A7_EXPECTED_WINDOWS,
    A7_WIN001_INPUT_HASH,
    AUTHORIZATION_SCOPE,
    EXPECTED_WINDOW_COUNT,
    HARD_MAX_LOCAL_ESTIMATE,
    HISTORICAL_CALL1_SIGNATURE,
    HISTORICAL_CALL2_SIGNATURE,
    MAX_ATTEMPTS_REQUIRED,
    PLANNER_VERSION_REQUIRED,
    PROJECT_NAME,
    WINDOW_ID,
)
from app.source_analysis_window_output_bounding.preflight import _payload_bytes


def _window_row(window) -> dict[str, Any]:
    return {
        "window_id": window.window_id,
        "first_present_src": window.first_owned_src_ref,
        "last_present_src": window.last_owned_src_ref,
        "owned_src_count": window.owned_src_count,
        "word_count": window.word_count,
        "local_request_estimate": int(window.estimated_input_tokens),
        "context_src_refs": list(window.context_src_refs),
        "input_hash": window.input_hash,
        "owned_content_sha256": window.owned_content_sha256,
        "planner_version": window.planner_version,
    }


def compare_to_a7(rows: list[dict[str, Any]]) -> dict[str, Any]:
    mismatches: list[dict[str, Any]] = []
    if len(rows) != len(A7_EXPECTED_WINDOWS):
        return {
            "matches_a7_expected": False,
            "materially_different": True,
            "mismatches": [
                {
                    "field": "window_count",
                    "expected": len(A7_EXPECTED_WINDOWS),
                    "actual": len(rows),
                }
            ],
        }
    keys = (
        "window_id",
        "first_present_src",
        "last_present_src",
        "owned_src_count",
        "word_count",
        "local_request_estimate",
    )
    for expected, actual in zip(A7_EXPECTED_WINDOWS, rows, strict=True):
        for key in keys:
            if expected[key] != actual[key]:
                mismatches.append(
                    {
                        "window_id": expected["window_id"],
                        "field": key,
                        "expected": expected[key],
                        "actual": actual[key],
                    }
                )
    return {
        "matches_a7_expected": not mismatches,
        "materially_different": bool(mismatches),
        "mismatches": mismatches,
    }


def rebuild_candidate_plan(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> dict[str, Any]:
    transcript = load_clean_transcript(project_name, sortie_dir=sortie_dir)
    config = small_window_planner_config()
    plan = plan_windows_v21_small(transcript, config=config)
    coverage = plan_coverage(transcript, plan)
    rows = [_window_row(window) for window in plan.windows]
    metrics = window_plan_metrics(plan)
    comparison = compare_to_a7(rows)
    tiny_stub = any(int(window.owned_src_count) < 20 for window in plan.windows)
    over_hard = any(
        int(window.estimated_input_tokens) > HARD_MAX_LOCAL_ESTIMATE
        for window in plan.windows
    )
    return {
        "planner_version": plan.planner_version,
        "config_version": config.version,
        "target_input_tokens": plan.target_input_tokens,
        "hard_max_input_tokens": plan.hard_max_input_tokens,
        "overlap_policy": plan.overlap_policy,
        "prompt_overhead_tokens": plan.prompt_overhead_tokens,
        "window_count": plan.window_count,
        "windows": rows,
        "metrics": metrics,
        "coverage": coverage,
        "tiny_stub": tiny_stub,
        "any_window_over_hard_max": over_hard,
        "context_policy": "NONE",
        "context_empty": coverage["context_src_empty"],
        "expected_window_count": EXPECTED_WINDOW_COUNT,
        "window_count_matches": plan.window_count == EXPECTED_WINDOW_COUNT,
        "a7_comparison": comparison,
        "plan_sha256": plan.plan_sha256(),
    }


def rebuild_small_win001_request(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> dict[str, Any]:
    transcript = load_clean_transcript(project_name, sortie_dir=sortie_dir)
    small_plan = plan_windows_v21_small(transcript)
    large_plan = plan_windows_v2(transcript)
    small = next(item for item in small_plan.windows if item.window_id == WINDOW_ID)
    large = next(item for item in large_plan.windows if item.window_id == WINDOW_ID)
    future = build_window_ai_request(
        small, transcript, prompt_version=WINDOW_ANALYSIS_PROMPT_VERSION
    )
    large_11 = build_window_ai_request(
        large, transcript, prompt_version=WINDOW_ANALYSIS_PROMPT_VERSION
    )
    large_10 = build_window_ai_request(
        large, transcript, prompt_version=WINDOW_ANALYSIS_PROMPT_VERSION_V10
    )
    timeout = diagnose_stage_timeout(STAGE_WINDOW)
    system = future.system_prompt or ""
    user = future.request.prompt or ""
    local = int(future.token_estimate["total_tokens"])
    return {
        "planner_version": small.planner_version,
        "required_planner_version": PLANNER_VERSION_REQUIRED,
        "planner_matches_required": small.planner_version == PLANNER_VERSION_REQUIRED,
        "window_id": small.window_id,
        "first_src": small.first_owned_src_ref,
        "last_src": small.last_owned_src_ref,
        "owned_src_count": small.owned_src_count,
        "word_count": small.word_count,
        "window_input_hash": small.input_hash,
        "a7_window_input_hash": A7_WIN001_INPUT_HASH,
        "window_input_hash_matches_a7": small.input_hash == A7_WIN001_INPUT_HASH,
        "owned_content_sha256": small.owned_content_sha256,
        "owned_src_ids_sha256": small.owned_src_ids_sha256,
        "context_src_ids_sha256": small.context_src_ids_sha256,
        "context_content_sha256": small.context_content_sha256,
        "context_src_refs": list(small.context_src_refs),
        "analysis_signature": future.signature,
        "prompt_version": future.signature_inputs.prompt_version,
        "prompt_sha256": window_prompt_sha256(system),
        "system_prompt_hash": window_prompt_sha256(system),
        "response_schema": SEMANTIC_TRANSPORT_VERSION,
        "response_schema_sha256": future.response_schema_sha256,
        "granularity_policy_version": POLICY_VERSION,
        "transport_version": SEMANTIC_TRANSPORT_VERSION,
        "provider": TARGET_PROVIDER,
        "model": TARGET_MODEL,
        "stage": future.request.stage,
        "system_chars": len(system),
        "user_chars": len(user),
        "combined_chars": len(system) + len(user),
        "local_estimated_input": local,
        "local_estimated_input_is_planner_units": True,
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
        "large_win001": {
            "planner_version": large.planner_version,
            "first_src": large.first_owned_src_ref,
            "last_src": large.last_owned_src_ref,
            "owned_src_count": large.owned_src_count,
            "word_count": large.word_count,
            "local_estimated_input": int(large_11.token_estimate["total_tokens"]),
            "window_input_hash": large.input_hash,
            "analysis_signature_1_1": large_11.signature,
            "analysis_signature_1_0": large_10.signature,
            "historical_call1_signature": HISTORICAL_CALL1_SIGNATURE,
            "historical_call2_signature": HISTORICAL_CALL2_SIGNATURE,
        },
        "distinct_from_large": {
            "planner_differs": small.planner_version != large.planner_version,
            "src_span_differs": (
                small.first_owned_src_ref != large.first_owned_src_ref
                or small.last_owned_src_ref != large.last_owned_src_ref
            ),
            "owned_count_differs": small.owned_src_count != large.owned_src_count,
            "word_count_differs": small.word_count != large.word_count,
            "local_estimate_differs": local
            != int(large_11.token_estimate["total_tokens"]),
            "window_input_hash_differs": small.input_hash != large.input_hash,
            "analysis_signature_differs_from_large_1_1": future.signature
            != large_11.signature,
            "analysis_signature_differs_from_call1": future.signature
            != HISTORICAL_CALL1_SIGNATURE,
            "analysis_signature_differs_from_call2": future.signature
            != HISTORICAL_CALL2_SIGNATURE,
            "cryptographically_distinct": (
                small.input_hash != large.input_hash
                and future.signature != large_11.signature
                and future.signature != HISTORICAL_CALL1_SIGNATURE
                and future.signature != HISTORICAL_CALL2_SIGNATURE
            ),
        },
        "real_calls": 0,
        "small_win001_executed": False,
    }


__all__ = [
    "rebuild_candidate_plan",
    "rebuild_small_win001_request",
]
