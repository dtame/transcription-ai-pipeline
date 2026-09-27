"""
Intégrité des trois sources (§9, §37).

Le canary est un DIAGNOSTIC : il ne doit jamais laisser
transcript_data.json, language_cleanup.json ou language_blocks.json changer
d'un seul octet. Le hash est calculé sur les OCTETS bruts du fichier — pas
sur un texte redécodé — pour que la vérification soit indépendante de toute
hypothèse d'encodage et détecte un changement de fin de ligne aussi bien
qu'un changement de contenu.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from app.language_blocks.writer import manifest_path as blocks_manifest_path
from app.language_cleanup.writer import manifest_path as cleanup_manifest_path
from app.semantic_canary.errors import IntegrityViolationError
from app.source_analysis.transcript_input import transcript_data_file
from app.source_analysis.writer import transcripts_dir as transcripts_directory

TRANSCRIPT_DATA_KEY = "transcript_data"
LANGUAGE_CLEANUP_KEY = "language_cleanup"
LANGUAGE_BLOCKS_KEY = "language_blocks"

SOURCE_KEYS = (TRANSCRIPT_DATA_KEY, LANGUAGE_CLEANUP_KEY, LANGUAGE_BLOCKS_KEY)


def sha256_of_file(path: Path) -> str:
    """SHA-256 hexadécimal des octets bruts d'un fichier."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_paths(project_name: str, *, sortie_dir: Path | None = None) -> dict[str, Path]:
    """Chemins canoniques des trois sources d'un projet, par clé stable."""
    transcripts_dir = transcripts_directory(project_name, sortie_dir=sortie_dir)

    return {
        TRANSCRIPT_DATA_KEY: transcript_data_file(transcripts_dir),
        LANGUAGE_CLEANUP_KEY: cleanup_manifest_path(project_name, sortie_dir=sortie_dir),
        LANGUAGE_BLOCKS_KEY: blocks_manifest_path(project_name, sortie_dir=sortie_dir),
    }


@dataclass(frozen=True)
class IntegritySnapshot:
    """Hashes des trois sources à un instant donné."""

    hashes: dict[str, str]

    def to_dict(self) -> dict:
        return dict(self.hashes)


def snapshot_sources(project_name: str, *, sortie_dir: Path | None = None) -> IntegritySnapshot:
    """
    Calcule le SHA-256 des trois sources.

    Lève FileNotFoundError (propagée telle quelle) si un fichier est absent :
    c'est déjà couvert en amont par la validation des sources (§8), qui doit
    tourner avant tout calcul d'intégrité.
    """
    paths = source_paths(project_name, sortie_dir=sortie_dir)

    return IntegritySnapshot(
        hashes={key: sha256_of_file(path) for key, path in paths.items()}
    )


def ensure_unchanged(before: IntegritySnapshot, after: IntegritySnapshot) -> None:
    """
    Vérifie que les trois sources sont restées byte-identiques (§37).

    Lève IntegrityViolationError avec le détail complet si l'un des trois
    fichiers a changé — jamais un simple booléen : un rapport doit pouvoir
    dire LEQUEL a changé.
    """
    violations = [
        f"{key} : sha256 avant={before.hashes.get(key)!r} != après={after.hashes.get(key)!r}"
        for key in SOURCE_KEYS
        if before.hashes.get(key) != after.hashes.get(key)
    ]

    if violations:
        raise IntegrityViolationError(
            "Intégrité rompue sur au moins une source protégée : " + " | ".join(violations)
        )
