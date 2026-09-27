"""
Adaptive consolidation router — local capacity only.

ALL_WINDOWS_READY → build actual direct ConsolidationInput → measure
→ DIRECT_GLOBAL if it fits the existing guard
→ REGIONAL_THEN_GLOBAL otherwise.

Never routes on window count or record count alone.
Never truncates to fit.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from app.source_analysis.consolidation_input import build_consolidation_input_from_plan
from app.source_analysis.consolidation_models import (
    CONSOLIDATION_SAFE_INPUT_BUDGET_TOKENS,
    ConsolidationInput,
)
from app.source_analysis.errors import WindowsIncompleteError
from app.source_analysis.orchestration_models import WindowOrchestrationResult
from app.source_analysis.window_models import WindowSemanticResult
from app.source_analysis_hybrid.contracts import WindowPlan
from app.source_analysis_small_window_hierarchy.constants import (
    CONSOLIDATION_GUARD,
    MAX_HIERARCHY_DEPTH,
    ROUTE_DIRECT_GLOBAL,
    ROUTE_REGIONAL_THEN_GLOBAL,
)
from app.source_analysis_small_window_hierarchy.grouping import (
    RegionalGroup,
    group_windows_for_regional,
    measure_results_tokens,
)


@dataclass(frozen=True)
class RouteDecision:
    route: str
    all_windows_ready: bool
    window_count: int
    ready_windows: int
    guard: int
    direct_estimated_tokens: int | None
    exceeds_guard: bool
    regional_groups: tuple[RegionalGroup, ...]
    regional_estimated_tokens: tuple[int, ...]
    final_global_estimated_tokens: int | None
    inspects_actual_built_input: bool
    python_semantic_merge: bool
    max_hierarchy_depth: int

    def to_dict(self) -> dict:
        return {
            "route": self.route,
            "all_windows_ready": self.all_windows_ready,
            "window_count": self.window_count,
            "ready_windows": self.ready_windows,
            "guard": self.guard,
            "direct_estimated_tokens": self.direct_estimated_tokens,
            "exceeds_guard": self.exceeds_guard,
            "regional_group_count": len(self.regional_groups),
            "regional_groups": [group.to_dict() for group in self.regional_groups],
            "regional_estimated_tokens": list(self.regional_estimated_tokens),
            "final_global_estimated_tokens": self.final_global_estimated_tokens,
            "inspects_actual_built_input": self.inspects_actual_built_input,
            "python_semantic_merge": self.python_semantic_merge,
            "max_hierarchy_depth": self.max_hierarchy_depth,
            "uses_window_count_only": False,
            "uses_record_count_only": False,
            "truncated_to_fit": False,
        }


def assert_all_windows_ready_for_route(
    plan: WindowPlan,
    results: Sequence[WindowSemanticResult],
    *,
    orchestration: WindowOrchestrationResult | None = None,
) -> None:
    ready = len(results)
    if orchestration is not None and not orchestration.all_windows_ready:
        raise WindowsIncompleteError(
            "ALL_WINDOWS_READY refusé — routage consolidation interdit "
            f"({orchestration.ready_windows}/{orchestration.total_windows})."
        )
    if ready != plan.window_count:
        raise WindowsIncompleteError(
            "ALL_WINDOWS_READY refusé — routage consolidation interdit "
            f"({ready}/{plan.window_count})."
        )


def measure_direct_input(
    plan: WindowPlan,
    results: Sequence[WindowSemanticResult],
    *,
    guard: int = CONSOLIDATION_SAFE_INPUT_BUDGET_TOKENS,
) -> tuple[ConsolidationInput, int, bool]:
    """Build the real production ConsolidationInput. Measure, do not truncate."""
    built = build_consolidation_input_from_plan(
        plan, results, safe_budget=guard, enforce_budget=False
    )
    tokens = int(built.estimated_tokens)
    return built, tokens, tokens > guard


def route_consolidation(
    plan: WindowPlan,
    results: Sequence[WindowSemanticResult],
    *,
    orchestration: WindowOrchestrationResult | None = None,
    guard: int = CONSOLIDATION_GUARD,
    group_if_direct: bool = False,
) -> RouteDecision:
    assert_all_windows_ready_for_route(plan, results, orchestration=orchestration)
    _built, tokens, exceeds = measure_direct_input(plan, results, guard=guard)
    if not exceeds:
        groups: tuple[RegionalGroup, ...] = ()
        if group_if_direct:
            groups = group_windows_for_regional(plan, results, guard=guard)
        return RouteDecision(
            route=ROUTE_DIRECT_GLOBAL,
            all_windows_ready=True,
            window_count=plan.window_count,
            ready_windows=len(results),
            guard=int(guard),
            direct_estimated_tokens=tokens,
            exceeds_guard=False,
            regional_groups=groups,
            regional_estimated_tokens=tuple(group.estimated_tokens for group in groups),
            final_global_estimated_tokens=tokens,
            inspects_actual_built_input=True,
            python_semantic_merge=False,
            max_hierarchy_depth=MAX_HIERARCHY_DEPTH,
        )
    groups = group_windows_for_regional(plan, results, guard=guard)
    return RouteDecision(
        route=ROUTE_REGIONAL_THEN_GLOBAL,
        all_windows_ready=True,
        window_count=plan.window_count,
        ready_windows=len(results),
        guard=int(guard),
        direct_estimated_tokens=tokens,
        exceeds_guard=True,
        regional_groups=groups,
        regional_estimated_tokens=tuple(group.estimated_tokens for group in groups),
        final_global_estimated_tokens=None,
        inspects_actual_built_input=True,
        python_semantic_merge=False,
        max_hierarchy_depth=MAX_HIERARCHY_DEPTH,
    )


__all__ = [
    "RouteDecision",
    "assert_all_windows_ready_for_route",
    "measure_direct_input",
    "measure_results_tokens",
    "route_consolidation",
]
