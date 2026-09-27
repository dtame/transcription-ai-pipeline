"""
Simulation déterministe de plan_windows() sur le transcript CLEAN.

Aucun appel provider. Aucune modification du transcript.
"""

from __future__ import annotations

from statistics import mean, median
from typing import Any, Iterable, Sequence

from app.ai.estimation import estimate_tokens
from app.cleanup_application.writer import audit_path, clean_json_path
from app.file_utils import content_hash
from app.source_analysis.context_strategy import (
    DEFAULT_WINDOW_OVERLAP_SEGMENTS,
    AnalysisWindow,
    plan_windows,
)
from app.source_analysis.prompt import build_system_prompt, build_user_prompt
from app.source_analysis.transcript_input import (
    SourceSegment,
    TranscriptInput,
    TranscriptInputMode,
    load_transcript_input,
)
from app.source_analysis.writer import transcripts_dir
from app.source_analysis_execution_strategy.constants import (
    CANDIDATE_WINDOW_INPUT_BUDGETS,
    EXPECTED_MODEL,
    SCHEMA_VERSION,
)

ESTIMATION_MODEL = EXPECTED_MODEL


def load_clean_transcript(
    project_name: str,
    *,
    sortie_dir=None,
) -> TranscriptInput:
    clean_path = clean_json_path(project_name, sortie_dir=sortie_dir)
    provenance_path = audit_path(project_name, sortie_dir=sortie_dir)
    original_path = (
        transcripts_dir(project_name, sortie_dir=sortie_dir) / "transcript_data.json"
    )
    return load_transcript_input(
        clean_path,
        project_name=project_name,
        mode=TranscriptInputMode.DERIVED,
        provenance_path=provenance_path,
        original_transcript_path=original_path,
    )


def estimate_prompt_tokens(
    transcript: TranscriptInput,
    segments: Sequence[SourceSegment] | None = None,
    *,
    model: str = ESTIMATION_MODEL,
) -> int:
    system = build_system_prompt(transcript.primary_language)
    user = build_user_prompt(transcript, segments=segments)
    return estimate_tokens("\n".join([system, user]), model=model).tokens


def _src_ids(segments: Iterable[SourceSegment]) -> tuple[str, ...]:
    return tuple(segment.src_id for segment in segments)


def _src_ids_sha256(src_ids: Sequence[str]) -> str:
    return content_hash("\n".join(src_ids))


def _stats(values: Sequence[int]) -> dict[str, float | int]:
    if not values:
        return {
            "min": 0,
            "max": 0,
            "mean": 0.0,
            "median": 0.0,
        }
    return {
        "min": min(values),
        "max": max(values),
        "mean": float(mean(values)),
        "median": float(median(values)),
    }


def _window_record(
    window: AnalysisWindow,
    transcript: TranscriptInput,
    *,
    estimated_tokens: int,
) -> dict[str, Any]:
    src_ids = _src_ids(window.segments)
    return {
        "index": window.index,
        "first_src": window.first_src,
        "last_src": window.last_src,
        "segment_count": len(window.segments),
        "word_count": sum(segment.word_count for segment in window.segments),
        "estimated_input_tokens": estimated_tokens,
        "src_ids_sha256": _src_ids_sha256(src_ids),
        "boundary_srcs": [window.first_src, window.last_src],
    }


def _coverage(
    transcript: TranscriptInput,
    windows: Sequence[AnalysisWindow],
    *,
    overlap_segments: int,
) -> dict[str, Any]:
    present = _src_ids(transcript.segments)
    present_set = set(present)
    seen: list[str] = []
    overlap_ids: list[str] = []
    previous: set[str] = set()
    for window in windows:
        ids = _src_ids(window.segments)
        shared = [src for src in ids if src in previous]
        overlap_ids.extend(shared)
        seen.extend(ids)
        previous = set(ids)
    union = set(seen)
    missing = sorted(present_set - union)
    extras = sorted(union - present_set)
    duplicates_outside_overlap = []
    if overlap_segments == 0:
        counts: dict[str, int] = {}
        for src in seen:
            counts[src] = counts.get(src, 0) + 1
        duplicates_outside_overlap = sorted(
            src for src, count in counts.items() if count > 1
        )
    return {
        "present_src_count": len(present),
        "union_src_count": len(union),
        "seen_src_occurrences": len(seen),
        "missing_src_ids": missing,
        "extra_src_ids": extras,
        "all_present_covered": not missing and not extras,
        "sparse_ids_preserved": extras == [] and all(src in present_set for src in seen),
        "overlap_src_count": len(overlap_ids),
        "overlap_src_ids": overlap_ids,
        "duplicate_src_ids_outside_documented_overlap": duplicates_outside_overlap,
        "present_src_order_sha256": _src_ids_sha256(present),
        "union_src_order_sha256": _src_ids_sha256(tuple(sorted(union))),
    }


def detect_oversized_srcs(
    transcript: TranscriptInput,
    budget_tokens: int,
    *,
    model: str = ESTIMATION_MODEL,
) -> dict[str, Any]:
    if not transcript.segments:
        return {
            "count": 0,
            "ids": [],
            "records": [],
            "largest_single_src": {
                "src_id": "",
                "estimated_input_tokens": 0,
                "word_count": 0,
            },
            "any_src_exceeds_budget": False,
        }

    system = build_system_prompt(transcript.primary_language)

    def _estimate(segment: SourceSegment) -> int:
        user = build_user_prompt(transcript, segments=(segment,))
        return estimate_tokens("\n".join([system, user]), model=model).tokens

    longest = max(
        transcript.segments,
        key=lambda segment: (len(segment.text), segment.word_count, segment.src_id),
    )
    longest_tokens = _estimate(longest)
    largest = {
        "src_id": longest.src_id,
        "estimated_input_tokens": longest_tokens,
        "word_count": longest.word_count,
    }
    if longest_tokens <= budget_tokens:
        return {
            "count": 0,
            "ids": [],
            "records": [],
            "largest_single_src": largest,
            "any_src_exceeds_budget": False,
        }

    oversized: list[dict[str, Any]] = []
    for segment in transcript.segments:
        tokens = _estimate(segment)
        if tokens > largest["estimated_input_tokens"]:
            largest = {
                "src_id": segment.src_id,
                "estimated_input_tokens": tokens,
                "word_count": segment.word_count,
            }
        if tokens > budget_tokens:
            oversized.append(
                {
                    "src_id": segment.src_id,
                    "estimated_input_tokens": tokens,
                    "word_count": segment.word_count,
                }
            )
    return {
        "count": len(oversized),
        "ids": [row["src_id"] for row in oversized],
        "records": oversized,
        "largest_single_src": largest,
        "any_src_exceeds_budget": bool(oversized),
    }


def simulate_candidate(
    transcript: TranscriptInput,
    budget_tokens: int,
    *,
    estimated_global_tokens: int,
    overlap_segments: int = DEFAULT_WINDOW_OVERLAP_SEGMENTS,
    model: str = ESTIMATION_MODEL,
    oversized_cache: dict[str, Any] | None = None,
) -> dict[str, Any]:
    windows = plan_windows(
        transcript,
        estimated_tokens=estimated_global_tokens,
        budget_tokens=budget_tokens,
        overlap_segments=overlap_segments,
    )
    records: list[dict[str, Any]] = []
    token_values: list[int] = []
    src_counts: list[int] = []
    exceeding: list[int] = []
    for window in windows:
        tokens = estimate_prompt_tokens(transcript, window.segments, model=model)
        token_values.append(tokens)
        src_counts.append(len(window.segments))
        if tokens > budget_tokens:
            exceeding.append(window.index)
        records.append(_window_record(window, transcript, estimated_tokens=tokens))
    oversized = oversized_cache or detect_oversized_srcs(
        transcript, budget_tokens, model=model
    )
    largest = max(records, key=lambda row: row["estimated_input_tokens"]) if records else None
    smallest = min(records, key=lambda row: row["estimated_input_tokens"]) if records else None
    return {
        "budget": budget_tokens,
        "planner": "plan_windows",
        "overlap_segments": overlap_segments,
        "overlap_kind": "technical_src_overlap",
        "semantic_overlap_added": False,
        "window_count": len(windows),
        "windows": records,
        "src_coverage": _coverage(
            transcript, windows, overlap_segments=overlap_segments
        ),
        "token_estimates": _stats(token_values),
        "src_counts": _stats(src_counts),
        "largest_window": largest,
        "smallest_window": smallest,
        "windows_exceeding_budget": exceeding,
        "any_window_exceeds_budget": bool(exceeding),
        "oversized_src": {
            "count": oversized["count"],
            "ids": oversized["ids"],
            "any_src_exceeds_budget": oversized["any_src_exceeds_budget"],
            "largest_single_src": oversized["largest_single_src"],
        },
        "determinism": True,
        "forces_minimum_two_windows": True,
    }


def simulate_window_strategy(
    transcript: TranscriptInput,
    *,
    budgets: Sequence[int] = CANDIDATE_WINDOW_INPUT_BUDGETS,
    overlap_segments: int = DEFAULT_WINDOW_OVERLAP_SEGMENTS,
    model: str = ESTIMATION_MODEL,
    scan_oversized: bool = True,
) -> dict[str, Any]:
    global_tokens = estimate_prompt_tokens(transcript, model=model)
    system = build_system_prompt(transcript.primary_language)
    empty_user = build_user_prompt(transcript, segments=())
    prompt_overhead = estimate_tokens(
        "\n".join([system, empty_user]), model=model
    ).tokens
    if scan_oversized:
        envelope = detect_oversized_srcs(transcript, max(budgets), model=model)
    else:
        longest = max(
            transcript.segments,
            key=lambda segment: (segment.word_count, segment.src_id),
            default=None,
        )
        envelope = {
            "count": 0,
            "ids": [],
            "records": [],
            "largest_single_src": {
                "src_id": longest.src_id if longest else "",
                "estimated_input_tokens": 0,
                "word_count": longest.word_count if longest else 0,
                "scan": "skipped_word_count_only",
            },
            "any_src_exceeds_budget": False,
        }
    results: list[dict[str, Any]] = []
    for budget in budgets:
        per_budget_oversized = {
            "count": 0,
            "ids": [],
            "records": [],
            "largest_single_src": envelope["largest_single_src"],
            "any_src_exceeds_budget": False,
        }
        if (
            scan_oversized
            and envelope["largest_single_src"]["estimated_input_tokens"] > budget
        ):
            per_budget_oversized = detect_oversized_srcs(
                transcript, budget, model=model
            )
        results.append(
            simulate_candidate(
                transcript,
                int(budget),
                estimated_global_tokens=global_tokens,
                overlap_segments=overlap_segments,
                model=model,
                oversized_cache=per_budget_oversized,
            )
        )
    payload = {
        "schema_version": SCHEMA_VERSION,
        "phase": "3B.6",
        "mode": "OFFLINE_WINDOW_PLANNING_SIMULATION",
        "planner": "app.source_analysis.context_strategy.plan_windows",
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
            "prompt_overhead_tokens": prompt_overhead,
            "estimated": True,
        },
        "planner_notes": {
            "window_count_formula": (
                "max(2, ceil(estimated_global_tokens / budget_tokens))"
            ),
            "segment_split": "equal SRC counts; never splits a SRC",
            "per_window_tokens_remeasured": True,
            "overlap_default_segments": DEFAULT_WINDOW_OVERLAP_SEGMENTS,
            "overlap_used": overlap_segments,
            "semantic_overlap_added": False,
            "minimum_windows_forced": 2,
            "overlap_creates_tail_stub_window": overlap_segments > 0,
            "limitation": (
                "With overlap_segments>0 the last advance is stop-overlap, "
                "so a leftover 2–3 SRC window can appear after otherwise "
                "equal parts. This is current plan_windows() behavior, not "
                "a semantic split. 3B.6 does not change the planner."
            ),
        },
        "candidate_budgets": list(budgets),
        "results": results,
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
    *,
    budgets: Sequence[int] = CANDIDATE_WINDOW_INPUT_BUDGETS,
    overlap_segments: int = DEFAULT_WINDOW_OVERLAP_SEGMENTS,
) -> tuple[dict[str, Any], str, str]:
    first = simulate_window_strategy(
        transcript, budgets=budgets, overlap_segments=overlap_segments
    )
    second = simulate_window_strategy(
        transcript, budgets=budgets, overlap_segments=overlap_segments
    )
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
