"""Écriture atomique des artefacts 3B.7.7A.10 — audit seulement."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from app.language_cleanup.transcript_source import audit_dir
from app.source_analysis_output_ceiling_review.constants import (
    CONTRACT_ARTIFACT,
    DECISION_ARTIFACT,
    FORENSICS_ARTIFACT,
    ISOLATION_ARTIFACT,
    OPTIONS_ARTIFACT,
    PHASE,
    REPORT_NAME,
    SCHEMA_VERSION,
)


def forensics_path(project_name: str, *, sortie_dir: Path | None = None) -> Path:
    return audit_dir(project_name, sortie_dir=sortie_dir) / FORENSICS_ARTIFACT


def contract_path(project_name: str, *, sortie_dir: Path | None = None) -> Path:
    return audit_dir(project_name, sortie_dir=sortie_dir) / CONTRACT_ARTIFACT


def options_path(project_name: str, *, sortie_dir: Path | None = None) -> Path:
    return audit_dir(project_name, sortie_dir=sortie_dir) / OPTIONS_ARTIFACT


def decision_path(project_name: str, *, sortie_dir: Path | None = None) -> Path:
    return audit_dir(project_name, sortie_dir=sortie_dir) / DECISION_ARTIFACT


def isolation_path(project_name: str, *, sortie_dir: Path | None = None) -> Path:
    return audit_dir(project_name, sortie_dir=sortie_dir) / ISOLATION_ARTIFACT


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
        leftover_name = path.with_name(path.name + ".partial")
        partial.replace(path)
        if leftover_name.exists() and leftover_name != path:
            leftover_name.unlink()
    except BaseException:
        partial.unlink(missing_ok=True)
        raise
    leftover = path.with_name(path.name + ".partial")
    if leftover.exists():
        leftover.unlink()
    return path
