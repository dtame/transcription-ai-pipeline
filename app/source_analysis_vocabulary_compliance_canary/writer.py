"""Écriture atomique des artefacts canary 3B.4.5 dans audit/ — jamais analysis/."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from app.language_cleanup.transcript_source import audit_dir
from app.source_analysis.writer import source_map_path
from app.source_analysis_vocabulary_compliance_canary.constants import (
    CANARY_SOURCEMAP_NAME,
    DRY_RUN_ARTIFACT_NAME,
    INPUT_ARTIFACT_NAME,
    REPORT_NAME,
    RESULT_ARTIFACT_NAME,
    TRANSPORT_ARTIFACT_NAME,
)


def canary_audit_dir(project_name: str, *, sortie_dir: Path | None = None) -> Path:
    return audit_dir(project_name, sortie_dir=sortie_dir)


def input_path(project_name: str, *, sortie_dir: Path | None = None) -> Path:
    return canary_audit_dir(project_name, sortie_dir=sortie_dir) / INPUT_ARTIFACT_NAME


def dry_run_path(project_name: str, *, sortie_dir: Path | None = None) -> Path:
    return canary_audit_dir(project_name, sortie_dir=sortie_dir) / DRY_RUN_ARTIFACT_NAME


def result_path(project_name: str, *, sortie_dir: Path | None = None) -> Path:
    return canary_audit_dir(project_name, sortie_dir=sortie_dir) / RESULT_ARTIFACT_NAME


def transport_path(project_name: str, *, sortie_dir: Path | None = None) -> Path:
    return canary_audit_dir(project_name, sortie_dir=sortie_dir) / TRANSPORT_ARTIFACT_NAME


def canary_sourcemap_path(project_name: str, *, sortie_dir: Path | None = None) -> Path:
    return canary_audit_dir(project_name, sortie_dir=sortie_dir) / CANARY_SOURCEMAP_NAME


def report_path(project_name: str, *, sortie_dir: Path | None = None) -> Path:
    return canary_audit_dir(project_name, sortie_dir=sortie_dir) / REPORT_NAME


def production_source_map_path(project_name: str, *, sortie_dir: Path | None = None) -> Path:
    return source_map_path(project_name, sortie_dir=sortie_dir)


def write_bytes_atomic(path: Path, payload: Mapping[str, Any] | str) -> Path:
    """
    Écriture atomique UTF-8 via write_bytes (pas de \\n → \\r\\n Windows).

    JSON déterministe : indent=2, ensure_ascii=False, newline final.
    """
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
    existed_before: bool = False,
) -> None:
    path = production_source_map_path(project_name, sortie_dir=sortie_dir)
    if path.exists() and not existed_before:
        raise RuntimeError(
            f"Le canary a créé un source_map de production : {path}"
        )
