"""Lecture seule des preuves A.15 / A.13. Aucune écriture. Aucune réparation."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from app.cleanup_application.writer import clean_json_path
from app.language_cleanup.transcript_source import audit_dir
from app.paths import SORTIE_DIR
from app.semantic_canary.integrity import sha256_of_file
from app.source_analysis.writer import source_map_path
from app.source_analysis_v2_a15_forensics.constants import (
    A15_EXECUTION_ARTIFACT,
    A15_FORENSIC_RELATIVE,
    A15_RAW_SHA256,
    A15_RAW_SIZE,
    A15_REPORT_NAME,
    PROJECT_NAME,
    PROTECTED_A15,
)
from app.source_analysis_v2_link_semantics.constants import PROTECTED_A13
from app.source_analysis_v2_link_semantics.evidence import protected_a13_hashes
from app.source_analysis_v2_real_win001.paths import (
    candidate_cache_dir,
    candidate_windows_root,
    production_win001_present,
)


def _sortie_root(sortie_dir: Path | None = None) -> Path:
    return Path(sortie_dir) if sortie_dir is not None else SORTIE_DIR


def a15_forensic_dir(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> Path:
    return _sortie_root(sortie_dir) / project_name / Path(A15_FORENSIC_RELATIVE)


def a15_raw_path(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> Path:
    return a15_forensic_dir(project_name, sortie_dir=sortie_dir) / "provider_raw_response.bin"


def a15_envelope_path(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> Path:
    return (
        a15_forensic_dir(project_name, sortie_dir=sortie_dir)
        / "provider_http_envelope.json"
    )


def read_a15_raw_bytes(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> bytes:
    path = a15_raw_path(project_name, sortie_dir=sortie_dir)
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != A15_RAW_SHA256:
        raise ValueError(
            f"A.15 raw hash drift: {digest} ≠ {A15_RAW_SHA256}. Evidence must stay byte-identical."
        )
    if len(raw) != A15_RAW_SIZE:
        raise ValueError(f"A.15 raw size drift: {len(raw)} ≠ {A15_RAW_SIZE}.")
    return raw


def protected_a15_hashes(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> dict[str, str]:
    root = _sortie_root(sortie_dir) / project_name
    hashes: dict[str, str] = {}
    for rel in PROTECTED_A15:
        path = root / rel
        if path.is_file():
            hashes[rel] = sha256_of_file(path)
    return hashes


def assert_a15_evidence_intact(
    before: dict[str, str],
    after: dict[str, str],
) -> None:
    for key, digest in before.items():
        if after.get(key) != digest:
            raise ValueError(f"A.15 evidence mutated: {key}")


def protected_historical_hashes(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> dict[str, str]:
    out = dict(protected_a13_hashes(project_name, sortie_dir=sortie_dir))
    out.update(protected_a15_hashes(project_name, sortie_dir=sortie_dir))
    return out


def evidence_inventory(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> dict[str, Any]:
    raw = a15_raw_path(project_name, sortie_dir=sortie_dir)
    envelope = a15_envelope_path(project_name, sortie_dir=sortie_dir)
    audit = audit_dir(project_name, sortie_dir=sortie_dir)
    from app.source_analysis_v2_a15_forensics.constants import A15_SIGNATURE

    cache_real = candidate_cache_dir(
        project_name, A15_SIGNATURE, sortie_dir=sortie_dir
    )
    isolated = candidate_windows_root(project_name, sortie_dir=sortie_dir)
    return {
        "raw_present": raw.is_file(),
        "envelope_present": envelope.is_file(),
        "execution_present": (audit / A15_EXECUTION_ARTIFACT).is_file(),
        "report_present": (audit / A15_REPORT_NAME).is_file(),
        "a13_protected": list(PROTECTED_A13),
        "a15_hashes": protected_a15_hashes(project_name, sortie_dir=sortie_dir),
        "a13_hashes": protected_a13_hashes(project_name, sortie_dir=sortie_dir),
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
    }


__all__ = [
    "a15_envelope_path",
    "a15_forensic_dir",
    "a15_raw_path",
    "assert_a15_evidence_intact",
    "evidence_inventory",
    "protected_a15_hashes",
    "protected_historical_hashes",
    "read_a15_raw_bytes",
]
