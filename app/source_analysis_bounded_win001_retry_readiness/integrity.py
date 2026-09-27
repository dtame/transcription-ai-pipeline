"""Intégrité des artefacts protégés jusqu'à 3B.7.7A.2 + CLEAN."""

from __future__ import annotations

from pathlib import Path

from app.cleanup_application.writer import clean_json_path
from app.language_cleanup.transcript_source import audit_dir
from app.semantic_canary.integrity import sha256_of_file
from app.source_analysis.window_prompt import (
    WINDOW_ANALYSIS_PROMPT_VERSION,
    WINDOW_ANALYSIS_PROMPT_VERSION_V10,
    build_window_system_prompt,
    window_prompt_sha256,
)
from app.source_analysis_bounded_win001_retry_readiness.constants import (
    PROJECT_NAME,
    PROTECTED_EVIDENCE,
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


def clean_integrity(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> dict[str, str | bool]:
    path = clean_json_path(project_name, sortie_dir=sortie_dir)
    return {
        "path": str(path),
        "present": path.is_file(),
        "sha256": sha256_of_file(path) if path.is_file() else "",
        "rewritten": False,
    }


def prompt_integrity() -> dict[str, str | bool]:
    v10 = build_window_system_prompt("en", version=WINDOW_ANALYSIS_PROMPT_VERSION_V10)
    v11 = build_window_system_prompt("en", version=WINDOW_ANALYSIS_PROMPT_VERSION)
    return {
        "historical_version": WINDOW_ANALYSIS_PROMPT_VERSION_V10,
        "successor_version": WINDOW_ANALYSIS_PROMPT_VERSION,
        "historical_sha256": window_prompt_sha256(v10),
        "successor_sha256": window_prompt_sha256(v11),
        "historical_byte_identical_across_calls": v10
        == build_window_system_prompt("en", version=WINDOW_ANALYSIS_PROMPT_VERSION_V10),
        "successor_byte_identical_across_calls": v11
        == build_window_system_prompt("en", version=WINDOW_ANALYSIS_PROMPT_VERSION),
        "versions_differ": v10 != v11,
    }


def generation_c_integrity() -> dict[str, object]:
    hashes = generation_c_hashes()
    return {
        "raw_sha256": hashes["raw_sha256"],
        "anthropic_sha256": hashes["anthropic_sha256"],
        "raw_matches_historical": bool(hashes["raw_matches_historical"]),
        "anthropic_matches_historical": bool(hashes["anthropic_matches_historical"]),
        "unchanged": bool(hashes["raw_matches_historical"])
        and bool(hashes["anthropic_matches_historical"]),
    }
