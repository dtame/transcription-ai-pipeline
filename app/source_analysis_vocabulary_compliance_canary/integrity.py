"""
Intégrité des artefacts protégés — liste 3B étendue jusqu'à 3B.4.4.

Le canary LIT ces fichiers ; il ne doit en changer aucun octet.
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
from app.source_analysis.vocabulary_audit import extra_protected_paths as extra_3b44

PHASE_3B44_REPORT = "PHASE_3B44_CANONICAL_VOCABULARY_CONTRACT_REPORT.md"
VOCABULARY_AUDIT = "source_analysis_vocabulary_contract_audit.json"
ULTRA_CANARY_DRY_RUN = "source_analysis_ultra_compact_canary_dry_run.json"
SCHEMA_CANARY_DRY_RUN = "source_analysis_schema_canary_dry_run.json"

PHASE_3B45_EXTRA = (
    f"audit/{PHASE_3B44_REPORT}",
    f"audit/{VOCABULARY_AUDIT}",
    f"audit/{ULTRA_CANARY_DRY_RUN}",
    f"audit/{SCHEMA_CANARY_DRY_RUN}",
)


def extra_protected_paths(
    project_name: str,
    *,
    sortie_dir: Path | None = None,
) -> dict[str, Path]:
    paths = dict(extra_3b44(project_name, sortie_dir=sortie_dir))
    directory = audit_dir(project_name, sortie_dir=sortie_dir)
    paths[f"audit/{PHASE_3B44_REPORT}"] = directory / PHASE_3B44_REPORT
    paths[f"audit/{VOCABULARY_AUDIT}"] = directory / VOCABULARY_AUDIT
    paths[f"audit/{ULTRA_CANARY_DRY_RUN}"] = directory / ULTRA_CANARY_DRY_RUN
    paths[f"audit/{SCHEMA_CANARY_DRY_RUN}"] = directory / SCHEMA_CANARY_DRY_RUN
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
            "Artefact(s) protégé(s) canary 3B.4.5 absent(s) : " + ", ".join(missing)
        )

    return ProtectedSnapshot(hashes=hashes)


def assert_protected_unchanged(
    before: ProtectedSnapshot,
    after: ProtectedSnapshot,
) -> None:
    violations = compare_protected(before, after)
    if violations:
        raise RuntimeError(
            "Artefacts protégés modifiés par le canary 3B.4.5 : "
            + ", ".join(violations)
        )
