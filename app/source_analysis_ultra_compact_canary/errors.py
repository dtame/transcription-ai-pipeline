"""Erreurs du canary 3B.4.3 — jamais rejouées comme incidents IA."""

from __future__ import annotations

from app.source_analysis.errors import SourceAnalysisError


class UltraCompactCanaryError(SourceAnalysisError):
    """Racine des échecs du canary 3B.4.3."""


class PreCallFailure(UltraCompactCanaryError):
    """STOP avant réseau : architecture, schéma, sélection, credential, dry-run."""


class SelectionError(UltraCompactCanaryError):
    """Sélection canary invalide ou hors bornes."""


class SchemaRegressionError(PreCallFailure):
    """Generation C a régressé de manière inattendue depuis 3B.4.2."""


class LocalSchemaAuditError(PreCallFailure):
    """Audit local Anthropic de Generation C : incompatibilités restantes."""
