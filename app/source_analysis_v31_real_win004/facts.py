"""Isolation / freeze historique A.13–A.26.1. 0 provider."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.language_cleanup.transcript_source import audit_dir
from app.paths import SORTIE_DIR
from app.semantic_canary.integrity import sha256_of_file
from app.source_analysis_v3_hardened_win004.facts import inspect_isolation as inspect_a24_isolation
from app.source_analysis_v3_symbolic_grammar_canary.paths import (
    production_windows_touched,
)
from app.source_analysis_v31_real_win004.constants import (
    A19_RESULT,
    A21_RESULT,
    A22_RESULT,
    A23_RESULT,
    A24_RESULT,
    A25_RESULT,
    A26_RESULT,
    A261_RESULT,
    MODE,
    PHASE,
    PRODUCTION_PLANNER_VERSION,
    PROJECT_NAME,
    PROTECTED_HISTORICAL,
    SCHEMA_VERSION,
)
from app.source_analysis_v31_real_win004.paths import (
    production_source_map_present,
    production_window_present,
)


def _optional_hash(path: Path) -> str | None:
    return sha256_of_file(path) if path.is_file() else None


def protected_a27_historical_hashes(
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
    a24 = inspect_a24_isolation(project_name, sortie_dir=sortie_dir)
    audit = audit_dir(project_name, sortie_dir=sortie_dir)
    extra = {
        "a24_report": _optional_hash(
            audit / "PHASE_3B77A24_REAL_WIN004_HARDENED_TYPE_CONTRACT_RETRY_REPORT.md"
        ),
        "a25_report": _optional_hash(
            audit / "PHASE_3B77A25_POST_A24_METADATA_ARCHITECTURE_DECISION_REPORT.md"
        ),
        "a26_report": _optional_hash(
            audit / "PHASE_3B77A26_IMPLEMENT_GLOBALIZED_IDEA_SUBTYPE_LOCAL_LITE_REPORT.md"
        ),
        "a26_future": _optional_hash(
            audit / "source_analysis_v31_future_win004_readiness.json"
        ),
        "a261_report": _optional_hash(
            audit / "PHASE_3B77A261_LOCAL_LITE_CANONICAL_SCHEMA_BOUNDARY_REPORT.md"
        ),
    }
    a24_intact = extra["a24_report"] is not None
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "a24_isolation": a24,
        "protected_hashes": protected_a27_historical_hashes(
            project_name, sortie_dir=sortie_dir
        ),
        "a24_a261_extra": extra,
        "a19_remains_fail": A19_RESULT == "FAIL",
        "a21_remains_pass": A21_RESULT == "PASS",
        "a22_remains_fail": A22_RESULT == "FAIL",
        "a23_remains_pass": A23_RESULT == "PASS",
        "a24_remains_fail": A24_RESULT == "FAIL",
        "a25_remains_partial": A25_RESULT == "PARTIAL",
        "a26_remains_pass": A26_RESULT == "PASS",
        "a261_remains_pass": A261_RESULT == "PASS",
        "a24_evidence_intact": a24_intact and extra["a24_report"] is not None,
        "a26_evidence_intact": extra["a26_report"] is not None,
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
        "other_windows_authorized": False,
        "consolidation_authorized": False,
        "source_map": "NOT PUBLISHED",
        "phase_3b": "INCOMPLETE",
        "v3_production_activation": False,
        "v31_production_activation": False,
        "v21_small_production_activation": False,
    }


__all__ = ["inspect_isolation", "protected_a27_historical_hashes"]
