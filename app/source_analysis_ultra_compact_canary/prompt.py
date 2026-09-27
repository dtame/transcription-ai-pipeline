"""
Addendum canary — le contrat sémantique Generation C de production reste inchangé.

Le schéma de réponse n'est pas simplifié. Seul l'input est un extrait.
"""

from __future__ import annotations

from typing import Iterable

from app.source_analysis.prompt import (
    SOURCE_ANALYZER_PROMPT_VERSION,
    build_system_prompt,
    build_user_prompt,
)
from app.source_analysis.transcript_input import SourceSegment, TranscriptInput
from app.source_analysis.ultra_compact_schema import SEMANTIC_TRANSPORT_VERSION
from app.source_analysis_ultra_compact_canary.constants import (
    CANARY_PROMPT_ADDENDUM_VERSION,
)

CANARY_EXCERPT_NOTICE = """NOTE DE VALIDATION TECHNIQUE

This is a small source-analysis corpus. Le corpus fourni ci-dessous est
volontairement un petit extrait de validation technique, pas le transcript
intégral. Analyse UNIQUEMENT cet extrait.
N'utilise que les identifiants SRC réellement présents ci-dessous.
N'invente rien.

Tu restes ANALYSTE DE SOURCE : pas auteur, pas éditeur, pas planificateur
de livre, pas vérificateur de faits.

Le contrat de sortie est exactement semantic-transport-v1 (Generation C) :
theme, intent, ic, aud, ac, records
et chaque record : k, v, s, l, m.

Aucun identifiant métier (topic_id, idea_id, example_id, reference_id,
uncertainty_id, repetition_id). s = vrais SRC. l = index globaux de records."""


def build_canary_system_prompt(primary_language: str) -> str:
    """Même rôle / fidélité / traçabilité que le Source Analyzer de production."""
    return build_system_prompt(primary_language)


def build_canary_user_prompt(
    transcript: TranscriptInput,
    segments: Iterable[SourceSegment],
) -> str:
    """Prompt utilisateur de production, précédé de la notice d'extrait."""
    production = build_user_prompt(transcript, segments=segments)
    return CANARY_EXCERPT_NOTICE + "\n\n" + production


def prompt_versions() -> dict[str, str]:
    return {
        "source_analyzer_prompt_version": SOURCE_ANALYZER_PROMPT_VERSION,
        "canary_addendum_version": CANARY_PROMPT_ADDENDUM_VERSION,
        "transport_version": SEMANTIC_TRANSPORT_VERSION,
    }
