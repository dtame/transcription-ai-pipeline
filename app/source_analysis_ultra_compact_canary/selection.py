"""
Sélection déterministe d'un petit extrait clean pour le canary 3B.4.3.

Préfère le passage 3B.4.1 (SRC003799–SRC003808) s'il est encore présent.
Aucun appel IA. Le texte n'est ni réécrit, ni traduit, ni fusionné.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.language_cleanup.language_detector import classify_text
from app.language_cleanup.models import LANGUAGE_EN, LANGUAGE_FR, LANGUAGE_UNKNOWN
from app.source_analysis.transcript_input import SourceSegment
from app.source_analysis_ultra_compact_canary.constants import (
    HISTORICAL_SRC_IDS,
    MAX_SRC,
    MAX_WORDS,
    MIN_SEGMENT_WORDS,
    MIN_SRC,
    MIN_WORDS,
    PREFERRED_MAX_SRC,
    SELECTION_RULE_FALLBACK,
    SELECTION_RULE_HISTORICAL,
    TARGET_WORDS,
)
from app.source_analysis_ultra_compact_canary.errors import SelectionError

_FILLER_RE = re.compile(
    r"^(uh+|um+|hmm+|euh+|ah+|oh+|mm+|mhm+|okay|ok|yes|yeah|amen|bon|voilà|"
    r"right|so|well)\.?$",
    re.IGNORECASE,
)
_LETTER_RE = re.compile(r"[A-Za-zÀ-ÿ]")


@dataclass(frozen=True)
class CanarySelection:
    """Fenêtre déterministe extraite du transcript clean."""

    segments: tuple[SourceSegment, ...]
    selection_rule: str

    @property
    def source_ids(self) -> tuple[str, ...]:
        return tuple(segment.src_id for segment in self.segments)

    @property
    def segment_count(self) -> int:
        return len(self.segments)

    @property
    def word_count(self) -> int:
        return sum(segment.word_count for segment in self.segments)

    def texts_unchanged(self, original_by_id: dict[str, str]) -> bool:
        return all(
            segment.text == original_by_id.get(segment.src_id)
            for segment in self.segments
        )


def is_eligible_canary_segment(segment: SourceSegment) -> bool:
    """True si le SRC est un candidat anglais substantiel."""
    text = (segment.text or "").strip()
    if not text or not _LETTER_RE.search(text):
        return False
    if segment.word_count < MIN_SEGMENT_WORDS:
        return False
    if _FILLER_RE.match(text):
        return False

    classification = classify_text(text)
    if classification.language in {LANGUAGE_FR, LANGUAGE_UNKNOWN}:
        return False
    return classification.language == LANGUAGE_EN


def historical_window_available(
    segments: tuple[SourceSegment, ...] | list[SourceSegment],
) -> bool:
    """True si les SRC 3B.4.1 sont tous présents et forment un extrait cohérent."""
    by_id = {segment.src_id: segment for segment in segments}
    if any(src_id not in by_id for src_id in HISTORICAL_SRC_IDS):
        return False

    chosen = [by_id[src_id] for src_id in HISTORICAL_SRC_IDS]
    if any(not str(segment.text).strip() for segment in chosen):
        return False
    if any(not str(segment.src_id).startswith("SRC") for segment in chosen):
        return False

    order = {segment.src_id: index for index, segment in enumerate(segments)}
    positions = [order[src_id] for src_id in HISTORICAL_SRC_IDS]
    return positions == list(range(positions[0], positions[0] + len(positions)))


def select_canary_segments(
    segments: tuple[SourceSegment, ...] | list[SourceSegment],
) -> CanarySelection:
    """
    Passage 3B.4.1 si encore présent, sinon première fenêtre EN contiguë.

    Lève SelectionError si aucune fenêtre ne respecte les bornes.
    """
    pool = tuple(segments)
    if not pool:
        raise SelectionError("Aucun segment clean disponible pour le canary.")

    if historical_window_available(pool):
        by_id = {segment.src_id: segment for segment in pool}
        chosen = tuple(by_id[src_id] for src_id in HISTORICAL_SRC_IDS)
        selection = CanarySelection(
            segments=chosen,
            selection_rule=SELECTION_RULE_HISTORICAL,
        )
        validate_selection(selection, expected_ids=HISTORICAL_SRC_IDS)
        return selection

    return _select_fallback_window(pool)


def _select_fallback_window(pool: tuple[SourceSegment, ...]) -> CanarySelection:
    eligible = [is_eligible_canary_segment(segment) for segment in pool]
    index = 0

    while index < len(pool):
        if not eligible[index]:
            index += 1
            continue

        end = index
        while end < len(pool) and eligible[end]:
            end += 1

        window = _cut_window(pool[index:end])
        if window is not None:
            selection = CanarySelection(
                segments=window,
                selection_rule=SELECTION_RULE_FALLBACK,
            )
            validate_selection(selection, expected_ids=selection.source_ids)
            return selection
        index = end

    raise SelectionError(
        "Aucune fenêtre clean anglaise contiguë ne satisfait les bornes "
        f"({MIN_SRC}–{MAX_SRC} SRC, {MIN_WORDS}–{MAX_WORDS} mots) "
        "et le passage 3B.4.1 n'est plus disponible."
    )


def _cut_window(run: tuple[SourceSegment, ...]) -> tuple[SourceSegment, ...] | None:
    if not run:
        return None

    chosen: list[SourceSegment] = []
    words = 0
    for segment in run:
        if len(chosen) >= MAX_SRC:
            break
        next_words = words + segment.word_count
        if next_words > MAX_WORDS and chosen:
            break
        chosen.append(segment)
        words = next_words
        if MIN_SRC <= len(chosen) <= PREFERRED_MAX_SRC and words >= TARGET_WORDS:
            return tuple(chosen)
        if len(chosen) == PREFERRED_MAX_SRC and words >= MIN_WORDS:
            return tuple(chosen)

    if not chosen or len(chosen) < MIN_SRC or words > MAX_WORDS:
        return None
    if words >= MIN_WORDS:
        return tuple(chosen)
    return None


def validate_selection(
    selection: CanarySelection,
    *,
    expected_ids: tuple[str, ...] | None = None,
) -> None:
    """Contrôles locaux AVANT réseau : bornes, IDs réels, texte non vide."""
    errors: list[str] = []
    historical = selection.selection_rule == SELECTION_RULE_HISTORICAL

    if selection.segment_count < MIN_SRC:
        errors.append(
            f"{selection.segment_count} SRC sélectionné(s), minimum {MIN_SRC}."
        )
    if selection.segment_count > MAX_SRC:
        errors.append(
            f"{selection.segment_count} SRC sélectionné(s), maximum {MAX_SRC}."
        )
    if selection.word_count > MAX_WORDS:
        errors.append(f"{selection.word_count} mot(s), maximum {MAX_WORDS}.")
    if not historical and selection.word_count < MIN_WORDS:
        errors.append(f"{selection.word_count} mot(s), minimum {MIN_WORDS}.")

    ids = selection.source_ids
    if len(set(ids)) != len(ids):
        errors.append(f"SRC dupliqués dans la sélection : {ids}.")

    if expected_ids is not None and ids != expected_ids:
        errors.append("Les SRC sélectionnés ne correspondent pas aux IDs attendus.")

    for segment in selection.segments:
        if not str(segment.src_id).startswith("SRC"):
            errors.append(f"identifiant non-SRC : {segment.src_id}.")
        if not str(segment.text).strip():
            errors.append(f"{segment.src_id} : texte vide.")

    if errors:
        raise SelectionError(
            "Sélection canary invalide, STOP AVANT RÉSEAU : " + " | ".join(errors)
        )
