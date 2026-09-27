"""Faits offline 3B.7.7A.10 — forensics, isolation, intégrité."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.ai.provider_forensics import ENVELOPE_JSON_NAME, RAW_BODY_NAME
from app.ai.structured_forensics import FORENSICS_JSON_NAME, FORENSICS_RAW_NAME
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
from app.source_analysis_output_ceiling_review.constants import (
    CALL1_SIGNATURE,
    CALL2_SIGNATURE,
    CLEAN_SHA,
    GENERATION_C_ANTHROPIC_SHA,
    GENERATION_C_RAW_SHA,
    PHASE,
    PROJECT_NAME,
    PROMPT_10_SHA,
    PROMPT_11_SHA,
    PROTECTED_EVIDENCE,
    SCHEMA_VERSION,
    SMALL_HTTP_RAW_SHA,
    SMALL_RAW_TEXT_SHA,
    SMALL_SIGNATURE,
    WINDOW_ID,
)
from app.source_analysis_output_ceiling_review.raw_analyzer import (
    analyze_persisted_forensics,
)
from app.source_analysis_timeout_config.audit import generation_c_hashes


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


def forensic_paths(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> dict[str, Path]:
    root = Path(sortie_dir) if sortie_dir is not None else SORTIE_DIR
    analysis = root / project_name / "analysis"
    provider = analysis / "provider_forensics" / WINDOW_ID / SMALL_SIGNATURE
    structured = analysis / "structured_output_forensics" / WINDOW_ID / SMALL_SIGNATURE
    return {
        "analysis": analysis,
        "provider_dir": provider,
        "structured_dir": structured,
        "http_envelope": provider / ENVELOPE_JSON_NAME,
        "http_raw": provider / RAW_BODY_NAME,
        "structured_json": structured / FORENSICS_JSON_NAME,
        "structured_raw": structured / FORENSICS_RAW_NAME,
        "call1_provider": analysis / "provider_forensics" / WINDOW_ID / CALL1_SIGNATURE,
        "call2_provider": analysis / "provider_forensics" / WINDOW_ID / CALL2_SIGNATURE,
        "call1_structured": (
            analysis / "structured_output_forensics" / WINDOW_ID / CALL1_SIGNATURE
        ),
        "call2_structured": (
            analysis / "structured_output_forensics" / WINDOW_ID / CALL2_SIGNATURE
        ),
    }


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
    http_raw_sha = (
        sha256_of_file(paths["http_raw"]) if paths["http_raw"].is_file() else ""
    )
    text_sha = (
        sha256_of_file(paths["structured_raw"])
        if paths["structured_raw"].is_file()
        else ""
    )
    historical = {
        "call1_provider_exists": paths["call1_provider"].exists(),
        "call2_provider_exists": paths["call2_provider"].exists(),
        "call1_structured_exists": paths["call1_structured"].exists(),
        "call2_structured_exists": paths["call2_structured"].exists(),
        "small_distinct_from_historical": SMALL_SIGNATURE
        not in {CALL1_SIGNATURE, CALL2_SIGNATURE},
        "historical_not_overwritten": (
            SMALL_SIGNATURE not in {CALL1_SIGNATURE, CALL2_SIGNATURE}
            and paths["http_raw"].is_file()
        ),
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "prompt_1_0_unchanged": prompt_10 == PROMPT_10_SHA,
        "prompt_1_1_unchanged": prompt_11 == PROMPT_11_SHA,
        "prompt_1_1_version": WINDOW_ANALYSIS_PROMPT_VERSION,
        "granularity_unchanged": POLICY_VERSION == "window-granularity-1.0",
        "generation_c_raw_unchanged": generation_c.get("raw_sha256")
        == GENERATION_C_RAW_SHA,
        "generation_c_anthropic_unchanged": generation_c.get("anthropic_sha256")
        == GENERATION_C_ANTHROPIC_SHA,
        "max_output_unchanged": WINDOW_MAX_OUTPUT_TOKENS == 32000,
        "production_planner": PLANNER_VERSION,
        "production_planner_unchanged": PLANNER_VERSION == "window-planner-v2.0",
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
        "historical": historical,
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
        "classes": [
            "FORENSIC_ARTIFACT",
            "SEMANTIC_ANALYSIS_ARTIFACT",
            "PUBLISHED_CANONICAL_ARTIFACT",
        ],
        "original_intent": (
            "Phase 3 isolation forbade real-project analysis publication. "
            "analysis/ existence was a historical proxy because the only "
            "intended file was source_map.json."
        ),
        "new_reality": (
            "Authorized provider forensics may live under analysis/"
            "provider_forensics and analysis/structured_output_forensics."
        ),
        "still_forbidden": [
            "analysis/source_map.json",
            "windows/transport.json",
            "windows/result.json",
            "consolidation result",
            "canonical reconstruction",
        ],
        "sortie": report,
        "target_project": project_name,
    }


def load_small_forensics(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> dict[str, Any]:
    paths = forensic_paths(project_name, sortie_dir=sortie_dir)
    return analyze_persisted_forensics(
        raw_http_path=paths["http_raw"],
        raw_text_path=paths["structured_raw"],
        parse_colno=22836,
    )
