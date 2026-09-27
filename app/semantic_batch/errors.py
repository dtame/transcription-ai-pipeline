"""
Erreurs de la Phase 3A.1.2B — classification sémantique par lots.

Ce module NE duplique PAS les erreurs de app.semantic_canary.errors : les
étapes déjà réutilisées telles quelles (sanitisation du payload, validation
stricte d'une réponse, préflight, garde-fou d'un appel réel) lèvent toujours
leurs erreurs canary d'origine — importées par les appelants, jamais
recopiées ici. Les erreurs ci-dessous couvrent uniquement ce qui est NOUVEAU
dans cette phase : population complète, planification par lots,
cache/reprise, intégrité élargie à 4 artefacts.
"""

from __future__ import annotations


class SemanticBatchError(RuntimeError):
    """Base des erreurs de la Phase 3A.1.2B."""


class SourceIntegrityError(SemanticBatchError):
    """
    Une des 4 sources protégées (transcript_data.json, language_cleanup.json,
    language_blocks.json, semantic_translation_canary.json) est absente,
    illisible, ou incohérente avec les autres. STOP AVANT RÉSEAU (§8-9).
    """


class BatchPlanError(SemanticBatchError):
    """
    Le plan de lots ne couvre pas exactement la population NEEDED attendue :
    doublon, omission, lot vide, lot trop grand, IDs non séquentiels (§17).
    STOP AVANT RÉSEAU.
    """


class CacheSignatureMismatchError(SemanticBatchError):
    """
    Un fichier de lot existe déjà mais ne correspond pas exactement à ce qui
    serait rejoué (signature, hashes, prompt_version, provider/model, ou
    résultats en cache invalides) (§19-20). Ne JAMAIS écraser silencieusement
    un résultat existant incompatible : STOP.
    """


class BatchExecutionError(SemanticBatchError):
    """Un lot a échoué à l'appel réseau ou à la validation locale (§21, §23)."""
