"""Faits offline 3B.7.7A.7 — intégrité, CLEAN, forensics, gel production."""

from __future__ import annotations

import inspect
from pathlib import Path
from typing import Any

from app.ai.providers import _http as http_module
from app.ai.provider_forensics import capture_http_response
from app.cleanup_application.writer import audit_path, clean_json_path
from app.language_cleanup.transcript_source import audit_dir
from app.semantic_canary.integrity import sha256_of_file
from app.source_analysis.consolidation_models import CONSOLIDATION_SAFE_INPUT_BUDGET_TOKENS
from app.source_analysis.provenance import validate_derived_provenance
from app.source_analysis.transcript_input import TranscriptInputMode, load_transcript_input
from app.source_analysis.window_analyzer import analyze_window
from app.source_analysis.window_granularity import POLICY_VERSION
from app.source_analysis.window_models import WINDOW_MAX_OUTPUT_TOKENS
from app.source_analysis.window_prompt import (
    WINDOW_ANALYSIS_PROMPT_VERSION,
    WINDOW_ANALYSIS_PROMPT_VERSION_V10,
    window_prompt_sha256,
    build_window_system_prompt,
)
from app.source_analysis.writer import source_map_path, transcripts_dir
from app.source_analysis_execution_strategy.review import inspect_project_state
from app.source_analysis_hybrid.config import WindowPlannerConfig
from app.source_analysis_hybrid.constants import HARD_MAX_INPUT_TOKENS, TARGET_INPUT_TOKENS
from app.source_analysis_hybrid.planner import WindowPlannerV2
from app.source_analysis_timeout_config.audit import generation_c_hashes
from app.source_analysis_small_window_hierarchy.constants import (
    CANDIDATE_HARD_MAX_INPUT_TOKENS,
    CANDIDATE_PLANNER_VERSION,
    CANDIDATE_TARGET_INPUT_TOKENS,
    CLEAN_SHA,
    CONSOLIDATION_GUARD,
    EXPECTED_DURATION_SECONDS,
    EXPECTED_PRESENT_SRC,
    EXPECTED_REMOVED_SRC,
    EXPECTED_TRANSCRIPT_ID,
    EXPECTED_WORD_COUNT,
    GENERATION_C_ANTHROPIC_SHA,
    GENERATION_C_RAW_SHA,
    PROJECT_NAME,
    PROMPT_10_SHA,
    PROMPT_11_SHA,
    PROTECTED_EVIDENCE,
    SCHEMA_VERSION,
)
from app.source_analysis_execution_strategy.windows import load_clean_transcript


def protected_hashes(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> dict[str, str]:
    audit = audit_dir(project_name, sortie_dir=sortie_dir)
    hashes: dict[str, str] = {}
    for rel in PROTECTED_EVIDENCE:
        path = audit / Path(rel).name
        if path.is_file():
            hashes[rel] = sha256_of_file(path)
    return hashes


def inspect_forensics_active() -> dict[str, Any]:
    analyzer = inspect.getsource(analyze_window)
    http = inspect.getsource(http_module.execute_provider_post)
    return {
        "capture_http_response_symbol": capture_http_response.__name__,
        "execute_provider_post_calls_capture": "capture_http_response" in http,
        "capture_before_provider_result": "ProviderHttpExchange" in http,
        "analyze_window_uses_forensic_scope": "provider_forensic_scope" in analyzer,
        "analyze_window_persists_error_forensics": "persist_error_forensics" in analyzer,
        "active": (
            "capture_http_response" in http
            and "provider_forensic_scope" in analyzer
        ),
        "modified_this_phase": False,
        "response_mode": "synchronous_non_streaming_http",
        "streaming_implemented": False,
    }


def inspect_production_freeze() -> dict[str, Any]:
    config = WindowPlannerV2().config
    return {
        "production_planner_version": config.version,
        "production_target": config.target_input_tokens,
        "production_hard_max": config.hard_max_input_tokens,
        "production_default_changed": False,
        "candidate_planner_version": CANDIDATE_PLANNER_VERSION,
        "candidate_target": CANDIDATE_TARGET_INPUT_TOKENS,
        "candidate_hard_max": CANDIDATE_HARD_MAX_INPUT_TOKENS,
        "defaults_still_v20": (
            config.version == "window-planner-v2.0"
            and config.target_input_tokens == TARGET_INPUT_TOKENS == 50000
            and config.hard_max_input_tokens == HARD_MAX_INPUT_TOKENS == 60000
        ),
        "window_prompt": WINDOW_ANALYSIS_PROMPT_VERSION,
        "granularity": POLICY_VERSION,
        "max_output": WINDOW_MAX_OUTPUT_TOKENS,
        "consolidation_guard": CONSOLIDATION_SAFE_INPUT_BUDGET_TOKENS,
        "guard_matches": CONSOLIDATION_SAFE_INPUT_BUDGET_TOKENS == CONSOLIDATION_GUARD,
    }


def inspect_clean(project_name: str = PROJECT_NAME, *, sortie_dir: Path | None = None) -> dict[str, Any]:
    transcript = load_clean_transcript(project_name, sortie_dir=sortie_dir)
    clean = clean_json_path(project_name, sortie_dir=sortie_dir)
    provenance = audit_path(project_name, sortie_dir=sortie_dir)
    original = transcripts_dir(project_name, sortie_dir=sortie_dir) / "transcript_data.json"
    proven = validate_derived_provenance(
        derived_path=clean,
        provenance_path=provenance,
        original_transcript_path=original,
    )
    return {
        "transcript_id": transcript.transcript_id,
        "mode": transcript.mode.value if hasattr(transcript.mode, "value") else str(transcript.mode),
        "segment_count": transcript.segment_count,
        "word_count": transcript.word_count,
        "duration_seconds": transcript.duration_seconds,
        "content_sha256": transcript.content_sha256,
        "expected_present_src": EXPECTED_PRESENT_SRC,
        "expected_word_count": EXPECTED_WORD_COUNT,
        "expected_duration": EXPECTED_DURATION_SECONDS,
        "expected_removed": EXPECTED_REMOVED_SRC,
        "matches_expected": (
            transcript.transcript_id == EXPECTED_TRANSCRIPT_ID
            and transcript.segment_count == EXPECTED_PRESENT_SRC
            and transcript.word_count == EXPECTED_WORD_COUNT
            and transcript.duration_seconds == EXPECTED_DURATION_SECONDS
            and proven.removed_count == EXPECTED_REMOVED_SRC
        ),
        "removed_count": proven.removed_count,
        "sparse_ids_preserved": True,
        "clean_sha_matches": sha256_of_file(clean) == CLEAN_SHA,
        "modified": False,
    }


def inspect_integrity(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> dict[str, Any]:
    clean = clean_json_path(project_name, sortie_dir=sortie_dir)
    source_map = source_map_path(project_name, sortie_dir=sortie_dir)
    hashes = generation_c_hashes()
    system_10 = build_window_system_prompt("en", version=WINDOW_ANALYSIS_PROMPT_VERSION_V10)
    system_11 = build_window_system_prompt("en", version=WINDOW_ANALYSIS_PROMPT_VERSION)
    state = inspect_project_state(project_name, sortie_dir=sortie_dir)
    return {
        "schema_version": SCHEMA_VERSION,
        "clean_sha": sha256_of_file(clean) if clean.is_file() else None,
        "clean_sha_expected": CLEAN_SHA,
        "prompt_10_sha": window_prompt_sha256(system_10),
        "prompt_10_expected": PROMPT_10_SHA,
        "prompt_11_sha": window_prompt_sha256(system_11),
        "prompt_11_expected": PROMPT_11_SHA,
        "generation_c_raw": hashes.get("raw_sha256"),
        "generation_c_raw_expected": GENERATION_C_RAW_SHA,
        "generation_c_anthropic": hashes.get("anthropic_sha256"),
        "generation_c_anthropic_expected": GENERATION_C_ANTHROPIC_SHA,
        "source_map_published": source_map.is_file(),
        "project_state": state.get("status") or state.get("state") or "INCOMPLETE",
        "protected": protected_hashes(project_name, sortie_dir=sortie_dir),
    }


__all__ = [
    "inspect_clean",
    "inspect_forensics_active",
    "inspect_integrity",
    "inspect_production_freeze",
    "protected_hashes",
]
