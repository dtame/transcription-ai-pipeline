"""Écriture atomique des artefacts A.28 — isolés, jamais production."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from app.language_cleanup.transcript_source import audit_dir
from app.source_analysis_v2_grammar_canary.writer import write_bytes_atomic
from app.source_analysis_v31_remaining_windows.constants import (
    PHASE,
    PREFLIGHT_ARTIFACT,
    READY_BEFORE,
    READY_STATE_ARTIFACT,
    RELATION_CROSS_ARTIFACT,
    REPORT_NAME,
    SCHEMA_VERSION,
    window_artifact,
)
from app.source_analysis_v31_remaining_windows.paths import (
    candidate_cache_dir,
    candidate_window_dir,
)
from app.source_analysis_v31_remaining_windows.relations import build_relation_cross
from app.source_analysis_v31_remaining_windows.report import render_report
from app.source_analysis_v31_remaining_windows.runner import RemainingWindowsResult


def artifact_path(project_name: str, name: str, *, sortie_dir: Path | None = None) -> Path:
    return audit_dir(project_name, sortie_dir=sortie_dir) / name


def write_preflight_artifact(
    project_name: str,
    preflight: Mapping[str, Any],
    *,
    sortie_dir: Path | None = None,
) -> Path:
    payload = dict(preflight)
    payload.pop("bundle", None)
    payload.pop("verified", None)
    payload["schema_version"] = SCHEMA_VERSION
    payload["phase"] = PHASE
    payload["secrets_included"] = False
    return write_bytes_atomic(
        artifact_path(project_name, PREFLIGHT_ARTIFACT, sortie_dir=sortie_dir),
        payload,
    )


def _persist_candidate(
    project_name: str,
    window_result: Mapping[str, Any],
    *,
    sortie_dir: Path | None,
) -> dict[str, str]:
    transport = window_result.get("transport")
    if not isinstance(transport, Mapping):
        return {}
    execution = window_result.get("execution") or {}
    review = window_result.get("review") or {}
    canonical = window_result.get("canonical") or {}
    if not execution.get("technical_ok"):
        return {}
    if review.get("semantic_quality") != "ACCEPTABLE_FOR_LOCAL_EXTRACTION":
        return {}
    if execution.get("v31_validator") != "PASS":
        return {}
    if not (execution.get("src_forensic") or {}).get("src_success"):
        return {}
    if execution.get("result") != "PASS":
        return {}
    if int(execution.get("idea_subtype_leakage") or 0) != 0:
        return {}
    if canonical.get("mixed_compatibility") != "PASS":
        return {}
    if (canonical.get("local") or {}).get("idea_validation") != "PASS":
        return {}
    signature = execution.get("analysis_signature")
    window_id = str(window_result.get("window_id") or execution.get("window_id") or "")
    if not signature or not window_id:
        return {}
    isolated = candidate_window_dir(project_name, window_id, sortie_dir=sortie_dir)
    cache = candidate_cache_dir(
        project_name, str(signature), window_id, sortie_dir=sortie_dir
    )
    metadata = {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "window_id": window_id,
        "analysis_signature": signature,
        "candidate_only": True,
        "production_analyzer_must_not_consume": True,
        "transport": "semantic-transport-v3.1-local-lite",
        "prompt": "window-analysis-1.4.0",
        "thinking_mode": "disabled",
        "architecture": "GLOBALIZE_IDEA_SUBTYPE",
        "technical_ok": True,
        "semantic_quality": review.get("semantic_quality"),
    }
    written: dict[str, str] = {}
    for root, label in ((isolated, "isolated"), (cache, "cache")):
        write_bytes_atomic(root / "transport.json", dict(transport))
        write_bytes_atomic(root / "metadata.json", metadata)
        written[label] = str(root)
    return written


def write_window_artifacts(
    project_name: str,
    window_result: Mapping[str, Any],
    *,
    sortie_dir: Path | None = None,
) -> dict[str, Path]:
    stored = _persist_candidate(project_name, window_result, sortie_dir=sortie_dir)
    execution = dict(window_result.get("execution") or {})
    execution["candidate_storage"] = stored
    window_id = str(window_result.get("window_id") or execution.get("window_id"))
    written = {
        "execution": write_bytes_atomic(
            artifact_path(
                project_name,
                window_artifact(window_id, "execution"),
                sortie_dir=sortie_dir,
            ),
            {
                "schema_version": SCHEMA_VERSION,
                "phase": PHASE,
                "window_id": window_id,
                "error": window_result.get("error"),
                "engine_generate_attempts": window_result.get(
                    "engine_generate_attempts"
                ),
                "anthropic_post_attempts": window_result.get("anthropic_post_attempts"),
                "execution": execution,
            },
        )
    }
    if window_result.get("metadata"):
        written["contract"] = write_bytes_atomic(
            artifact_path(
                project_name,
                window_artifact(window_id, "contract_analysis"),
                sortie_dir=sortie_dir,
            ),
            window_result["metadata"],
        )
    if window_result.get("src_audit"):
        written["src"] = write_bytes_atomic(
            artifact_path(
                project_name,
                window_artifact(window_id, "src_analysis"),
                sortie_dir=sortie_dir,
            ),
            window_result["src_audit"],
        )
    if window_result.get("handles"):
        written["handles"] = write_bytes_atomic(
            artifact_path(
                project_name,
                window_artifact(window_id, "handle_analysis"),
                sortie_dir=sortie_dir,
            ),
            window_result["handles"],
        )
    if window_result.get("review"):
        written["review"] = write_bytes_atomic(
            artifact_path(
                project_name,
                window_artifact(window_id, "semantic_review"),
                sortie_dir=sortie_dir,
            ),
            window_result["review"],
        )
    if window_result.get("canonical"):
        written["canonical"] = write_bytes_atomic(
            artifact_path(
                project_name,
                window_artifact(window_id, "canonical_reconstruction"),
                sortie_dir=sortie_dir,
            ),
            window_result["canonical"],
        )
    return written


def write_phase_artifacts(
    project_name: str,
    result: RemainingWindowsResult,
    *,
    sortie_dir: Path | None = None,
    tests: str | None = None,
) -> dict[str, Path]:
    for window_result in result.windows.values():
        write_window_artifacts(project_name, window_result, sortie_dir=sortie_dir)
    cross = build_relation_cross(result)
    result.relation_cross = cross
    ready_state = {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "ready_before": READY_BEFORE,
        "ready_after": f"{result.ready_after_count} / 7",
        "ready_after_count": result.ready_after_count,
        "historical": {"WIN001": "READY", "WIN004": "READY"},
        "attempted": {
            window_id: (item.get("execution") or {}).get("result")
            for window_id, item in result.windows.items()
        },
        "phase_result": result.phase_result,
        "stopped_at": result.stopped_at,
        "consolidation_authorized": False,
        "source_map": "NOT PUBLISHED",
        "phase_3b": "INCOMPLETE",
    }
    written = {
        "relations": write_bytes_atomic(
            artifact_path(project_name, RELATION_CROSS_ARTIFACT, sortie_dir=sortie_dir),
            cross,
        ),
        "ready": write_bytes_atomic(
            artifact_path(project_name, READY_STATE_ARTIFACT, sortie_dir=sortie_dir),
            ready_state,
        ),
        "report": write_bytes_atomic(
            artifact_path(project_name, REPORT_NAME, sortie_dir=sortie_dir),
            render_report(result, tests=tests),
        ),
    }
    return written


__all__ = [
    "artifact_path",
    "write_phase_artifacts",
    "write_preflight_artifact",
    "write_window_artifacts",
]
