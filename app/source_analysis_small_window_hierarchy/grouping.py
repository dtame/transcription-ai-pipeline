"""
Deterministic regional grouping — source-ordered, contiguous, capacity-aware.

No semantic Python clustering. Group count is not hardcoded.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Sequence

from app.source_analysis.consolidation_input import build_consolidation_input_from_plan
from app.source_analysis.consolidation_models import CONSOLIDATION_SAFE_INPUT_BUDGET_TOKENS
from app.source_analysis.errors import (
    ConsolidationCapacityExceeded,
    HierarchyDepthExceeded,
)
from app.source_analysis.window_models import WindowSemanticResult
from app.source_analysis_hybrid.contracts import WindowInput, WindowPlan
from app.source_analysis_hybrid.planner import apply_tiny_tail, balanced_cuts
from app.source_analysis_small_window_hierarchy.constants import (
    MAX_HIERARCHY_DEPTH,
    REGIONAL_ID_WIDTH,
)

REGIONAL_GROUP_ID_PATTERN = re.compile(rf"^REG\d{{{REGIONAL_ID_WIDTH},}}$")


def format_regional_group_id(index: int) -> str:
    if int(index) < 1:
        raise ValueError(f"index de groupe régional invalide : {index}.")
    return f"REG{int(index):0{REGIONAL_ID_WIDTH}d}"


def _subset_plan(plan: WindowPlan, windows: Sequence[WindowInput]) -> WindowPlan:
    estimates = [window.estimated_input_tokens for window in windows]
    return WindowPlan(
        strategy=plan.strategy,
        planner_version=plan.planner_version,
        transcript_id=plan.transcript_id,
        transcript_sha256=plan.transcript_sha256,
        target_input_tokens=plan.target_input_tokens,
        hard_max_input_tokens=plan.hard_max_input_tokens,
        overlap_policy=plan.overlap_policy,
        prompt_overhead_tokens=plan.prompt_overhead_tokens,
        windows=tuple(windows),
        owned_src_count=sum(window.owned_src_count for window in windows),
        context_src_count=sum(window.context_src_count for window in windows),
        window_count=len(windows),
        estimated_input_tokens_min=min(estimates) if estimates else 0,
        estimated_input_tokens_max=max(estimates) if estimates else 0,
        estimated_input_tokens_mean=plan.estimated_input_tokens_mean,
        estimated_input_tokens_median=plan.estimated_input_tokens_median,
    )


def measure_results_tokens(
    plan: WindowPlan,
    results: Sequence[WindowSemanticResult],
    *,
    guard: int = CONSOLIDATION_SAFE_INPUT_BUDGET_TOKENS,
) -> int:
    built = build_consolidation_input_from_plan(
        plan, results, safe_budget=guard, enforce_budget=False
    )
    return int(built.estimated_tokens)


@dataclass(frozen=True)
class RegionalGroup:
    group_id: str
    window_ids: tuple[str, ...]
    estimated_tokens: int
    within_guard: bool

    def to_dict(self) -> dict:
        return {
            "group_id": self.group_id,
            "window_ids": list(self.window_ids),
            "estimated_tokens": self.estimated_tokens,
            "within_guard": self.within_guard,
            "contiguous_source_order": True,
            "semantic_python_clustering": False,
        }


def group_windows_for_regional(
    plan: WindowPlan,
    results: Sequence[WindowSemanticResult],
    *,
    guard: int = CONSOLIDATION_SAFE_INPUT_BUDGET_TOKENS,
    hierarchy_depth: int = 1,
) -> tuple[RegionalGroup, ...]:
    """
    Capacity-aware contiguous groups. Fail closed if a single WindowResult
    cannot fit the guard. Does not split semantic records.
    """
    if hierarchy_depth > MAX_HIERARCHY_DEPTH - 1:
        raise HierarchyDepthExceeded(
            f"profondeur régionale {hierarchy_depth} > "
            f"{MAX_HIERARCHY_DEPTH - 1} niveau(x) autorisé(s)."
        )
    by_id = {result.window_id: result for result in results}
    ordered_results = [by_id[window.window_id] for window in plan.windows]
    singleton_weights: list[int] = []
    for window, result in zip(plan.windows, ordered_results):
        subset = _subset_plan(plan, (window,))
        tokens = measure_results_tokens(subset, (result,), guard=guard)
        if tokens > guard:
            raise ConsolidationCapacityExceeded(
                f"WindowResult {window.window_id} seul dépasse la garde "
                f"({tokens} > {guard}). Aucun split sémantique local.",
                estimated_tokens=tokens,
                safe_input_budget=guard,
            )
        singleton_weights.append(tokens)

    n = len(plan.windows)
    total = sum(singleton_weights)
    parts = max(1, math.ceil(total / max(1, guard)))
    min_content = max(1, int(0.15 * max(1, total // max(1, parts))))
    while True:
        cuts = balanced_cuts(singleton_weights, parts)
        cuts = apply_tiny_tail(
            cuts,
            singleton_weights,
            min_content=min_content,
            hard_content=guard,
        )
        groups: list[RegionalGroup] = []
        overflow = False
        for index, (start, stop) in enumerate(zip(cuts[:-1], cuts[1:]), start=1):
            windows = plan.windows[start:stop]
            subset_results = ordered_results[start:stop]
            subset = _subset_plan(plan, windows)
            tokens = measure_results_tokens(subset, subset_results, guard=guard)
            if tokens > guard:
                overflow = True
            groups.append(
                RegionalGroup(
                    group_id=format_regional_group_id(index),
                    window_ids=tuple(window.window_id for window in windows),
                    estimated_tokens=tokens,
                    within_guard=tokens <= guard,
                )
            )
        if not overflow:
            return tuple(groups)
        if parts >= n:
            offending = next(group for group in groups if not group.within_guard)
            raise ConsolidationCapacityExceeded(
                f"groupe régional {offending.group_id} dépasse la garde "
                f"({offending.estimated_tokens} > {guard}) même à N=fenêtres.",
                estimated_tokens=offending.estimated_tokens,
                safe_input_budget=guard,
            )
        parts += 1


__all__ = [
    "REGIONAL_GROUP_ID_PATTERN",
    "RegionalGroup",
    "format_regional_group_id",
    "group_windows_for_regional",
    "measure_results_tokens",
]
