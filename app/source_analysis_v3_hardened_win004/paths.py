"""Chemins isolés audit/canary/v3_hardened_win004 — jamais production."""

from __future__ import annotations

from pathlib import Path

from app.language_cleanup.transcript_source import audit_dir
from app.source_analysis.writer import source_map_path
from app.source_analysis.window_writer import result_path, transport_path, windows_root
from app.source_analysis_v3_hardened_win004.constants import (
    CANARY_SUBDIR,
    CANDIDATE_CACHE_SUBDIR,
    CANDIDATE_WINDOWS_SUBDIR,
    LOCK_NAME,
    WINDOW_ID,
)
from app.source_analysis_v3_second_window.paths import (
    a22_lock_path,
    candidate_cache_dir as a22_candidate_cache_dir,
)


def canary_root(project_name: str, *, sortie_dir: Path | None = None) -> Path:
    return audit_dir(project_name, sortie_dir=sortie_dir) / Path(CANARY_SUBDIR)


def a24_lock_path(project_name: str, *, sortie_dir: Path | None = None) -> Path:
    return canary_root(project_name, sortie_dir=sortie_dir) / LOCK_NAME


def candidate_windows_root(project_name: str, *, sortie_dir: Path | None = None) -> Path:
    return canary_root(project_name, sortie_dir=sortie_dir) / CANDIDATE_WINDOWS_SUBDIR


def candidate_window_dir(
    project_name: str,
    *,
    sortie_dir: Path | None = None,
    window_id: str = WINDOW_ID,
) -> Path:
    return candidate_windows_root(project_name, sortie_dir=sortie_dir) / window_id


def candidate_cache_dir(
    project_name: str,
    analysis_signature: str,
    *,
    sortie_dir: Path | None = None,
) -> Path:
    return (
        canary_root(project_name, sortie_dir=sortie_dir)
        / CANDIDATE_CACHE_SUBDIR
        / analysis_signature
        / WINDOW_ID
    )


def forensic_windows_root(project_name: str, *, sortie_dir: Path | None = None) -> Path:
    return canary_root(project_name, sortie_dir=sortie_dir) / "windows"


def production_source_map_present(
    project_name: str, *, sortie_dir: Path | None = None
) -> bool:
    return source_map_path(project_name, sortie_dir=sortie_dir).exists()


def production_window_present(
    project_name: str,
    window_id: str = WINDOW_ID,
    *,
    sortie_dir: Path | None = None,
) -> bool:
    root = windows_root(project_name, sortie_dir=sortie_dir)
    return transport_path(project_name, window_id, root=root).exists() or result_path(
        project_name, window_id, root=root
    ).exists()


__all__ = [
    "a22_candidate_cache_dir",
    "a22_lock_path",
    "a24_lock_path",
    "audit_dir",
    "canary_root",
    "candidate_cache_dir",
    "candidate_window_dir",
    "candidate_windows_root",
    "forensic_windows_root",
    "production_source_map_present",
    "production_window_present",
]
