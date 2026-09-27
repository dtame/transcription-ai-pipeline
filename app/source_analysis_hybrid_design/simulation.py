"""
Simulation offline de WindowPlannerV2 sur le transcript CLEAN.

Aucun appel provider. Le transcript n'est pas modifié.
"""

from __future__ import annotations

from statistics import mean, median
from typing import Any, Sequence

from app.file_utils import content_hash
from app.source_analysis.context_strategy import (
    DEFAULT_WINDOW_OVERLAP_SEGMENTS,
    plan_windows,
)
from app.source_analysis.transcript_input import TranscriptInput
from app.source_analysis_execution_strategy.windows import (
    detect_oversized_srcs,
    estimate_prompt_tokens,
    load_clean_transcript,
)
from app.source_analysis_hybrid_design.boundaries import audit_boundary_signals
from app.source_analysis_hybrid_design.constants import (
    CANDIDATE_HARD_MAX_INPUT_TOKENS,
    CANDIDATE_TARGET_INPUT_TOKENS,
    ESTIMATION_MODEL,
    HARD_MAX_INPUT_TOKENS,
    OVERLAP_POLICY,
    PHASE,
    PLANNER_NAME,
    PLANNER_VERSION,
    SCHEMA_VERSION,
    TARGET_INPUT_TOKENS,
)
from app.source_analysis_hybrid_design.planner_v2 import (
    PlannedWindow,
    estimate_prompt_overhead,
    estimate_segment_content_tokens,
    plan_windows_v2,
    planner_v2_pseudocode,
)


def _stats(values: Sequence[int]) -> dict[str, float | int]:
    if not values:
        return {"min": 0, "max": 0, "mean": 0.0, "median": 0.0}
    return {
        "min": min(values),
        "max": max(values),
        "mean": float(mean(values)),
        "median": float(median(values)),
    }


def _window_row(window: PlannedWindow) -> dict[str, Any]:
    return {
        "window_id": window.window_id,
        "index": window.index,
        "first_owned_src": window.first_owned_src,
        "last_owned_src": window.last_owned_src,
        "owned_src_count": window.owned_src_count,
        "context_src_count": len(window.context_src_ids),
        "word_count": window.word_count,
        "content_tokens": window.content_tokens,
        "planner_estimate_tokens": window.planner_estimate_tokens,
        "estimated_input_tokens": window.estimated_input_tokens,
        "owned_src_ids_sha256": window.owned_src_ids_sha256,
        "owned_content_sha256": window.owned_content_sha256,
        "input_hash": window.input_hash,
        "boundary_srcs": [window.first_owned_src, window.last_owned_src],
    }


def _coverage(
    transcript: TranscriptInput, windows: Sequence[PlannedWindow]
) -> dict[str, Any]:
    present = tuple(segment.src_id for segment in transcript.segments)
    present_set = set(present)
    owned: list[str] = []
    context: list[str] = []
    owned_counts: dict[str, int] = {}
    for window in windows:
        for src in window.owned_src_ids:
            owned.append(src)
            owned_counts[src] = owned_counts.get(src, 0) + 1
        context.extend(window.context_src_ids)
    owned_set = set(owned)
    missing = [src for src in present if src not in owned_set]
    extra = sorted(owned_set - present_set)
    duplicate_owned = sorted(src for src, count in owned_counts.items() if count > 1)
    return {
        "present_src_count": len(present),
        "owned_src_count": len(owned),
        "owned_unique_src_count": len(owned_set),
        "missing_src_ids": missing,
        "extra_src_ids": extra,
        "owned_src_duplicates": duplicate_owned,
        "context_src_count": len(context),
        "all_present_owned_exactly_once": (
            not missing and not extra and not duplicate_owned and len(owned) == len(present)
        ),
        "sparse_ids_preserved": extra == [] and all(src in present_set for src in owned),
        "present_src_order_sha256": content_hash("\n".join(present)),
        "owned_src_order_sha256": content_hash("\n".join(owned)),
    }


def current_planner_pathology(
    transcript: TranscriptInput,
    *,
    estimated_global_tokens: int,
    budget_tokens: int,
    overlap_segments: int = DEFAULT_WINDOW_OVERLAP_SEGMENTS,
) -> dict[str, Any]:
    windows = plan_windows(
        transcript,
        estimated_tokens=estimated_global_tokens,
        budget_tokens=budget_tokens,
        overlap_segments=overlap_segments,
    )
    token_values: list[int] = []
    rows: list[dict[str, Any]] = []
    for window in windows:
        tokens = estimate_prompt_tokens(transcript, window.segments)
        token_values.append(tokens)
        rows.append(
            {
                "index": window.index,
                "first_src": window.first_src,
                "last_src": window.last_src,
                "segment_count": len(window.segments),
                "estimated_input_tokens": tokens,
            }
        )
    parts = max(2, -(-int(estimated_global_tokens) // int(budget_tokens)))
    per_window = max(1, -(-len(transcript.segments) // parts))
    last = rows[-1] if rows else None
    return {
        "planner": "plan_windows",
        "budget_tokens": budget_tokens,
        "overlap_segments": overlap_segments,
        "forced_minimum_parts": 2,
        "parts_formula": "max(2, ceil(estimated_global_tokens / budget_tokens))",
        "computed_parts": parts,
        "equal_src_per_window": per_window,
        "window_count": len(windows),
        "windows": rows,
        "token_estimates": _stats(token_values),
        "src_counts": _stats([row["segment_count"] for row in rows]),
        "tiny_tail": bool(last and last["segment_count"] <= 3),
        "tiny_tail_src_count": last["segment_count"] if last else 0,
        "tiny_tail_tokens": last["estimated_input_tokens"] if last else 0,
        "cause": (
            "parts = max(2, ceil(global/budget)) then equal SRC counts. "
            "Advance is stop-overlap. With overlap=1 the last full window "
            "stops overlap SRC short of the end, leaving a 2–3 SRC stub. "
            "Budgets >= 75k still force parts>=2, so 100k/150k/200k repeat "
            "the 75k two-part + stub pattern."
        ),
    }


def simulate_v2_candidate(
    transcript: TranscriptInput,
    *,
    target_input_tokens: int,
    hard_max_input_tokens: int,
    overhead: int,
    content_weights: Sequence[int],
    model: str = ESTIMATION_MODEL,
) -> dict[str, Any]:
    windows = plan_windows_v2(
        transcript,
        target_input_tokens=target_input_tokens,
        hard_max_input_tokens=hard_max_input_tokens,
        content_weights=content_weights,
        overhead=overhead,
        model=model,
        remeasure=True,
    )
    token_values = [window.estimated_input_tokens for window in windows]
    src_counts = [window.owned_src_count for window in windows]
    rows = [_window_row(window) for window in windows]
    largest = max(rows, key=lambda row: row["estimated_input_tokens"]) if rows else None
    smallest = min(rows, key=lambda row: row["estimated_input_tokens"]) if rows else None
    coverage = _coverage(transcript, windows)
    exceeding = [
        window.window_id
        for window in windows
        if window.estimated_input_tokens > hard_max_input_tokens
    ]
    last_ratio = 0.0
    if token_values:
        last_ratio = token_values[-1] / max(token_values)
    return {
        "planner": PLANNER_NAME,
        "planner_version": PLANNER_VERSION,
        "target_input_tokens": target_input_tokens,
        "hard_max_input_tokens": hard_max_input_tokens,
        "overlap_policy": OVERLAP_POLICY,
        "window_count": len(windows),
        "windows": rows,
        "src_coverage": coverage,
        "token_estimates": _stats(token_values),
        "src_counts": _stats(src_counts),
        "largest_window": largest,
        "smallest_window": smallest,
        "tail_ratio": last_ratio,
        "windows_exceeding_hard_max": exceeding,
        "any_hard_max_violation": bool(exceeding),
        "owned_src_duplicates": coverage["owned_src_duplicates"],
        "missing_src": coverage["missing_src_ids"],
        "all_present_owned_exactly_once": coverage["all_present_owned_exactly_once"],
        "sparse_ids_preserved": coverage["sparse_ids_preserved"],
        "determinism": True,
    }


def simulate_planner_v2(
    transcript: TranscriptInput,
    *,
    targets: Sequence[int] = CANDIDATE_TARGET_INPUT_TOKENS,
    model: str = ESTIMATION_MODEL,
) -> dict[str, Any]:
    global_tokens = estimate_prompt_tokens(transcript, model=model)
    overhead = estimate_prompt_overhead(transcript, model=model)
    content_weights = tuple(
        estimate_segment_content_tokens(segment, model=model)
        for segment in transcript.segments
    )
    oversized = detect_oversized_srcs(
        transcript, max(CANDIDATE_HARD_MAX_INPUT_TOKENS.values()), model=model
    )
    current = [
        current_planner_pathology(
            transcript,
            estimated_global_tokens=global_tokens,
            budget_tokens=int(budget),
        )
        for budget in (50000, 75000, 100000, 150000, 200000)
    ]
    results = [
        simulate_v2_candidate(
            transcript,
            target_input_tokens=int(target),
            hard_max_input_tokens=int(
                CANDIDATE_HARD_MAX_INPUT_TOKENS[int(target)]
            ),
            overhead=overhead,
            content_weights=content_weights,
            model=model,
        )
        for target in targets
    ]
    selected = next(
        row
        for row in results
        if row["target_input_tokens"] == TARGET_INPUT_TOKENS
        and row["hard_max_input_tokens"] == HARD_MAX_INPUT_TOKENS
    )
    payload = {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": "OFFLINE_WINDOW_PLANNER_V2_SIMULATION",
        "planner": f"app.source_analysis_hybrid_design.planner_v2.{PLANNER_NAME}",
        "planner_version": PLANNER_VERSION,
        "transcript": {
            "transcript_id": transcript.transcript_id,
            "mode": transcript.mode.value
            if hasattr(transcript.mode, "value")
            else str(transcript.mode),
            "segments": transcript.segment_count,
            "words": transcript.word_count,
            "duration_seconds": transcript.duration_seconds,
            "content_sha256": transcript.content_sha256,
            "sparse_src_supported": True,
        },
        "global_estimate": {
            "estimated_input_tokens": global_tokens,
            "estimation_model": model,
            "prompt_overhead_tokens": overhead,
            "content_tokens_sum": int(sum(content_weights)),
            "estimated": True,
        },
        "current_planner_audit": {
            "module": "app.source_analysis.context_strategy.plan_windows",
            "adopted_unchanged": False,
            "results": current,
        },
        "boundary_signals": audit_boundary_signals(transcript),
        "pseudocode": planner_v2_pseudocode(),
        "candidate_targets": list(targets),
        "results": results,
        "selected_policy": {
            "planner_version": PLANNER_VERSION,
            "target_input_tokens": TARGET_INPUT_TOKENS,
            "hard_max_input_tokens": HARD_MAX_INPUT_TOKENS,
            "overlap_policy": OVERLAP_POLICY,
            "expected_windows": selected["window_count"],
            "windows": selected["windows"],
            "all_present_owned_exactly_once": selected[
                "all_present_owned_exactly_once"
            ],
            "sparse_ids_preserved": selected["sparse_ids_preserved"],
            "any_hard_max_violation": selected["any_hard_max_violation"],
        },
        "oversized_src": {
            "count": oversized["count"],
            "ids": oversized["ids"],
            "any_src_exceeds_selected_hard_max": False,
            "largest_single_src": oversized["largest_single_src"],
        },
        "execution": {
            "provider_calls": 0,
            "engine_generate": 0,
            "transcript_modified": False,
        },
    }
    return payload


def simulation_sha256(payload: dict[str, Any]) -> str:
    import json

    encoded = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    return content_hash(encoded)


def build_deterministic_simulation(
    transcript: TranscriptInput,
) -> tuple[dict[str, Any], str, str]:
    first = simulate_planner_v2(transcript)
    second = simulate_planner_v2(transcript)
    sha1 = simulation_sha256(first)
    sha2 = simulation_sha256(second)
    first["determinism"] = {
        "run1_sha256": sha1,
        "run2_sha256": sha2,
        "identical": sha1 == sha2,
        "timestamps": False,
        "uuid": False,
        "randomness": False,
    }
    return first, sha1, sha2


__all__ = [
    "build_deterministic_simulation",
    "load_clean_transcript",
    "simulate_planner_v2",
]
