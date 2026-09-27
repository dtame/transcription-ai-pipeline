"""Écriture atomique des artefacts A.18 — audit only, jamais production."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from app.language_cleanup.transcript_source import audit_dir
from app.source_analysis_v3_symbolic_grammar_canary.constants import (
    EXECUTION_ARTIFACT,
    HANDLES_ARTIFACT,
    PAYLOAD_ARTIFACT,
    PHASE,
    REPORT_NAME,
    SCHEMA_VERSION,
)
from app.source_analysis_v3_symbolic_grammar_canary.report import (
    bundle_from_result,
    render_report,
)
from app.source_analysis_v3_symbolic_grammar_canary.runner import CanaryRunResult


def artifact_path(project_name: str, name: str, *, sortie_dir: Path | None = None) -> Path:
    return audit_dir(project_name, sortie_dir=sortie_dir) / name


def write_bytes_atomic(path: Path, payload: Mapping[str, Any] | str) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(payload, str):
        content = payload if payload.endswith("\n") else payload + "\n"
    else:
        content = json.dumps(dict(payload), ensure_ascii=False, indent=2) + "\n"
    encoded = content.encode("utf-8")
    partial = path.with_name(path.name + ".partial")
    try:
        partial.write_bytes(encoded)
        if partial.read_bytes() != encoded:
            raise ValueError(f"Octets partiels ≠ contenu canonique pour {path.name}.")
        leftover_name = path.with_name(path.name + ".partial")
        partial.replace(path)
        if leftover_name.exists() and leftover_name != path:
            leftover_name.unlink()
    except BaseException:
        partial.unlink(missing_ok=True)
        raise
    leftover = path.with_name(path.name + ".partial")
    if leftover.exists():
        leftover.unlink()
    return path


def execution_artifact(result: CanaryRunResult, *, extra: Mapping[str, Any] | None = None) -> dict[str, Any]:
    payload = result.to_dict()
    payload["schema_version"] = SCHEMA_VERSION
    payload["phase"] = PHASE
    if extra:
        payload.update(dict(extra))
    return payload


def payload_artifact(result: CanaryRunResult) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "secrets_included": False,
        "payload_audit": result.payload_audit,
        "schema_metrics": result.schema_metrics,
    }


def handles_artifact(result: CanaryRunResult) -> dict[str, Any]:
    exe = result.execution or {}
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "handles": exe.get("handles") or {},
        "reconstruction": exe.get("reconstruction"),
        "structured_parse": exe.get("structured_parse"),
        "v3_decoder": exe.get("v3_decoder"),
        "handle_registry": exe.get("handle_registry"),
        "handle_resolution": exe.get("handle_resolution"),
        "v3_validator": exe.get("v3_validator"),
        "kinds": exe.get("kinds") or [],
        "source_refs": exe.get("source_refs") or [],
        "validation_errors": exe.get("validation_errors") or [],
        "source_map": "NOT PUBLISHED",
        "repaired": False,
    }


def write_canary_artifacts(
    project_name: str,
    result: CanaryRunResult,
    *,
    sortie_dir: Path | None = None,
    report_bundle: Mapping[str, Any] | None = None,
    extra_header: Mapping[str, Any] | None = None,
    dry_run_1: Mapping[str, Any] | None = None,
    dry_run_2: Mapping[str, Any] | None = None,
    files_created: list[str] | None = None,
    files_modified: list[str] | None = None,
) -> dict[str, Path]:
    bundle = report_bundle or bundle_from_result(
        result,
        dry_run_1=dry_run_1,
        dry_run_2=dry_run_2,
        extra_header=extra_header,
        files_created=files_created,
        files_modified=files_modified,
    )
    report_text = render_report(bundle)
    written = {
        "execution": write_bytes_atomic(
            artifact_path(project_name, EXECUTION_ARTIFACT, sortie_dir=sortie_dir),
            execution_artifact(result),
        ),
        "payload": write_bytes_atomic(
            artifact_path(project_name, PAYLOAD_ARTIFACT, sortie_dir=sortie_dir),
            payload_artifact(result),
        ),
        "handles": write_bytes_atomic(
            artifact_path(project_name, HANDLES_ARTIFACT, sortie_dir=sortie_dir),
            handles_artifact(result),
        ),
    }
    if report_text:
        written["report"] = write_bytes_atomic(
            artifact_path(project_name, REPORT_NAME, sortie_dir=sortie_dir),
            report_text,
        )
    return written


__all__ = [
    "artifact_path",
    "execution_artifact",
    "handles_artifact",
    "payload_artifact",
    "write_bytes_atomic",
    "write_canary_artifacts",
]
