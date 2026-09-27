"""Écriture atomique des artefacts A.25 — nouveaux fichiers seulement."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from app.language_cleanup.transcript_source import audit_dir
from app.source_analysis_v3_a25_forensics.constants import (
    ARCHITECTURE_ARTIFACT,
    DELTA_ARTIFACT,
    FUTURE_ARTIFACT,
    I44_ARTIFACT,
    METADATA_ARTIFACT,
    PHASE,
    POLICY_ARTIFACT,
    REPORT_NAME,
    SCHEMA_VERSION,
    SEMANTIC_ARTIFACT,
    VIOLATION_ARTIFACT,
)


def artifact_path(project_name: str, name: str, *, sortie_dir: Path | None = None) -> Path:
    return audit_dir(project_name, sortie_dir=sortie_dir) / name


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


def _jsonable(payload: Mapping[str, Any]) -> dict[str, Any]:
    skip = {"window", "transcript", "transport"}
    return {key: value for key, value in payload.items() if key not in skip}


def write_audit_bundle(
    project_name: str,
    bundle: Mapping[str, Any],
    *,
    sortie_dir: Path | None = None,
) -> dict[str, Path]:
    written = {
        "violations": write_bytes_atomic(
            artifact_path(project_name, VIOLATION_ARTIFACT, sortie_dir=sortie_dir),
            _jsonable(bundle["inventory"]),
        ),
        "i44": write_bytes_atomic(
            artifact_path(project_name, I44_ARTIFACT, sortie_dir=sortie_dir),
            _jsonable(bundle["i44"]),
        ),
        "metadata": write_bytes_atomic(
            artifact_path(project_name, METADATA_ARTIFACT, sortie_dir=sortie_dir),
            _jsonable(bundle["metadata"]),
        ),
        "architecture": write_bytes_atomic(
            artifact_path(project_name, ARCHITECTURE_ARTIFACT, sortie_dir=sortie_dir),
            _jsonable(bundle["architecture"]),
        ),
        "delta": write_bytes_atomic(
            artifact_path(project_name, DELTA_ARTIFACT, sortie_dir=sortie_dir),
            _jsonable(bundle["delta"]),
        ),
        "semantic": write_bytes_atomic(
            artifact_path(project_name, SEMANTIC_ARTIFACT, sortie_dir=sortie_dir),
            _jsonable(bundle["semantic"]),
        ),
        "policy": write_bytes_atomic(
            artifact_path(project_name, POLICY_ARTIFACT, sortie_dir=sortie_dir),
            _jsonable(bundle["policy"]),
        ),
        "future": write_bytes_atomic(
            artifact_path(project_name, FUTURE_ARTIFACT, sortie_dir=sortie_dir),
            _jsonable(bundle["future"]),
        ),
        "report": write_bytes_atomic(
            artifact_path(project_name, REPORT_NAME, sortie_dir=sortie_dir),
            bundle["report"],
        ),
    }
    return written


__all__ = ["artifact_path", "write_audit_bundle", "write_bytes_atomic"]
