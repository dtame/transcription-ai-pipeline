"""Faits offline 3B.7.7A.12 — isolation, freeze historique, état projet."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.cleanup_application.writer import clean_json_path
from app.language_cleanup.transcript_source import audit_dir
from app.paths import SORTIE_DIR
from app.semantic_canary.integrity import sha256_of_file
from app.source_analysis.publication_isolation import inspect_sortie_isolation
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
from app.source_analysis_hybrid.constants import PLANNER_VERSION
from app.source_analysis_local_v2.prompt import (
    build_window_system_prompt_v12,
    window_prompt_v12_sha256,
)
from app.source_analysis_local_v2.schema import compare_v1_v2_schemas
from app.source_analysis_local_v2.synthetic import measure_v2_worst_case
from app.source_analysis_output_ceiling_review.facts import forensic_paths
from app.source_analysis_thinking_contract.constants import (
    CLEAN_SHA,
    GENERATION_C_ANTHROPIC_SHA,
    GENERATION_C_RAW_SHA,
    GRANULARITY_POLICY_VERSION,
    PHASE,
    PRODUCTION_PLANNER_VERSION,
    PROJECT_NAME,
    PROMPT_10_SHA,
    PROMPT_11_SHA,
    PROTECTED_EVIDENCE_A12,
    SCHEMA_VERSION,
    SMALL_HTTP_RAW_SHA,
    SMALL_RAW_TEXT_SHA,
    TARGET_JSON_LOCAL_TOKENS,
    WINDOW_ANALYSIS_PROMPT_VERSION_V12,
    WINDOW_ID,
)
from app.source_analysis_timeout_config.audit import generation_c_hashes


def protected_hashes(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> dict[str, str]:
    audit = audit_dir(project_name, sortie_dir=sortie_dir)
    hashes: dict[str, str] = {}
    for rel in PROTECTED_EVIDENCE_A12:
        path = audit / Path(rel).name
        if path.is_file():
            hashes[rel] = sha256_of_file(path)
    return hashes


def inspect_integrity(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> dict[str, Any]:
    paths = forensic_paths(project_name, sortie_dir=sortie_dir)
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
    prompt_12 = window_prompt_v12_sha256(build_window_system_prompt_v12("en"))
    schemas = compare_v1_v2_schemas()
    worst = measure_v2_worst_case()
    http_raw_sha = (
        sha256_of_file(paths["http_raw"]) if paths["http_raw"].is_file() else ""
    )
    text_sha = (
        sha256_of_file(paths["structured_raw"])
        if paths["structured_raw"].is_file()
        else ""
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "prompt_1_0_unchanged": prompt_10 == PROMPT_10_SHA,
        "prompt_1_1_unchanged": prompt_11 == PROMPT_11_SHA,
        "prompt_1_2_version": WINDOW_ANALYSIS_PROMPT_VERSION_V12,
        "prompt_1_2_sha256": prompt_12,
        "granularity_1_0_unchanged": POLICY_VERSION == "window-granularity-1.0",
        "granularity_1_1_minimal": GRANULARITY_POLICY_VERSION,
        "generation_c_raw_unchanged": generation_c.get("raw_sha256")
        == GENERATION_C_RAW_SHA,
        "generation_c_anthropic_unchanged": generation_c.get("anthropic_sha256")
        == GENERATION_C_ANTHROPIC_SHA,
        "transport_v2_raw_bytes": schemas["v2_generic"]["raw_bytes"],
        "transport_v2_adapted_bytes": schemas["v2_generic"]["adapted_bytes"],
        "max_output_unchanged": WINDOW_MAX_OUTPUT_TOKENS == 32000,
        "synthetic_worst_case_tokens": worst["local_tokens"],
        "synthetic_worst_case_within_target": worst["local_tokens"]
        <= TARGET_JSON_LOCAL_TOKENS,
        "production_planner": PLANNER_VERSION,
        "production_planner_unchanged": PLANNER_VERSION == PRODUCTION_PLANNER_VERSION,
        "clean_unchanged": clean.is_file() and sha256_of_file(clean) == CLEAN_SHA,
        "source_map_present": source_map.is_file(),
        "transport_exists": transport_path(
            project_name, WINDOW_ID, root=root
        ).exists(),
        "result_exists": result_path(project_name, WINDOW_ID, root=root).exists(),
        "project_state": {
            **state,
            "not_success": str(state.get("status") or "") != "success",
        },
        "forensic_bytes_preserved": {
            "http_raw_sha256": http_raw_sha,
            "http_raw_expected": SMALL_HTTP_RAW_SHA,
            "http_raw_unchanged": http_raw_sha == SMALL_HTTP_RAW_SHA,
            "structured_raw_sha256": text_sha,
            "structured_raw_expected": SMALL_RAW_TEXT_SHA,
            "structured_raw_unchanged": text_sha == SMALL_RAW_TEXT_SHA,
        },
        "protected": protected_hashes(project_name, sortie_dir=sortie_dir),
    }


def inspect_isolation(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> dict[str, Any]:
    root = Path(sortie_dir) if sortie_dir is not None else SORTIE_DIR
    report = inspect_sortie_isolation(root)
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "sortie": report,
        "target_project": project_name,
        "forensics_allowed": True,
        "unauthorized_semantic_artifacts_forbidden": True,
    }


__all__ = ["inspect_integrity", "inspect_isolation", "protected_hashes"]
