"""Lecture seule de la réponse A.35 sauvée. Aucune réparation. Aucune écriture."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from app.language_cleanup.transcript_source import audit_dir
from app.paths import SORTIE_DIR
from app.semantic_canary.integrity import sha256_of_file
from app.source_analysis.writer import source_map_path
from app.source_analysis_v31_global_canary_forensics.constants import (
    A35_FORENSIC_RELATIVE,
    A35_RAW_SHA256,
    A35_RAW_SIZE,
    A35_REPORT_NAME,
    A35_REQUEST_ID,
    A35_REQUEST_IDENTITY,
    PROJECT_NAME,
    PROTECTED_HISTORICAL,
)


def _sortie_root(sortie_dir: Path | None = None) -> Path:
    return Path(sortie_dir) if sortie_dir is not None else SORTIE_DIR


def a35_forensic_dir(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> Path:
    return _sortie_root(sortie_dir) / project_name / Path(A35_FORENSIC_RELATIVE)


def a35_raw_path(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> Path:
    return a35_forensic_dir(project_name, sortie_dir=sortie_dir) / (
        "provider_raw_response.bin"
    )


def a35_envelope_path(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> Path:
    return a35_forensic_dir(project_name, sortie_dir=sortie_dir) / (
        "provider_http_envelope.json"
    )


def read_a35_raw_bytes(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> bytes:
    path = a35_raw_path(project_name, sortie_dir=sortie_dir)
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != A35_RAW_SHA256:
        raise ValueError(
            f"A.35 raw hash drift: {digest} ≠ {A35_RAW_SHA256}. Evidence must stay byte-identical."
        )
    if len(raw) != A35_RAW_SIZE:
        raise ValueError(
            f"A.35 raw size drift: {len(raw)} ≠ {A35_RAW_SIZE}."
        )
    return raw


def extract_a35_text_and_json(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> tuple[str, dict[str, Any], bytes]:
    raw = read_a35_raw_bytes(project_name, sortie_dir=sortie_dir)
    data = json.loads(raw.decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError("A.35 raw JSON is not an object")
    blocks = data.get("content") or []
    parts: list[str] = []
    if isinstance(blocks, list):
        for block in blocks:
            if isinstance(block, dict) and isinstance(block.get("text"), str):
                parts.append(block["text"])
    text = "".join(parts)
    return text, data, raw


def load_a35_envelope(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> dict[str, Any]:
    path = a35_envelope_path(project_name, sortie_dir=sortie_dir)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("A.35 envelope is not an object")
    return payload


def verify_a35_identity(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> dict[str, Any]:
    envelope = load_a35_envelope(project_name, sortie_dir=sortie_dir)
    raw = read_a35_raw_bytes(project_name, sortie_dir=sortie_dir)
    request_id = envelope.get("request_id") or (
        (envelope.get("headers_subset") or {}).get("request-id")
    )
    identity = envelope.get("analysis_signature")
    ok = (
        request_id == A35_REQUEST_ID
        and identity == A35_REQUEST_IDENTITY
        and envelope.get("raw_sha256") == A35_RAW_SHA256
        and int(envelope.get("raw_size") or 0) == A35_RAW_SIZE
        and hashlib.sha256(raw).hexdigest() == A35_RAW_SHA256
    )
    return {
        "ok": ok,
        "request_id": request_id,
        "expected_request_id": A35_REQUEST_ID,
        "analysis_signature": identity,
        "expected_identity": A35_REQUEST_IDENTITY,
        "raw_sha256": hashlib.sha256(raw).hexdigest(),
        "raw_size": len(raw),
        "http_status": envelope.get("http_status"),
        "finish_reason": envelope.get("finish_reason"),
        "thinking_tokens": (
            ((envelope.get("usage") or {}).get("output_tokens_details") or {}).get(
                "thinking_tokens"
            )
        ),
    }


def protected_a36_historical_hashes(
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


def a35_report_path(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> Path:
    return audit_dir(project_name, sortie_dir=sortie_dir) / A35_REPORT_NAME


def production_source_map_present(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> bool:
    return source_map_path(project_name, sortie_dir=sortie_dir).is_file()


__all__ = [
    "a35_envelope_path",
    "a35_forensic_dir",
    "a35_raw_path",
    "a35_report_path",
    "extract_a35_text_and_json",
    "load_a35_envelope",
    "production_source_map_present",
    "protected_a36_historical_hashes",
    "read_a35_raw_bytes",
    "verify_a35_identity",
]
