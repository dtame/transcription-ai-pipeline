"""
Emplacements et publication atomique des artefacts de la Phase 3A.1.2B
(§18, §26).

EMPLACEMENTS

    sortie/<projet>/audit/semantic_batches/BATCH001.json, BATCH002.json, ...
    sortie/<projet>/audit/semantic_translation_classification.json

Même répertoire `audit/` que language_cleanup.json, language_blocks.json et
semantic_translation_canary.json : cette phase documente une analyse de la
même famille, jamais une écriture dans transcripts/.

PUBLICATION ATOMIQUE : même schéma que le reste du projet, via
app.file_utils.write_json_atomic — un checkpoint de lot n'est écrit
qu'APRÈS validation locale complète de sa réponse (§18, §23), jamais avant.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.file_utils import write_json_atomic
from app.paths import SORTIE_DIR

AUDIT_DIR_NAME = "audit"
BATCHES_DIR_NAME = "semantic_batches"
CLASSIFICATION_ARTIFACT_NAME = "semantic_translation_classification.json"


def audit_dir(project_name: str, *, sortie_dir: Path | None = None) -> Path:
    root = Path(sortie_dir) if sortie_dir is not None else SORTIE_DIR
    return root / project_name / AUDIT_DIR_NAME


def batches_dir(project_name: str, *, sortie_dir: Path | None = None) -> Path:
    """Répertoire des checkpoints de lot (§18)."""
    return audit_dir(project_name, sortie_dir=sortie_dir) / BATCHES_DIR_NAME


def batch_path(project_name: str, batch_id: str, *, sortie_dir: Path | None = None) -> Path:
    """Chemin canonique d'un checkpoint de lot : .../BATCH001.json, ..."""
    return batches_dir(project_name, sortie_dir=sortie_dir) / f"{batch_id}.json"


def classification_artifact_path(
    project_name: str, *, sortie_dir: Path | None = None
) -> Path:
    """Chemin canonique de semantic_translation_classification.json (§26)."""
    return audit_dir(project_name, sortie_dir=sortie_dir) / CLASSIFICATION_ARTIFACT_NAME


def write_batch_atomic(path: Path, payload: dict) -> Path:
    """Écrit un checkpoint de lot atomiquement (§18)."""
    return write_json_atomic(Path(path), payload)


def read_batch_payload(path: Path) -> dict | None:
    """Relit un checkpoint de lot publié, ou None s'il est absent ou illisible."""
    path = Path(path)

    if not path.exists():
        return None

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    return payload if isinstance(payload, dict) else None


def write_classification_artifact(path: Path, payload: dict) -> Path:
    """Écrit l'artefact final atomiquement (§26), uniquement après validation complète."""
    return write_json_atomic(Path(path), payload)
