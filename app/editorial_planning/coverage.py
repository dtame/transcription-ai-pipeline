"""
Politique de couverture des IDEA — Phase 4.

Vocabulaire minimal :

    ASSIGNED    l'idée a une section primaire
    DEFERRED    hors plan actuel, motif obligatoire
    EXCLUDED    hors livre, motif obligatoire

Grouper plusieurs IDEA dans une même section n'est PAS une fusion
sémantique : toutes les refs sont conservées. Une réutilisation dans
d'autres sections est auditable via additional_section_ids.
L'omission silencieuse est un FAIL.
"""

from __future__ import annotations

from typing import Mapping

from app.editorial_planning.constants import (
    DEFERRAL_REASONS,
    EXCLUSION_REASONS,
    IDEA_COVERAGE_POLICY_VERSION,
    IDEA_DISPOSITIONS,
)
from app.editorial_planning.models import EditorialPlan, IdeaDisposition
from app.source_analysis.models import SourceMap

SILENT_OMISSION = "FORBIDDEN"
DEFAULT_SUBSTANTIVE_EXPECTATION = (
    "Substantive SourceMap IDEAs should appear somewhere in the plan. "
    "Silent omission is forbidden."
)

UNCERTAINTY_POLICY = (
    "UNC refs remain visible. The planner must not convert uncertainty "
    "into certainty. Unassigned UNC refs are listed, never erased."
)


def coverage_policy_dict() -> dict:
    return {
        "policy_version": IDEA_COVERAGE_POLICY_VERSION,
        "dispositions": list(IDEA_DISPOSITIONS),
        "exclusion_reasons": list(EXCLUSION_REASONS),
        "deferral_reasons": list(DEFERRAL_REASONS),
        "silent_omission": SILENT_OMISSION,
        "grouping_is_not_semantic_merge": True,
        "primary_assignment": "one primary section per ASSIGNED idea",
        "reuse": (
            "Additional section placements are explicit via "
            "additional_section_ids. Not a separate disposition."
        ),
        "default_expectation": DEFAULT_SUBSTANTIVE_EXPECTATION,
        "uncertainty_policy": UNCERTAINTY_POLICY,
        "relations_authoritative": False,
        "technical_windows_as_editorial_units": False,
    }


def source_map_idea_ids(source_map: SourceMap) -> tuple[str, ...]:
    return tuple(idea.idea_id for idea in source_map.ideas)


def coverage_index(plan: EditorialPlan) -> dict[str, IdeaDisposition]:
    return {item.idea_id: item for item in plan.idea_coverage}


def missing_idea_ids(plan: EditorialPlan, source_map: SourceMap) -> tuple[str, ...]:
    covered = {item.idea_id for item in plan.idea_coverage}
    return tuple(
        idea_id for idea_id in source_map_idea_ids(source_map) if idea_id not in covered
    )


def unknown_coverage_ids(plan: EditorialPlan, source_map: SourceMap) -> tuple[str, ...]:
    known = set(source_map_idea_ids(source_map))
    return tuple(
        item.idea_id for item in plan.idea_coverage if item.idea_id not in known
    )


def valid_reason_for(disposition: str, reason: str) -> bool:
    if disposition == "ASSIGNED":
        return True
    if disposition == "EXCLUDED":
        return reason in EXCLUSION_REASONS
    if disposition == "DEFERRED":
        return reason in DEFERRAL_REASONS
    return False


def policy_for_audit() -> Mapping[str, object]:
    return coverage_policy_dict()
