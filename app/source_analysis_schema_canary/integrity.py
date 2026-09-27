"""
Intégrité des artefacts protégés — liste 3B étendue des fichiers 3B.4.

Le canary LIT ces fichiers ; il ne doit en changer aucun octet.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.language_cleanup.transcript_source import audit_dir
from app.semantic_canary.integrity import sha256_of_file
from app.source_analysis.compact_audit import AUDIT_ARTIFACT_NAME
from app.source_analysis.protected import (
    PROTECTED_KEYS,
    ProtectedSnapshot,
    compare_protected,
    protected_paths,
    snapshot_protected,
)

PHASE_3B_REPORT_NAME = "PHASE_3B_REAL_SOURCE_ANALYZER_CLEAN_REPORT.md"
PHASE_3B_REPORT = f"audit/{PHASE_3B_REPORT_NAME}"
PHASE_3B4_REPORT = "audit/PHASE_3B4_COMPACT_ANTHROPIC_SCHEMA_REPORT.md"
COMPACT_SCHEMA_AUDIT = f"audit/{AUDIT_ARTIFACT_NAME}"

EXTRA_PROTECTED_KEYS = (
    PHASE_3B_REPORT,
    PHASE_3B4_REPORT,
    COMPACT_SCHEMA_AUDIT,
)

CANARY_PROTECTED_KEYS = PROTECTED_KEYS + EXTRA_PROTECTED_KEYS


def extra_protected_paths(
    project_name: str,
    *,
    sortie_dir: Path | None = None,
) -> dict[str, Path]:
    directory = audit_dir(project_name, sortie_dir=sortie_dir)
    return {
        PHASE_3B_REPORT: directory / PHASE_3B_REPORT_NAME,
        PHASE_3B4_REPORT: directory / "PHASE_3B4_COMPACT_ANTHROPIC_SCHEMA_REPORT.md",
        COMPACT_SCHEMA_AUDIT: directory / AUDIT_ARTIFACT_NAME,
    }


def canary_protected_paths(
    project_name: str,
    *,
    sortie_dir: Path | None = None,
) -> dict[str, Path]:
    paths = dict(protected_paths(project_name, sortie_dir=sortie_dir))
    paths.update(extra_protected_paths(project_name, sortie_dir=sortie_dir))
    return paths


def snapshot_canary_protected(
    project_name: str,
    *,
    sortie_dir: Path | None = None,
    require_all: bool = True,
) -> ProtectedSnapshot:
    base = snapshot_protected(
        project_name,
        sortie_dir=sortie_dir,
        require_all=require_all,
    )
    hashes = dict(base.hashes)
    missing: list[str] = []

    for key, path in extra_protected_paths(project_name, sortie_dir=sortie_dir).items():
        if not Path(path).is_file():
            missing.append(key)
            continue
        hashes[key] = sha256_of_file(path)

    if require_all and missing:
        raise FileNotFoundError(
            "Artefact(s) protégé(s) canary absent(s) : " + ", ".join(missing)
        )

    return ProtectedSnapshot(hashes=hashes)


def assert_protected_unchanged(
    before: ProtectedSnapshot,
    after: ProtectedSnapshot,
) -> None:
    violations = compare_protected(before, after)
    if violations:
        raise RuntimeError(
            "Artefacts protégés modifiés par le canary : " + ", ".join(violations)
        )
