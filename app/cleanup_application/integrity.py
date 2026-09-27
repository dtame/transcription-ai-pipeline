"""
Intégrité des SEPT artefacts protégés de cette phase :

    transcripts/transcript_data.json
    transcripts/transcript.txt
    audit/language_cleanup.json
    audit/language_blocks.json
    audit/semantic_translation_canary.json
    audit/semantic_translation_classification.json
    audit/cleanup_policy_simulation.json

Aucun n'est ouvert en écriture par ce paquet.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.cleanup_policy.integrity import source_paths as _policy_source_paths
from app.cleanup_policy.writer import artifact_path as _simulation_artifact_path
from app.semantic_batch.integrity import (
    LANGUAGE_BLOCKS_KEY,
    LANGUAGE_CLEANUP_KEY,
    SEMANTIC_CANARY_KEY,
    TRANSCRIPT_DATA_KEY,
)
from app.semantic_canary.integrity import sha256_of_file
from app.source_analysis.writer import transcripts_dir as _transcripts_dir
from app.transcript_writer import transcript_text_path as _transcript_text_path

from app.cleanup_application.errors import SourceIntegrityError

SEMANTIC_CLASSIFICATION_KEY = "semantic_translation_classification"
TRANSCRIPT_TXT_KEY = "transcript_txt"
CLEANUP_SIMULATION_KEY = "cleanup_policy_simulation"

SOURCE_KEYS = (
    TRANSCRIPT_DATA_KEY,
    TRANSCRIPT_TXT_KEY,
    LANGUAGE_CLEANUP_KEY,
    LANGUAGE_BLOCKS_KEY,
    SEMANTIC_CANARY_KEY,
    SEMANTIC_CLASSIFICATION_KEY,
    CLEANUP_SIMULATION_KEY,
)


@dataclass(frozen=True)
class IntegritySnapshot:
    hashes: dict[str, str]

    def to_dict(self) -> dict:
        return dict(self.hashes)


def source_paths(project_name: str, *, sortie_dir: Path | None = None) -> dict[str, Path]:
    paths = dict(_policy_source_paths(project_name, sortie_dir=sortie_dir))
    paths[TRANSCRIPT_TXT_KEY] = _transcript_text_path(
        _transcripts_dir(project_name, sortie_dir=sortie_dir)
    )
    paths[CLEANUP_SIMULATION_KEY] = _simulation_artifact_path(
        project_name, sortie_dir=sortie_dir
    )
    return paths


def snapshot_sources(project_name: str, *, sortie_dir: Path | None = None) -> IntegritySnapshot:
    paths = source_paths(project_name, sortie_dir=sortie_dir)
    missing = [f"{key} introuvable : {path}" for key, path in paths.items() if not path.exists()]
    if missing:
        raise SourceIntegrityError(
            "Source(s) protégée(s) absente(s) : " + " | ".join(missing)
        )
    return IntegritySnapshot(
        hashes={key: sha256_of_file(path) for key, path in paths.items()}
    )


def ensure_unchanged(before: IntegritySnapshot, after: IntegritySnapshot) -> None:
    violations = [
        f"{key} : sha256 avant={before.hashes.get(key)!r} != après={after.hashes.get(key)!r}"
        for key in SOURCE_KEYS
        if before.hashes.get(key) != after.hashes.get(key)
    ]
    if violations:
        raise SourceIntegrityError(
            "Intégrité rompue sur au moins un artefact protégé : " + " | ".join(violations)
        )
