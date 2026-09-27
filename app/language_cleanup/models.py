"""
Contrat de sortie de l'audit linguistique — language_cleanup.json.

Ce module décrit CE QUE LE MANIFESTE EST, rien d'autre : pas de lecture de
fichier, pas de détection, pas de correspondance. Même séparation que
app/transcript_models.py (contrat) / app/transcript_validator.py (jugement) /
app/language_cleanup/auditor.py (fabrication).

Aucun champ non déterministe (horodatage, UUID) n'apparaît dans ce contrat :
deux audits du même transcript_data.json, avec le même code, produisent un
language_cleanup.json identique octet pour octet (voir §27 du cahier des
charges).
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Version du contrat publié dans language_cleanup.json. Indépendante de
# app.transcript_models.SCHEMA_VERSION : deux contrats différents.
SCHEMA_VERSION = "1.0"

# ---------------------------------------------------------------------------
# Vocabulaires fermés
# ---------------------------------------------------------------------------

LANGUAGE_EN = "EN"
LANGUAGE_FR = "FR"
LANGUAGE_MIXED = "MIXED"
LANGUAGE_UNKNOWN = "UNKNOWN"

LANGUAGE_LABELS = (LANGUAGE_EN, LANGUAGE_FR, LANGUAGE_MIXED, LANGUAGE_UNKNOWN)

DECISION_KEEP = "KEEP"
DECISION_REMOVE_TRANSLATION = "REMOVE_TRANSLATION"
DECISION_REVIEW = "REVIEW"

DECISIONS = (DECISION_KEEP, DECISION_REMOVE_TRANSLATION, DECISION_REVIEW)

MATCH_BEFORE = "BEFORE"
MATCH_AFTER = "AFTER"
MATCH_BOTH = "BOTH"

MATCH_DIRECTIONS = (MATCH_BEFORE, MATCH_AFTER, MATCH_BOTH)


# ---------------------------------------------------------------------------
# Politique de l'audit
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AuditPolicy:
    """
    Règles déclarées de l'audit, recopiées dans le manifeste pour qu'un lecteur
    humain n'ait pas à retrouver les seuils dans le code.
    """

    target_language: str = "en"
    remove_only_verified_interpreter_translation: bool = True
    ambiguous_action: str = DECISION_REVIEW

    def to_dict(self) -> dict:
        return {
            "target_language": self.target_language,
            "remove_only_verified_interpreter_translation": (
                self.remove_only_verified_interpreter_translation
            ),
            "ambiguous_action": self.ambiguous_action,
        }


# ---------------------------------------------------------------------------
# Classification et correspondance (résultats intermédiaires, réutilisés par
# l'auditeur pour construire un SegmentAudit)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class LanguageClassification:
    """Résultat de language_detector.classify_text() pour un SRC."""

    language: str
    confidence: float
    reason: str

    def to_dict(self) -> dict:
        return {
            "language": self.language,
            "confidence": self.confidence,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class TranslationMatch:
    """
    Résultat de translation_matcher pour un bloc FR candidat.

    `matched_source_refs` est vide et `direction` est None lorsqu'aucune
    correspondance anglaise locale n'a été trouvée ou retenue.
    """

    matched_source_refs: tuple[str, ...]
    direction: str | None
    confidence: float
    reason: str

    def to_dict(self) -> dict:
        return {
            "matched_source_refs": list(self.matched_source_refs),
            "direction": self.direction,
            "confidence": self.confidence,
            "reason": self.reason,
        }


# ---------------------------------------------------------------------------
# Une ligne du manifeste
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SegmentAudit:
    """Une entrée de language_cleanup.json : un SRC et sa décision proposée."""

    source_ref: str
    audio_id: str
    start_seconds: float
    end_seconds: float
    text: str

    language: str
    language_confidence: float

    decision: str

    matched_english_source_refs: tuple[str, ...] = ()
    match_direction: str | None = None
    translation_confidence: float = 0.0

    reason: str = ""

    def to_dict(self) -> dict:
        return {
            "source_ref": self.source_ref,
            "audio_id": self.audio_id,
            "start_seconds": self.start_seconds,
            "end_seconds": self.end_seconds,
            "text": self.text,
            "language": self.language,
            "language_confidence": self.language_confidence,
            "decision": self.decision,
            "matched_english_source_refs": list(self.matched_english_source_refs),
            "match_direction": self.match_direction,
            "translation_confidence": self.translation_confidence,
            "reason": self.reason,
        }


# ---------------------------------------------------------------------------
# Statistiques (§20-21 du cahier des charges)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AuditStats:
    total_segments: int = 0

    EN_segments: int = 0
    FR_segments: int = 0
    MIXED_segments: int = 0
    UNKNOWN_segments: int = 0

    KEEP_segments: int = 0
    REMOVE_TRANSLATION_segments: int = 0
    REVIEW_segments: int = 0

    total_words: int = 0
    estimated_EN_words: int = 0
    estimated_FR_words: int = 0
    REMOVE_TRANSLATION_words: int = 0
    REVIEW_words: int = 0

    fr_matched_before: int = 0
    fr_matched_after: int = 0
    fr_matched_both: int = 0
    fr_unmatched: int = 0

    duration_EN: float = 0.0
    duration_FR: float = 0.0
    duration_MIXED: float = 0.0
    duration_UNKNOWN: float = 0.0
    duration_REMOVE_TRANSLATION: float = 0.0
    duration_REVIEW: float = 0.0

    audit_duration_seconds: float = 0.0

    def to_dict(self) -> dict:
        return {
            "total_segments": self.total_segments,
            "EN_segments": self.EN_segments,
            "FR_segments": self.FR_segments,
            "MIXED_segments": self.MIXED_segments,
            "UNKNOWN_segments": self.UNKNOWN_segments,
            "KEEP_segments": self.KEEP_segments,
            "REMOVE_TRANSLATION_segments": self.REMOVE_TRANSLATION_segments,
            "REVIEW_segments": self.REVIEW_segments,
            "total_words": self.total_words,
            "estimated_EN_words": self.estimated_EN_words,
            "estimated_FR_words": self.estimated_FR_words,
            "REMOVE_TRANSLATION_words": self.REMOVE_TRANSLATION_words,
            "REVIEW_words": self.REVIEW_words,
            "fr_matched_before": self.fr_matched_before,
            "fr_matched_after": self.fr_matched_after,
            "fr_matched_both": self.fr_matched_both,
            "fr_unmatched": self.fr_unmatched,
            "duration_EN": self.duration_EN,
            "duration_FR": self.duration_FR,
            "duration_MIXED": self.duration_MIXED,
            "duration_UNKNOWN": self.duration_UNKNOWN,
            "duration_REMOVE_TRANSLATION": self.duration_REMOVE_TRANSLATION,
            "duration_REVIEW": self.duration_REVIEW,
            "audit_duration_seconds": self.audit_duration_seconds,
        }


# ---------------------------------------------------------------------------
# Le manifeste complet
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AuditManifest:
    """
    language_cleanup.json — manifeste d'audit complet.

    `to_dict()` fixe l'ordre des clés : en-tête, politique, statistiques, puis
    segments. `audit_duration_seconds` vit dans `stats` mais est exclue de la
    signature canonique par `canonical_dict()` (voir §27 : le déterminisme ne
    porte jamais sur une mesure de temps d'exécution).
    """

    transcript_id: str
    transcript_sha256: str
    policy: AuditPolicy
    stats: AuditStats
    segments: tuple[SegmentAudit, ...] = field(default_factory=tuple)
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "transcript_id": self.transcript_id,
            "transcript_sha256": self.transcript_sha256,
            "policy": self.policy.to_dict(),
            "stats": self.stats.to_dict(),
            "segments": [segment.to_dict() for segment in self.segments],
        }

    def canonical_dict(self) -> dict:
        """
        Vue utilisée pour comparer deux audits (déterminisme, §27).

        Exclut `stats.audit_duration_seconds`, seul champ du manifeste qui
        dépend de la machine et de l'instant d'exécution plutôt que du contenu
        audité.
        """
        payload = self.to_dict()
        stats = dict(payload["stats"])
        stats.pop("audit_duration_seconds", None)
        payload["stats"] = stats
        return payload
