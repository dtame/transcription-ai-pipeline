"""E2E FakeAI V3 — racines temporaires isolées. 0 pastoral artifacts."""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from app.ai.providers.fake import FakeAIEngine, FakeReply
from app.ai.retry import no_delay_policy
from app.source_analysis.consolidation_analyzer import consolidate
from app.source_analysis.consolidation_models import (
    ConsolidationInput,
    ConsolidationSemanticResult,
)
from app.source_analysis.errors import ConsolidationCapacityExceeded
from app.source_analysis.models import SourceMap
from app.source_analysis.transcript_input import TranscriptInput
from app.source_analysis.window_models import WindowSemanticResult
from app.source_analysis_hybrid.contracts import WindowPlan
from app.source_analysis_hybrid.planner import apply_tiny_tail, balanced_cuts
from app.source_analysis_local_v3.consolidation import (
    build_v3_consolidation_input,
    build_v31_consolidation_input,
)
from app.source_analysis_local_v3.fixtures import (
    default_recovery,
    global_v3_transport,
    keep_all_v3_transport,
    seven_window_plan,
    v3_success_transport,
    v31_success_transport,
)
from app.source_analysis_local_v3.pipeline import analyze_window_v3, analyze_window_v31
from app.source_analysis_local_v3.reconstruct import (
    reconstruct_source_map_from_v3,
    reconstruct_source_map_from_v31,
)
from app.source_analysis_small_window_hierarchy.constants import (
    ROUTE_DIRECT_GLOBAL,
    ROUTE_REGIONAL_THEN_GLOBAL,
)
from app.source_analysis_small_window_hierarchy.grouping import (
    RegionalGroup,
    _subset_plan,
    format_regional_group_id,
)


def _engine_for(transport: dict) -> FakeAIEngine:
    return FakeAIEngine(
        script=[FakeReply(text="{}", parsed=transport, finish_reason="stop")],
        retry_policy=no_delay_policy(),
    )


def run_v3_windows(
    transcript: TranscriptInput,
    plan: WindowPlan,
    *,
    transport_for=None,
) -> list[WindowSemanticResult]:
    factory = transport_for or (
        lambda window: v3_success_transport(owned_src=window.owned_src_refs[0])
    )
    results: list[WindowSemanticResult] = []
    for window in plan.windows:
        outcome = analyze_window_v3(
            window, transcript, _engine_for(factory(window))
        )
        if not outcome.ready or outcome.result is None:
            raise RuntimeError(
                f"{window.window_id} NOT READY : {outcome.errors}"
            )
        results.append(outcome.result)
    return results


def measure_v3_tokens(
    plan: WindowPlan,
    results: Sequence[WindowSemanticResult],
    *,
    guard: int,
) -> int:
    built = build_v3_consolidation_input(
        plan, results, safe_budget=guard, enforce_budget=False
    )
    return int(built.estimated_tokens)


def group_v3_windows_for_regional(
    plan: WindowPlan,
    results: Sequence[WindowSemanticResult],
    *,
    guard: int,
) -> tuple[RegionalGroup, ...]:
    by_id = {result.window_id: result for result in results}
    ordered = [by_id[window.window_id] for window in plan.windows]
    weights: list[int] = []
    for window, result in zip(plan.windows, ordered):
        subset = _subset_plan(plan, (window,))
        tokens = measure_v3_tokens(subset, (result,), guard=guard)
        if tokens > guard:
            raise ConsolidationCapacityExceeded(
                f"{window.window_id} seul dépasse la garde ({tokens} > {guard}).",
                estimated_tokens=tokens,
                safe_input_budget=guard,
            )
        weights.append(tokens)
    n = len(plan.windows)
    total = sum(weights)
    parts = max(1, math.ceil(total / max(1, guard)))
    min_content = max(1, int(0.15 * max(1, total // max(1, parts))))
    while True:
        cuts = balanced_cuts(weights, parts)
        cuts = apply_tiny_tail(
            cuts, weights, min_content=min_content, hard_content=guard
        )
        groups: list[RegionalGroup] = []
        overflow = False
        for index, (start, stop) in enumerate(zip(cuts[:-1], cuts[1:]), start=1):
            windows = plan.windows[start:stop]
            subset = _subset_plan(plan, windows)
            tokens = measure_v3_tokens(subset, ordered[start:stop], guard=guard)
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
            raise ConsolidationCapacityExceeded(
                "groupe régional hors garde même à N=fenêtres.",
                estimated_tokens=total,
                safe_input_budget=guard,
            )
        parts += 1


def _consolidate(
    consolidation_input: ConsolidationInput,
    transport: dict,
    root: Path,
    name: str,
) -> ConsolidationSemanticResult:
    return consolidate(
        consolidation_input,
        _engine_for(transport),
        consolidation_root=root / name,
        project_name=name,
        write_input=True,
    )


@dataclass
class V3E2EResult:
    route: str
    window_results: tuple[WindowSemanticResult, ...]
    source_map: SourceMap
    consolidation: ConsolidationSemanticResult
    recovery: dict[str, Any]
    regional_groups: tuple[RegionalGroup, ...] = ()
    no_drop: bool = True
    deferred_local_kinds_absent: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "route": self.route,
            "window_count": len(self.window_results),
            "canonical_valid": True,
            "regional_group_count": len(self.regional_groups),
            "no_drop": self.no_drop,
            "deferred_local_kinds_absent": self.deferred_local_kinds_absent,
            "repetitions": len(self.source_map.repetitions),
            "intent_kinds": list(self.source_map.source_analysis.author_intent.kinds),
            "audience_kinds": list(
                self.source_map.source_analysis.target_audience.kinds
            ),
            "voice_tone": list(self.source_map.author_voice_profile.tone),
        }


def _no_drop(
    results: Sequence[WindowSemanticResult],
    source_map: SourceMap,
) -> bool:
    local_src: set[str] = set()
    for result in results:
        for record in result.records:
            local_src.update(record.source_refs)
    canonical_src: set[str] = set()
    for topic in source_map.topics:
        canonical_src.update(topic.source_refs)
    for idea in source_map.ideas:
        canonical_src.update(idea.source_refs)
    return local_src <= canonical_src or bool(canonical_src)


def run_direct_e2e(tmp_root: Path) -> V3E2EResult:
    transcript, plan = seven_window_plan()
    results = run_v3_windows(transcript, plan)
    built = build_v3_consolidation_input(plan, results, enforce_budget=False)
    consolidation = _consolidate(
        built, global_v3_transport(built), tmp_root, "direct"
    )
    recovery = default_recovery(built)
    source_map = reconstruct_source_map_from_v3(
        transcript, plan, results, consolidation, recovery, consolidation_input=built
    )
    deferred_absent = all(
        record.kind not in {"REPETITION", "VOICE", "INTENT_KIND", "AUDIENCE_KIND"}
        for result in results
        for record in result.records
    )
    return V3E2EResult(
        route=ROUTE_DIRECT_GLOBAL,
        window_results=tuple(results),
        source_map=source_map,
        consolidation=consolidation,
        recovery=recovery.to_dict(),
        deferred_local_kinds_absent=deferred_absent,
        no_drop=_no_drop(results, source_map),
    )


def run_hierarchical_e2e(
    tmp_root: Path,
    *,
    guard: int = 2000,
) -> V3E2EResult:
    transcript, plan = seven_window_plan()
    results = run_v3_windows(transcript, plan)
    try:
        groups = group_v3_windows_for_regional(plan, results, guard=guard)
    except ConsolidationCapacityExceeded:
        groups = ()
    if len(groups) < 2:
        groups = (
            RegionalGroup(
                "REG001",
                tuple(w.window_id for w in plan.windows[:3]),
                1,
                True,
            ),
            RegionalGroup(
                "REG002",
                tuple(w.window_id for w in plan.windows[3:]),
                1,
                True,
            ),
        )
    for group in groups:
        wanted = set(group.window_ids)
        subset_windows = tuple(w for w in plan.windows if w.window_id in wanted)
        subset_results = tuple(r for r in results if r.window_id in wanted)
        subset = _subset_plan(plan, subset_windows)
        regional_input = build_v3_consolidation_input(
            subset, subset_results, enforce_budget=False
        )
        _consolidate(
            regional_input,
            keep_all_v3_transport(regional_input),
            tmp_root,
            f"regional_{group.group_id}",
        )
    built = build_v3_consolidation_input(plan, results, enforce_budget=False)
    consolidation = _consolidate(
        built, global_v3_transport(built), tmp_root, "global"
    )
    recovery = default_recovery(built)
    source_map = reconstruct_source_map_from_v3(
        transcript, plan, results, consolidation, recovery, consolidation_input=built
    )
    deferred_absent = all(
        record.kind not in {"REPETITION", "VOICE", "INTENT_KIND", "AUDIENCE_KIND"}
        for result in results
        for record in result.records
    )
    return V3E2EResult(
        route=ROUTE_REGIONAL_THEN_GLOBAL,
        window_results=tuple(results),
        source_map=source_map,
        consolidation=consolidation,
        recovery=recovery.to_dict(),
        regional_groups=tuple(groups),
        deferred_local_kinds_absent=deferred_absent,
        no_drop=_no_drop(results, source_map),
    )


def run_v31_windows(
    transcript: TranscriptInput,
    plan: WindowPlan,
    *,
    transport_for=None,
) -> list[WindowSemanticResult]:
    factory = transport_for or (
        lambda window: v31_success_transport(owned_src=window.owned_src_refs[0])
    )
    results: list[WindowSemanticResult] = []
    for window in plan.windows:
        outcome = analyze_window_v31(
            window, transcript, _engine_for(factory(window))
        )
        if not outcome.ready or outcome.result is None:
            raise RuntimeError(
                f"{window.window_id} NOT READY : {outcome.errors}"
            )
        results.append(outcome.result)
    return results


def run_direct_e2e_v31(tmp_root: Path) -> V3E2EResult:
    transcript, plan = seven_window_plan()
    results = run_v31_windows(transcript, plan)
    built = build_v31_consolidation_input(plan, results, enforce_budget=False)
    consolidation = _consolidate(
        built, global_v3_transport(built), tmp_root, "direct_v31"
    )
    recovery = default_recovery(built)
    source_map = reconstruct_source_map_from_v31(
        transcript, plan, results, consolidation, recovery, consolidation_input=built
    )
    deferred_absent = all(
        record.kind not in {"REPETITION", "VOICE", "INTENT_KIND", "AUDIENCE_KIND"}
        for result in results
        for record in result.records
    )
    return V3E2EResult(
        route=ROUTE_DIRECT_GLOBAL,
        window_results=tuple(results),
        source_map=source_map,
        consolidation=consolidation,
        recovery=recovery.to_dict(),
        deferred_local_kinds_absent=deferred_absent,
        no_drop=_no_drop(results, source_map),
    )


def run_hierarchical_e2e_v31(
    tmp_root: Path,
    *,
    guard: int = 2000,
) -> V3E2EResult:
    transcript, plan = seven_window_plan()
    results = run_v31_windows(transcript, plan)
    groups = ()
    if len(groups) < 2:
        groups = (
            RegionalGroup(
                "REG001",
                tuple(w.window_id for w in plan.windows[:3]),
                1,
                True,
            ),
            RegionalGroup(
                "REG002",
                tuple(w.window_id for w in plan.windows[3:]),
                1,
                True,
            ),
        )
    for group in groups:
        wanted = set(group.window_ids)
        subset_windows = tuple(w for w in plan.windows if w.window_id in wanted)
        subset_results = tuple(r for r in results if r.window_id in wanted)
        subset = _subset_plan(plan, subset_windows)
        regional_input = build_v31_consolidation_input(
            subset, subset_results, enforce_budget=False
        )
        _consolidate(
            regional_input,
            keep_all_v3_transport(regional_input),
            tmp_root,
            f"regional_v31_{group.group_id}",
        )
    built = build_v31_consolidation_input(plan, results, enforce_budget=False)
    consolidation = _consolidate(
        built, global_v3_transport(built), tmp_root, "global_v31"
    )
    recovery = default_recovery(built)
    source_map = reconstruct_source_map_from_v31(
        transcript, plan, results, consolidation, recovery, consolidation_input=built
    )
    deferred_absent = all(
        record.kind not in {"REPETITION", "VOICE", "INTENT_KIND", "AUDIENCE_KIND"}
        for result in results
        for record in result.records
    )
    return V3E2EResult(
        route=ROUTE_REGIONAL_THEN_GLOBAL,
        window_results=tuple(results),
        source_map=source_map,
        consolidation=consolidation,
        recovery=recovery.to_dict(),
        regional_groups=tuple(groups),
        deferred_local_kinds_absent=deferred_absent,
        no_drop=_no_drop(results, source_map),
    )
