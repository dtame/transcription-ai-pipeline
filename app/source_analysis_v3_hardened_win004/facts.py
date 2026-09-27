"""Isolation / freeze historique A.13–A.23. 0 provider."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.language_cleanup.transcript_source import audit_dir
from app.paths import SORTIE_DIR
from app.semantic_canary.integrity import sha256_of_file
from app.source_analysis_v3_hardened_win004.constants import (
    MODE,
    PHASE,
    PRODUCTION_PLANNER_VERSION,
    PROJECT_NAME,
    PROTECTED_HISTORICAL,
    SCHEMA_VERSION,
)
from app.source_analysis_v3_hardened_win004.paths import (
    production_source_map_present,
    production_window_present,
)
from app.source_analysis_v3_second_window.facts import (
    inspect_isolation as inspect_a22_isolation,
    protected_a22_historical_hashes,
)
from app.source_analysis_v3_symbolic_grammar_canary.paths import (
    production_windows_touched,
)


def _optional_hash(path: Path) -> str | None:
    return sha256_of_file(path) if path.is_file() else None


def protected_a24_historical_hashes(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> dict[str, str]:
    root = Path(sortie_dir) if sortie_dir is not None else SORTIE_DIR
    project_root = root / project_name
    hashes = dict(protected_a22_historical_hashes(project_name, sortie_dir=sortie_dir))
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
    a22 = inspect_a22_isolation(project_name, sortie_dir=sortie_dir)
    audit = audit_dir(project_name, sortie_dir=sortie_dir)
    extra = {
        "a19_report": _optional_hash(
            audit / "PHASE_3B77A19_REAL_V3_SMALL_WIN001_SYMBOLIC_HANDLE_CANARY_REPORT.md"
        ),
        "a21_report": _optional_hash(
            audit / "PHASE_3B77A21_REAL_V3_SMALL_WIN001_HARDENED_RETRY_REPORT.md"
        ),
        "a22_report": _optional_hash(
            audit / "PHASE_3B77A22_SECOND_INDEPENDENT_REAL_WINDOW_CANARY_REPORT.md"
        ),
        "a22_execution": _optional_hash(
            audit / "source_analysis_v3_second_window_execution.json"
        ),
        "a23_report": _optional_hash(
            audit / "PHASE_3B77A23_A22_IDEA_EXAMPLE_TYPE_CONTRACT_FORENSICS_REPORT.md"
        ),
        "a23_future": _optional_hash(
            audit / "source_analysis_v3_future_win004_retry_readiness.json"
        ),
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "a22_isolation": a22,
        "protected_hashes": protected_a24_historical_hashes(
            project_name, sortie_dir=sortie_dir
        ),
        "a19_a23_extra": extra,
        "a19_remains_fail": True,
        "a21_remains_pass": True,
        "a22_remains_fail": True,
        "a23_remains_pass": True,
        "a22_evidence_intact": extra["a22_report"] is not None,
        "a23_evidence_intact": extra["a23_report"] is not None,
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
        "v21_small_production_activation": False,
    }


__all__ = ["inspect_isolation", "protected_a24_historical_hashes"]
