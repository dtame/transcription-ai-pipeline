"""Chemins isolés audit/canary/v3_symbolic_handle_grammar — jamais production."""

from __future__ import annotations

from pathlib import Path

from app.language_cleanup.transcript_source import audit_dir
from app.source_analysis.writer import source_map_path
from app.source_analysis.window_writer import result_path, transport_path, windows_root
from app.source_analysis_v3_symbolic_grammar_canary.constants import (
    CANARY_SUBDIR,
    CANARY_WINDOW_ID,
    LOCK_NAME,
)


def canary_root(project_name: str, *, sortie_dir: Path | None = None) -> Path:
    return audit_dir(project_name, sortie_dir=sortie_dir) / Path(CANARY_SUBDIR)


def canary_windows_root(project_name: str, *, sortie_dir: Path | None = None) -> Path:
    return canary_root(project_name, sortie_dir=sortie_dir) / "windows"


def canary_lock_path(project_name: str, *, sortie_dir: Path | None = None) -> Path:
    return canary_root(project_name, sortie_dir=sortie_dir) / LOCK_NAME


def production_windows_touched(project_name: str, *, sortie_dir: Path | None = None) -> bool:
    root = windows_root(project_name, sortie_dir=sortie_dir)
    return any(
        path.exists()
        for path in (
            transport_path(project_name, "WIN001", root=root),
            result_path(project_name, "WIN001", root=root),
            transport_path(project_name, CANARY_WINDOW_ID, root=root),
            result_path(project_name, CANARY_WINDOW_ID, root=root),
        )
    ) or source_map_path(project_name, sortie_dir=sortie_dir).exists()


__all__ = [
    "canary_lock_path",
    "canary_root",
    "canary_windows_root",
    "production_windows_touched",
]
