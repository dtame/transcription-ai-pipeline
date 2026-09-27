"""
Intégrité des artefacts protégés — liste 3B étendue jusqu'à 3B.4.5.

Le run LIT ces fichiers ; il ne doit en changer aucun octet.
"""

from __future__ import annotations

from pathlib import Path

from app.language_cleanup.transcript_source import audit_dir
from app.semantic_canary.integrity import sha256_of_file
from app.source_analysis.protected import (
    ProtectedSnapshot,
    compare_protected,
    snapshot_protected,
)
from app.source_analysis_vocabulary_compliance_canary import integrity as canary_integrity

OPTIONAL_PROTECTED = (
    "audit/source_analysis_ultra_compact_canary_source_map.json",
)

PHASE_3B45_NOW_HISTORICAL = (
    "audit/PHASE_3B45_CANONICAL_VOCABULARY_COMPLIANCE_CANARY_REPORT.md",
    "audit/source_analysis_vocabulary_compliance_canary_input.json",
    "audit/source_analysis_vocabulary_compliance_canary_dry_run.json",
    "audit/source_analysis_vocabulary_compliance_canary_transport.json",
    "audit/source_analysis_vocabulary_compliance_canary_result.json",
    "audit/source_analysis_vocabulary_compliance_canary_source_map.json",
)


def extra_protected_paths(
    project_name: str,
    *,
    sortie_dir: Path | None = None,
) -> dict[str, Path]:
    paths = dict(
        canary_integrity.extra_protected_paths(project_name, sortie_dir=sortie_dir)
    )
    directory = audit_dir(project_name, sortie_dir=sortie_dir)
    for key in PHASE_3B45_NOW_HISTORICAL:
        paths[key] = directory / Path(key).name
    paths[OPTIONAL_PROTECTED[0]] = directory / Path(OPTIONAL_PROTECTED[0]).name
    return paths


def snapshot_final_protected(
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
    optional = set(OPTIONAL_PROTECTED)

    for key, path in extra_protected_paths(project_name, sortie_dir=sortie_dir).items():
        if not Path(path).is_file():
            if key in optional:
                continue
            missing.append(key)
            continue
        hashes[key] = sha256_of_file(path)

    if require_all and missing:
        raise FileNotFoundError(
            "Artefact(s) protégé(s) 3B Final absent(s) : " + ", ".join(missing)
        )

    return ProtectedSnapshot(hashes=hashes)


def assert_protected_unchanged(
    before: ProtectedSnapshot,
    after: ProtectedSnapshot,
) -> None:
    violations = compare_protected(before, after)
    if violations:
        raise RuntimeError(
            "Artefacts protégés modifiés par le run 3B Final : "
            + ", ".join(violations)
        )
