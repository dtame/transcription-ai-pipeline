"""Artefacts protégés pour 3B.6 — historique jusqu'à Attempt #2 inclus."""

from __future__ import annotations

from pathlib import Path

from app.language_cleanup.transcript_source import audit_dir
from app.semantic_canary.integrity import sha256_of_file
from app.source_analysis.protected import ProtectedSnapshot, compare_protected
from app.source_analysis_global_clean_attempt2 import integrity as prior_integrity
from app.source_analysis_global_clean_attempt2.constants import (
    DRY_RUN_ARTIFACT_NAME as ATTEMPT2_DRY_RUN,
    REPORT_NAME as ATTEMPT2_REPORT,
    RESULT_ARTIFACT_NAME as ATTEMPT2_RESULT,
)

PHASE_3B_ATTEMPT2_NOW_HISTORICAL = (
    f"audit/{ATTEMPT2_RESULT}",
    f"audit/{ATTEMPT2_DRY_RUN}",
    f"audit/{ATTEMPT2_REPORT}",
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
    for key in PHASE_3B_ATTEMPT2_NOW_HISTORICAL:
        paths[key] = directory / Path(key).name
    return paths


def snapshot_strategy_review_protected(
    project_name: str,
    *,
    sortie_dir: Path | None = None,
    require_all: bool = True,
) -> ProtectedSnapshot:
    base = prior_integrity.snapshot_attempt2_protected(
        project_name,
        sortie_dir=sortie_dir,
        require_all=False,
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
            "Artefact(s) protégé(s) 3B.6 absent(s) : " + ", ".join(missing)
        )
    return ProtectedSnapshot(hashes=hashes)


def assert_protected_unchanged(
    before: ProtectedSnapshot,
    after: ProtectedSnapshot,
) -> None:
    violations = compare_protected(before, after)
    if violations:
        raise RuntimeError(
            "Artefacts protégés modifiés par la revue 3B.6 : "
            + ", ".join(violations)
        )
