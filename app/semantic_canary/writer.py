"""
Emplacement et publication atomique de semantic_translation_canary.json (§21).

EMPLACEMENT

    sortie/<projet>/audit/semantic_translation_canary.json

Même répertoire `audit/` que language_cleanup.json et language_blocks.json :
c'est un diagnostic de la même famille. Il ne modifie AUCUN des deux
manifestes déjà publiés (§21, IMPORTANT).

PUBLICATION ATOMIQUE : même schéma que le reste du projet, via
app.file_utils.write_json_atomic — écrit APRÈS validation complète de la
réponse, jamais avant (§35).
"""

from __future__ import annotations

import json
from pathlib import Path

from app.file_utils import write_json_atomic
from app.paths import SORTIE_DIR

AUDIT_DIR_NAME = "audit"
ARTIFACT_NAME = "semantic_translation_canary.json"


def audit_dir(project_name: str, *, sortie_dir: Path | None = None) -> Path:
    root = Path(sortie_dir) if sortie_dir is not None else SORTIE_DIR
    return root / project_name / AUDIT_DIR_NAME


def artifact_path(project_name: str, *, sortie_dir: Path | None = None) -> Path:
    """Chemin canonique de semantic_translation_canary.json."""
    return audit_dir(project_name, sortie_dir=sortie_dir) / ARTIFACT_NAME


def write_artifact(path: Path, payload: dict) -> Path:
    """Écrit l'artefact canary atomiquement."""
    return write_json_atomic(Path(path), payload)


def read_artifact_payload(path: Path) -> dict | None:
    """Relit un artefact publié, ou None s'il est absent ou illisible."""
    path = Path(path)

    if not path.exists():
        return None

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    return payload if isinstance(payload, dict) else None
