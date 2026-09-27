"""
Builder ConsolidationInput compatible V2.

Ne mute pas consolidation-1.0. Ne passe pas par validate_window_result V1.
"""

from __future__ import annotations

from typing import Sequence

from app.source_analysis.consolidation_input import (
    _build_from_ordered,
    _ordered_results_from_plan,
)
from app.source_analysis.consolidation_models import (
    CONSOLIDATION_SAFE_INPUT_BUDGET_TOKENS,
    ConsolidationInput,
)
from app.source_analysis.errors import ConsolidationInputError
from app.source_analysis.window_models import WindowSemanticResult
from app.source_analysis_hybrid.contracts import WindowPlan
from app.source_analysis_local_v2.constants import (
    CONSOLIDATION_RECOVERY_VERSION,
    DEFERRED_KINDS,
    SEMANTIC_TRANSPORT_VERSION_V2,
    WINDOW_ANALYSIS_PROMPT_VERSION_V12,
    WINDOW_ANALYSIS_PROMPT_VERSION_V121,
)
from app.source_analysis_local_v2.result import assert_no_deferred_records


def build_v2_consolidation_input(
    plan: WindowPlan,
    results: Sequence[WindowSemanticResult],
    *,
    safe_budget: int = CONSOLIDATION_SAFE_INPUT_BUDGET_TOKENS,
    enforce_budget: bool = True,
) -> ConsolidationInput:
    """
    Adapter : fenêtres V2 validées → ConsolidationInput historique.

    Category C (VOICE/INTENT/AUDIENCE) est absente volontairement.
    consolidation-1.0 accepte gm evidence pointant vers TOPIC/IDEA.
    """
    if len(results) != plan.window_count:
        raise ConsolidationInputError(
            f"ALL_WINDOWS_READY refusé : {len(results)}/{plan.window_count}"
        )
    ordered = _ordered_results_from_plan(plan, results)
    for result in ordered:
        if result.transport_version != SEMANTIC_TRANSPORT_VERSION_V2:
            raise ConsolidationInputError(
                f"{result.window_id} : transport {result.transport_version} ≠ v2"
            )
        if result.prompt_version not in {
            WINDOW_ANALYSIS_PROMPT_VERSION_V12,
            WINDOW_ANALYSIS_PROMPT_VERSION_V121,
        }:
            raise ConsolidationInputError(
                f"{result.window_id} : prompt {result.prompt_version} "
                f"∉ {{1.2, 1.2.1}}"
            )
        assert_no_deferred_records(result)
        deferred = [r.kind for r in result.records if r.kind in DEFERRED_KINDS]
        if deferred:
            raise ConsolidationInputError(
                f"{result.window_id} : kinds différés {deferred}"
            )
    return _build_from_ordered(
        transcript_id=plan.transcript_id,
        planner_version=plan.planner_version,
        results=ordered,
        plan=None,
        safe_budget=safe_budget,
        enforce_budget=enforce_budget,
    )


def v2_consolidation_compatibility() -> dict:
    return {
        "historical_consolidation_1_0_unchanged": True,
        "recovery_contract": CONSOLIDATION_RECOVERY_VERSION,
        "local_v2_feeds_existing_input_shape": True,
        "category_c_absent_intentional": True,
        "gm_evidence_may_point_to_topic_or_idea": True,
        "repetition_via_rep_ops": True,
        "python_does_not_invent_global_metadata": True,
        "regional_does_not_decide_final_metadata": True,
        "global_owns_metadata_repetition_relations_merges": True,
    }
