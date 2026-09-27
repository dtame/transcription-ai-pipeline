"""Erreurs du run 3B Final — jamais rejouées comme incidents IA."""

from __future__ import annotations

from app.source_analysis.errors import SourceAnalysisError


class GlobalCleanError(SourceAnalysisError):
    """Racine des échecs du Source Analyzer global CLEAN."""


class PreCallFailure(GlobalCleanError):
    """STOP avant réseau : schéma, prompt, parité, cache, credential."""


class SchemaDriftError(PreCallFailure):
    """Generation C a divergé de la version server-verified."""


class UnexpectedCacheHit(PreCallFailure):
    """Cache production inattendu sur le premier run 1.3 / Generation C."""


class ExistingSourceMapStop(PreCallFailure):
    """source_map.json existe déjà : revue humaine avant tout écrasement."""


class TransportPreserveError(GlobalCleanError):
    """La préservation du transport a échoué : publication interdite."""
