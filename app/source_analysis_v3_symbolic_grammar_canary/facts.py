"""Intégrité historique + isolation production pour A.18."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.language_cleanup.transcript_source import audit_dir
from app.semantic_canary.integrity import sha256_of_file
from app.source_analysis.writer import source_map_path
from app.source_analysis_execution_strategy.review import inspect_project_state
from app.source_analysis_hybrid.constants import PLANNER_VERSION
from app.source_analysis_local_v3.prompt import build_window_system_prompt_v13
from app.source_analysis_local_v3.schema import measure_v3_schema_pair
from app.source_analysis_thinking_contract.facts import inspect_integrity, inspect_isolation
from app.source_analysis_v2_a15_forensics.constants import A15_REPORT_NAME as A15_REPORT
from app.source_analysis_v2_grammar_canary.constants import REPORT_NAME as A13_REPORT
from app.source_analysis_v3_symbolic_grammar_canary.constants import (
    EXPECTED_ADAPTED_SCHEMA_BYTES,
    EXPECTED_RAW_SCHEMA_BYTES,
    PRODUCTION_PLANNER_VERSION,
    PROJECT_NAME,
    SCHEMA_VERSION,
    WINDOW_ANALYSIS_PROMPT_VERSION_V13,
)
from app.source_analysis_v3_symbolic_grammar_canary.paths import production_windows_touched
from app.source_analysis_v3_symbolic_handles.constants import (
    REPORT_NAME as A17_REPORT,
    SCHEMA_ARTIFACT as A17_SCHEMA_ARTIFACT,
)

A16_REPORT = "PHASE_3B77A16_A15_INVALID_LINK_FORENSICS_OFFLINE_SEMANTIC_REVIEW_REPORT.md"


def _optional_hash(path: Path) -> str | None:
    return sha256_of_file(path) if path.is_file() else None


def historical_freeze(project_name: str = PROJECT_NAME, *, sortie_dir: Path | None = None) -> dict[str, Any]:
    integrity = inspect_integrity(project_name, sortie_dir=sortie_dir)
    isolation = inspect_isolation(project_name, sortie_dir=sortie_dir)
    state = inspect_project_state(project_name, sortie_dir=sortie_dir)
    audit = audit_dir(project_name, sortie_dir=sortie_dir)
    v3 = measure_v3_schema_pair()
    prompt_13 = build_window_system_prompt_v13("en")
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
        "prompt_1_3_version": WINDOW_ANALYSIS_PROMPT_VERSION_V13,
        "prompt_1_3_present": "HANDLE RULES" in prompt_13,
        "v3_schema_bytes": {
            "raw": v3["raw_bytes"],
            "adapted": v3["adapted_bytes"],
            "matches_a17": (
                v3["raw_bytes"] == EXPECTED_RAW_SCHEMA_BYTES
                and v3["adapted_bytes"] == EXPECTED_ADAPTED_SCHEMA_BYTES
            ),
        },
        "historical_reports": {
            "a13": _optional_hash(audit / A13_REPORT),
            "a15": _optional_hash(audit / A15_REPORT),
            "a16": _optional_hash(audit / A16_REPORT),
            "a17": _optional_hash(audit / A17_REPORT),
            "a17_schema": _optional_hash(audit / A17_SCHEMA_ARTIFACT),
        },
    }


__all__ = ["historical_freeze"]
