"""
Simulations hypothétiques WindowPlannerV2 — 1.1, SRC, estimateur local.

Ne change pas la config production. Plans uniquement.
"""

from __future__ import annotations

from statistics import mean
from typing import Any, Sequence

from app.ai.estimation import estimate_tokens
from app.source_analysis.transcript_input import TranscriptInput
from app.source_analysis.window_prompt import (
    WINDOW_ANALYSIS_PROMPT_VERSION,
    build_window_system_prompt,
    build_window_user_prompt,
    estimate_window_request_tokens,
)
from app.source_analysis_execution_strategy.windows import load_clean_transcript
from app.source_analysis_hybrid.config import WindowPlannerConfig
from app.source_analysis_hybrid.constants import (
    ESTIMATION_MODEL,
    HARD_MAX_INPUT_TOKENS,
    OVERLAP_POLICY,
    PLANNER_VERSION,
    TARGET_INPUT_TOKENS,
)
from app.source_analysis_hybrid.contracts import WindowInput
from app.source_analysis_hybrid.materialize import WindowContent
from app.source_analysis_hybrid.planner import (
    min_useful_content_tokens,
    plan_windows_v2,
)
from app.source_analysis_hybrid.tokens import content_weights_for
from app.source_analysis_hybrid.validation import validate_window_plan
from app.source_analysis_post_canary_architecture.constants import (
    BALANCE_MIN_RATIO,
    CANDIDATE_PAIRS,
    CURRENT_HARD_MAX,
    CURRENT_TARGET,
    PHASE,
    SCHEMA_VERSION,
)


def estimate_window_11_overhead(
    transcript: TranscriptInput,
    *,
    model: str = ESTIMATION_MODEL,
) -> int:
    """Overhead window-analysis-1.1 : system + user sans SRC owned."""
    dummy = WindowInput(
        window_id="WIN001",
        transcript_id=transcript.transcript_id,
        planner_version=PLANNER_VERSION,
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
    empty = WindowContent(window_id="WIN001", owned=(), context=())
    system = build_window_system_prompt(
        transcript.primary_language, version=WINDOW_ANALYSIS_PROMPT_VERSION
    )
    user = build_window_user_prompt(
        transcript, dummy, empty, version=WINDOW_ANALYSIS_PROMPT_VERSION
    )
    return int(estimate_tokens("\n".join([system, user]), model=model).tokens)


def remesure_window_11(
    transcript: TranscriptInput,
    window: WindowInput,
    *,
    model: str = ESTIMATION_MODEL,
) -> int:
    estimate = estimate_window_request_tokens(
        transcript,
        window,
        model=model,
        version=WINDOW_ANALYSIS_PROMPT_VERSION,
    )
    return int(estimate["total_tokens"])


def _stats(values: Sequence[int]) -> dict[str, float | int]:
    if not values:
        return {"min": 0, "max": 0, "mean": 0.0}
    return {
        "min": int(min(values)),
        "max": int(max(values)),
        "mean": float(mean(values)),
    }


def _coverage(transcript: TranscriptInput, windows: Sequence[WindowInput]) -> dict[str, Any]:
    present = list(transcript.src_ids())
    present_set = set(present)
    owned_seen: list[str] = []
    for window in windows:
        owned_seen.extend(window.owned_src_refs)
    counts: dict[str, int] = {}
    for src in owned_seen:
        counts[src] = counts.get(src, 0) + 1
    missing = [src for src in present if src not in counts]
    extras = sorted(set(owned_seen) - present_set)
    duplicates = sorted(src for src, count in counts.items() if count > 1)
    ordered = True
    cursor = 0
    for window in windows:
        slice_ids = present[cursor : cursor + window.owned_src_count]
        if tuple(slice_ids) != window.owned_src_refs:
            ordered = False
            break
        cursor += window.owned_src_count
    if cursor != len(present):
        ordered = False
    return {
        "present_src_count": len(present),
        "owned_occurrences": len(owned_seen),
        "union_owned": len(set(owned_seen)),
        "missing_src": missing,
        "duplicate_owned_src": duplicates,
        "extra_src": extras,
        "coverage_complete": not missing and not extras,
        "no_owned_overlap": not duplicates,
        "source_order_preserved": ordered,
        "sparse_ids_preserved": extras == [] and all(src in present_set for src in owned_seen),
        "every_present_src_owned_once": not missing and not duplicates and not extras,
    }


def summarize_plan(
    transcript: TranscriptInput,
    plan,
    *,
    target: int,
    hard_max: int,
    overhead_11: int,
    remesured: Sequence[int],
    production: bool,
) -> dict[str, Any]:
    windows = list(plan.windows)
    src_counts = [window.owned_src_count for window in windows]
    words = [window.word_count for window in windows]
    local = list(remesured)
    coverage = _coverage(transcript, windows)
    src_stats = _stats(src_counts)
    word_stats = _stats(words)
    token_stats = _stats(local)
    min_content = min_useful_content_tokens(target, overhead_11)
    last_content = int(windows[-1].content_tokens) if windows else 0
    tiny_stub = bool(windows) and last_content < min_content
    min_local = int(token_stats["min"])
    max_local = int(token_stats["max"])
    token_balance = (min_local / max_local) if max_local else 0.0
    src_balance = (
        int(src_stats["min"]) / int(src_stats["max"]) if src_stats["max"] else 0.0
    )
    word_balance = (
        int(word_stats["min"]) / int(word_stats["max"]) if word_stats["max"] else 0.0
    )
    balance_metric = min(token_balance, src_balance, word_balance)
    stub_ratio = (
        float(local[-1]) / float(token_stats["mean"]) if token_stats["mean"] else 0.0
    )
    mean_local = float(token_stats["mean"])
    overhead_pct = (100.0 * overhead_11 / mean_local) if mean_local else 0.0
    hard_violations = [
        windows[index].window_id
        for index, tokens in enumerate(local)
        if tokens > hard_max
    ]
    durations = []
    for window in windows:
        owned = transcript.segments[window.source_order_start : window.source_order_stop]
        durations.append(
            sum(max(0.0, float(segment.end) - float(segment.start)) for segment in owned)
        )
    return {
        "label": f"{target}/{hard_max}",
        "target": target,
        "hard_max": hard_max,
        "production_defaults": production,
        "planner_version_used": plan.planner_version,
        "algorithm": "WindowPlannerV2",
        "prompt_version": WINDOW_ANALYSIS_PROMPT_VERSION,
        "granularity_policy": "window-granularity-1.0",
        "overlap_policy": plan.overlap_policy,
        "context_src_refs_empty": all(not window.context_src_refs for window in windows),
        "prompt_overhead_tokens": overhead_11,
        "prompt_overhead_pct_of_mean_request": round(overhead_pct, 4),
        "repeated_overhead_tokens": overhead_11 * len(windows),
        "window_count": len(windows),
        "provider_calls_required": len(windows),
        "owned_src": src_stats,
        "words": word_stats,
        "local_estimated_request": token_stats,
        "duration_span_seconds": _stats([int(value) for value in durations]),
        "coverage": coverage,
        "missing_src": coverage["missing_src"],
        "duplicates": coverage["duplicate_owned_src"],
        "tiny_stub": tiny_stub,
        "stub_ratio": round(stub_ratio, 4),
        "min_useful_content_tokens": min_content,
        "last_window_content_tokens": last_content,
        "balance_metric": round(balance_metric, 4),
        "balance_definition": (
            "min(min/max local request, min/max owned SRC, min/max words)"
        ),
        "balanced": balance_metric >= BALANCE_MIN_RATIO and not tiny_stub,
        "hard_max_violations_after_1_1_remeasure": hard_violations,
        "within_hard_max": not hard_violations,
        "target_gt_overhead": target > overhead_11,
        "margin_tokens": hard_max - target,
        "windows": [
            {
                "window_id": window.window_id,
                "owned_src_count": window.owned_src_count,
                "word_count": window.word_count,
                "first_owned_src_ref": window.first_owned_src_ref,
                "last_owned_src_ref": window.last_owned_src_ref,
                "content_tokens": window.content_tokens,
                "planner_estimate_tokens": window.planner_estimate_tokens,
                "local_estimated_request_1_1": local[index],
                "context_src_refs": list(window.context_src_refs),
                "duration_span_seconds": durations[index],
            }
            for index, window in enumerate(windows)
        ],
    }


def simulate_pair(
    transcript: TranscriptInput,
    *,
    target: int,
    hard_max: int,
    overhead_11: int,
    content_weights: Sequence[int],
    production: bool = False,
) -> dict[str, Any]:
    if target <= overhead_11:
        return {
            "label": f"{target}/{hard_max}",
            "target": target,
            "hard_max": hard_max,
            "feasible": False,
            "infeasible_reason": "target <= window-analysis-1.1 prompt overhead",
            "prompt_overhead_tokens": overhead_11,
            "window_count": 0,
            "provider_calls_required": 0,
            "tiny_stub": False,
            "balanced": False,
            "coverage": {
                "coverage_complete": False,
                "no_owned_overlap": False,
                "every_present_src_owned_once": False,
            },
        }
    config = WindowPlannerConfig(
        version=PLANNER_VERSION,
        target_input_tokens=target,
        hard_max_input_tokens=hard_max,
        overlap_policy=OVERLAP_POLICY,
    )
    plan = plan_windows_v2(
        transcript,
        config=config,
        content_weights=content_weights,
        overhead=overhead_11,
        remeasure=False,
    )
    validate_window_plan(plan, transcript, config)
    remesured = [remesure_window_11(transcript, window) for window in plan.windows]
    summary = summarize_plan(
        transcript,
        plan,
        target=target,
        hard_max=hard_max,
        overhead_11=overhead_11,
        remesured=remesured,
        production=production,
    )
    summary["feasible"] = True
    summary["plan"] = plan
    return summary


def audio_source_boundaries(transcript: TranscriptInput) -> dict[str, Any]:
    groups: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for segment in transcript.segments:
        key = segment.source_id
        if key not in groups:
            groups[key] = {
                "source_id": key,
                "src_count": 0,
                "word_count": 0,
                "first_src": segment.src_id,
                "last_src": segment.src_id,
                "start": float(segment.start),
                "end": float(segment.end),
            }
            order.append(key)
        bucket = groups[key]
        bucket["src_count"] += 1
        bucket["word_count"] += segment.word_count
        bucket["last_src"] = segment.src_id
        bucket["end"] = float(segment.end)
    files = [groups[key] for key in order]
    return {
        "audio_file_count": len(files),
        "files": files,
        "useful_as_technical_constraint": len(files) >= 2,
        "editorial_chapters": False,
        "principle": (
            "technical segmentation must NEVER define editorial chapters"
        ),
        "assumption_each_file_is_chapter": False,
    }


def simulate_current_production(
    transcript: TranscriptInput,
    *,
    overhead_11: int,
) -> dict[str, Any]:
    """Plan production 50k/60k inchangé, puis re-mesure 1.1 des mêmes fenêtres."""
    plan = plan_windows_v2(transcript)
    remesured = [remesure_window_11(transcript, window) for window in plan.windows]
    summary = summarize_plan(
        transcript,
        plan,
        target=TARGET_INPUT_TOKENS,
        hard_max=HARD_MAX_INPUT_TOKENS,
        overhead_11=overhead_11,
        remesured=remesured,
        production=True,
    )
    summary["feasible"] = True
    summary["production_planner_target"] = TARGET_INPUT_TOKENS
    summary["production_planner_hard_max"] = HARD_MAX_INPUT_TOKENS
    summary["production_planner_estimate_tokens"] = [
        window.estimated_input_tokens for window in plan.windows
    ]
    summary["plan"] = plan
    return summary


def run_window_simulations(
    project_name: str,
    *,
    sortie_dir=None,
    pairs: Sequence[tuple[int, int]] = CANDIDATE_PAIRS,
) -> dict[str, Any]:
    transcript = load_clean_transcript(project_name, sortie_dir=sortie_dir)
    overhead_11 = estimate_window_11_overhead(transcript)
    weights = content_weights_for(transcript)
    current = simulate_current_production(transcript, overhead_11=overhead_11)
    candidates: list[dict[str, Any]] = []
    for target, hard_max in pairs:
        row = simulate_pair(
            transcript,
            target=target,
            hard_max=hard_max,
            overhead_11=overhead_11,
            content_weights=weights,
            production=target == CURRENT_TARGET and hard_max == CURRENT_HARD_MAX,
        )
        candidates.append(row)
    audio = audio_source_boundaries(transcript)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": "OFFLINE_WINDOW_SIZE_SIMULATION",
        "real_provider_calls": 0,
        "prompt_version": WINDOW_ANALYSIS_PROMPT_VERSION,
        "granularity_policy": "window-granularity-1.0",
        "production_planner_unchanged": True,
        "production_target": TARGET_INPUT_TOKENS,
        "production_hard_max": HARD_MAX_INPUT_TOKENS,
        "transcript": {
            "transcript_id": transcript.transcript_id,
            "segment_count": transcript.segment_count,
            "word_count": transcript.word_count,
            "duration_seconds": transcript.duration_seconds,
            "content_sha256": transcript.content_sha256,
            "first_src": transcript.src_ids()[0] if transcript.segments else "",
            "last_src": transcript.src_ids()[-1] if transcript.segments else "",
            "sparse_ids_preserved": True,
        },
        "prompt_overhead_1_1": overhead_11,
        "estimator_model": ESTIMATION_MODEL,
        "current_three_window": _public_plan(current),
        "candidates": [_public_plan(row) for row in candidates],
        "audio_sources": audio,
        "plans": {"current": current, "candidates": candidates},
        "transcript_obj": transcript,
    }
    return payload


def _public_plan(row: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in row.items() if key != "plan"}
