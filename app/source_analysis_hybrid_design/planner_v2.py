"""
WindowPlannerV2 — prototype de référence OFFLINE.

Découpe déterministe, token-équilibrée, frontières SRC uniquement.
Aucun appel provider. Non branché dans analyzer.py.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

from app.ai.estimation import estimate_tokens
from app.file_utils import content_hash
from app.source_analysis.prompt import (
    build_system_prompt,
    build_user_prompt,
    render_segment,
)
from app.source_analysis.transcript_input import SourceSegment, TranscriptInput
from app.source_analysis_hybrid_design.constants import (
    ESTIMATION_MODEL,
    HARD_MAX_INPUT_TOKENS,
    OVERLAP_POLICY,
    PLANNER_VERSION,
    TARGET_INPUT_TOKENS,
    TINY_TAIL_MIN_CONTENT_OVERHEAD_FACTOR,
    TINY_TAIL_MIN_FRACTION_OF_TARGET,
)


def format_window_id(index: int) -> str:
    return f"WIN{index:03d}"


@dataclass(frozen=True)
class PlannedWindow:
    window_id: str
    index: int
    start: int
    stop: int
    owned_src_ids: tuple[str, ...]
    context_src_ids: tuple[str, ...]
    first_owned_src: str
    last_owned_src: str
    owned_src_count: int
    word_count: int
    content_tokens: int
    estimated_input_tokens: int
    planner_estimate_tokens: int
    owned_src_ids_sha256: str
    owned_content_sha256: str
    input_hash: str


@dataclass(frozen=True)
class PlannerError:
    code: str
    src_id: str
    estimated_input_tokens: int
    hard_max_input_tokens: int


def estimate_prompt_overhead(
    transcript: TranscriptInput, *, model: str = ESTIMATION_MODEL
) -> int:
    system = build_system_prompt(transcript.primary_language)
    user = build_user_prompt(transcript, segments=())
    return estimate_tokens("\n".join([system, user]), model=model).tokens


def estimate_segment_content_tokens(
    segment: SourceSegment, *, model: str = ESTIMATION_MODEL
) -> int:
    return estimate_tokens(render_segment(segment), model=model).tokens


def estimate_window_input_tokens(
    transcript: TranscriptInput,
    segments: Sequence[SourceSegment],
    *,
    model: str = ESTIMATION_MODEL,
) -> int:
    system = build_system_prompt(transcript.primary_language)
    user = build_user_prompt(transcript, segments=segments)
    return estimate_tokens("\n".join([system, user]), model=model).tokens


def _src_ids_hash(src_ids: Sequence[str]) -> str:
    return content_hash("\n".join(src_ids))


def _content_hash(segments: Sequence[SourceSegment]) -> str:
    return content_hash(
        "\n".join(f"{segment.src_id}\t{segment.text}" for segment in segments)
    )


def _input_hash(
    *,
    planner_version: str,
    window_id: str,
    owned: Sequence[str],
    context: Sequence[str],
    content_sha: str,
) -> str:
    return content_hash(
        "\n".join(
            [
                planner_version,
                window_id,
                "owned:" + ",".join(owned),
                "context:" + ",".join(context),
                content_sha,
            ]
        )
    )


def _min_useful_content_tokens(target_input_tokens: int, overhead: int) -> int:
    return max(
        int(overhead * TINY_TAIL_MIN_CONTENT_OVERHEAD_FACTOR),
        int((target_input_tokens - overhead) * TINY_TAIL_MIN_FRACTION_OF_TARGET),
    )


def _balanced_cuts(weights: Sequence[int], parts: int) -> list[int]:
    """
    Bornes exclusives déterministes pour `parts` fenêtres contigues.

    Retourne [0, c1, c2, ..., n]. Chaque coupe minimise l'écart à la
    cible cumulative i * total / parts. En cas d'égalité, la coupe la
    plus à gauche est retenue pour éviter d'affamer la dernière fenêtre.
    """
    n = len(weights)
    if parts <= 1 or n <= 1:
        return [0, n]
    parts = min(parts, n)
    prefix = [0]
    for weight in weights:
        prefix.append(prefix[-1] + weight)
    total = prefix[-1]
    cuts = [0]
    used = 0
    for index in range(1, parts):
        target = (total * index) / parts
        lo = used + 1
        hi = n - (parts - index)
        best = lo
        best_err = abs(prefix[lo] - target)
        for candidate in range(lo, hi + 1):
            err = abs(prefix[candidate] - target)
            if err < best_err:
                best = candidate
                best_err = err
        cuts.append(best)
        used = best
    cuts.append(n)
    return cuts


def _window_count(
    total_content: int,
    target_input_tokens: int,
    hard_max_input_tokens: int,
    overhead: int,
) -> int:
    usable_target = max(1, target_input_tokens - overhead)
    usable_hard = max(1, hard_max_input_tokens - overhead)
    by_target = max(1, math.ceil(total_content / usable_target))
    by_hard = max(1, math.ceil(total_content / usable_hard))
    return max(by_target, by_hard)


def _apply_tiny_tail(
    cuts: list[int],
    weights: Sequence[int],
    *,
    min_content: int,
    hard_content: int,
) -> list[int]:
    if len(cuts) <= 2:
        return cuts
    last_start = cuts[-2]
    last_stop = cuts[-1]
    last_content = sum(weights[last_start:last_stop])
    if last_content >= min_content:
        return cuts

    prev_start = cuts[-3]
    prev_content = sum(weights[prev_start:last_start])
    if prev_content + last_content <= hard_content:
        return cuts[:-2] + [cuts[-1]]

    steal = last_start
    while steal > prev_start + 1:
        candidate = steal - 1
        new_prev = sum(weights[prev_start:candidate])
        new_last = sum(weights[candidate:last_stop])
        if new_prev > hard_content:
            break
        steal = candidate
        if new_last >= min_content and new_prev >= min_content:
            break
        if new_last >= min_content:
            break
    if steal == last_start:
        return cuts
    return cuts[:-2] + [steal, last_stop]


def detect_oversized_src(
    transcript: TranscriptInput,
    *,
    hard_max_input_tokens: int,
    overhead: int,
    content_weights: Sequence[int],
    model: str = ESTIMATION_MODEL,
) -> PlannerError | None:
    del model
    if not transcript.segments:
        return None
    longest_index = max(
        range(len(transcript.segments)),
        key=lambda i: (content_weights[i], transcript.segments[i].src_id),
    )
    estimated = overhead + int(content_weights[longest_index])
    if estimated <= hard_max_input_tokens:
        return None
    return PlannerError(
        code="OVERSIZED_SRC",
        src_id=transcript.segments[longest_index].src_id,
        estimated_input_tokens=estimated,
        hard_max_input_tokens=hard_max_input_tokens,
    )


def plan_windows_v2(
    transcript: TranscriptInput,
    *,
    target_input_tokens: int = TARGET_INPUT_TOKENS,
    hard_max_input_tokens: int = HARD_MAX_INPUT_TOKENS,
    overlap_policy: str = OVERLAP_POLICY,
    planner_version: str = PLANNER_VERSION,
    model: str = ESTIMATION_MODEL,
    content_weights: Sequence[int] | None = None,
    overhead: int | None = None,
    remeasure: bool = True,
) -> tuple[PlannedWindow, ...]:
    """
    Planifie des fenêtres OWNED disjointes, token-équilibrées.

    overlap_policy accepté ici : NO_OWNED_OVERLAP uniquement.
    Le contexte de frontière n'est pas injecté dans l'ownership.
    """
    del overlap_policy
    segments = transcript.segments
    if not segments:
        return ()

    if overhead is None:
        overhead = estimate_prompt_overhead(transcript, model=model)
    if content_weights is None:
        content_weights = tuple(
            estimate_segment_content_tokens(segment, model=model)
            for segment in segments
        )
    oversized = detect_oversized_src(
        transcript,
        hard_max_input_tokens=hard_max_input_tokens,
        overhead=overhead,
        content_weights=content_weights,
        model=model,
    )
    if oversized is not None:
        raise ValueError(
            f"{oversized.code}: {oversized.src_id} "
            f"estimated={oversized.estimated_input_tokens} "
            f"hard_max={oversized.hard_max_input_tokens}"
        )

    total_content = sum(content_weights)
    parts = _window_count(
        total_content, target_input_tokens, hard_max_input_tokens, overhead
    )
    hard_content = max(1, hard_max_input_tokens - overhead)
    min_content = _min_useful_content_tokens(target_input_tokens, overhead)

    cuts = _balanced_cuts(content_weights, parts)
    cuts = _apply_tiny_tail(
        cuts,
        content_weights,
        min_content=min_content,
        hard_content=hard_content,
    )

    windows: list[PlannedWindow] = []
    for index, (start, stop) in enumerate(zip(cuts[:-1], cuts[1:]), start=1):
        owned = segments[start:stop]
        owned_ids = tuple(segment.src_id for segment in owned)
        content_tokens = int(sum(content_weights[start:stop]))
        planner_estimate = overhead + content_tokens
        if planner_estimate > hard_max_input_tokens:
            raise ValueError(
                f"HARD_MAX_VIOLATION: {format_window_id(index)} "
                f"planner_estimate={planner_estimate} "
                f"hard_max={hard_max_input_tokens}"
            )
        measured = (
            estimate_window_input_tokens(transcript, owned, model=model)
            if remeasure
            else planner_estimate
        )
        if measured > hard_max_input_tokens:
            raise ValueError(
                f"HARD_MAX_VIOLATION: {format_window_id(index)} "
                f"remeasured={measured} hard_max={hard_max_input_tokens}"
            )
        window_id = format_window_id(index)
        content_sha = _content_hash(owned)
        windows.append(
            PlannedWindow(
                window_id=window_id,
                index=index,
                start=start,
                stop=stop,
                owned_src_ids=owned_ids,
                context_src_ids=(),
                first_owned_src=owned_ids[0],
                last_owned_src=owned_ids[-1],
                owned_src_count=len(owned_ids),
                word_count=sum(segment.word_count for segment in owned),
                content_tokens=content_tokens,
                estimated_input_tokens=measured,
                planner_estimate_tokens=planner_estimate,
                owned_src_ids_sha256=_src_ids_hash(owned_ids),
                owned_content_sha256=content_sha,
                input_hash=_input_hash(
                    planner_version=planner_version,
                    window_id=window_id,
                    owned=owned_ids,
                    context=(),
                    content_sha=content_sha,
                ),
            )
        )
    return tuple(windows)


def planner_v2_pseudocode() -> list[str]:
    return [
        "overhead = estimate(system + empty_user_prompt)",
        "weights[i] = estimate(render_segment(SRC_i))  # never split a SRC",
        "if any overhead+weights[i] > hard_max: FAIL OVERSIZED_SRC",
        "parts = max(ceil(sum(weights)/(target-overhead)),",
        "            ceil(sum(weights)/(hard_max-overhead)), 1)",
        "cuts = balanced_prefix_cuts(weights, parts)  # SRC boundaries only",
        "if last_window.content < max(2*overhead, 0.15*(target-overhead)):",
        "    merge last into previous if combined <= hard_max",
        "    else steal SRC from previous until last >= min or blocked",
        "owned_src = disjoint partition; context_src = empty (NO_OWNED_OVERLAP)",
        "window_id = WIN001..WINnnn by source appearance order",
        "remeasure each window with the real window prompt; fail if > hard_max",
    ]
