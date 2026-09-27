"""
Artefacts protégés pour l'essai #2 — liste 3B.5.2 + politique/rapport 3B.5.2.

L'essai #2 LIT ces fichiers ; il ne doit en changer aucun octet, y compris
les artefacts historiques de l'essai #1.
"""

from __future__ import annotations

from pathlib import Path

from app.language_cleanup.transcript_source import audit_dir
from app.semantic_canary.integrity import sha256_of_file
from app.source_analysis.protected import ProtectedSnapshot, compare_protected
from app.source_analysis_global_clean import integrity as final_integrity
from app.source_analysis_long_run_policy import integrity as prior_integrity
from app.source_analysis_long_run_policy.constants import (
    POLICY_ARTIFACT_NAME,
    REPORT_NAME as POLICY_REPORT_NAME,
)

PHASE_3B52_NOW_HISTORICAL = (
    f"audit/{POLICY_ARTIFACT_NAME}",
    f"audit/{POLICY_REPORT_NAME}",
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
    for key in PHASE_3B52_NOW_HISTORICAL:
        paths[key] = directory / Path(key).name
    return paths


def snapshot_attempt2_protected(
    project_name: str,
    *,
    sortie_dir: Path | None = None,
    require_all: bool = True,
) -> ProtectedSnapshot:
    # require_all=False sur 3B.5.2 : le source_map canary ultra-compact
    # est OPTIONAL depuis 3B Final. 3B.5.1 le re-exigeait par erreur.
    base = prior_integrity.snapshot_long_run_policy_protected(
        project_name,
        sortie_dir=sortie_dir,
        require_all=False,
    )
    hashes = dict(base.hashes)
    missing: list[str] = []
    optional = set(final_integrity.OPTIONAL_PROTECTED)
    expected = extra_protected_paths(project_name, sortie_dir=sortie_dir)
    for key, path in expected.items():
        if key in hashes:
            continue
        if not Path(path).is_file():
            if key in optional:
                continue
            missing.append(key)
            continue
        hashes[key] = sha256_of_file(path)
    if require_all:
        from app.source_analysis.protected import protected_paths

        for key, path in protected_paths(
            project_name, sortie_dir=sortie_dir
        ).items():
            if key in hashes:
                continue
            if not Path(path).is_file():
                missing.append(key)
    if require_all and missing:
        raise FileNotFoundError(
            "Artefact(s) protégé(s) essai #2 absent(s) : " + ", ".join(missing)
        )
    return ProtectedSnapshot(hashes=hashes)


def assert_protected_unchanged(
    before: ProtectedSnapshot,
    after: ProtectedSnapshot,
) -> None:
    violations = compare_protected(before, after)
    if violations:
        raise RuntimeError(
            "Artefacts protégés modifiés par l'essai #2 : "
            + ", ".join(violations)
        )
