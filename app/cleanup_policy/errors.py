"""
Erreurs de la Phase 3A.2A — simulation des politiques de nettoyage.

Comme app/semantic_batch/errors.py, ce module ne redéfinit jamais une
erreur déjà portée par une phase réutilisée (semantic_batch, semantic_canary) :
les erreurs ci-dessous couvrent uniquement ce qui est propre à cette phase.
"""

from __future__ import annotations


class CleanupPolicyError(RuntimeError):
    """Base des erreurs de la Phase 3A.2A."""


class SourceIntegrityError(CleanupPolicyError):
    """
    Une des cinq sources protégées (transcript_data.json,
    language_cleanup.json, language_blocks.json,
    semantic_translation_canary.json, semantic_translation_classification.json)
    est absente, illisible, ou incohérente. STOP AVANT TOUT CALCUL.
    """


class PopulationError(CleanupPolicyError):
    """
    La population reconstruite (333 blocs attendus pour le projet réel, mais
    ce module reste générique) ne couvre pas exactement les blocs de
    language_blocks.json : doublon, omission, origine incohérente, ou un
    résultat sémantique orphelin/manquant.
    """


class SimulationValidationError(CleanupPolicyError):
    """
    L'artefact simulé viole une des invariantes strictes du validateur
    (cahier des charges §39) : une politique a produit une décision
    incohérente avec son propre cahier des charges, ou une statistique ne
    boucle pas sur le total attendu.
    """
