"""Lecture seule des preuves A.28 / WIN003 / historiques. Aucune écriture."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from app.language_cleanup.transcript_source import audit_dir
from app.paths import SORTIE_DIR
from app.semantic_canary.integrity import sha256_of_file
from app.source_analysis.writer import source_map_path
from app.source_analysis_v3_a22_forensics.evidence import a22_raw_path
from app.source_analysis_v3_a25_forensics.evidence import a24_raw_path
from app.source_analysis_v3_hardened_win001.paths import (
    candidate_cache_dir as a21_candidate_cache_dir,
)
from app.source_analysis_v31_real_win004.paths import (
    candidate_cache_dir as a27_candidate_cache_dir,
)
from app.source_analysis_v31_remaining_windows.paths import (
    candidate_cache_dir as a28_candidate_cache_dir,
    production_source_map_present,
    production_window_present,
)
from app.source_analysis_v31_length_ceiling.constants import (
    A21_SIGNATURE,
    A22_RAW_SHA256,
    A22_RAW_SIZE,
    A24_RAW_SHA256,
    A24_RAW_SIZE,
    A27_SIGNATURE,
    A28_REPORT_NAME,
    MODE,
    PHASE,
    PROJECT_NAME,
    PROTECTED_HISTORICAL,
    SCHEMA_VERSION,
    WIN002_SIGNATURE,
    WIN003_FORENSIC_RELATIVE,
    WIN003_RAW_SHA256,
    WIN003_RAW_SIZE,
    WINDOW_ID,
)


def _sortie_root(sortie_dir: Path | None = None) -> Path:
    return Path(sortie_dir) if sortie_dir is not None else SORTIE_DIR


def win003_forensic_dir(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> Path:
    return _sortie_root(sortie_dir) / project_name / Path(WIN003_FORENSIC_RELATIVE)


def win003_raw_path(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> Path:
    return win003_forensic_dir(project_name, sortie_dir=sortie_dir) / (
        "provider_raw_response.bin"
    )


def win003_envelope_path(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> Path:
    return win003_forensic_dir(project_name, sortie_dir=sortie_dir) / (
        "provider_http_envelope.json"
    )


def read_win003_raw_bytes(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> bytes:
    path = win003_raw_path(project_name, sortie_dir=sortie_dir)
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != WIN003_RAW_SHA256:
        raise ValueError(
            f"WIN003 raw hash drift: {digest} ≠ {WIN003_RAW_SHA256}."
        )
    if len(raw) != WIN003_RAW_SIZE:
        raise ValueError(f"WIN003 raw size drift: {len(raw)} ≠ {WIN003_RAW_SIZE}.")
    return raw


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON objet attendu : {path}")
    return payload


def protected_a29_historical_hashes(
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


def ready_transport_path(
    project_name: str,
    window_id: str,
    *,
    sortie_dir: Path | None = None,
) -> Path:
    if window_id == "WIN001":
        return a21_candidate_cache_dir(
            project_name, A21_SIGNATURE, sortie_dir=sortie_dir
        ) / "transport.json"
    if window_id == "WIN002":
        return (
            a28_candidate_cache_dir(
                project_name,
                WIN002_SIGNATURE,
                "WIN002",
                sortie_dir=sortie_dir,
            )
            / "transport.json"
        )
    if window_id == "WIN004":
        return (
            a27_candidate_cache_dir(
                project_name, A27_SIGNATURE, sortie_dir=sortie_dir
            )
            / "transport.json"
        )
    raise ValueError(f"READY transport inconnu : {window_id}")


def evidence_inventory(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> dict[str, Any]:
    audit = audit_dir(project_name, sortie_dir=sortie_dir)
    raw = win003_raw_path(project_name, sortie_dir=sortie_dir)
    envelope = win003_envelope_path(project_name, sortie_dir=sortie_dir)
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "read_only": True,
        "repaired": False,
        "normalized": False,
        "promoted": False,
        "win003_raw_present": raw.is_file(),
        "win003_envelope_present": envelope.is_file(),
        "a28_report_present": (audit / A28_REPORT_NAME).is_file(),
        "win001_transport_present": ready_transport_path(
            project_name, "WIN001", sortie_dir=sortie_dir
        ).is_file(),
        "win002_transport_present": ready_transport_path(
            project_name, "WIN002", sortie_dir=sortie_dir
        ).is_file(),
        "win004_transport_present": ready_transport_path(
            project_name, "WIN004", sortie_dir=sortie_dir
        ).is_file(),
        "a22_raw_present": a22_raw_path(
            project_name, sortie_dir=sortie_dir
        ).is_file(),
        "a24_raw_present": a24_raw_path(
            project_name, sortie_dir=sortie_dir
        ).is_file(),
        "a22_raw_sha_ok": (
            sha256_of_file(a22_raw_path(project_name, sortie_dir=sortie_dir))
            == A22_RAW_SHA256
            if a22_raw_path(project_name, sortie_dir=sortie_dir).is_file()
            else False
        ),
        "a24_raw_sha_ok": (
            sha256_of_file(a24_raw_path(project_name, sortie_dir=sortie_dir))
            == A24_RAW_SHA256
            if a24_raw_path(project_name, sortie_dir=sortie_dir).is_file()
            else False
        ),
        "a22_raw_size_ok": (
            a22_raw_path(project_name, sortie_dir=sortie_dir).stat().st_size
            == A22_RAW_SIZE
            if a22_raw_path(project_name, sortie_dir=sortie_dir).is_file()
            else False
        ),
        "a24_raw_size_ok": (
            a24_raw_path(project_name, sortie_dir=sortie_dir).stat().st_size
            == A24_RAW_SIZE
            if a24_raw_path(project_name, sortie_dir=sortie_dir).is_file()
            else False
        ),
        "source_map_present": source_map_path(
            project_name, sortie_dir=sortie_dir
        ).exists(),
        "production_source_map_present": production_source_map_present(
            project_name, sortie_dir=sortie_dir
        ),
        "production_win003_present": production_window_present(
            project_name, WINDOW_ID, sortie_dir=sortie_dir
        ),
        "protected_hashes": protected_a29_historical_hashes(
            project_name, sortie_dir=sortie_dir
        ),
    }


__all__ = [
    "assert_historical_intact",
    "evidence_inventory",
    "protected_a29_historical_hashes",
    "read_json",
    "read_win003_raw_bytes",
    "ready_transport_path",
    "win003_envelope_path",
    "win003_forensic_dir",
    "win003_raw_path",
]
