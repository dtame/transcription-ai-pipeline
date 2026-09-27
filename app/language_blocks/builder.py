"""
Builder — orchestration de la Phase 3A.1.1.

    transcript_data.json + language_cleanup.json
          |   combined_source.load_combined_source        (lecture + fusion)
    CombinedSource
          |   runs.build_runs                               (SRC -> runs par langue/AUDIO)
    Run[]
          |   bridging.build_block_spans                    (runs FR -> blocs, avec ponts)
    BlockSpan[]
          |   context.find_english_context (x2 par bloc)
          |   classifier.*  (structure, direction, décisions 3A.1, revue sémantique)
    LanguageBlock[]
          |   stats.compute_stats
    BlocksManifestStats
          |   models.LanguageBlocksManifest
    language_blocks.json                          (writer.py, atomique)

CE MODULE N'EST BRANCHÉ NULLE PART AUTOMATIQUEMENT : ni main.py, ni
pipeline_runner.py ne l'importent. Aucun appel réseau, aucun LLM.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

from app.language_blocks import writer as writer_module
from app.language_blocks.bridging import BlockSpan, build_block_spans
from app.language_blocks.classifier import (
    aggregate_phase_3a1,
    classify_candidate_direction,
    classify_structure,
    compute_already_resolved,
    compute_semantic_review,
)
from app.language_blocks.combined_source import CombinedSource, load_combined_source
from app.language_blocks.constants import (
    BRIDGE_MAX_DURATION_SECONDS,
    BRIDGE_MAX_RUN_SEGMENTS,
    BRIDGE_MAX_TOTAL_GAP_SECONDS,
    BRIDGE_MAX_WORDS_PER_SEGMENT,
    CONTEXT_WINDOW_MAX_BLOCK_SKIP,
    FR_GAP_SPLIT_THRESHOLD_SECONDS,
    MAX_CONTEXT_SECONDS,
    MAX_CONTEXT_SEGMENTS,
    MAX_CONTEXT_WORDS,
)
from app.language_blocks.context import find_english_context
from app.language_blocks.models import (
    BlocksConfiguration,
    LanguageBlock,
    LanguageBlocksManifest,
)
from app.language_blocks.runs import Run, build_runs
from app.language_blocks.stats import compute_stats

LANGUAGE_FR = "FR"


def _format_block_id(order: int) -> str:
    """FRB0001, FRB0002, ... — déterministe, dans l'ordre d'apparition (§9)."""
    return f"FRB{order:04d}"


def _build_block(
    order: int,
    span: BlockSpan,
    runs: tuple[Run, ...],
    *,
    valid_refs: frozenset[str],
    language_by_ref: dict[str, str],
) -> LanguageBlock:
    all_source_refs = tuple(segment.src_id for segment in span.segments)
    text = " ".join(segment.text for segment in span.segments)

    before_result = find_english_context(runs, span, direction="before")
    after_result = find_english_context(runs, span, direction="after")

    structure = classify_structure(before_result.reason, after_result.reason)
    candidate_direction = classify_candidate_direction(
        before_result.reason, after_result.reason
    )

    fr_segments = tuple(
        segment for segment in span.segments if segment.language == LANGUAGE_FR
    )

    aggregated = aggregate_phase_3a1(fr_segments)

    already_resolved = compute_already_resolved(
        aggregated,
        fr_segments,
        valid_refs=valid_refs,
        language_by_ref=language_by_ref,
    )

    needs_semantic_review, semantic_review_status = compute_semantic_review(
        already_resolved=already_resolved,
        before_reason=before_result.reason,
        after_reason=after_result.reason,
    )

    return LanguageBlock(
        block_id=_format_block_id(order),
        audio_id=span.audio_id,
        start_seconds=span.segments[0].start,
        end_seconds=span.segments[-1].end,
        all_source_refs=all_source_refs,
        fr_source_refs=span.fr_source_refs,
        bridge_source_refs=span.bridge_source_refs,
        text=text,
        word_count=len(text.split()),
        segment_count=len(all_source_refs),
        fr_segment_count=len(fr_segments),
        structure=structure,
        candidate_direction=candidate_direction,
        english_before=before_result.context,
        english_after=after_result.context,
        phase_3a1_decisions=aggregated.decisions,
        phase_3a1_remove_refs=aggregated.remove_refs,
        phase_3a1_review_refs=aggregated.review_refs,
        phase_3a1_keep_refs=aggregated.keep_refs,
        phase_3a1_status=aggregated.status,
        already_resolved=already_resolved,
        needs_semantic_review=needs_semantic_review,
        semantic_review_status=semantic_review_status,
    )


def build_manifest(combined: CombinedSource, *, analysis_duration_seconds: float = 0.0) -> LanguageBlocksManifest:
    """Construit le manifeste complet à partir d'une source déjà fusionnée."""
    runs = build_runs(combined.segments)
    spans = build_block_spans(runs)

    valid_refs = frozenset(segment.src_id for segment in combined.segments)
    language_by_ref = {segment.src_id: segment.language for segment in combined.segments}

    blocks = tuple(
        _build_block(
            order,
            span,
            runs,
            valid_refs=valid_refs,
            language_by_ref=language_by_ref,
        )
        for order, span in enumerate(spans, start=1)
    )

    stats = compute_stats(combined, blocks, analysis_duration_seconds=analysis_duration_seconds)

    configuration = BlocksConfiguration(
        fr_gap_split_threshold_seconds=FR_GAP_SPLIT_THRESHOLD_SECONDS,
        bridge_max_run_segments=BRIDGE_MAX_RUN_SEGMENTS,
        bridge_max_words_per_segment=BRIDGE_MAX_WORDS_PER_SEGMENT,
        bridge_max_duration_seconds=BRIDGE_MAX_DURATION_SECONDS,
        bridge_max_total_gap_seconds=BRIDGE_MAX_TOTAL_GAP_SECONDS,
        context_window_max_block_skip=CONTEXT_WINDOW_MAX_BLOCK_SKIP,
        max_context_segments=MAX_CONTEXT_SEGMENTS,
        max_context_words=MAX_CONTEXT_WORDS,
        max_context_seconds=MAX_CONTEXT_SECONDS,
    )

    return LanguageBlocksManifest(
        transcript_id=combined.transcript_id,
        transcript_sha256=combined.transcript_sha256,
        language_cleanup_sha256=combined.language_cleanup_sha256,
        configuration=configuration,
        stats=stats,
        blocks=blocks,
    )


@dataclass(frozen=True)
class BlockAnalysisResult:
    """Résultat complet d'une analyse, prêt pour le rapport Phase 3A.1.1."""

    manifest: LanguageBlocksManifest
    combined: CombinedSource
    analysis_duration_seconds: float
    output_path: Path | None
    anthropic_calls: int = 0
    openai_calls: int = 0
    whisper_calls: int = 0
    other_network_calls: int = 0


def run_block_analysis(
    project_name: str,
    *,
    sortie_dir: Path | None = None,
    transcripts_dir: Path | None = None,
    language_cleanup_path: Path | None = None,
    output_path: Path | None = None,
    write: bool = True,
) -> BlockAnalysisResult:
    """
    Exécute l'analyse structurelle complète et publie le manifeste.

    `write=False` permet aux tests de calculer un manifeste sans toucher au
    disque (déterminisme : comparer deux manifestes en mémoire).
    """
    started = time.monotonic()

    combined = load_combined_source(
        project_name,
        sortie_dir=sortie_dir,
        transcripts_dir=transcripts_dir,
        language_cleanup_path=language_cleanup_path,
    )

    duration = round(time.monotonic() - started, 6)

    manifest = build_manifest(combined, analysis_duration_seconds=duration)

    path: Path | None = None
    if write:
        path = (
            Path(output_path)
            if output_path is not None
            else writer_module.manifest_path(project_name, sortie_dir=sortie_dir)
        )
        writer_module.write_manifest(path, manifest.to_dict())

    return BlockAnalysisResult(
        manifest=manifest,
        combined=combined,
        analysis_duration_seconds=duration,
        output_path=path,
    )
