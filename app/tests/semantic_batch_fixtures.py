"""
Fixtures de la Phase 3A.1.2B (classification par lots).

Réutilise le VRAI petit projet construit par
app.tests.semantic_canary_fixtures (transcript_data.json -> vrai auditeur
Phase 3A.1 -> vrai analyseur Phase 3A.1.1) : 17 blocs NEEDED (6 ALL_REVIEW +
6 ALL_KEEP + 5 atypiques), 6 ALREADY_RESOLVED, 0 NO_ENGLISH_CONTEXT (le
fixture canary n'en construit pas — cette phase n'a pas besoin de ce
bassin pour ses propres tests, il est couvert par des blocs synthétiques
dans test_semantic_batch.py là où c'est nécessaire).

Ajoute uniquement ce qui est nouveau pour cette phase : un artefact
semantic_translation_canary.json stub sur disque (§9 — le 4e artefact
protégé doit exister et être lisible ; son CONTENU exact n'a pas
d'importance pour cette phase, seule sa présence et son immutabilité
comptent).
"""

from __future__ import annotations

from pathlib import Path

from app.semantic_canary.writer import artifact_path as canary_artifact_path
from app.semantic_canary.writer import write_artifact as write_canary_artifact
from app.tests.semantic_canary_fixtures import PROJECT, build_fixture_project

__all__ = ["PROJECT", "build_fixture_project", "write_stub_canary_artifact"]


def write_stub_canary_artifact(sortie_dir: Path) -> Path:
    """
    Écrit un semantic_translation_canary.json minimal mais réaliste.

    Ce n'est PAS un second run du vrai canary (hors périmètre de cette
    fixture) : juste assez de structure pour que
    app.semantic_batch.integrity puisse le hasher et le surveiller comme un
    artefact protégé parmi les quatre (§9, §41).
    """
    payload = {
        "schema_version": "1.0",
        "prompt_version": "1.0",
        "provider": "anthropic",
        "model": "claude-sonnet-5",
        "project": PROJECT,
        "results": [],
        "note": "Stub de test — pas un vrai run du canary Phase 3A.1.2A.",
    }

    path = canary_artifact_path(PROJECT, sortie_dir=sortie_dir)
    return write_canary_artifact(path, payload)


def build_full_fixture_project(sortie_dir: Path):
    """Projet fixture complet (3 sources + stub canary) prêt pour cette phase."""
    result = build_fixture_project(sortie_dir)
    write_stub_canary_artifact(sortie_dir)
    return result
