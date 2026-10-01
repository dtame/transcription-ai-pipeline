"""Lecture seule des preuves A.31 / WIN007 / historiques. Aucune écriture."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from app.language_cleanup.transcript_source import audit_dir
from app.paths import SORTIE_DIR
from app.semantic_canary.integrity import sha256_of_file
from app.source_analysis.writer import source_map_path
from app.source_analysis_v31_final_three.paths import (
    candidate_window_dir,
    production_source_map_present,
    production_window_present,
)
from app.source_analysis_v31_src_typo_forensics.constants import (
    A31_REPORT_NAME,
    HISTORICAL_RESPONSES,
    MODE,
    PHASE,
    PROJECT_NAME,
    PROTECTED_HISTORICAL,
    SCHEMA_VERSION,
    WIN007_FORENSIC_RELATIVE,
    WIN007_RAW_SHA256,
    WIN007_RAW_SIZE,
    WIN007_REQUEST_ID,
    WINDOW_ID,
)


def _sortie_root(sortie_dir: Path | None = None) -> Path:
    return Path(sortie_dir) if sortie_dir is not None else SORTIE_DIR


def win007_forensic_dir(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> Path:
    return _sortie_root(sortie_dir) / project_name / Path(WIN007_FORENSIC_RELATIVE)


def win007_raw_path(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> Path:
    return win007_forensic_dir(project_name, sortie_dir=sortie_dir) / (
        "provider_raw_response.bin"
    )


def win007_envelope_path(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> Path:
    return win007_forensic_dir(project_name, sortie_dir=sortie_dir) / (
        "provider_http_envelope.json"
    )


def read_win007_raw_bytes(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> bytes:
    path = win007_raw_path(project_name, sortie_dir=sortie_dir)
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != WIN007_RAW_SHA256:
        raise ValueError(f"WIN007 raw hash drift: {digest} ≠ {WIN007_RAW_SHA256}.")
    if len(raw) != WIN007_RAW_SIZE:
        raise ValueError(f"WIN007 raw size drift: {len(raw)} ≠ {WIN007_RAW_SIZE}.")
    return raw


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON objet attendu : {path}")
    return payload


def extract_text_from_raw(raw: bytes) -> tuple[str, dict[str, Any]]:
    data = json.loads(raw.decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError("WIN007 raw n'est pas un objet JSON")
    texts: list[str] = []
    content = data.get("content")
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                texts.append(str(block.get("text") or ""))
    return "".join(texts), data


def historical_raw_path(
    relative: str,
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> Path:
    return _sortie_root(sortie_dir) / project_name / Path(relative) / (
        "provider_raw_response.bin"
    )


def protected_a32_historical_hashes(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> dict[str, str]:
    root = _sortie_root(sortie_dir) / project_name
    hashes: dict[str, str] = {}
    for rel in PROTECTED_HISTORICAL:
        path = root / rel
        if path.is_file():
            hashes[rel] = sha256_of_file(path)
    return hashes


def assert_historical_intact(before: dict[str, str], after: dict[str, str]) -> None:
    for key, digest in before.items():
        if after.get(key) != digest:
            raise ValueError(f"Historical evidence mutated: {key}")


def evidence_inventory(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> dict[str, Any]:
    audit = audit_dir(project_name, sortie_dir=sortie_dir)
    raw = win007_raw_path(project_name, sortie_dir=sortie_dir)
    envelope = win007_envelope_path(project_name, sortie_dir=sortie_dir)
    historical = []
    for row in HISTORICAL_RESPONSES:
        path = historical_raw_path(row["relative"], project_name, sortie_dir=sortie_dir)
        historical.append(
            {
                **row,
                "raw_present": path.is_file(),
                "raw_size": path.stat().st_size if path.is_file() else 0,
            }
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "read_only": True,
        "repaired": False,
        "normalized": False,
        "promoted": False,
        "win007_raw_present": raw.is_file(),
        "win007_envelope_present": envelope.is_file(),
        "win007_request_id": WIN007_REQUEST_ID,
        "a31_report_present": (audit / A31_REPORT_NAME).is_file(),
        "win005_candidate_present": (
            candidate_window_dir(project_name, "WIN005", sortie_dir=sortie_dir)
            / "transport.json"
        ).is_file(),
        "win006_candidate_present": (
            candidate_window_dir(project_name, "WIN006", sortie_dir=sortie_dir)
            / "transport.json"
        ).is_file(),
        "historical_raw_responses": historical,
        "source_map_present": source_map_path(
            project_name, sortie_dir=sortie_dir
        ).exists(),
        "production_source_map_present": production_source_map_present(
            project_name, sortie_dir=sortie_dir
        ),
        "production_win007_present": production_window_present(
            project_name, WINDOW_ID, sortie_dir=sortie_dir
        ),
        "protected_hashes": protected_a32_historical_hashes(
            project_name, sortie_dir=sortie_dir
        ),
    }


__all__ = [
    "assert_historical_intact",
    "evidence_inventory",
    "extract_text_from_raw",
    "historical_raw_path",
    "protected_a32_historical_hashes",
    "read_json",
    "read_win007_raw_bytes",
    "win007_envelope_path",
    "win007_forensic_dir",
    "win007_raw_path",
]
