"""Isolation / freeze historique A.13–A.18. 0 provider."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.language_cleanup.transcript_source import audit_dir
from app.paths import SORTIE_DIR
from app.semantic_canary.integrity import sha256_of_file
from app.source_analysis_v2_a15_forensics.evidence import protected_historical_hashes
from app.source_analysis_v3_real_win001.constants import (
    MODE,
    PHASE,
    PRODUCTION_PLANNER_VERSION,
    PROJECT_NAME,
    PROTECTED_HISTORICAL,
    SCHEMA_VERSION,
)
from app.source_analysis_v3_real_win001.paths import (
    production_source_map_present,
    production_win001_present,
)
from app.source_analysis_v3_symbolic_grammar_canary.facts import (
    historical_freeze as a18_historical_freeze,
)
from app.source_analysis_v3_symbolic_grammar_canary.paths import (
    production_windows_touched,
)


def _optional_hash(path: Path) -> str | None:
    return sha256_of_file(path) if path.is_file() else None


def protected_a19_historical_hashes(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> dict[str, str]:
    root = Path(sortie_dir) if sortie_dir is not None else SORTIE_DIR
    project_root = root / project_name
    hashes = dict(protected_historical_hashes(project_name, sortie_dir=sortie_dir))
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
    freeze = a18_historical_freeze(project_name, sortie_dir=sortie_dir)
    audit = audit_dir(project_name, sortie_dir=sortie_dir)
    extra = {
        "a18_report": _optional_hash(audit / "PHASE_3B77A18_SYMBOLIC_HANDLE_TINY_GRAMMAR_CANARY_REPORT.md"),
        "a18_execution": _optional_hash(
            audit / "source_analysis_v3_symbolic_grammar_canary_execution.json"
        ),
        "a18_payload": _optional_hash(
            audit / "source_analysis_v3_symbolic_grammar_canary_payload.json"
        ),
    }
    reports = dict(freeze.get("historical_reports") or {})
    reports.update(extra)
    freeze = dict(freeze)
    freeze["historical_reports"] = reports
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "a18_freeze": freeze,
        "protected_hashes": protected_a19_historical_hashes(
            project_name, sortie_dir=sortie_dir
        ),
        "source_map_present": production_source_map_present(
            project_name, sortie_dir=sortie_dir
        ),
        "production_win001_present": production_win001_present(
            project_name, sortie_dir=sortie_dir
        ),
        "production_windows_touched": production_windows_touched(
            project_name, sortie_dir=sortie_dir
        ),
        "production_planner": PRODUCTION_PLANNER_VERSION,
        "production_planner_unchanged": True,
        "win002_authorized": False,
        "consolidation_authorized": False,
        "source_map": "NOT PUBLISHED",
        "phase_3b": "INCOMPLETE",
        "v3_production_activation": False,
    }


__all__ = ["inspect_isolation", "protected_a19_historical_hashes"]
