"""Erreurs du canary de grammaire — jamais rejouées comme incidents IA."""

from __future__ import annotations

from app.source_analysis.errors import SourceAnalysisError


class SchemaCanaryError(SourceAnalysisError):
    """Racine des échecs du canary 3B.4.1."""


class PreCallFailure(SchemaCanaryError):
    """STOP avant réseau : architecture, schéma, sélection, credential, dry-run."""


class SelectionError(SchemaCanaryError):
    """Sélection canary invalide ou hors bornes."""


class SchemaRegressionError(PreCallFailure):
    """Le schéma compact a régressé de manière importante depuis 3B.4."""


class LocalSchemaAuditError(PreCallFailure):
    """Audit local Anthropic du schéma adapté : incompatibilités restantes."""
