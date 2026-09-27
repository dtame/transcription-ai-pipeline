"""
Intégrité des CINQ artefacts protégés de cette phase (§5, §44) :

    transcript_data.json
    language_cleanup.json
    language_blocks.json
    semantic_translation_canary.json
    semantic_translation_classification.json

Réutilise app.semantic_batch.integrity pour les quatre premiers chemins et
le calcul de hash ; ajoute uniquement le cinquième chemin (l'artefact de
classification de la Phase 3A.1.2B) à la surveillance. Cette phase ne lit
JAMAIS le contenu métier de language_cleanup.json (seule sa présence et son
hash comptent ici — la vérité métier utile est déjà distillée dans
language_blocks.json, §6).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.semantic_batch.integrity import (
    LANGUAGE_BLOCKS_KEY,
    LANGUAGE_CLEANUP_KEY,
    SEMANTIC_CANARY_KEY,
    TRANSCRIPT_DATA_KEY,
    sha256_of_file,
)
from app.semantic_batch.integrity import source_paths as _batch_source_paths
from app.semantic_batch.writer import (
    classification_artifact_path as _classification_artifact_path,
)

SEMANTIC_CLASSIFICATION_KEY = "semantic_translation_classification"

SOURCE_KEYS = (
    TRANSCRIPT_DATA_KEY,
    LANGUAGE_CLEANUP_KEY,
    LANGUAGE_BLOCKS_KEY,
    SEMANTIC_CANARY_KEY,
    SEMANTIC_CLASSIFICATION_KEY,
)


@dataclass(frozen=True)
class IntegritySnapshot:
    """Hashes des cinq artefacts protégés à un instant donné."""

    hashes: dict[str, str]

    def to_dict(self) -> dict:
        return dict(self.hashes)


def source_paths(project_name: str, *, sortie_dir: Path | None = None) -> dict[str, Path]:
    """Chemins canoniques des cinq artefacts protégés d'un projet."""
    paths = dict(_batch_source_paths(project_name, sortie_dir=sortie_dir))
    paths[SEMANTIC_CLASSIFICATION_KEY] = _classification_artifact_path(
        project_name, sortie_dir=sortie_dir
    )
    return paths


def snapshot_sources(project_name: str, *, sortie_dir: Path | None = None) -> IntegritySnapshot:
    """
    Calcule le SHA-256 des cinq artefacts protégés.

    Lève FileNotFoundError (propagée telle quelle) si l'un d'eux est absent :
    c'est déjà couvert en amont par la validation des sources (§39 loader),
    qui doit tourner avant tout calcul d'intégrité.
    """
    paths = source_paths(project_name, sortie_dir=sortie_dir)

    return IntegritySnapshot(
        hashes={key: sha256_of_file(path) for key, path in paths.items()}
    )


def ensure_unchanged(before: IntegritySnapshot, after: IntegritySnapshot) -> None:
    """
    Vérifie que les cinq artefacts sont restés byte-identiques (§5, §44).

    Lève SourceIntegrityError avec le détail complet si l'un d'eux a changé —
    jamais un simple booléen : un rapport doit pouvoir dire LEQUEL a changé.
    """
    violations = [
        f"{key} : sha256 avant={before.hashes.get(key)!r} != après={after.hashes.get(key)!r}"
        for key in SOURCE_KEYS
        if before.hashes.get(key) != after.hashes.get(key)
    ]

    if violations:
        from app.cleanup_policy.errors import SourceIntegrityError

        raise SourceIntegrityError(
            "Intégrité rompue sur au moins un artefact protégé : "
            + " | ".join(violations)
        )
