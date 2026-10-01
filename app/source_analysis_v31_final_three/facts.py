"""Isolation / freeze historique A.13–A.30. 0 provider."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.language_cleanup.transcript_source import audit_dir
from app.paths import SORTIE_DIR
from app.semantic_canary.integrity import sha256_of_file
from app.source_analysis_v3_symbolic_grammar_canary.paths import (
    production_windows_touched,
)
from app.source_analysis_v31_final_three.constants import (
    A19_RESULT,
    A21_RESULT,
    A22_RESULT,
    A23_RESULT,
    A24_RESULT,
    A25_RESULT,
    A26_RESULT,
    A261_RESULT,
    A27_RESULT,
    A28_RESULT,
    A29_RESULT,
    A30_REPORT_NAME,
    A30_RESULT,
    MODE,
    PHASE,
    PRODUCTION_PLANNER_VERSION,
    PROJECT_NAME,
    PROTECTED_HISTORICAL,
    SCHEMA_VERSION,
    WIN003_PROVENANCE,
)
from app.source_analysis_v31_final_three.paths import (
    a28_lock_path,
    production_source_map_present,
    production_window_present,
)
from app.source_analysis_v31_remaining_windows.facts import inspect_isolation as inspect_a28


def _optional_hash(path: Path) -> str | None:
    return sha256_of_file(path) if path.is_file() else None


def protected_a31_historical_hashes(
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
    a28 = inspect_a28(project_name, sortie_dir=sortie_dir)
    audit = audit_dir(project_name, sortie_dir=sortie_dir)
    extra = {
        "a30_report": _optional_hash(audit / A30_REPORT_NAME),
        "a28_lock": a28_lock_path(project_name, sortie_dir=sortie_dir).is_file(),
        "ready_after_a30": _optional_hash(
            audit / "source_analysis_ready_windows_after_a30.json"
        ),
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "a28_isolation": a28,
        "protected_hashes": protected_a31_historical_hashes(
            project_name, sortie_dir=sortie_dir
        ),
        "a30_extra": extra,
        "a19_remains_fail": A19_RESULT == "FAIL",
        "a21_remains_pass": A21_RESULT == "PASS",
        "a22_remains_fail": A22_RESULT == "FAIL",
        "a23_remains_pass": A23_RESULT == "PASS",
        "a24_remains_fail": A24_RESULT == "FAIL",
        "a25_remains_partial": A25_RESULT == "PARTIAL",
        "a26_remains_pass": A26_RESULT == "PASS",
        "a261_remains_pass": A261_RESULT == "PASS",
        "a27_remains_pass": A27_RESULT == "PASS",
        "a28_remains_fail": A28_RESULT == "FAIL",
        "a29_remains_pass": A29_RESULT == "PASS",
        "a30_remains_pass": A30_RESULT == "PASS",
        "a30_evidence_intact": extra["a30_report"] is not None,
        "win003_provenance": WIN003_PROVENANCE,
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
        "win002_authorized": False,
        "win003_authorized": False,
        "win004_authorized": False,
        "consolidation_authorized": False,
        "source_map": "NOT PUBLISHED",
        "phase_3b": "INCOMPLETE",
        "v3_production_activation": False,
        "v31_production_activation": False,
        "v21_small_production_activation": False,
        "local_lite_global_activation": False,
    }


__all__ = ["inspect_isolation", "protected_a31_historical_hashes"]
