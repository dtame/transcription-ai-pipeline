"""Écriture atomique des artefacts 3B.6."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from app.language_cleanup.transcript_source import audit_dir
from app.source_analysis.writer import source_map_path
from app.source_analysis_execution_strategy.constants import (
    PHASE,
    REPORT_NAME,
    REVIEW_ARTIFACT_NAME,
    SCHEMA_VERSION,
    SIMULATION_ARTIFACT_NAME,
)

__all__ = [
    "REPORT_NAME",
    "REVIEW_ARTIFACT_NAME",
    "SIMULATION_ARTIFACT_NAME",
    "assert_no_production_source_map",
    "report_path",
    "review_path",
    "simulation_path",
    "write_bytes_atomic",
]


def simulation_path(project_name: str, *, sortie_dir: Path | None = None) -> Path:
    return audit_dir(project_name, sortie_dir=sortie_dir) / SIMULATION_ARTIFACT_NAME


def review_path(project_name: str, *, sortie_dir: Path | None = None) -> Path:
    return audit_dir(project_name, sortie_dir=sortie_dir) / REVIEW_ARTIFACT_NAME


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
            if loaded.get("phase") not in (PHASE, "3B.6"):
                raise ValueError(f"phase inattendue dans {path.name}.")
            network = loaded.get("network") or loaded.get("execution") or {}
            if isinstance(loaded.get("network"), dict):
                if loaded["network"].get("anthropic") not in (0, None):
                    raise ValueError("network.anthropic doit rester 0.")
            if network.get("provider_calls") not in (0, None):
                if loaded.get("execution", {}).get("provider_calls") not in (0, None):
                    if loaded["execution"]["provider_calls"] != 0:
                        raise ValueError("provider_calls doit rester 0.")
        partial.replace(path)
    except BaseException:
        partial.unlink(missing_ok=True)
        raise
    leftover = path.with_name(path.name + ".partial")
    if leftover.exists():
        leftover.unlink()
    return path


def assert_no_production_source_map(
    project_name: str,
    *,
    sortie_dir: Path | None = None,
) -> None:
    path = source_map_path(project_name, sortie_dir=sortie_dir)
    if path.exists():
        raise RuntimeError(f"source_map de production présent : {path}")
