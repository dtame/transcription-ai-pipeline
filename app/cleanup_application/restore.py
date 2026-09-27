"""
Réversibilité : merge(clean SRC + removed snapshots) selon original_index
doit reconstituer la séquence originale (IDs, ordre, texte, audio_id,
timestamps).
"""

from __future__ import annotations

from app.cleanup_application.errors import ReversibilityError
from app.cleanup_application.models import RemovalSnapshot
from app.transcript_models import TranscriptDocument, TranscriptSegment


def restore_segments(
    original: TranscriptDocument,
    clean: TranscriptDocument,
    removed: tuple[RemovalSnapshot, ...] | list[RemovalSnapshot],
) -> list[TranscriptSegment]:
    """
    Reconstitue la séquence originale à partir du clean + des snapshots.

    `original_index` est 0-based dans le tableau original `segments`.
    """
    restored: list[TranscriptSegment | None] = [None] * len(original.segments)
    used_clean: set[str] = set()
    used_removed: set[str] = set()

    for snapshot in removed:
        if snapshot.original_index < 0 or snapshot.original_index >= len(restored):
            raise ReversibilityError(
                f"{snapshot.source_ref} : original_index {snapshot.original_index} hors bornes."
            )
        if restored[snapshot.original_index] is not None:
            raise ReversibilityError(
                f"original_index {snapshot.original_index} occupé deux fois."
            )
        restored[snapshot.original_index] = TranscriptSegment(
            id=snapshot.source_ref,
            source_id=snapshot.audio_id,
            source_order=snapshot.source_order,
            start=snapshot.start,
            end=snapshot.end,
            text=snapshot.text,
        )
        used_removed.add(snapshot.source_ref)

    original_by_id = {segment.id: (index, segment) for index, segment in enumerate(original.segments)}

    for segment in clean.segments:
        if segment.id not in original_by_id:
            raise ReversibilityError(f"SRC clean inattendu : {segment.id}")
        index, _ = original_by_id[segment.id]
        if restored[index] is not None:
            raise ReversibilityError(
                f"{segment.id} : collision entre clean et snapshot à l'index {index}."
            )
        restored[index] = segment
        used_clean.add(segment.id)

    missing = [index for index, item in enumerate(restored) if item is None]
    if missing:
        raise ReversibilityError(f"Index originaux non reconstitués : {missing}.")

    return [item for item in restored if item is not None]


def assert_reversible(
    original: TranscriptDocument,
    clean: TranscriptDocument,
    removed: tuple[RemovalSnapshot, ...] | list[RemovalSnapshot],
) -> None:
    restored = restore_segments(original, clean, removed)
    errors: list[str] = []

    if len(restored) != len(original.segments):
        errors.append(
            f"longueur restaurée {len(restored)} ≠ originale {len(original.segments)}"
        )

    for index, (got, expected) in enumerate(zip(restored, original.segments)):
        if got.id != expected.id:
            errors.append(f"index {index} : id {got.id} ≠ {expected.id}")
        if got.source_id != expected.source_id:
            errors.append(
                f"{expected.id} : audio_id {got.source_id} ≠ {expected.source_id}"
            )
        if got.start != expected.start or got.end != expected.end:
            errors.append(
                f"{expected.id} : timestamps ({got.start}, {got.end}) ≠ "
                f"({expected.start}, {expected.end})"
            )
        if got.text != expected.text:
            errors.append(f"{expected.id} : texte survivant/restauré différent de l'original")

    if errors:
        raise ReversibilityError(
            "restore(clean + removed) ≠ original : " + " | ".join(errors[:20])
        )
