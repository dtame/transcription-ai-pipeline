"""Erreurs du canary 3B.4.5 — jamais rejouées comme incidents IA."""

from __future__ import annotations

from app.source_analysis.errors import SourceAnalysisError


class VocabularyComplianceCanaryError(SourceAnalysisError):
    """Racine des échecs du canary 3B.4.5."""


class PreCallFailure(VocabularyComplianceCanaryError):
    """STOP avant réseau : schéma, prompt, parité, sélection, credential."""


class HistoricalInputUnavailable(PreCallFailure):
    """L'extrait historique SRC003799–SRC003808 n'est plus reproductible."""


class SchemaDriftError(PreCallFailure):
    """Generation C a divergé de la version server-verified 3B.4.3."""


class VocabularyParityError(PreCallFailure):
    """Parité prompt / decoder rompue avant l'appel."""
