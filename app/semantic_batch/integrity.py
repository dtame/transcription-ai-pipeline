"""
Intégrité des QUATRE artefacts protégés de cette phase (§9, §41) :

    transcript_data.json
    language_cleanup.json
    language_blocks.json
    semantic_translation_canary.json   (Phase 3A.1.2A — expérience séparée ;
                                          §10 : jamais modifié par cette phase)

Réutilise app.semantic_canary.integrity pour les trois premiers chemins et
le calcul de hash ; ajoute uniquement le quatrième chemin (l'artefact du
canary) à la surveillance.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.semantic_canary.integrity import (
    LANGUAGE_BLOCKS_KEY,
    LANGUAGE_CLEANUP_KEY,
    TRANSCRIPT_DATA_KEY,
    sha256_of_file,
)
from app.semantic_canary.integrity import source_paths as _canary_source_paths
from app.semantic_canary.writer import artifact_path as _canary_artifact_path

SEMANTIC_CANARY_KEY = "semantic_translation_canary"

SOURCE_KEYS = (
    TRANSCRIPT_DATA_KEY,
    LANGUAGE_CLEANUP_KEY,
    LANGUAGE_BLOCKS_KEY,
    SEMANTIC_CANARY_KEY,
)


@dataclass(frozen=True)
class IntegritySnapshot:
    """Hashes des quatre artefacts protégés à un instant donné."""

    hashes: dict[str, str]

    def to_dict(self) -> dict:
        return dict(self.hashes)


def source_paths(project_name: str, *, sortie_dir: Path | None = None) -> dict[str, Path]:
    """Chemins canoniques des quatre artefacts protégés d'un projet."""
    paths = dict(_canary_source_paths(project_name, sortie_dir=sortie_dir))
    paths[SEMANTIC_CANARY_KEY] = _canary_artifact_path(project_name, sortie_dir=sortie_dir)
    return paths


def snapshot_sources(project_name: str, *, sortie_dir: Path | None = None) -> IntegritySnapshot:
    """
    Calcule le SHA-256 des quatre artefacts protégés.

    Lève FileNotFoundError (propagée telle quelle) si l'un d'eux est absent :
    c'est déjà couvert en amont par la validation des sources (§8-9), qui
    doit tourner avant tout calcul d'intégrité.
    """
    paths = source_paths(project_name, sortie_dir=sortie_dir)

    return IntegritySnapshot(
        hashes={key: sha256_of_file(path) for key, path in paths.items()}
    )


def ensure_unchanged(before: IntegritySnapshot, after: IntegritySnapshot) -> None:
    """
    Vérifie que les quatre artefacts sont restés byte-identiques (§37, §41).

    Lève SourceIntegrityError avec le détail complet si l'un d'eux a changé —
    jamais un simple booléen : un rapport doit pouvoir dire LEQUEL a changé.
    """
    violations = [
        f"{key} : sha256 avant={before.hashes.get(key)!r} != après={after.hashes.get(key)!r}"
        for key in SOURCE_KEYS
        if before.hashes.get(key) != after.hashes.get(key)
    ]

    if violations:
        # Import tardif : évite un cycle (errors.py ne dépend pas d'integrity.py).
        from app.semantic_batch.errors import SourceIntegrityError

        raise SourceIntegrityError(
            "Intégrité rompue sur au moins un artefact protégé : "
            + " | ".join(violations)
        )
