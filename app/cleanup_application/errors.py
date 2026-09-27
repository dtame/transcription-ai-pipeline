"""Erreurs de la Phase 3A.2B — application réelle de POLICY_B+."""

from __future__ import annotations


class CleanupApplicationError(RuntimeError):
    """Base des erreurs de la Phase 3A.2B."""


class SourceIntegrityError(CleanupApplicationError):
    """Une source protégée est absente, illisible, ou a changé d'un octet."""


class PreflightError(CleanupApplicationError):
    """
    Le jeu de suppression (removal_set) viole une invariante. STOP : aucun
    transcript clean ni audit n'est publié.
    """


class CleanTranscriptError(CleanupApplicationError):
    """Le transcript clean viole le contrat de vue dérivée."""


class ReversibilityError(CleanupApplicationError):
    """restore(clean + removed) ne reconstitue pas la séquence originale."""


class ApplicationValidationError(CleanupApplicationError):
    """L'audit ou la transaction de publication viole une invariante."""
