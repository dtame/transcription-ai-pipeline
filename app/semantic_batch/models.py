"""
Vocabulaire et structures propres à la Phase 3A.1.2B.

Le vocabulaire fermé de classification (TRANSLATION_BEFORE, TRANSLATION_AFTER,
NOT_TRANSLATION, UNCERTAIN, matched_direction) et la structure
`CanaryClassification` / `SelectedBlock` restent ceux de
app.semantic_canary.models : réexportés ici, jamais redéfinis (§10) — une
classification produite par un lot de cette phase doit être structurellement
identique à celle produite par le canary.
"""

from __future__ import annotations

from dataclasses import dataclass

# Réexports explicites (§10) : ce module ne redéfinit jamais ce vocabulaire.
from app.semantic_canary.models import (  # noqa: F401
    CLASSIFICATION_NOT_TRANSLATION,
    CLASSIFICATION_TRANSLATION_AFTER,
    CLASSIFICATION_TRANSLATION_BEFORE,
    CLASSIFICATION_UNCERTAIN,
    CLASSIFICATIONS,
    DIRECTION_AFTER,
    DIRECTION_BEFORE,
    DIRECTION_NONE,
    EXPECTED_DIRECTION_FOR_CLASSIFICATION,
    MATCHED_DIRECTIONS,
    CanaryClassification,
    SelectedBlock,
)

SCHEMA_VERSION = "1.0"

# §13-14, §17 : taille maximale d'un lot. Validée par le canary (Phase
# 3A.1.2A) — ne jamais augmenter uniquement pour économiser des appels (§14).
MAX_BLOCKS_PER_BATCH = 20

STATUS_NEEDED = "NEEDED"
STATUS_ALREADY_RESOLVED = "ALREADY_RESOLVED"
STATUS_NO_ENGLISH_CONTEXT = "NO_ENGLISH_CONTEXT"

TRANSLATION_CLASSIFICATIONS = frozenset(
    {CLASSIFICATION_TRANSLATION_BEFORE, CLASSIFICATION_TRANSLATION_AFTER}
)


def batch_id_for_index(index: int) -> str:
    """BATCH001, BATCH002, ... — `index` est 1-based (§17)."""
    if index < 1:
        raise ValueError(f"batch_id_for_index : index doit être >= 1 : {index}")

    return f"BATCH{index:03d}"


@dataclass(frozen=True)
class BatchPlanItem:
    """Un lot planifié EN MÉMOIRE, avant tout appel réseau (§17)."""

    batch_id: str
    blocks: tuple[SelectedBlock, ...]
    estimated_input_tokens: int

    @property
    def block_ids(self) -> list[str]:
        return [block.block_id for block in self.blocks]

    @property
    def block_count(self) -> int:
        return len(self.blocks)

    def to_plan_summary(self) -> dict:
        """Vue minimale du lot (§17) : batch_id, block_ids, block_count, estimation."""
        return {
            "batch_id": self.batch_id,
            "block_ids": self.block_ids,
            "block_count": self.block_count,
            "estimated_input_tokens": self.estimated_input_tokens,
        }
