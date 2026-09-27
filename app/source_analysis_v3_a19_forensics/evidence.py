"""Lecture seule des preuves A.19 / historiques. Aucune écriture. Aucune réparation."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from app.cleanup_application.writer import clean_json_path
from app.language_cleanup.transcript_source import audit_dir
from app.paths import SORTIE_DIR
from app.semantic_canary.integrity import sha256_of_file
from app.source_analysis.writer import source_map_path
from app.source_analysis_v3_a19_forensics.constants import (
    A19_EXECUTION_ARTIFACT,
    A19_FORENSIC_RELATIVE,
    A19_HANDLE_ARTIFACT,
    A19_PREFLIGHT_ARTIFACT,
    A19_RAW_SHA256,
    A19_RAW_SIZE,
    A19_REPORT_NAME,
    PROJECT_NAME,
    PROTECTED_A19,
    PROTECTED_HISTORICAL,
)
from app.source_analysis_v3_real_win001.facts import protected_a19_historical_hashes
from app.source_analysis_v3_real_win001.paths import (
    candidate_cache_dir,
    candidate_windows_root,
    production_win001_present,
)


def _sortie_root(sortie_dir: Path | None = None) -> Path:
    return Path(sortie_dir) if sortie_dir is not None else SORTIE_DIR


def a19_forensic_dir(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> Path:
    return _sortie_root(sortie_dir) / project_name / Path(A19_FORENSIC_RELATIVE)


def a19_raw_path(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> Path:
    return a19_forensic_dir(project_name, sortie_dir=sortie_dir) / "provider_raw_response.bin"


def a19_envelope_path(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> Path:
    return (
        a19_forensic_dir(project_name, sortie_dir=sortie_dir)
        / "provider_http_envelope.json"
    )


def read_a19_raw_bytes(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> bytes:
    path = a19_raw_path(project_name, sortie_dir=sortie_dir)
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != A19_RAW_SHA256:
        raise ValueError(
            f"A.19 raw hash drift: {digest} ≠ {A19_RAW_SHA256}. Evidence must stay byte-identical."
        )
    if len(raw) != A19_RAW_SIZE:
        raise ValueError(f"A.19 raw size drift: {len(raw)} ≠ {A19_RAW_SIZE}.")
    return raw


def protected_a19_phase_hashes(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> dict[str, str]:
    root = _sortie_root(sortie_dir) / project_name
    hashes = dict(protected_a19_historical_hashes(project_name, sortie_dir=sortie_dir))
    for rel in PROTECTED_A19:
        path = root / rel
        if path.is_file():
            hashes[rel] = sha256_of_file(path)
    return hashes


def assert_a19_evidence_intact(
    before: dict[str, str],
    after: dict[str, str],
) -> None:
    for key, digest in before.items():
        if after.get(key) != digest:
            raise ValueError(f"A.19 / historical evidence mutated: {key}")


def evidence_inventory(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> dict[str, Any]:
    raw = a19_raw_path(project_name, sortie_dir=sortie_dir)
    envelope = a19_envelope_path(project_name, sortie_dir=sortie_dir)
    audit = audit_dir(project_name, sortie_dir=sortie_dir)
    from app.source_analysis_v3_a19_forensics.constants import A19_SIGNATURE

    cache_real = candidate_cache_dir(
        project_name, A19_SIGNATURE, sortie_dir=sortie_dir
    )
    isolated = candidate_windows_root(project_name, sortie_dir=sortie_dir)
    return {
        "raw_present": raw.is_file(),
        "envelope_present": envelope.is_file(),
        "execution_present": (audit / A19_EXECUTION_ARTIFACT).is_file(),
        "preflight_present": (audit / A19_PREFLIGHT_ARTIFACT).is_file(),
        "handle_present": (audit / A19_HANDLE_ARTIFACT).is_file(),
        "report_present": (audit / A19_REPORT_NAME).is_file(),
        "protected_historical": list(PROTECTED_HISTORICAL),
        "protected_a19": list(PROTECTED_A19),
        "hashes": protected_a19_phase_hashes(project_name, sortie_dir=sortie_dir),
        "source_map_present": source_map_path(
            project_name, sortie_dir=sortie_dir
        ).exists(),
        "production_win001_present": production_win001_present(
            project_name, sortie_dir=sortie_dir
        ),
        "candidate_cache_present": cache_real.exists(),
        "isolated_candidate_windows_present": isolated.exists()
        and any(isolated.iterdir()),
        "clean_present": clean_json_path(project_name, sortie_dir=sortie_dir).is_file(),
        "read_only": True,
        "repaired": False,
        "cached_from_invalid": False,
        "normalized": False,
    }


__all__ = [
    "a19_envelope_path",
    "a19_forensic_dir",
    "a19_raw_path",
    "assert_a19_evidence_intact",
    "evidence_inventory",
    "protected_a19_phase_hashes",
    "read_a19_raw_bytes",
]
