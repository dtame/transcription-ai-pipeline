"""Impact aval : Editorial Planner, Book Generator, publication. Offline."""

from __future__ import annotations

from typing import Any

from app.source_analysis.writer import source_map_path
from app.source_analysis_v31_local_lite.constants import (
    MODE,
    PHASE,
    PROJECT_NAME,
    SCHEMA_VERSION,
)


def build_downstream_impact(
    project_name: str = PROJECT_NAME,
    *,
    source_map_exists: bool | None = None,
) -> dict[str, Any]:
    published = (
        source_map_path(project_name).exists()
        if source_map_exists is None
        else source_map_exists
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "editorial_planner_dependency": "NONE",
        "editorial_planner": (
            "No Phase 4 Editorial Planner consumer of Idea.kind exists "
            "in this repository."
        ),
        "book_generator_dependency": "NONE",
        "book_generator": (
            "No Book Generator consumer of Idea.kind exists in this repository."
        ),
        "source_map_publication": "NOT PUBLISHED" if not published else "PRESENT",
        "source_map_can_represent_absent_kind": True,
        "phase4_contract_unchanged": True,
        "requires_local_idea_subtype": False,
        "requires_canonical_idea_subtype": False,
    }


__all__ = ["build_downstream_impact"]
