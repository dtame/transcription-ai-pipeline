"""Builder ConsolidationInput compatible V3. Ne mute pas consolidation-1.0 ni v2."""

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
from app.source_analysis_local_v2.constants import DEFERRED_KINDS
from app.source_analysis_local_v3.constants import (
    SEMANTIC_TRANSPORT_VERSION_V3,
    SEMANTIC_TRANSPORT_VERSION_V31_LOCAL_LITE,
    WINDOW_ANALYSIS_PROMPT_VERSION_V13,
    WINDOW_ANALYSIS_PROMPT_VERSION_V140,
)
from app.source_analysis_local_v3.result import assert_no_deferred_records


def build_v3_consolidation_input(
    plan: WindowPlan,
    results: Sequence[WindowSemanticResult],
    *,
    safe_budget: int = CONSOLIDATION_SAFE_INPUT_BUDGET_TOKENS,
    enforce_budget: bool = True,
) -> ConsolidationInput:
    if len(results) != plan.window_count:
        raise ConsolidationInputError(
            f"ALL_WINDOWS_READY refusé : {len(results)}/{plan.window_count}"
        )
    ordered = _ordered_results_from_plan(plan, results)
    for result in ordered:
        if result.transport_version != SEMANTIC_TRANSPORT_VERSION_V3:
            raise ConsolidationInputError(
                f"{result.window_id} : transport {result.transport_version} ≠ v3"
            )
        if result.prompt_version != WINDOW_ANALYSIS_PROMPT_VERSION_V13:
            raise ConsolidationInputError(
                f"{result.window_id} : prompt {result.prompt_version} ≠ 1.3"
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


def build_v31_consolidation_input(
    plan: WindowPlan,
    results: Sequence[WindowSemanticResult],
    *,
    safe_budget: int = CONSOLIDATION_SAFE_INPUT_BUDGET_TOKENS,
    enforce_budget: bool = True,
) -> ConsolidationInput:
    if len(results) != plan.window_count:
        raise ConsolidationInputError(
            f"ALL_WINDOWS_READY refusé : {len(results)}/{plan.window_count}"
        )
    ordered = _ordered_results_from_plan(plan, results)
    for result in ordered:
        if result.transport_version != SEMANTIC_TRANSPORT_VERSION_V31_LOCAL_LITE:
            raise ConsolidationInputError(
                f"{result.window_id} : transport {result.transport_version} "
                "≠ v3.1-local-lite"
            )
        if result.prompt_version != WINDOW_ANALYSIS_PROMPT_VERSION_V140:
            raise ConsolidationInputError(
                f"{result.window_id} : prompt {result.prompt_version} ≠ 1.4.0"
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
