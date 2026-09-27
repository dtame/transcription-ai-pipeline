"""Artefacts protégés pour 3B.5.1 — liste 3B.5 + diagnostic/rapport 3B.5."""

from __future__ import annotations

from pathlib import Path

from app.language_cleanup.transcript_source import audit_dir
from app.semantic_canary.integrity import sha256_of_file
from app.source_analysis.protected import ProtectedSnapshot, compare_protected
from app.source_analysis_timeout_audit import integrity as prior_integrity
from app.source_analysis_timeout_audit.constants import (
    DIAGNOSTIC_ARTIFACT_NAME as AUDIT_3B5_JSON,
    REPORT_NAME as AUDIT_3B5_REPORT,
)

PHASE_3B5_NOW_HISTORICAL = (
    f"audit/{AUDIT_3B5_JSON}",
    f"audit/{AUDIT_3B5_REPORT}",
)


def extra_protected_paths(
    project_name: str,
    *,
    sortie_dir: Path | None = None,
) -> dict[str, Path]:
    paths = dict(
        prior_integrity.extra_protected_paths(project_name, sortie_dir=sortie_dir)
    )
    directory = audit_dir(project_name, sortie_dir=sortie_dir)
    for key in PHASE_3B5_NOW_HISTORICAL:
        paths[key] = directory / Path(key).name
    return paths


def snapshot_timeout_config_protected(
    project_name: str,
    *,
    sortie_dir: Path | None = None,
    require_all: bool = True,
) -> ProtectedSnapshot:
    base = prior_integrity.snapshot_timeout_audit_protected(
        project_name,
        sortie_dir=sortie_dir,
        require_all=require_all,
    )
    hashes = dict(base.hashes)
    missing: list[str] = []
    for key, path in extra_protected_paths(
        project_name, sortie_dir=sortie_dir
    ).items():
        if key in hashes:
            continue
        if not Path(path).is_file():
            missing.append(key)
            continue
        hashes[key] = sha256_of_file(path)
    if require_all and missing:
        raise FileNotFoundError(
            "Artefact(s) protégé(s) 3B.5.1 absent(s) : " + ", ".join(missing)
        )
    return ProtectedSnapshot(hashes=hashes)


def assert_protected_unchanged(
    before: ProtectedSnapshot,
    after: ProtectedSnapshot,
) -> None:
    violations = compare_protected(before, after)
    if violations:
        raise RuntimeError(
            "Artefacts protégés modifiés par l'audit 3B.5.1 : "
            + ", ".join(violations)
        )
