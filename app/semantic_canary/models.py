"""
Vocabulaire fermé et structures de données du canary sémantique.

Ce module décrit CE QUE LE CANARY EST (constantes, dataclasses, to_dict),
sans logique de sélection, de prompt ou de validation — cette dernière vit
dans selection.py / prompt.py / validator.py, comme le fait déjà
app/language_blocks/models.py pour la Phase 3A.1.1.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

SCHEMA_VERSION = "1.0"

# ---------------------------------------------------------------------------
# Vocabulaire fermé — classification (§3)
# ---------------------------------------------------------------------------

CLASSIFICATION_TRANSLATION_BEFORE = "TRANSLATION_BEFORE"
CLASSIFICATION_TRANSLATION_AFTER = "TRANSLATION_AFTER"
CLASSIFICATION_NOT_TRANSLATION = "NOT_TRANSLATION"
CLASSIFICATION_UNCERTAIN = "UNCERTAIN"

CLASSIFICATIONS = (
    CLASSIFICATION_TRANSLATION_BEFORE,
    CLASSIFICATION_TRANSLATION_AFTER,
    CLASSIFICATION_NOT_TRANSLATION,
    CLASSIFICATION_UNCERTAIN,
)

DIRECTION_BEFORE = "BEFORE"
DIRECTION_AFTER = "AFTER"
DIRECTION_NONE = "NONE"

MATCHED_DIRECTIONS = (DIRECTION_BEFORE, DIRECTION_AFTER, DIRECTION_NONE)

# Correspondance imposée classification -> matched_direction (§18).
EXPECTED_DIRECTION_FOR_CLASSIFICATION = {
    CLASSIFICATION_TRANSLATION_BEFORE: DIRECTION_BEFORE,
    CLASSIFICATION_TRANSLATION_AFTER: DIRECTION_AFTER,
    CLASSIFICATION_NOT_TRANSLATION: DIRECTION_NONE,
    CLASSIFICATION_UNCERTAIN: DIRECTION_NONE,
}

# ---------------------------------------------------------------------------
# Groupes de sélection locaux (§13, §23) — JAMAIS envoyés au modèle (§15)
# ---------------------------------------------------------------------------

GROUP_CONTROL_RESOLVED = "CONTROL_RESOLVED"
GROUP_REVIEW = "REVIEW"
GROUP_KEEP = "KEEP"
GROUP_ATYPICAL = "ATYPICAL"

SELECTION_GROUPS = (
    GROUP_CONTROL_RESOLVED,
    GROUP_REVIEW,
    GROUP_KEEP,
    GROUP_ATYPICAL,
)

# Taille cible par groupe (§13).
TARGET_GROUP_SIZE = 5
TARGET_TOTAL_SIZE = 20


# ---------------------------------------------------------------------------
# Un bloc sélectionné (métadonnées locales, §14) — pas encore le payload
# envoyé au modèle (voir payload.py pour la vue sanitisée, §15-16).
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SelectedBlock:
    """
    Un bloc retenu pour le canary, avec sa provenance LOCALE.

    `raw_block` est le dict brut de language_blocks.json : toutes les
    informations utiles à l'inspection humaine (§25) et à la comparaison
    après-coup (§22-24) en proviennent, mais seul un sous-ensemble sanitisé
    (payload.py) part réellement dans la requête réseau.
    """

    block_id: str
    selection_group: str
    selection_reason: str
    raw_block: dict[str, Any] = field(default_factory=dict)

    @property
    def audio_id(self) -> str:
        return str(self.raw_block.get("audio_id", ""))

    @property
    def structure(self) -> str:
        return str(self.raw_block.get("structure", ""))

    @property
    def candidate_direction(self) -> str:
        return str(self.raw_block.get("candidate_direction", ""))

    @property
    def semantic_review_status(self) -> str:
        return str(self.raw_block.get("semantic_review_status", ""))

    @property
    def fr_source_refs(self) -> list[str]:
        return list(self.raw_block.get("fr_source_refs") or [])

    @property
    def fr_word_count(self) -> int:
        return int(self.raw_block.get("word_count", 0))

    @property
    def english_before(self) -> dict | None:
        return self.raw_block.get("english_before")

    @property
    def english_after(self) -> dict | None:
        return self.raw_block.get("english_after")

    def control_summary(self) -> dict:
        """
        Vue de contrôle affichée AVANT l'appel réseau (§14) : les champs
        listés par le cahier des charges, rien de plus.
        """
        before = self.english_before
        after = self.english_after

        return {
            "block_id": self.block_id,
            "audio_id": self.audio_id,
            "structure": self.structure,
            "candidate_direction": self.candidate_direction,
            "fr_source_refs": self.fr_source_refs,
            "fr_word_count": self.fr_word_count,
            "phase_3a1_status": self.raw_block.get("phase_3a1_status"),
            "semantic_review_status": self.semantic_review_status,
            "english_before_word_count": (before or {}).get("word_count"),
            "english_after_word_count": (after or {}).get("word_count"),
            "selection_group": self.selection_group,
            "selection_reason": self.selection_reason,
        }


# ---------------------------------------------------------------------------
# Un résultat de classification (réponse du modèle, décodée) — §18-19
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CanaryClassification:
    """Une ligne de `results[]`, déjà validée localement (validator.py)."""

    block_id: str
    classification: str
    matched_direction: str
    confidence: float
    reason: str

    def to_dict(self) -> dict:
        return {
            "block_id": self.block_id,
            "classification": self.classification,
            "matched_direction": self.matched_direction,
            "confidence": self.confidence,
            "reason": self.reason,
        }
