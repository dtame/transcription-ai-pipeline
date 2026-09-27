"""Écriture atomique des artefacts 3B.7.7A.5 — audit seulement."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from app.language_cleanup.transcript_source import audit_dir
from app.source_analysis_provider_boundary.constants import (
    ARCHITECTURE_ARTIFACT,
    DIAGNOSIS_ARTIFACT,
    MATRIX_ARTIFACT,
    PHASE,
    REPORT_NAME,
    SCHEMA_VERSION,
    TWO_CALL_ARTIFACT,
)


def diagnosis_path(project_name: str, *, sortie_dir: Path | None = None) -> Path:
    return audit_dir(project_name, sortie_dir=sortie_dir) / DIAGNOSIS_ARTIFACT


def matrix_path(project_name: str, *, sortie_dir: Path | None = None) -> Path:
    return audit_dir(project_name, sortie_dir=sortie_dir) / MATRIX_ARTIFACT


def architecture_path(project_name: str, *, sortie_dir: Path | None = None) -> Path:
    return audit_dir(project_name, sortie_dir=sortie_dir) / ARCHITECTURE_ARTIFACT


def two_call_path(project_name: str, *, sortie_dir: Path | None = None) -> Path:
    return audit_dir(project_name, sortie_dir=sortie_dir) / TWO_CALL_ARTIFACT


def report_path(project_name: str, *, sortie_dir: Path | None = None) -> Path:
    return audit_dir(project_name, sortie_dir=sortie_dir) / REPORT_NAME


def write_bytes_atomic(path: Path, payload: Mapping[str, Any] | str) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(payload, str):
        content = payload if payload.endswith("\n") else payload + "\n"
    else:
        content = json.dumps(dict(payload), ensure_ascii=False, indent=2) + "\n"
    encoded = content.encode("utf-8")
    partial = path.with_name(path.name + ".partial")
    try:
        partial.write_bytes(encoded)
        if partial.read_bytes() != encoded:
            raise ValueError(f"Octets partiels ≠ contenu canonique pour {path.name}.")
        if not isinstance(payload, str):
            loaded = json.loads(encoded.decode("utf-8"))
            if not isinstance(loaded, dict) or loaded.get("schema_version") != SCHEMA_VERSION:
                raise ValueError(f"Artefact partiel invalide : {path.name}.")
            if loaded.get("phase") != PHASE:
                raise ValueError(f"phase inattendue dans {path.name}.")
        partial.replace(path)
    except BaseException:
        partial.unlink(missing_ok=True)
        raise
    leftover = path.with_name(path.name + ".partial")
    if leftover.exists():
        leftover.unlink()
    return path
