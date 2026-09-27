"""
Emplacement et publication atomique de language_blocks.json.

EMPLACEMENT

    sortie/<projet>/audit/language_blocks.json

Même répertoire `audit/` que language_cleanup.json (Phase 3A.1) : les deux
manifestes documentent des analyses de la même famille, jamais une écriture
dans transcripts/.

PUBLICATION ATOMIQUE

Même schéma que Phase 3A.1 : écriture dans « .partial », remplacement
atomique via Path.replace() (app.file_utils.write_json_atomic).
"""

from __future__ import annotations

import json
from pathlib import Path

from app.file_utils import write_json_atomic
from app.paths import SORTIE_DIR

AUDIT_DIR_NAME = "audit"
MANIFEST_NAME = "language_blocks.json"


def audit_dir(project_name: str, *, sortie_dir: Path | None = None) -> Path:
    root = Path(sortie_dir) if sortie_dir is not None else SORTIE_DIR
    return root / project_name / AUDIT_DIR_NAME


def manifest_path(project_name: str, *, sortie_dir: Path | None = None) -> Path:
    """Chemin canonique de language_blocks.json."""
    return audit_dir(project_name, sortie_dir=sortie_dir) / MANIFEST_NAME


def write_manifest(path: Path, payload: dict) -> Path:
    """Écrit le manifeste d'analyse structurelle atomiquement."""
    return write_json_atomic(Path(path), payload)


def read_manifest_payload(path: Path) -> dict | None:
    """Relit un language_blocks.json publié, ou None s'il est absent ou illisible."""
    path = Path(path)

    if not path.exists():
        return None

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    return payload if isinstance(payload, dict) else None
