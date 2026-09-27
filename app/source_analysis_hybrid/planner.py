"""
WindowPlannerV2 — planification déterministe, frontières SRC uniquement.

Algorithme approuvé 3B.7 (window-planner-v2.0) :

    overhead = estimate(system + user vide)
    weights[i] = estimate(render_segment(SRC_i))  # jamais scinder un SRC
    si overhead + weights[i] > hard_max : FAIL OVERSIZED_SRC
    N = max(
        ceil(sum(weights) / (target - overhead)),
        ceil(sum(weights) / (hard_max - overhead)),
        1,
    )
    cuts = coupes de préfixe équilibrées (frontières SRC)
           tie-break = plus petite |erreur|, puis coupe la plus à gauche
    tiny-tail : si contenu(dernière) < max(2*overhead, 0.15*(target-overhead))
        fusionner dans la précédente si combiné <= hard_max
        sinon voler des SRC à la précédente jusqu'à min ou blocage
    owned disjoint ; context_src_refs = () en v1
    window_id = WIN001..WINnnn dans l'ordre source
    re-mesure de chaque fenêtre ; fail si > hard_max
    jamais de troncature

N n'est pas une formule unique ignorante des frontières : après coupe
réelle, chaque fenêtre est re-mesurée. Si une fenêtre dépasse encore le
hard max, échec explicite — pas d'augmentation silencieuse de N, pas de
troncature.

Non branché dans analyzer.py. plan_windows() historique inchangé.
"""

from __future__ import annotations

import math
from statistics import mean, median
from typing import Sequence

from app.source_analysis.errors import (
    SourceAnalysisEmptyTranscript,
    SourceAnalysisWindowPlanError,
    SourceAnalysisWindowTooLarge,
)
from app.source_analysis.transcript_input import SourceSegment, TranscriptInput
from app.source_analysis_hybrid.config import WindowPlannerConfig
from app.source_analysis_hybrid.constants import (
    ESTIMATION_MODEL,
    PLAN_STRATEGY,
    TINY_TAIL_MIN_CONTENT_OVERHEAD_FACTOR,
    TINY_TAIL_MIN_FRACTION_OF_TARGET,
)
from app.source_analysis_hybrid.contracts import (
    WindowInput,
    WindowPlan,
    empty_context_refs,
    format_window_id,
    segments_content_hash,
    src_ids_hash,
    window_input_hash,
)
from app.source_analysis_hybrid.tokens import (
    content_weights_for,
    estimate_prompt_overhead,
    estimate_window_input_tokens,
)
from app.source_analysis_hybrid.validation import (
    assert_unique_src_ids,
    validate_window_plan,
)


def min_useful_content_tokens(target_input_tokens: int, overhead: int) -> int:
    """
    Seuil anti-tiny-tail 3B.7 :

        max(2 * overhead, 0.15 * (target - overhead))
    """
    return max(
        int(overhead * TINY_TAIL_MIN_CONTENT_OVERHEAD_FACTOR),
        int((target_input_tokens - overhead) * TINY_TAIL_MIN_FRACTION_OF_TARGET),
    )


def balanced_cuts(weights: Sequence[int], parts: int) -> list[int]:
    """
    Bornes exclusives [0, c1, ..., n] pour `parts` fenêtres contigues.

    Chaque coupe minimise |prefix[c] - i * total / parts|.
    Tie-break : la coupe la plus à gauche (évite d'affamer la dernière
    fenêtre). Aucun hasard.
    """
    n = len(weights)
    if parts <= 1 or n <= 1:
        return [0, n]
    parts = min(parts, n)
    prefix = [0]
    for weight in weights:
        prefix.append(prefix[-1] + int(weight))
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


def apply_tiny_tail(
    cuts: list[int],
    weights: Sequence[int],
    *,
    min_content: int,
    hard_content: int,
) -> list[int]:
    """
    Politique 3B.7 : si la dernière fenêtre est trop petite,

    1. la fusionner dans la précédente si combiné <= hard_content ;
    2. sinon voler des SRC à la précédente jusqu'à last >= min,
       sans faire dépasser hard_content à la précédente.
    """
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


def window_count(
    total_content: int,
    target_input_tokens: int,
    hard_max_input_tokens: int,
    overhead: int,
) -> int:
    """
    N conceptuel. Une seule fenêtre si le contenu tient dans
    (target - overhead). Pas de minimum forcé à 2.
    """
    usable_target = max(1, target_input_tokens - overhead)
    usable_hard = max(1, hard_max_input_tokens - overhead)
    by_target = max(1, math.ceil(total_content / usable_target))
    by_hard = max(1, math.ceil(total_content / usable_hard))
    return max(by_target, by_hard)


def _detect_oversized(
    transcript: TranscriptInput,
    *,
    hard_max_input_tokens: int,
    overhead: int,
    content_weights: Sequence[int],
) -> None:
    longest_index = max(
        range(len(transcript.segments)),
        key=lambda i: (content_weights[i], transcript.segments[i].src_id),
    )
    estimated = overhead + int(content_weights[longest_index])
    src_id = transcript.segments[longest_index].src_id
    if estimated > hard_max_input_tokens:
        raise SourceAnalysisWindowTooLarge(
            f"OVERSIZED_SRC: {src_id} estimated={estimated} "
            f"hard_max={hard_max_input_tokens}",
            src_id=src_id,
            estimated_tokens=estimated,
            hard_max_input_tokens=hard_max_input_tokens,
        )


def _build_window(
    transcript: TranscriptInput,
    *,
    config: WindowPlannerConfig,
    index: int,
    start: int,
    stop: int,
    content_weights: Sequence[int],
    overhead: int,
    model: str,
    remeasure: bool,
) -> WindowInput:
    owned = transcript.segments[start:stop]
    if not owned:
        raise SourceAnalysisWindowPlanError(
            f"fenêtre {index} vide — WIN vide interdit."
        )
    owned_ids = tuple(segment.src_id for segment in owned)
    context_ids = empty_context_refs()
    content_tokens = int(sum(content_weights[start:stop]))
    planner_estimate = overhead + content_tokens
    window_id = format_window_id(index)
    if planner_estimate > config.hard_max_input_tokens:
        raise SourceAnalysisWindowPlanError(
            f"HARD_MAX_VIOLATION: {window_id} "
            f"planner_estimate={planner_estimate} "
            f"hard_max={config.hard_max_input_tokens}"
        )
    measured = (
        estimate_window_input_tokens(transcript, owned, model=model)
        if remeasure
        else planner_estimate
    )
    if measured > config.hard_max_input_tokens:
        raise SourceAnalysisWindowPlanError(
            f"HARD_MAX_VIOLATION: {window_id} "
            f"remeasured={measured} hard_max={config.hard_max_input_tokens}"
        )
    owned_content = segments_content_hash(owned)
    context_content = segments_content_hash(())
    return WindowInput(
        window_id=window_id,
        transcript_id=transcript.transcript_id,
        planner_version=config.version,
        owned_src_refs=owned_ids,
        context_src_refs=context_ids,
        first_owned_src_ref=owned_ids[0],
        last_owned_src_ref=owned_ids[-1],
        owned_src_count=len(owned_ids),
        estimated_input_tokens=measured,
        owned_src_ids_sha256=src_ids_hash(owned_ids),
        owned_content_sha256=owned_content,
        context_src_ids_sha256=src_ids_hash(context_ids),
        context_content_sha256=context_content,
        input_hash=window_input_hash(
            planner_version=config.version,
            window_id=window_id,
            owned=owned_ids,
            context=context_ids,
            owned_content_sha256=owned_content,
            context_content_sha256=context_content,
        ),
        source_order_start=start,
        source_order_stop=stop,
        word_count=sum(segment.word_count for segment in owned),
        content_tokens=content_tokens,
        planner_estimate_tokens=planner_estimate,
    )


def _token_stats(values: Sequence[int]) -> tuple[int, int, float, float]:
    if not values:
        return 0, 0, 0.0, 0.0
    return min(values), max(values), float(mean(values)), float(median(values))


class WindowPlannerV2:
    """TranscriptInput + estimateur + config → WindowPlan ordonné."""

    def __init__(
        self,
        config: WindowPlannerConfig | None = None,
        *,
        model: str = ESTIMATION_MODEL,
    ) -> None:
        self.config = config or WindowPlannerConfig()
        self.model = model

    def plan(
        self,
        transcript: TranscriptInput,
        *,
        content_weights: Sequence[int] | None = None,
        overhead: int | None = None,
        remeasure: bool = True,
    ) -> WindowPlan:
        assert_unique_src_ids(transcript)
        segments = transcript.segments
        if not segments:
            raise SourceAnalysisEmptyTranscript(
                "TranscriptInput vide : aucun WIN001 vide n'est créé."
            )

        config = self.config
        if overhead is None:
            overhead = estimate_prompt_overhead(transcript, model=self.model)
        if content_weights is None:
            content_weights = content_weights_for(transcript, model=self.model)
        if len(content_weights) != len(segments):
            raise SourceAnalysisWindowPlanError(
                "content_weights et segments de longueurs différentes."
            )

        _detect_oversized(
            transcript,
            hard_max_input_tokens=config.hard_max_input_tokens,
            overhead=overhead,
            content_weights=content_weights,
        )

        total_content = int(sum(content_weights))
        parts = window_count(
            total_content,
            config.target_input_tokens,
            config.hard_max_input_tokens,
            overhead,
        )
        hard_content = max(1, config.hard_max_input_tokens - overhead)
        min_content = min_useful_content_tokens(config.target_input_tokens, overhead)
        cuts = balanced_cuts(content_weights, parts)
        cuts = apply_tiny_tail(
            cuts,
            content_weights,
            min_content=min_content,
            hard_content=hard_content,
        )

        windows: list[WindowInput] = []
        for index, (start, stop) in enumerate(zip(cuts[:-1], cuts[1:]), start=1):
            windows.append(
                _build_window(
                    transcript,
                    config=config,
                    index=index,
                    start=start,
                    stop=stop,
                    content_weights=content_weights,
                    overhead=overhead,
                    model=self.model,
                    remeasure=remeasure,
                )
            )

        token_values = [window.estimated_input_tokens for window in windows]
        lo, hi, avg, mid = _token_stats(token_values)
        plan = WindowPlan(
            strategy=PLAN_STRATEGY,
            planner_version=config.version,
            transcript_id=transcript.transcript_id,
            transcript_sha256=transcript.content_sha256,
            target_input_tokens=config.target_input_tokens,
            hard_max_input_tokens=config.hard_max_input_tokens,
            overlap_policy=config.overlap_policy,
            prompt_overhead_tokens=int(overhead),
            windows=tuple(windows),
            owned_src_count=sum(window.owned_src_count for window in windows),
            context_src_count=sum(window.context_src_count for window in windows),
            window_count=len(windows),
            estimated_input_tokens_min=lo,
            estimated_input_tokens_max=hi,
            estimated_input_tokens_mean=avg,
            estimated_input_tokens_median=mid,
        )
        validate_window_plan(plan, transcript, config)
        return plan


def plan_windows_v2(
    transcript: TranscriptInput,
    *,
    config: WindowPlannerConfig | None = None,
    model: str = ESTIMATION_MODEL,
    content_weights: Sequence[int] | None = None,
    overhead: int | None = None,
    remeasure: bool = True,
) -> WindowPlan:
    return WindowPlannerV2(config, model=model).plan(
        transcript,
        content_weights=content_weights,
        overhead=overhead,
        remeasure=remeasure,
    )


# Réexport pour les tests d'algorithme (même sémantique que le design 3B.7).
__all__ = [
    "SourceSegment",
    "WindowPlannerV2",
    "apply_tiny_tail",
    "balanced_cuts",
    "min_useful_content_tokens",
    "plan_windows_v2",
    "window_count",
]
