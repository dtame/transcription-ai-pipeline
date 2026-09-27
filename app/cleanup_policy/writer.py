"""
Emplacement et publication atomique de cleanup_policy_simulation.json (§21).

    sortie/<projet>/audit/cleanup_policy_simulation.json

Même répertoire `audit/` que les autres artefacts de cette famille de
phases : cette phase documente une simulation, jamais une écriture dans
transcripts/.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.file_utils import write_json_atomic
from app.semantic_batch.writer import audit_dir

ARTIFACT_NAME = "cleanup_policy_simulation.json"


def artifact_path(project_name: str, *, sortie_dir: Path | None = None) -> Path:
    return audit_dir(project_name, sortie_dir=sortie_dir) / ARTIFACT_NAME


def write_artifact(path: Path, payload: dict) -> Path:
    """Écrit l'artefact final atomiquement, uniquement après validation complète."""
    return write_json_atomic(Path(path), payload)


def read_artifact(path: Path) -> dict | None:
    path = Path(path)
    if not path.exists():
        return None

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    return payload if isinstance(payload, dict) else None
