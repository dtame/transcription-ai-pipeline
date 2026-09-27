"""
Emplacement et publication atomique de language_cleanup.json.

EMPLACEMENT

    sortie/<projet>/audit/language_cleanup.json

Un répertoire neuf, `audit/`, distinct de `analysis/` (Source Analyzer) et de
`transcripts/` (contrat V2) : ce manifeste n'est ni le Source Map, ni le
transcript, ni un chunk technique. Il documente des décisions PROPOSÉES pour
une phase de nettoyage qui n'a pas encore eu lieu (Phase 3A.2).

PUBLICATION ATOMIQUE

Même schéma que Phase 1 et Phase 3 (source_map.json) : écriture dans
« .partial », remplacement atomique via Path.replace(). Voir
app.file_utils.write_json_atomic.

Ce module n'écrit JAMAIS dans transcripts/ : aucune fonction ici ne touche à
transcript_data.json ni transcript.txt.
"""

from __future__ import annotations

from pathlib import Path

from app.file_utils import write_json_atomic
from app.paths import SORTIE_DIR

AUDIT_DIR_NAME = "audit"
MANIFEST_NAME = "language_cleanup.json"


def audit_dir(project_name: str, *, sortie_dir: Path | None = None) -> Path:
    root = Path(sortie_dir) if sortie_dir is not None else SORTIE_DIR
    return root / project_name / AUDIT_DIR_NAME


def manifest_path(project_name: str, *, sortie_dir: Path | None = None) -> Path:
    """Chemin canonique de language_cleanup.json."""
    return audit_dir(project_name, sortie_dir=sortie_dir) / MANIFEST_NAME


def write_manifest(path: Path, payload: dict) -> Path:
    """Écrit le manifeste d'audit atomiquement."""
    return write_json_atomic(Path(path), payload)


def read_manifest_payload(path: Path) -> dict | None:
    """
    Relit un language_cleanup.json publié, ou None s'il est absent ou illisible.
    """
    import json

    path = Path(path)

    if not path.exists():
        return None

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    return payload if isinstance(payload, dict) else None
