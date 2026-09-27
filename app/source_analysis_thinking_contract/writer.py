"""Écriture atomique des artefacts 3B.7.7A.12 — audit seulement."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from app.language_cleanup.transcript_source import audit_dir
from app.source_analysis_thinking_contract.constants import (
    CALL_C_ARTIFACT,
    CONTRACT_ARTIFACT,
    DECISION_ARTIFACT,
    OPTIONS_ARTIFACT,
    PAYLOAD_ARTIFACT,
    PHASE,
    READINESS_ARTIFACT,
    REPORT_NAME,
    SCHEMA_VERSION,
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


def write_audit_bundle(
    project_name: str,
    bundle: Mapping[str, Mapping[str, Any] | str],
    *,
    sortie_dir: Path | None = None,
) -> dict[str, Path]:
    written: dict[str, Path] = {}
    mapping = {
        "official_contract": CONTRACT_ARTIFACT,
        "call_c": CALL_C_ARTIFACT,
        "options": OPTIONS_ARTIFACT,
        "decision": DECISION_ARTIFACT,
        "payload": PAYLOAD_ARTIFACT,
        "readiness": READINESS_ARTIFACT,
        "report": REPORT_NAME,
    }
    for key, name in mapping.items():
        path = artifact_path(project_name, name, sortie_dir=sortie_dir)
        write_bytes_atomic(path, bundle[key])
        written[key] = path
    return written


__all__ = ["artifact_path", "write_audit_bundle", "write_bytes_atomic"]
