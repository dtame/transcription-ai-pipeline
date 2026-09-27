"""Écriture atomique des artefacts 3B.7.7A.7 — audit seulement."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from app.language_cleanup.transcript_source import audit_dir
from app.source_analysis_small_window_hierarchy.constants import (
    DIRECT_FAKEAI_ARTIFACT,
    HIERARCHICAL_FAKEAI_ARTIFACT,
    PHASE,
    PLAN_ARTIFACT,
    PREFLIGHT_ARTIFACT,
    REPORT_NAME,
    ROUTER_ARTIFACT,
    SCHEMA_VERSION,
    TRACEABILITY_ARTIFACT,
)


def plan_path(project_name: str, *, sortie_dir: Path | None = None) -> Path:
    return audit_dir(project_name, sortie_dir=sortie_dir) / PLAN_ARTIFACT


def router_path(project_name: str, *, sortie_dir: Path | None = None) -> Path:
    return audit_dir(project_name, sortie_dir=sortie_dir) / ROUTER_ARTIFACT


def direct_path(project_name: str, *, sortie_dir: Path | None = None) -> Path:
    return audit_dir(project_name, sortie_dir=sortie_dir) / DIRECT_FAKEAI_ARTIFACT


def hierarchical_path(project_name: str, *, sortie_dir: Path | None = None) -> Path:
    return audit_dir(project_name, sortie_dir=sortie_dir) / HIERARCHICAL_FAKEAI_ARTIFACT


def traceability_path(project_name: str, *, sortie_dir: Path | None = None) -> Path:
    return audit_dir(project_name, sortie_dir=sortie_dir) / TRACEABILITY_ARTIFACT


def preflight_path(project_name: str, *, sortie_dir: Path | None = None) -> Path:
    return audit_dir(project_name, sortie_dir=sortie_dir) / PREFLIGHT_ARTIFACT


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


__all__ = [
    "direct_path",
    "hierarchical_path",
    "plan_path",
    "preflight_path",
    "report_path",
    "router_path",
    "traceability_path",
    "write_bytes_atomic",
]
