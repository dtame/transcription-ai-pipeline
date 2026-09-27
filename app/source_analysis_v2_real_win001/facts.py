"""Isolation / freeze historique A.15. 0 provider."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.source_analysis_v2_grammar_canary.facts import historical_freeze
from app.source_analysis_v2_link_semantics.facts import inspect_a14_integrity
from app.source_analysis_v2_real_win001.constants import (
    MODE,
    PHASE,
    PRODUCTION_PLANNER_VERSION,
    PROJECT_NAME,
    SCHEMA_VERSION,
)
from app.source_analysis_v2_real_win001.paths import (
    production_source_map_present,
    production_win001_present,
    production_windows_touched,
)


def inspect_isolation(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> dict[str, Any]:
    freeze = historical_freeze(project_name, sortie_dir=sortie_dir)
    a14 = inspect_a14_integrity(project_name, sortie_dir=sortie_dir)
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "a13_freeze": freeze,
        "a14": a14,
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
    }


__all__ = ["inspect_isolation"]
