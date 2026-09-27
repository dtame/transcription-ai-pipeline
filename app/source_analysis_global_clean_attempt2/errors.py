"""Erreurs spécifiques à l'essai #2 — jamais rejouées."""

from __future__ import annotations

from app.source_analysis_global_clean.errors import PreCallFailure


class TimeoutPolicyMismatch(PreCallFailure):
    """Timeouts effectifs ≠ politique 3B.5.2 (30, 7200)."""


class PolicyArtifactMismatch(PreCallFailure):
    """La configuration pré-appel ne correspond pas à la politique 3B.5.2."""


class UnexpectedProjectState(PreCallFailure):
    """L'état projet n'est plus l'échec historique de l'essai #1."""
