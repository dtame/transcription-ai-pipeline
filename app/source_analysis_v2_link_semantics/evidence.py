"""Lecture seule des preuves A.13. Aucune écriture. Aucune réparation."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from app.language_cleanup.transcript_source import audit_dir
from app.paths import SORTIE_DIR
from app.semantic_canary.integrity import sha256_of_file
from app.source_analysis_v2_link_semantics.constants import (
    A13_EXECUTION_ARTIFACT,
    A13_FORENSIC_RELATIVE,
    A13_PAYLOAD_ARTIFACT,
    A13_RAW_SHA256,
    A13_RAW_SIZE,
    A13_REPORT_NAME,
    A13_REQUEST_IDENTITY,
    PROJECT_NAME,
    PROTECTED_A13,
)


def _sortie_root(sortie_dir: Path | None = None) -> Path:
    return Path(sortie_dir) if sortie_dir is not None else SORTIE_DIR


def a13_forensic_dir(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> Path:
    root = _sortie_root(sortie_dir) / project_name
    return root / Path(A13_FORENSIC_RELATIVE)


def a13_raw_path(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> Path:
    return a13_forensic_dir(project_name, sortie_dir=sortie_dir) / "provider_raw_response.bin"


def a13_envelope_path(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> Path:
    return (
        a13_forensic_dir(project_name, sortie_dir=sortie_dir)
        / "provider_http_envelope.json"
    )


def read_a13_raw_bytes(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> bytes:
    path = a13_raw_path(project_name, sortie_dir=sortie_dir)
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != A13_RAW_SHA256:
        raise ValueError(
            f"A.13 raw hash drift: {digest} ≠ {A13_RAW_SHA256}. Evidence must stay byte-identical."
        )
    if len(raw) != A13_RAW_SIZE:
        raise ValueError(f"A.13 raw size drift: {len(raw)} ≠ {A13_RAW_SIZE}.")
    return raw


def protected_a13_hashes(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> dict[str, str]:
    root = _sortie_root(sortie_dir) / project_name
    hashes: dict[str, str] = {}
    for rel in PROTECTED_A13:
        path = root / rel
        if path.is_file():
            hashes[rel] = sha256_of_file(path)
    return hashes


def assert_a13_evidence_intact(
    before: dict[str, str],
    after: dict[str, str],
) -> None:
    for key, digest in before.items():
        if after.get(key) != digest:
            raise ValueError(f"A.13 evidence mutated: {key}")


def a13_execution_path(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> Path:
    return audit_dir(project_name, sortie_dir=sortie_dir) / A13_EXECUTION_ARTIFACT


def evidence_inventory(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> dict[str, Any]:
    raw = a13_raw_path(project_name, sortie_dir=sortie_dir)
    envelope = a13_envelope_path(project_name, sortie_dir=sortie_dir)
    execution = a13_execution_path(project_name, sortie_dir=sortie_dir)
    audit = audit_dir(project_name, sortie_dir=sortie_dir)
    return {
        "request_identity": A13_REQUEST_IDENTITY,
        "raw_present": raw.is_file(),
        "envelope_present": envelope.is_file(),
        "execution_present": execution.is_file(),
        "payload_present": (audit / A13_PAYLOAD_ARTIFACT).is_file(),
        "report_present": (audit / A13_REPORT_NAME).is_file(),
        "hashes": protected_a13_hashes(project_name, sortie_dir=sortie_dir),
        "read_only": True,
        "repaired": False,
    }


__all__ = [
    "a13_envelope_path",
    "a13_execution_path",
    "a13_forensic_dir",
    "a13_raw_path",
    "assert_a13_evidence_intact",
    "evidence_inventory",
    "protected_a13_hashes",
    "read_a13_raw_bytes",
]
