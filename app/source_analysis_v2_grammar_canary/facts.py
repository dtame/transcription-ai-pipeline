"""Intégrité historique + isolation production pour A.13."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.source_analysis.writer import source_map_path
from app.source_analysis_execution_strategy.review import inspect_project_state
from app.source_analysis_hybrid.constants import PLANNER_VERSION
from app.source_analysis_thinking_contract.facts import inspect_integrity, inspect_isolation
from app.source_analysis_v2_grammar_canary.constants import (
    PRODUCTION_PLANNER_VERSION,
    PROJECT_NAME,
    SCHEMA_VERSION,
)
from app.source_analysis_v2_grammar_canary.paths import production_windows_touched


def historical_freeze(project_name: str = PROJECT_NAME, *, sortie_dir: Path | None = None) -> dict[str, Any]:
    integrity = inspect_integrity(project_name, sortie_dir=sortie_dir)
    isolation = inspect_isolation(project_name, sortie_dir=sortie_dir)
    state = inspect_project_state(project_name, sortie_dir=sortie_dir)
    return {
        "schema_version": SCHEMA_VERSION,
        "integrity": integrity,
        "isolation": isolation,
        "project_state": {
            **state,
            "not_success": str(state.get("status") or "") != "success",
        },
        "source_map_present": source_map_path(project_name, sortie_dir=sortie_dir).exists(),
        "production_windows_touched": production_windows_touched(
            project_name, sortie_dir=sortie_dir
        ),
        "production_planner": PLANNER_VERSION,
        "production_planner_unchanged": PLANNER_VERSION == PRODUCTION_PLANNER_VERSION,
        "real_windows_ready": "0 / 7",
    }


__all__ = ["historical_freeze"]
