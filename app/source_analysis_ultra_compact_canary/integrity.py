"""
Intégrité des artefacts protégés — liste 3B étendue des fichiers 3B.4 / 3B.4.1 / 3B.4.2.

Le canary LIT ces fichiers ; il ne doit en changer aucun octet.
"""

from __future__ import annotations

from pathlib import Path

from app.language_cleanup.transcript_source import audit_dir
from app.semantic_canary.integrity import sha256_of_file
from app.source_analysis.compact_audit import AUDIT_ARTIFACT_NAME as COMPACT_AUDIT_NAME
from app.source_analysis.protected import (
    ProtectedSnapshot,
    compare_protected,
    protected_paths,
    snapshot_protected,
)
from app.source_analysis.ultra_compact_audit import AUDIT_ARTIFACT_NAME as ULTRA_AUDIT_NAME

PHASE_3B_REPORT_NAME = "PHASE_3B_REAL_SOURCE_ANALYZER_CLEAN_REPORT.md"
PHASE_3B4_REPORT_NAME = "PHASE_3B4_COMPACT_ANTHROPIC_SCHEMA_REPORT.md"
PHASE_3B41_REPORT_NAME = "PHASE_3B41_SERVER_GRAMMAR_CANARY_REPORT.md"
PHASE_3B42_REPORT_NAME = "PHASE_3B42_ULTRA_COMPACT_SEMANTIC_TRANSPORT_REPORT.md"
SCHEMA_CANARY_INPUT = "source_analysis_schema_canary_input.json"
SCHEMA_CANARY_RESULT = "source_analysis_schema_canary_result.json"

EXTRA_PROTECTED_KEYS = (
    f"audit/{PHASE_3B_REPORT_NAME}",
    f"audit/{PHASE_3B4_REPORT_NAME}",
    f"audit/{COMPACT_AUDIT_NAME}",
    f"audit/{PHASE_3B41_REPORT_NAME}",
    f"audit/{SCHEMA_CANARY_INPUT}",
    f"audit/{SCHEMA_CANARY_RESULT}",
    f"audit/{PHASE_3B42_REPORT_NAME}",
    f"audit/{ULTRA_AUDIT_NAME}",
)


def extra_protected_paths(
    project_name: str,
    *,
    sortie_dir: Path | None = None,
) -> dict[str, Path]:
    directory = audit_dir(project_name, sortie_dir=sortie_dir)
    return {
        f"audit/{PHASE_3B_REPORT_NAME}": directory / PHASE_3B_REPORT_NAME,
        f"audit/{PHASE_3B4_REPORT_NAME}": directory / PHASE_3B4_REPORT_NAME,
        f"audit/{COMPACT_AUDIT_NAME}": directory / COMPACT_AUDIT_NAME,
        f"audit/{PHASE_3B41_REPORT_NAME}": directory / PHASE_3B41_REPORT_NAME,
        f"audit/{SCHEMA_CANARY_INPUT}": directory / SCHEMA_CANARY_INPUT,
        f"audit/{SCHEMA_CANARY_RESULT}": directory / SCHEMA_CANARY_RESULT,
        f"audit/{PHASE_3B42_REPORT_NAME}": directory / PHASE_3B42_REPORT_NAME,
        f"audit/{ULTRA_AUDIT_NAME}": directory / ULTRA_AUDIT_NAME,
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
            "Artefact(s) protégé(s) canary 3B.4.3 absent(s) : " + ", ".join(missing)
        )

    return ProtectedSnapshot(hashes=hashes)


def assert_protected_unchanged(
    before: ProtectedSnapshot,
    after: ProtectedSnapshot,
) -> None:
    violations = compare_protected(before, after)
    if violations:
        raise RuntimeError(
            "Artefacts protégés modifiés par le canary 3B.4.3 : "
            + ", ".join(violations)
        )
