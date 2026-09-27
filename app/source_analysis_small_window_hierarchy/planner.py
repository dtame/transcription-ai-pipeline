"""
Candidate planner window-planner-v2.1-small.

Reuses WindowPlannerV2 algorithm. Does NOT change production defaults.
Overhead and remesure use actual window-analysis-1.1 request construction.
N is not hardcoded.
"""

from __future__ import annotations

from dataclasses import replace
from statistics import mean, median
from typing import Sequence

from app.source_analysis.errors import (
    SmallWindowPlanningError,
    SourceAnalysisEmptyTranscript,
    SourceAnalysisWindowPlanError,
    SourceAnalysisWindowTooLarge,
)
from app.source_analysis.transcript_input import TranscriptInput
from app.source_analysis.window_prompt import (
    WINDOW_ANALYSIS_PROMPT_VERSION,
    build_window_system_prompt,
    build_window_user_prompt,
    estimate_window_request_tokens,
)
from app.source_analysis_hybrid.config import WindowPlannerConfig
from app.source_analysis_hybrid.constants import ESTIMATION_MODEL, OVERLAP_POLICY
from app.source_analysis_hybrid.contracts import WindowInput, WindowPlan
from app.source_analysis_hybrid.materialize import WindowContent
from app.source_analysis_hybrid.planner import plan_windows_v2
from app.source_analysis_hybrid.tokens import content_weights_for
from app.source_analysis_hybrid.validation import validate_window_plan
from app.ai.estimation import estimate_tokens
from app.source_analysis_small_window_hierarchy.constants import (
    CANDIDATE_HARD_MAX_INPUT_TOKENS,
    CANDIDATE_PLANNER_VERSION,
    CANDIDATE_TARGET_INPUT_TOKENS,
)


def small_window_planner_config() -> WindowPlannerConfig:
    """Explicit candidate policy. Never the production default."""
    return WindowPlannerConfig(
        version=CANDIDATE_PLANNER_VERSION,
        target_input_tokens=CANDIDATE_TARGET_INPUT_TOKENS,
        hard_max_input_tokens=CANDIDATE_HARD_MAX_INPUT_TOKENS,
        overlap_policy=OVERLAP_POLICY,
    )


def _empty_window_shell(transcript: TranscriptInput) -> WindowInput:
    return WindowInput(
        window_id="WIN001",
        transcript_id=transcript.transcript_id,
        planner_version=CANDIDATE_PLANNER_VERSION,
        owned_src_refs=(),
        context_src_refs=(),
        first_owned_src_ref="",
        last_owned_src_ref="",
        owned_src_count=0,
        estimated_input_tokens=0,
        owned_src_ids_sha256="",
        owned_content_sha256="",
        context_src_ids_sha256="",
        context_content_sha256="",
        input_hash="",
        source_order_start=0,
        source_order_stop=0,
        word_count=0,
        content_tokens=0,
        planner_estimate_tokens=0,
    )


def estimate_window_11_overhead(
    transcript: TranscriptInput,
    *,
    model: str = ESTIMATION_MODEL,
    prompt_version: str = WINDOW_ANALYSIS_PROMPT_VERSION,
) -> int:
    """Actual window-analysis-1.1 system + empty-user framing. Not 3609."""
    dummy = _empty_window_shell(transcript)
    empty = WindowContent(window_id="WIN001", owned=(), context=())
    system = build_window_system_prompt(
        transcript.primary_language, version=prompt_version
    )
    user = build_window_user_prompt(
        transcript, dummy, empty, version=prompt_version
    )
    return int(estimate_tokens("\n".join([system, user]), model=model).tokens)


def remesure_window_11(
    transcript: TranscriptInput,
    window: WindowInput,
    *,
    model: str = ESTIMATION_MODEL,
    prompt_version: str = WINDOW_ANALYSIS_PROMPT_VERSION,
) -> int:
    estimate = estimate_window_request_tokens(
        transcript,
        window,
        model=model,
        version=prompt_version,
    )
    return int(estimate["total_tokens"])


def _token_stats(values: Sequence[int]) -> tuple[int, int, float, float]:
    if not values:
        return 0, 0, 0.0, 0.0
    return min(values), max(values), float(mean(values)), float(median(values))


def _apply_11_remeasure(
    transcript: TranscriptInput,
    plan: WindowPlan,
    config: WindowPlannerConfig,
    *,
    model: str,
    prompt_version: str,
) -> WindowPlan:
    remesured: list[WindowInput] = []
    for window in plan.windows:
        measured = remesure_window_11(
            transcript, window, model=model, prompt_version=prompt_version
        )
        if measured > config.hard_max_input_tokens:
            raise SmallWindowPlanningError(
                f"HARD_MAX_VIOLATION: {window.window_id} "
                f"remeasured_1_1={measured} hard_max={config.hard_max_input_tokens}"
            )
        remesured.append(replace(window, estimated_input_tokens=measured))
    token_values = [window.estimated_input_tokens for window in remesured]
    lo, hi, avg, mid = _token_stats(token_values)
    updated = WindowPlan(
        strategy=plan.strategy,
        planner_version=plan.planner_version,
        transcript_id=plan.transcript_id,
        transcript_sha256=plan.transcript_sha256,
        target_input_tokens=plan.target_input_tokens,
        hard_max_input_tokens=plan.hard_max_input_tokens,
        overlap_policy=plan.overlap_policy,
        prompt_overhead_tokens=plan.prompt_overhead_tokens,
        windows=tuple(remesured),
        owned_src_count=plan.owned_src_count,
        context_src_count=plan.context_src_count,
        window_count=len(remesured),
        estimated_input_tokens_min=lo,
        estimated_input_tokens_max=hi,
        estimated_input_tokens_mean=avg,
        estimated_input_tokens_median=mid,
    )
    validate_window_plan(updated, transcript, config)
    return updated


def plan_windows_v21_small(
    transcript: TranscriptInput,
    *,
    config: WindowPlannerConfig | None = None,
    model: str = ESTIMATION_MODEL,
    content_weights: Sequence[int] | None = None,
    overhead: int | None = None,
    prompt_version: str = WINDOW_ANALYSIS_PROMPT_VERSION,
) -> WindowPlan:
    """
    Candidate plan. Uses WindowPlannerV2 cuts + tiny-tail.

    Overhead and remesure are window-analysis-1.1. Window count is not
    hardcoded: it emerges from corpus + target/hard max + algorithm.
    """
    chosen = config or small_window_planner_config()
    if chosen.version != CANDIDATE_PLANNER_VERSION:
        raise SmallWindowPlanningError(
            f"planner candidat exige {CANDIDATE_PLANNER_VERSION}, "
            f"reçu {chosen.version!r}."
        )
    try:
        if overhead is None:
            overhead = estimate_window_11_overhead(
                transcript, model=model, prompt_version=prompt_version
            )
        if chosen.target_input_tokens <= int(overhead):
            raise SmallWindowPlanningError(
                f"target ({chosen.target_input_tokens}) <= overhead 1.1 "
                f"({overhead})."
            )
        if content_weights is None:
            content_weights = content_weights_for(transcript, model=model)
        plan = plan_windows_v2(
            transcript,
            config=chosen,
            model=model,
            content_weights=content_weights,
            overhead=int(overhead),
            remeasure=False,
        )
    except SourceAnalysisEmptyTranscript:
        raise
    except SourceAnalysisWindowTooLarge as exc:
        raise SmallWindowPlanningError(str(exc)) from exc
    except SourceAnalysisWindowPlanError as exc:
        if isinstance(exc, SmallWindowPlanningError):
            raise
        raise SmallWindowPlanningError(str(exc)) from exc
    return _apply_11_remeasure(
        transcript, plan, chosen, model=model, prompt_version=prompt_version
    )


def plan_coverage(transcript: TranscriptInput, plan: WindowPlan) -> dict:
    present = list(transcript.src_ids())
    present_set = set(present)
    owned: list[str] = []
    for window in plan.windows:
        owned.extend(window.owned_src_refs)
    counts: dict[str, int] = {}
    for src in owned:
        counts[src] = counts.get(src, 0) + 1
    missing = [src for src in present if src not in counts]
    extras = sorted(set(owned) - present_set)
    duplicates = sorted(src for src, count in counts.items() if count > 1)
    ordered = True
    cursor = 0
    for window in plan.windows:
        slice_ids = present[cursor : cursor + window.owned_src_count]
        if tuple(slice_ids) != window.owned_src_refs:
            ordered = False
            break
        cursor += window.owned_src_count
    if cursor != len(present):
        ordered = False
    context_empty = all(not window.context_src_refs for window in plan.windows)
    return {
        "present_src_count": len(present),
        "owned_occurrences": len(owned),
        "union_owned": len(set(owned)),
        "missing_src": missing,
        "duplicate_owned_src": duplicates,
        "extra_src": extras,
        "coverage_complete": not missing and not extras,
        "no_owned_overlap": not duplicates,
        "source_order_preserved": ordered,
        "sparse_ids_preserved": extras == [] and all(src in present_set for src in owned),
        "every_present_src_owned_once": not missing and not duplicates and not extras,
        "context_src_empty": context_empty,
        "owned_coverage": f"{len(present) - len(missing)}/{len(present)}",
    }


def window_plan_metrics(plan: WindowPlan) -> list[dict]:
    """Per-window metrics required by the phase report."""
    overhead = int(plan.prompt_overhead_tokens)
    target = int(plan.target_input_tokens)
    rows: list[dict] = []
    for window in plan.windows:
        local = int(window.estimated_input_tokens)
        rows.append(
            {
                "window_id": window.window_id,
                "first_present_src": window.first_owned_src_ref,
                "last_present_src": window.last_owned_src_ref,
                "owned_src_count": window.owned_src_count,
                "word_count": window.word_count,
                "local_request_estimate": local,
                "distance_from_target": local - target,
                "prompt_overhead_tokens": overhead,
                "prompt_overhead_pct": (
                    round(100.0 * overhead / local, 4) if local else 0.0
                ),
                "content_tokens": window.content_tokens,
                "planner_estimate_tokens": window.planner_estimate_tokens,
                "context_src_refs": list(window.context_src_refs),
                "input_hash": window.input_hash,
                "owned_content_sha256": window.owned_content_sha256,
            }
        )
    return rows


__all__ = [
    "estimate_window_11_overhead",
    "plan_windows_v21_small",
    "remesure_window_11",
    "small_window_planner_config",
    "window_plan_metrics",
]
