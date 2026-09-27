"""
Sélection historique exacte SRC003799–SRC003808.

Aucun repli. Si l'extrait 3B.4.1 / 3B.4.3 n'est plus reproductible : STOP.
"""

from __future__ import annotations

from app.source_analysis.transcript_input import SourceSegment
from app.source_analysis_ultra_compact_canary.selection import (
    CanarySelection,
    validate_selection,
)
from app.source_analysis_vocabulary_compliance_canary import constants as canary_constants
from app.source_analysis_vocabulary_compliance_canary.constants import (
    SELECTION_RULE_HISTORICAL,
)
from app.source_analysis_vocabulary_compliance_canary.errors import (
    HistoricalInputUnavailable,
)


def historical_window_available(
    segments: tuple[SourceSegment, ...] | list[SourceSegment],
    *,
    expected_ids: tuple[str, ...] | None = None,
) -> bool:
    """True si les SRC historiques sont tous présents, non vides et contigus."""
    expected = expected_ids if expected_ids is not None else canary_constants.HISTORICAL_SRC_IDS
    by_id = {segment.src_id: segment for segment in segments}
    if any(src_id not in by_id for src_id in expected):
        return False

    chosen = [by_id[src_id] for src_id in expected]
    if any(not str(segment.text).strip() for segment in chosen):
        return False
    if any(not str(segment.src_id).startswith("SRC") for segment in chosen):
        return False

    order = {segment.src_id: index for index, segment in enumerate(segments)}
    positions = [order[src_id] for src_id in expected]
    return positions == list(range(positions[0], positions[0] + len(positions)))


def select_historical_canary_segments(
    segments: tuple[SourceSegment, ...] | list[SourceSegment],
) -> CanarySelection:
    """
    Exige le passage historique. Ne choisit jamais un autre extrait.
    """
    pool = tuple(segments)
    expected = canary_constants.HISTORICAL_SRC_IDS
    if not historical_window_available(pool, expected_ids=expected):
        present = {segment.src_id for segment in pool}
        missing = [src_id for src_id in expected if src_id not in present]
        raise HistoricalInputUnavailable(
            "L'extrait historique SRC003799–SRC003808 n'est plus reproductible "
            "exactement. STOP pour revue. "
            f"SRC manquants : {missing or '(fenêtre non contiguë ou texte vide)'}."
        )

    by_id = {segment.src_id: segment for segment in pool}
    chosen = tuple(by_id[src_id] for src_id in expected)
    selection = CanarySelection(
        segments=chosen,
        selection_rule=SELECTION_RULE_HISTORICAL,
    )
    validate_selection(selection, expected_ids=expected)
    return selection


def canary_source_set(selection: CanarySelection) -> frozenset[str]:
    return frozenset(selection.source_ids)
