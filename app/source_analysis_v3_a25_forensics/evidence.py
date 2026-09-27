"""Lecture seule des preuves A.24 / A.23 / A.22 / A.21 / A.19. Aucune réparation."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from app.cleanup_application.writer import clean_json_path
from app.language_cleanup.transcript_source import audit_dir
from app.paths import SORTIE_DIR
from app.semantic_canary.integrity import sha256_of_file
from app.source_analysis.writer import source_map_path
from app.source_analysis_v3_a25_forensics.constants import (
    A24_EXECUTION_ARTIFACT,
    A24_FORENSIC_RELATIVE,
    A24_HANDLE_ARTIFACT,
    A24_PREFLIGHT_ARTIFACT,
    A24_RAW_SHA256,
    A24_RAW_SIZE,
    A24_REPORT_NAME,
    A24_REVIEW_ARTIFACT,
    A24_SIGNATURE,
    PROJECT_NAME,
    PROTECTED_A24,
    PROTECTED_HISTORICAL,
)
from app.source_analysis_v3_second_window.facts import protected_a22_historical_hashes
from app.source_analysis_v3_second_window.paths import (
    candidate_cache_dir,
    candidate_windows_root,
    production_source_map_present,
    production_window_present,
)


def _sortie_root(sortie_dir: Path | None = None) -> Path:
    return Path(sortie_dir) if sortie_dir is not None else SORTIE_DIR


def a24_forensic_dir(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> Path:
    return _sortie_root(sortie_dir) / project_name / Path(A24_FORENSIC_RELATIVE)


def a24_raw_path(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> Path:
    return a24_forensic_dir(project_name, sortie_dir=sortie_dir) / "provider_raw_response.bin"


def a24_envelope_path(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> Path:
    return (
        a24_forensic_dir(project_name, sortie_dir=sortie_dir)
        / "provider_http_envelope.json"
    )


def read_a24_raw_bytes(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> bytes:
    path = a24_raw_path(project_name, sortie_dir=sortie_dir)
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != A24_RAW_SHA256:
        raise ValueError(
            f"A.24 raw hash drift: {digest} ≠ {A24_RAW_SHA256}. Evidence must stay byte-identical."
        )
    if len(raw) != A24_RAW_SIZE:
        raise ValueError(f"A.24 raw size drift: {len(raw)} ≠ {A24_RAW_SIZE}.")
    return raw


def protected_a24_phase_hashes(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> dict[str, str]:
    root = _sortie_root(sortie_dir) / project_name
    hashes = dict(protected_a22_historical_hashes(project_name, sortie_dir=sortie_dir))
    for rel in PROTECTED_HISTORICAL:
        path = root / rel
        if path.is_file():
            hashes[rel] = sha256_of_file(path)
    return hashes


def assert_a24_evidence_intact(
    before: dict[str, str],
    after: dict[str, str],
) -> None:
    for key, digest in before.items():
        if after.get(key) != digest:
            raise ValueError(f"A.24 / historical evidence mutated: {key}")


def evidence_inventory(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> dict[str, Any]:
    raw = a24_raw_path(project_name, sortie_dir=sortie_dir)
    envelope = a24_envelope_path(project_name, sortie_dir=sortie_dir)
    audit = audit_dir(project_name, sortie_dir=sortie_dir)
    cache_real = candidate_cache_dir(
        project_name, A24_SIGNATURE, "WIN004", sortie_dir=sortie_dir
    )
    isolated = candidate_windows_root(project_name, sortie_dir=sortie_dir)
    return {
        "raw_present": raw.is_file(),
        "envelope_present": envelope.is_file(),
        "execution_present": (audit / A24_EXECUTION_ARTIFACT).is_file(),
        "preflight_present": (audit / A24_PREFLIGHT_ARTIFACT).is_file(),
        "handle_present": (audit / A24_HANDLE_ARTIFACT).is_file(),
        "review_present": (audit / A24_REVIEW_ARTIFACT).is_file(),
        "report_present": (audit / A24_REPORT_NAME).is_file(),
        "protected_historical": list(PROTECTED_HISTORICAL),
        "protected_a24": list(PROTECTED_A24),
        "hashes": protected_a24_phase_hashes(project_name, sortie_dir=sortie_dir),
        "source_map_present": source_map_path(
            project_name, sortie_dir=sortie_dir
        ).exists(),
        "production_source_map_present": production_source_map_present(
            project_name, sortie_dir=sortie_dir
        ),
        "production_win004_present": production_window_present(
            project_name, "WIN004", sortie_dir=sortie_dir
        ),
        "candidate_cache_present": cache_real.exists(),
        "isolated_candidate_windows_present": isolated.exists()
        and any(isolated.iterdir()),
        "clean_present": clean_json_path(project_name, sortie_dir=sortie_dir).is_file(),
        "read_only": True,
        "repaired": False,
        "cached_from_invalid": False,
        "normalized": False,
        "promoted": False,
    }


__all__ = [
    "a24_envelope_path",
    "a24_forensic_dir",
    "a24_raw_path",
    "assert_a24_evidence_intact",
    "evidence_inventory",
    "protected_a24_phase_hashes",
    "read_a24_raw_bytes",
]
