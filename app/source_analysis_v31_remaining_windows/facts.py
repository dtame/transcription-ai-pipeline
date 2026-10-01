"""Isolation / freeze historique A.13–A.27. 0 provider."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.language_cleanup.transcript_source import audit_dir
from app.paths import SORTIE_DIR
from app.semantic_canary.integrity import sha256_of_file
from app.source_analysis_v3_symbolic_grammar_canary.paths import (
    production_windows_touched,
)
from app.source_analysis_v31_real_win004.facts import inspect_isolation as inspect_a27
from app.source_analysis_v31_remaining_windows.constants import (
    A19_RESULT,
    A21_RESULT,
    A22_RESULT,
    A23_RESULT,
    A24_RESULT,
    A25_RESULT,
    A26_RESULT,
    A261_RESULT,
    A27_RESULT,
    MODE,
    PHASE,
    PRODUCTION_PLANNER_VERSION,
    PROJECT_NAME,
    PROTECTED_HISTORICAL,
    SCHEMA_VERSION,
)
from app.source_analysis_v31_remaining_windows.paths import (
    a27_lock_path,
    production_source_map_present,
    production_window_present,
)


def _optional_hash(path: Path) -> str | None:
    return sha256_of_file(path) if path.is_file() else None


def protected_a28_historical_hashes(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> dict[str, str]:
    root = Path(sortie_dir) if sortie_dir is not None else SORTIE_DIR
    project_root = root / project_name
    hashes: dict[str, str] = {}
    for rel in PROTECTED_HISTORICAL:
        path = project_root / rel
        if path.is_file():
            hashes[rel] = sha256_of_file(path)
    return hashes


def inspect_isolation(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> dict[str, Any]:
    a27 = inspect_a27(project_name, sortie_dir=sortie_dir)
    audit = audit_dir(project_name, sortie_dir=sortie_dir)
    extra = {
        "a27_report": _optional_hash(
            audit / "PHASE_3B77A27_REAL_WIN004_LOCAL_LITE_CANARY_REPORT.md"
        ),
        "a27_lock": a27_lock_path(project_name, sortie_dir=sortie_dir).is_file(),
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "a27_isolation": a27,
        "protected_hashes": protected_a28_historical_hashes(
            project_name, sortie_dir=sortie_dir
        ),
        "a27_extra": extra,
        "a19_remains_fail": A19_RESULT == "FAIL",
        "a21_remains_pass": A21_RESULT == "PASS",
        "a22_remains_fail": A22_RESULT == "FAIL",
        "a23_remains_pass": A23_RESULT == "PASS",
        "a24_remains_fail": A24_RESULT == "FAIL",
        "a25_remains_partial": A25_RESULT == "PARTIAL",
        "a26_remains_pass": A26_RESULT == "PASS",
        "a261_remains_pass": A261_RESULT == "PASS",
        "a27_remains_pass": A27_RESULT == "PASS",
        "a27_evidence_intact": extra["a27_report"] is not None,
        "source_map_present": production_source_map_present(
            project_name, sortie_dir=sortie_dir
        ),
        "production_win001_present": production_window_present(
            project_name, "WIN001", sortie_dir=sortie_dir
        ),
        "production_win004_present": production_window_present(
            project_name, "WIN004", sortie_dir=sortie_dir
        ),
        "production_windows_touched": production_windows_touched(
            project_name, sortie_dir=sortie_dir
        ),
        "production_planner": PRODUCTION_PLANNER_VERSION,
        "production_planner_unchanged": True,
        "win001_authorized": False,
        "win004_authorized": False,
        "consolidation_authorized": False,
        "source_map": "NOT PUBLISHED",
        "phase_3b": "INCOMPLETE",
        "v3_production_activation": False,
        "v31_production_activation": False,
        "v21_small_production_activation": False,
    }


__all__ = ["inspect_isolation", "protected_a28_historical_hashes"]
