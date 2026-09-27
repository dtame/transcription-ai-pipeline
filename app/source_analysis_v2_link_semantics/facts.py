"""Isolation / freeze historique A.14."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.source_analysis_local_v2.facts import inspect_integrity as inspect_a11_integrity
from app.source_analysis_thinking_contract.facts import inspect_isolation
from app.source_analysis_v2_grammar_canary.facts import historical_freeze
from app.source_analysis_v2_link_semantics.constants import (
    MODE,
    PHASE,
    SCHEMA_VERSION,
)
from app.source_analysis_v2_link_semantics.evidence import (
    evidence_inventory,
    protected_a13_hashes,
)


def inspect_a14_integrity(
    project_name: str,
    *,
    sortie_dir: Path | None = None,
) -> dict[str, Any]:
    base = inspect_a11_integrity(project_name, sortie_dir=sortie_dir)
    freeze = historical_freeze(project_name, sortie_dir=sortie_dir)
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "a11": base,
        "a13_freeze": freeze,
        "a13_evidence": evidence_inventory(project_name, sortie_dir=sortie_dir),
        "a13_hashes": protected_a13_hashes(project_name, sortie_dir=sortie_dir),
        "source_map_present": base.get("source_map_present"),
        "project_state": base.get("project_state"),
        "production_planner_unchanged": base.get("production_planner_unchanged"),
    }


__all__ = ["inspect_a14_integrity", "inspect_isolation"]
