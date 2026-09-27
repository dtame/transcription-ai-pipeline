"""Erreurs du paquet d'audit linguistique (Phase 3A.1)."""

from __future__ import annotations


class LanguageCleanupError(RuntimeError):
    """Base des erreurs de l'audit linguistique."""


class AuditTranscriptError(LanguageCleanupError):
    """transcript_data.json est absent, illisible, ou ne peut pas être audité."""


class DependencyRequiredError(LanguageCleanupError):
    """
    Une dépendance supplémentaire semblerait indispensable.

    Levée volontairement plutôt qu'une installation automatique — voir §7 du
    cahier des charges Phase 3A.1 : « ne pas ajouter automatiquement une
    dépendance lourde ». Non utilisée en pratique par ce paquet (les
    heuristiques déterministes en place suffisent), mais conservée pour
    documenter explicitement la voie de sortie prévue si un besoin réel
    apparaissait un jour.
    """


class ManifestValidationError(LanguageCleanupError):
    """language_cleanup.json ne satisfait pas son propre contrat."""

    def __init__(self, errors: list[str]):
        self.errors = list(errors)
        super().__init__(
            f"{len(self.errors)} violation(s) du manifeste language_cleanup.json : "
            + " | ".join(self.errors)
        )
