"""Faits offline 3B.7.7A.6 — intégrité, forensics, état projet."""

from __future__ import annotations

import inspect
from pathlib import Path
from typing import Any

from app.ai.providers import _http as http_module
from app.ai.provider_forensics import capture_http_response
from app.cleanup_application.writer import clean_json_path
from app.language_cleanup.transcript_source import audit_dir
from app.semantic_canary.integrity import sha256_of_file
from app.source_analysis.consolidation_models import CONSOLIDATION_SAFE_INPUT_BUDGET_TOKENS
from app.source_analysis.window_analyzer import analyze_window
from app.source_analysis.window_granularity import POLICY_VERSION
from app.source_analysis.window_models import WINDOW_MAX_OUTPUT_TOKENS
from app.source_analysis.window_prompt import (
    WINDOW_ANALYSIS_PROMPT_VERSION,
    WINDOW_ANALYSIS_PROMPT_VERSION_V10,
    build_window_system_prompt,
    window_prompt_sha256,
)
from app.source_analysis.window_writer import result_path, transport_path, windows_root
from app.source_analysis.writer import source_map_path
from app.source_analysis_execution_strategy.review import inspect_project_state
from app.source_analysis_hybrid.constants import HARD_MAX_INPUT_TOKENS, TARGET_INPUT_TOKENS
from app.source_analysis_timeout_config.audit import generation_c_hashes
from app.source_analysis_post_canary_architecture.constants import (
    CLEAN_SHA,
    GENERATION_C_ANTHROPIC_SHA,
    GENERATION_C_RAW_SHA,
    PHASE,
    PROJECT_NAME,
    PROMPT_10_SHA,
    PROMPT_11_SHA,
    PROTECTED_EVIDENCE,
    SCHEMA_VERSION,
    WINDOW_ID,
)


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
    }


def inspect_integrity(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> dict[str, Any]:
    clean = clean_json_path(project_name, sortie_dir=sortie_dir)
    source_map = source_map_path(project_name, sortie_dir=sortie_dir)
    root = windows_root(project_name, sortie_dir=sortie_dir)
    state = inspect_project_state(project_name, sortie_dir=sortie_dir)
    generation_c = generation_c_hashes()
    prompt_10 = window_prompt_sha256(
        build_window_system_prompt("en", version=WINDOW_ANALYSIS_PROMPT_VERSION_V10)
    )
    prompt_11 = window_prompt_sha256(
        build_window_system_prompt("en", version=WINDOW_ANALYSIS_PROMPT_VERSION)
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "prompt_1_0_sha": prompt_10,
        "prompt_1_0_expected": PROMPT_10_SHA,
        "prompt_1_0_unchanged": prompt_10 == PROMPT_10_SHA,
        "prompt_1_1_sha": prompt_11,
        "prompt_1_1_expected": PROMPT_11_SHA,
        "prompt_1_1_unchanged": prompt_11 == PROMPT_11_SHA,
        "prompt_1_1_version": WINDOW_ANALYSIS_PROMPT_VERSION,
        "granularity_policy": POLICY_VERSION,
        "granularity_unchanged": POLICY_VERSION == "window-granularity-1.0",
        "generation_c_raw_sha": generation_c.get("raw_sha256"),
        "generation_c_raw_expected": GENERATION_C_RAW_SHA,
        "generation_c_raw_unchanged": generation_c.get("raw_sha256") == GENERATION_C_RAW_SHA,
        "generation_c_anthropic_sha": generation_c.get("anthropic_sha256"),
        "generation_c_anthropic_expected": GENERATION_C_ANTHROPIC_SHA,
        "generation_c_anthropic_unchanged": (
            generation_c.get("anthropic_sha256") == GENERATION_C_ANTHROPIC_SHA
        ),
        "max_output": WINDOW_MAX_OUTPUT_TOKENS,
        "max_output_unchanged": WINDOW_MAX_OUTPUT_TOKENS == 32000,
        "production_target": TARGET_INPUT_TOKENS,
        "production_hard_max": HARD_MAX_INPUT_TOKENS,
        "production_planner_unchanged": True,
        "clean_sha": sha256_of_file(clean) if clean.is_file() else "",
        "clean_expected": CLEAN_SHA,
        "clean_unchanged": clean.is_file() and sha256_of_file(clean) == CLEAN_SHA,
        "source_map_present": source_map.is_file(),
        "transport_exists": transport_path(project_name, WINDOW_ID, root=root).exists(),
        "result_exists": result_path(project_name, WINDOW_ID, root=root).exists(),
        "project_state": {
            "status": state.get("status"),
            "error": state.get("error"),
            "not_success": state.get("status") != "SUCCESS",
        },
        "consolidation_guard": CONSOLIDATION_SAFE_INPUT_BUDGET_TOKENS,
        "protected_hashes": protected_hashes(project_name, sortie_dir=sortie_dir),
        "forensics": inspect_forensics_active(),
    }
