"""
Auditor — orchestration de la Phase 3A.1.

Enchaînement, une responsabilité par étape, aucune d'elles implémentée ici :

    transcript_data.json
          ↓   transcript_source.load_audit_transcript          (lecture seule)
    AuditTranscript
          ↓   language_detector.classify_text (par SRC)
    LanguageClassification[]
          ↓   blocks.build_blocks                                (SRC -> blocs)
    Block[]
          ↓   translation_matcher.match_fr_block (blocs FR uniquement)
    BlockMatchCandidates
          ↓   décision (seuils documentés ci-dessous)
    SegmentAudit[]                                    (une entrée par SRC)
          ↓   models.AuditManifest
    language_cleanup.json                              (writer.py, atomique)

RÈGLE DE SÉCURITÉ (§14 du cahier des charges) : l'asymétrie est volontaire.
Un faux KEEP ou REVIEW est acceptable — il reste visible pour une révision
humaine. Un faux REMOVE_TRANSLATION est dangereux : les seuils ci-dessous sont
donc délibérément conservateurs, et le doute tranche toujours vers REVIEW.

CE MODULE N'EST BRANCHÉ NULLE PART AUTOMATIQUEMENT (comme
app/source_analysis/analyzer.py) : ni main.py, ni pipeline_runner.py ne
l'importent. Aucun appel réseau, aucun LLM, aucun appel Whisper.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

from app.language_cleanup import writer as writer_module
from app.language_cleanup.blocks import Block, build_blocks
from app.language_cleanup.language_detector import classify_text
from app.language_cleanup.models import (
    LANGUAGE_EN,
    LANGUAGE_FR,
    LANGUAGE_MIXED,
    LANGUAGE_UNKNOWN,
    MATCH_AFTER,
    MATCH_BEFORE,
    MATCH_BOTH,
    AuditManifest,
    AuditPolicy,
    AuditStats,
    LanguageClassification,
    SegmentAudit,
)
from app.language_cleanup.transcript_source import (
    AuditTranscript,
    AuditSourceSegment,
    load_audit_transcript,
    transcript_data_file,
)
from app.language_cleanup.translation_matcher import (
    BlockMatchCandidates,
    MatchScore,
    match_fr_block,
)

# ---------------------------------------------------------------------------
# Seuils de décision (§14, §16, §23 du cahier des charges) — DOCUMENTÉS ICI,
# nulle part ailleurs dans le code, pour qu'un futur audit (3A.2) les retrouve
# en un seul endroit.
# ---------------------------------------------------------------------------
#
# REMOVE_TRANSLATION exige les TROIS conditions à la fois :
#   - coverage   >= REMOVE_COVERAGE_THRESHOLD   (recouvrement lexical fort)
#   - matched    >= REMOVE_MIN_MATCHED_TOKENS   (pas une coïncidence sur 1 mot)
#   - confidence >= REMOVE_CONFIDENCE_THRESHOLD (score composite conservateur)
#
# En dessous, mais avec un signal non nul, REVIEW plutôt que KEEP : le doute
# reste visible pour un humain (§14). Sans aucun signal (coverage == 0 et
# aucun bloc anglais dans la fenêtre), KEEP : rien ne suggère une traduction.
REMOVE_COVERAGE_THRESHOLD = 0.55
REMOVE_MIN_MATCHED_TOKENS = 2
REMOVE_CONFIDENCE_THRESHOLD = 0.60

REVIEW_COVERAGE_THRESHOLD = 0.20
REVIEW_MIN_MATCHED_TOKENS = 1


def _qualifies_for_removal(score: MatchScore | None) -> bool:
    if score is None:
        return False
    return (
        score.coverage >= REMOVE_COVERAGE_THRESHOLD
        and score.matched_tokens >= REMOVE_MIN_MATCHED_TOKENS
        and score.confidence >= REMOVE_CONFIDENCE_THRESHOLD
    )


def _qualifies_for_review(score: MatchScore | None) -> bool:
    if score is None:
        return False
    return (
        score.coverage >= REVIEW_COVERAGE_THRESHOLD
        or score.matched_tokens >= REVIEW_MIN_MATCHED_TOKENS
    )


@dataclass(frozen=True)
class _BlockDecision:
    decision: str
    matched_english_source_refs: tuple[str, ...]
    match_direction: str | None
    translation_confidence: float
    reason: str


def _decide_fr_block(candidates: BlockMatchCandidates) -> _BlockDecision:
    before_qualifies = _qualifies_for_removal(candidates.before_score)
    after_qualifies = _qualifies_for_removal(candidates.after_score)

    if before_qualifies and after_qualifies:
        refs = candidates.before_block.source_refs + candidates.after_block.source_refs
        # Confiance combinée = le MINIMUM des deux, jamais la moyenne ni le
        # maximum : la sécurité asymétrique (§14) interdit qu'une bonne
        # correspondance d'un côté compense une correspondance plus faible de
        # l'autre pour franchir le seuil de suppression.
        confidence = round(min(candidates.before_score.confidence, candidates.after_score.confidence), 2)
        return _BlockDecision(
            decision="REMOVE_TRANSLATION",
            matched_english_source_refs=refs,
            match_direction=MATCH_BOTH,
            translation_confidence=confidence,
            reason=(
                "correspondance anglaise locale des deux côtés : avant "
                f"({candidates.before_score.reason}) et après "
                f"({candidates.after_score.reason})"
            ),
        )

    if before_qualifies:
        return _BlockDecision(
            decision="REMOVE_TRANSLATION",
            matched_english_source_refs=candidates.before_block.source_refs,
            match_direction=MATCH_BEFORE,
            translation_confidence=candidates.before_score.confidence,
            reason=f"correspondance anglaise avant le bloc FR : {candidates.before_score.reason}",
        )

    if after_qualifies:
        return _BlockDecision(
            decision="REMOVE_TRANSLATION",
            matched_english_source_refs=candidates.after_block.source_refs,
            match_direction=MATCH_AFTER,
            translation_confidence=candidates.after_score.confidence,
            reason=f"correspondance anglaise après le bloc FR : {candidates.after_score.reason}",
        )

    # Aucun candidat n'atteint le seuil de suppression : REVIEW si un signal
    # partiel existe malgré tout, KEEP sinon (§14 : le doute va vers REVIEW,
    # jamais vers REMOVE_TRANSLATION).
    best = candidates.best_single

    if best is None:
        return _BlockDecision(
            decision="KEEP",
            matched_english_source_refs=(),
            match_direction=None,
            translation_confidence=0.0,
            reason="aucun bloc anglais dans la fenêtre locale documentée (§11)",
        )

    direction, block, score = best

    if _qualifies_for_review(score):
        return _BlockDecision(
            decision="REVIEW",
            matched_english_source_refs=block.source_refs,
            match_direction=direction,
            translation_confidence=score.confidence,
            reason=(
                "signal de traduction partiel, sous le seuil de suppression "
                f"conservateur : {score.reason}"
            ),
        )

    return _BlockDecision(
        decision="KEEP",
        matched_english_source_refs=(),
        match_direction=None,
        translation_confidence=score.confidence,
        reason=(
            "bloc anglais présent dans la fenêtre locale mais aucune relation "
            f"de traduction démontrée : {score.reason}"
        ),
    )


@dataclass(frozen=True)
class AuditRunResult:
    """Résultat complet d'un audit, prêt pour le rapport Phase 3A.1."""

    manifest: AuditManifest
    transcript: AuditTranscript
    audit_duration_seconds: float
    output_path: Path | None
    anthropic_calls: int = 0
    openai_calls: int = 0
    whisper_calls: int = 0
    other_network_calls: int = 0


def run_audit(
    project_name: str,
    *,
    sortie_dir: Path | None = None,
    transcripts_dir: Path | None = None,
    output_path: Path | None = None,
    write: bool = True,
) -> AuditRunResult:
    """
    Exécute l'audit linguistique complet sur un projet et publie le manifeste.

    `write=False` permet aux tests de calculer un manifeste sans toucher au
    disque (utile pour le contrôle de déterminisme : comparer deux manifestes
    en mémoire est plus direct que comparer deux fichiers).
    """
    started = time.monotonic()

    source_path = (
        Path(transcripts_dir) / "transcript_data.json"
        if transcripts_dir is not None
        else transcript_data_file(project_name, sortie_dir=sortie_dir)
    )

    transcript = load_audit_transcript(source_path, project_name=project_name)

    classifications = tuple(classify_text(segment.text) for segment in transcript.segments)
    blocks = build_blocks(transcript.segments, classifications)

    segment_audits = _build_segment_audits(transcript.segments, classifications, blocks)

    duration = round(time.monotonic() - started, 6)

    stats = _compute_stats(segment_audits, duration)

    manifest = AuditManifest(
        transcript_id=transcript.transcript_id,
        transcript_sha256=transcript.content_sha256,
        policy=AuditPolicy(),
        stats=stats,
        segments=segment_audits,
    )

    path: Path | None = None
    if write:
        path = (
            Path(output_path)
            if output_path is not None
            else writer_module.manifest_path(project_name, sortie_dir=sortie_dir)
        )
        writer_module.write_manifest(path, manifest.to_dict())

    return AuditRunResult(
        manifest=manifest,
        transcript=transcript,
        audit_duration_seconds=duration,
        output_path=path,
    )


def _build_segment_audits(
    segments: tuple[AuditSourceSegment, ...],
    classifications: tuple[LanguageClassification, ...],
    blocks: tuple[Block, ...],
) -> tuple[SegmentAudit, ...]:
    decisions_by_src: dict[str, _BlockDecision] = {}

    for index, block in enumerate(blocks):
        if block.language == LANGUAGE_EN:
            decision = _BlockDecision(
                decision="KEEP",
                matched_english_source_refs=(),
                match_direction=None,
                translation_confidence=0.0,
                reason="anglais : langue cible, conservé tel quel",
            )
        elif block.language == LANGUAGE_UNKNOWN:
            decision = _BlockDecision(
                decision="KEEP",
                matched_english_source_refs=(),
                match_direction=None,
                translation_confidence=0.0,
                reason=(
                    "langue indéterminée (signal grammatical insuffisant) : "
                    "aucune suppression proposée par principe de conservation"
                ),
            )
        elif block.language == LANGUAGE_MIXED:
            decision = _BlockDecision(
                decision="REVIEW",
                matched_english_source_refs=(),
                match_direction=None,
                translation_confidence=0.0,
                reason=(
                    "segment MIXED : révision humaine par défaut (§17), jamais "
                    "de suppression automatique"
                ),
            )
        else:  # LANGUAGE_FR
            candidates = match_fr_block(blocks, index)
            decision = _decide_fr_block(candidates)

        for src_id in block.source_refs:
            decisions_by_src[src_id] = decision

    audits: list[SegmentAudit] = []

    for segment, classification in zip(segments, classifications):
        decision = decisions_by_src[segment.src_id]
        audits.append(
            SegmentAudit(
                source_ref=segment.src_id,
                audio_id=segment.source_id,
                start_seconds=segment.start,
                end_seconds=segment.end,
                text=segment.text,
                language=classification.language,
                language_confidence=classification.confidence,
                decision=decision.decision,
                matched_english_source_refs=decision.matched_english_source_refs,
                match_direction=decision.match_direction,
                translation_confidence=decision.translation_confidence,
                reason=decision.reason,
            )
        )

    return tuple(audits)


def _compute_stats(segments: tuple[SegmentAudit, ...], audit_duration_seconds: float) -> AuditStats:
    counters = {
        "total_segments": len(segments),
        "EN_segments": 0,
        "FR_segments": 0,
        "MIXED_segments": 0,
        "UNKNOWN_segments": 0,
        "KEEP_segments": 0,
        "REMOVE_TRANSLATION_segments": 0,
        "REVIEW_segments": 0,
        "total_words": 0,
        "estimated_EN_words": 0,
        "estimated_FR_words": 0,
        "REMOVE_TRANSLATION_words": 0,
        "REVIEW_words": 0,
        "fr_matched_before": 0,
        "fr_matched_after": 0,
        "fr_matched_both": 0,
        "fr_unmatched": 0,
    }
    durations = {
        "duration_EN": 0.0,
        "duration_FR": 0.0,
        "duration_MIXED": 0.0,
        "duration_UNKNOWN": 0.0,
        "duration_REMOVE_TRANSLATION": 0.0,
        "duration_REVIEW": 0.0,
    }

    for segment in segments:
        word_count = len(segment.text.split())
        duration = max(0.0, segment.end_seconds - segment.start_seconds)

        counters["total_words"] += word_count

        counters[f"{segment.language}_segments"] += 1
        durations[f"duration_{segment.language}"] += duration

        if segment.language == LANGUAGE_EN:
            counters["estimated_EN_words"] += word_count
        elif segment.language == LANGUAGE_FR:
            counters["estimated_FR_words"] += word_count

        counters[f"{segment.decision}_segments"] += 1

        if segment.decision == "REMOVE_TRANSLATION":
            counters["REMOVE_TRANSLATION_words"] += word_count
            durations["duration_REMOVE_TRANSLATION"] += duration
        elif segment.decision == "REVIEW":
            counters["REVIEW_words"] += word_count
            durations["duration_REVIEW"] += duration

        if segment.language == LANGUAGE_FR:
            if segment.match_direction == MATCH_BEFORE:
                counters["fr_matched_before"] += 1
            elif segment.match_direction == MATCH_AFTER:
                counters["fr_matched_after"] += 1
            elif segment.match_direction == MATCH_BOTH:
                counters["fr_matched_both"] += 1
            else:
                counters["fr_unmatched"] += 1

    return AuditStats(
        total_segments=counters["total_segments"],
        EN_segments=counters["EN_segments"],
        FR_segments=counters["FR_segments"],
        MIXED_segments=counters["MIXED_segments"],
        UNKNOWN_segments=counters["UNKNOWN_segments"],
        KEEP_segments=counters["KEEP_segments"],
        REMOVE_TRANSLATION_segments=counters["REMOVE_TRANSLATION_segments"],
        REVIEW_segments=counters["REVIEW_segments"],
        total_words=counters["total_words"],
        estimated_EN_words=counters["estimated_EN_words"],
        estimated_FR_words=counters["estimated_FR_words"],
        REMOVE_TRANSLATION_words=counters["REMOVE_TRANSLATION_words"],
        REVIEW_words=counters["REVIEW_words"],
        fr_matched_before=counters["fr_matched_before"],
        fr_matched_after=counters["fr_matched_after"],
        fr_matched_both=counters["fr_matched_both"],
        fr_unmatched=counters["fr_unmatched"],
        duration_EN=round(durations["duration_EN"], 3),
        duration_FR=round(durations["duration_FR"], 3),
        duration_MIXED=round(durations["duration_MIXED"], 3),
        duration_UNKNOWN=round(durations["duration_UNKNOWN"], 3),
        duration_REMOVE_TRANSLATION=round(durations["duration_REMOVE_TRANSLATION"], 3),
        duration_REVIEW=round(durations["duration_REVIEW"], 3),
        audit_duration_seconds=audit_duration_seconds,
    )
