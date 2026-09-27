"""
Groupement TEMPORAIRE de SRC consécutifs de même langue classifiée.

Un Block n'existe que pour la durée de l'audit : il ne modifie, ne fusionne et
ne renumérote jamais les SRC (§8, §10 du cahier des charges). Il sert
uniquement à chercher une relation de traduction entre un groupe français et
son voisinage anglais immédiat.

Règle de groupement : deux SRC consécutifs (dans l'ordre canonique du
transcript) rejoignent le même bloc si et seulement si leur classification
porte exactement la même étiquette de langue (EN, FR, MIXED ou UNKNOWN). Un
changement d'étiquette — y compris vers MIXED ou UNKNOWN — ferme le bloc
courant et en ouvre un nouveau. Ce choix simple garantit qu'un bloc FR est
composé à 100 % de SRC classifiés FR : aucune notion de « bloc très
majoritairement FR » n'est nécessaire.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.language_cleanup.models import LanguageClassification
from app.language_cleanup.transcript_source import AuditSourceSegment


@dataclass(frozen=True)
class Block:
    """Bloc temporaire de SRC consécutifs partageant la même langue classifiée."""

    index: int
    language: str
    source_refs: tuple[str, ...]
    start_seconds: float
    end_seconds: float
    text: str
    word_count: int

    @property
    def duration_seconds(self) -> float:
        return max(0.0, self.end_seconds - self.start_seconds)


def build_blocks(
    segments: tuple[AuditSourceSegment, ...],
    classifications: tuple[LanguageClassification, ...],
) -> tuple[Block, ...]:
    """
    Construit les blocs consécutifs à partir des SRC classifiés, dans l'ordre
    canonique du transcript (celui de `segments`, jamais réordonné).
    """
    if len(segments) != len(classifications):
        raise ValueError(
            "segments et classifications doivent avoir la même longueur "
            f"({len(segments)} != {len(classifications)})"
        )

    blocks: list[Block] = []

    current_refs: list[str] = []
    current_texts: list[str] = []
    current_language: str | None = None
    current_start = 0.0
    current_end = 0.0

    def _flush() -> None:
        if not current_refs:
            return
        text = " ".join(current_texts)
        blocks.append(
            Block(
                index=len(blocks),
                language=current_language,
                source_refs=tuple(current_refs),
                start_seconds=current_start,
                end_seconds=current_end,
                text=text,
                word_count=len(text.split()),
            )
        )

    for segment, classification in zip(segments, classifications):
        if current_language is not None and classification.language == current_language:
            current_refs.append(segment.src_id)
            current_texts.append(segment.text)
            current_end = segment.end
            continue

        _flush()
        current_refs = [segment.src_id]
        current_texts = [segment.text]
        current_language = classification.language
        current_start = segment.start
        current_end = segment.end

    _flush()

    return tuple(blocks)
