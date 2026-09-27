"""Erreurs du canary sémantique FR <-> EN (Phase 3A.1.2A)."""

from __future__ import annotations


class SemanticCanaryError(RuntimeError):
    """Base des erreurs du canary sémantique."""


class SourceIntegrityError(SemanticCanaryError):
    """
    Les trois sources (transcript_data.json, language_cleanup.json,
    language_blocks.json) n'ont pas les comptes attendus, ou l'un des
    fichiers est absent/illisible. STOP AVANT RÉSEAU (§8, §14).
    """


class SelectionError(SemanticCanaryError):
    """
    La sélection déterministe des ~20 blocs n'est pas valide : moins de 20
    blocs uniques, un NO_ENGLISH_CONTEXT s'est glissé dans la sélection, une
    référence source est invalide, ou un texte n'est pas reconstructible
    (§14). STOP AVANT RÉSEAU.
    """


class PreflightError(SemanticCanaryError):
    """
    Une condition du préflight Anthropic (§29) n'est pas satisfaite :
    credential absent, capability structured_output manquante, schéma
    provider non conforme. STOP AVANT RÉSEAU.
    """


class MaxRealCallsExceededError(SemanticCanaryError):
    """
    Un second appel réel a été tenté depuis ce runner (§12, §32). Ce garde-fou
    ne doit jamais être atteint en fonctionnement normal : le déclencher est
    en soi un signal d'anomalie à corriger, pas à contourner.
    """


class CanaryResponseValidationError(SemanticCanaryError):
    """
    La réponse structurée du modèle ne respecte pas le contrat local (§19) :
    nombre de résultats, doublons, block_id inconnu ou manquant, vocabulaire
    fermé, cohérence classification/direction, bornes de confidence, reason
    vide. Ne déclenche JAMAIS un second appel (§19, §34).
    """

    def __init__(self, errors: list[str]):
        self.errors = list(errors)
        super().__init__(
            f"{len(self.errors)} violation(s) de la réponse du canary : "
            + " | ".join(self.errors)
        )


class IntegrityViolationError(SemanticCanaryError):
    """
    Un des trois fichiers sources a changé (SHA-256 différent) entre le début
    et la fin du traitement (§9, §37). Ce canary ne doit JAMAIS écrire dans
    transcript_data.json, language_cleanup.json ou language_blocks.json.
    """
