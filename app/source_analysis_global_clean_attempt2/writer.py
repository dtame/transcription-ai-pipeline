"""Écriture atomique des artefacts de l'essai #2 — n'écrase pas l'essai #1."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from app.language_cleanup.transcript_source import audit_dir
from app.source_analysis.writer import source_map_path
from app.source_analysis_global_clean.writer import (
    assert_no_new_production_source_map,
    write_bytes_atomic,
)
from app.source_analysis_global_clean_attempt2.constants import (
    DRY_RUN_ARTIFACT_NAME,
    FAILED_NORMALIZED_NAME,
    FAILED_RAW_NAME,
    REPORT_NAME,
    RESULT_ARTIFACT_NAME,
    TRANSPORT_ARTIFACT_NAME,
)

__all__ = [
    "DRY_RUN_ARTIFACT_NAME",
    "FAILED_NORMALIZED_NAME",
    "FAILED_RAW_NAME",
    "REPORT_NAME",
    "RESULT_ARTIFACT_NAME",
    "TRANSPORT_ARTIFACT_NAME",
    "assert_attempt1_artifacts_untouched",
    "dry_run_path",
    "failed_normalized_path",
    "failed_raw_path",
    "production_source_map_path",
    "report_path",
    "result_path",
    "transport_path",
    "write_bytes_atomic",
]


def attempt2_audit_dir(project_name: str, *, sortie_dir: Path | None = None) -> Path:
    return audit_dir(project_name, sortie_dir=sortie_dir)


def dry_run_path(project_name: str, *, sortie_dir: Path | None = None) -> Path:
    return attempt2_audit_dir(project_name, sortie_dir=sortie_dir) / DRY_RUN_ARTIFACT_NAME


def transport_path(project_name: str, *, sortie_dir: Path | None = None) -> Path:
    return attempt2_audit_dir(project_name, sortie_dir=sortie_dir) / TRANSPORT_ARTIFACT_NAME


def result_path(project_name: str, *, sortie_dir: Path | None = None) -> Path:
    return attempt2_audit_dir(project_name, sortie_dir=sortie_dir) / RESULT_ARTIFACT_NAME


def failed_raw_path(project_name: str, *, sortie_dir: Path | None = None) -> Path:
    return attempt2_audit_dir(project_name, sortie_dir=sortie_dir) / FAILED_RAW_NAME


def failed_normalized_path(project_name: str, *, sortie_dir: Path | None = None) -> Path:
    return attempt2_audit_dir(project_name, sortie_dir=sortie_dir) / FAILED_NORMALIZED_NAME


def report_path(project_name: str, *, sortie_dir: Path | None = None) -> Path:
    return attempt2_audit_dir(project_name, sortie_dir=sortie_dir) / REPORT_NAME


def production_source_map_path(project_name: str, *, sortie_dir: Path | None = None) -> Path:
    return source_map_path(project_name, sortie_dir=sortie_dir)


def attempt1_dry_run_path(project_name: str, *, sortie_dir: Path | None = None) -> Path:
    from app.source_analysis_global_clean.writer import dry_run_path as attempt1

    return attempt1(project_name, sortie_dir=sortie_dir)


def attempt1_result_path(project_name: str, *, sortie_dir: Path | None = None) -> Path:
    from app.source_analysis_global_clean.writer import result_path as attempt1

    return attempt1(project_name, sortie_dir=sortie_dir)


def attempt1_report_path(project_name: str, *, sortie_dir: Path | None = None) -> Path:
    from app.source_analysis_global_clean.writer import report_path as attempt1

    return attempt1(project_name, sortie_dir=sortie_dir)


def assert_attempt1_artifacts_untouched(
    project_name: str,
    *,
    sortie_dir: Path | None = None,
    hashes_before: Mapping[str, str] | None = None,
) -> None:
    """Les chemins de l'essai #1 ne doivent pas être les cibles d'écriture #2."""
    if dry_run_path(project_name, sortie_dir=sortie_dir) == attempt1_dry_run_path(
        project_name, sortie_dir=sortie_dir
    ):
        raise RuntimeError("Le dry-run #2 écraserait le dry-run #1.")
    if result_path(project_name, sortie_dir=sortie_dir) == attempt1_result_path(
        project_name, sortie_dir=sortie_dir
    ):
        raise RuntimeError("Le résultat #2 écraserait le résultat #1.")
    if report_path(project_name, sortie_dir=sortie_dir) == attempt1_report_path(
        project_name, sortie_dir=sortie_dir
    ):
        raise RuntimeError("Le rapport #2 écraserait le rapport #1.")
    if hashes_before is None:
        return
    from app.semantic_canary.integrity import sha256_of_file

    for key, expected in hashes_before.items():
        if "source_analysis_global_clean_dry_run.json" in key:
            path = attempt1_dry_run_path(project_name, sortie_dir=sortie_dir)
        elif "source_analysis_global_clean_result.json" in key:
            path = attempt1_result_path(project_name, sortie_dir=sortie_dir)
        elif "PHASE_3B_FINAL_GLOBAL_CLEAN_SOURCE_ANALYZER_REPORT.md" in key:
            path = attempt1_report_path(project_name, sortie_dir=sortie_dir)
        else:
            continue
        if path.is_file() and sha256_of_file(path) != expected:
            raise RuntimeError(f"Artefact essai #1 modifié : {key}")
