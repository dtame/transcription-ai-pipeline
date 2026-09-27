"""
Validation structurelle d'un WindowPlan.

Contiguïté = adjacence dans la séquence réelle des SRC présents,
pas une continuité numérique d'identifiants.
"""

from __future__ import annotations

from typing import Any

from app.source_analysis.errors import SourceAnalysisWindowPlanError
from app.source_analysis.transcript_input import TranscriptInput
from app.source_analysis_hybrid.config import WindowPlannerConfig
from app.source_analysis_hybrid.contracts import (
    WINDOW_ID_PATTERN,
    WindowInput,
    WindowPlan,
    format_window_id,
    segments_content_hash,
    src_ids_hash,
    window_input_hash,
)


def assert_unique_src_ids(transcript: TranscriptInput) -> None:
    """Pas de déduplication silencieuse."""
    seen: set[str] = set()
    for segment in transcript.segments:
        if segment.src_id in seen:
            raise SourceAnalysisWindowPlanError(
                f"TranscriptInput viole l'unicité SRC : {segment.src_id}."
            )
        seen.add(segment.src_id)


def _fail(message: str) -> None:
    raise SourceAnalysisWindowPlanError(message)


def validate_window(window: WindowInput, transcript: TranscriptInput) -> None:
    present = transcript.src_ids()
    present_set = set(present)
    if not WINDOW_ID_PATTERN.fullmatch(window.window_id):
        _fail(f"window_id invalide : {window.window_id!r}.")
    if window.transcript_id != transcript.transcript_id:
        _fail(
            f"{window.window_id}: transcript_id {window.transcript_id} "
            f"≠ {transcript.transcript_id}."
        )
    if not window.owned_src_refs:
        _fail(f"{window.window_id}: owned_src_refs vide.")
    if window.owned_src_count != len(window.owned_src_refs):
        _fail(f"{window.window_id}: owned_src_count incohérent.")
    if window.first_owned_src_ref != window.owned_src_refs[0]:
        _fail(f"{window.window_id}: first_owned_src_ref incohérent.")
    if window.last_owned_src_ref != window.owned_src_refs[-1]:
        _fail(f"{window.window_id}: last_owned_src_ref incohérent.")
    if window.source_order_stop - window.source_order_start != window.owned_src_count:
        _fail(f"{window.window_id}: source_order start/stop incohérents.")
    slice_ids = present[window.source_order_start : window.source_order_stop]
    if tuple(slice_ids) != window.owned_src_refs:
        _fail(
            f"{window.window_id}: owned_src_refs n'est pas une tranche "
            "contiguë de l'ordre source présent."
        )
    unknown_owned = [src for src in window.owned_src_refs if src not in present_set]
    unknown_context = [src for src in window.context_src_refs if src not in present_set]
    if unknown_owned:
        _fail(f"{window.window_id}: SRC owned absents : {unknown_owned}.")
    if unknown_context:
        _fail(f"{window.window_id}: SRC context absents : {unknown_context}.")
    owned_set = set(window.owned_src_refs)
    if len(owned_set) != len(window.owned_src_refs):
        _fail(f"{window.window_id}: doublons dans owned_src_refs.")
    context_set = set(window.context_src_refs)
    if len(context_set) != len(window.context_src_refs):
        _fail(f"{window.window_id}: doublons dans context_src_refs.")
    overlap = owned_set & context_set
    if overlap:
        _fail(f"{window.window_id}: owned/context non disjoints : {sorted(overlap)}.")
    if src_ids_hash(window.owned_src_refs) != window.owned_src_ids_sha256:
        _fail(f"{window.window_id}: owned_src_ids_sha256 incohérent.")
    if src_ids_hash(window.context_src_refs) != window.context_src_ids_sha256:
        _fail(f"{window.window_id}: context_src_ids_sha256 incohérent.")
    owned_segments = transcript.segments[
        window.source_order_start : window.source_order_stop
    ]
    if segments_content_hash(owned_segments) != window.owned_content_sha256:
        _fail(f"{window.window_id}: owned_content_sha256 incohérent.")
    expected_input = window_input_hash(
        planner_version=window.planner_version,
        window_id=window.window_id,
        owned=window.owned_src_refs,
        context=window.context_src_refs,
        owned_content_sha256=window.owned_content_sha256,
        context_content_sha256=window.context_content_sha256,
    )
    if expected_input != window.input_hash:
        _fail(f"{window.window_id}: input_hash incohérent.")


def validate_window_plan(
    plan: WindowPlan,
    transcript: TranscriptInput,
    config: WindowPlannerConfig,
) -> None:
    present = transcript.src_ids()
    if plan.transcript_id != transcript.transcript_id:
        _fail("transcript_id du plan ≠ TranscriptInput.")
    if plan.transcript_sha256 != transcript.content_sha256:
        _fail("transcript_sha256 du plan ≠ TranscriptInput.")
    if plan.planner_version != config.version:
        _fail("planner_version du plan ≠ config.")
    if plan.target_input_tokens != config.target_input_tokens:
        _fail("target_input_tokens du plan ≠ config.")
    if plan.hard_max_input_tokens != config.hard_max_input_tokens:
        _fail("hard_max_input_tokens du plan ≠ config.")
    if plan.overlap_policy != config.overlap_policy:
        _fail("overlap_policy du plan ≠ config.")
    if plan.window_count != len(plan.windows):
        _fail("window_count incohérent.")
    if not plan.windows:
        _fail("WindowPlan sans fenêtre.")

    seen_ids: set[str] = set()
    owned_all: list[str] = []
    context_all: list[str] = []
    for index, window in enumerate(plan.windows, start=1):
        expected_id = format_window_id(index)
        if window.window_id != expected_id:
            _fail(f"window_id attendu {expected_id}, reçu {window.window_id}.")
        if window.window_id in seen_ids:
            _fail(f"window_id dupliqué : {window.window_id}.")
        seen_ids.add(window.window_id)
        if window.planner_version != plan.planner_version:
            _fail(f"{window.window_id}: planner_version ≠ plan.")
        if window.estimated_input_tokens > plan.hard_max_input_tokens:
            _fail(
                f"{window.window_id}: estimated_input_tokens "
                f"{window.estimated_input_tokens} > hard_max "
                f"{plan.hard_max_input_tokens}."
            )
        validate_window(window, transcript)
        owned_all.extend(window.owned_src_refs)
        context_all.extend(window.context_src_refs)

    if owned_all != list(present):
        _fail(
            "concaténation owned_src_refs ≠ séquence CLEAN présente "
            "(ordre ou membership)."
        )
    if plan.owned_src_count != len(owned_all):
        _fail("owned_src_count du plan incohérent.")
    if plan.context_src_count != len(context_all):
        _fail("context_src_count du plan incohérent.")
    if len(owned_all) != len(set(owned_all)):
        _fail("ownership dupliquée entre fenêtres.")


def plan_validation_report(
    plan: WindowPlan, transcript: TranscriptInput, config: WindowPlannerConfig
) -> dict[str, Any]:
    present = list(transcript.src_ids())
    owned = [src for window in plan.windows for src in window.owned_src_refs]
    context = [src for window in plan.windows for src in window.context_src_refs]
    owned_set = set(owned)
    present_set = set(present)
    missing = [src for src in present if src not in owned_set]
    extra = sorted(owned_set - present_set)
    counts: dict[str, int] = {}
    for src in owned:
        counts[src] = counts.get(src, 0) + 1
    duplicates = sorted(src for src, count in counts.items() if count > 1)
    try:
        validate_window_plan(plan, transcript, config)
        valid = True
        error = None
    except SourceAnalysisWindowPlanError as exc:
        valid = False
        error = str(exc)
    return {
        "valid": valid,
        "error": error,
        "all_sources_owned_exactly_once": (
            not missing and not extra and not duplicates and owned == present
        ),
        "source_order_preserved": owned == present,
        "sparse_src_preserved": extra == [] and all(src in present_set for src in owned),
        "hard_max_respected": all(
            window.estimated_input_tokens <= plan.hard_max_input_tokens
            for window in plan.windows
        ),
        "owned_overlap_count": len(duplicates),
        "context_src_count": len(context),
        "missing_src_count": len(missing),
        "extra_src_count": len(extra),
        "duplicate_ownership": duplicates,
    }
