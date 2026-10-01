"""Écriture atomique des artefacts A.35 — canary isolé, jamais production."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from app.language_cleanup.transcript_source import audit_dir
from app.source_analysis_v2_grammar_canary.writer import write_bytes_atomic
from app.source_analysis_v31_global_grammar_canary.constants import (
    CANONICAL_ARTIFACT,
    CONTRACT_ARTIFACT,
    DISPOSITION_ARTIFACT,
    EXECUTION_ARTIFACT,
    FIXTURE_ARTIFACT,
    PHASE,
    READINESS_ARTIFACT,
    REPORT_NAME,
    REQUEST_ARTIFACT,
    SCHEMA_VERSION,
    USAGE_ARTIFACT,
)
from app.source_analysis_v31_global_grammar_canary.fixture import (
    build_synthetic_fixture,
    fixture_payload,
)
from app.source_analysis_v31_global_grammar_canary.paths import (
    canary_artifact_path,
)
from app.source_analysis_v31_global_grammar_canary.report import render_report
from app.source_analysis_v31_global_grammar_canary.runner import CanaryRunResult


def write_canary_artifacts(
    project_name: str,
    result: CanaryRunResult,
    *,
    sortie_dir: Path | None = None,
    tests: str = "offline A.35",
    extra_header: Mapping[str, Any] | None = None,
) -> dict[str, Path]:
    exe = result.execution or {}
    dry = result.dry_run or {}
    fixture = build_synthetic_fixture()
    request_meta = {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "secrets_included": False,
        "prompt_version": dry.get("prompt_version"),
        "transport_version": dry.get("transport"),
        "schema_hash": dry.get("schema_hash") or exe.get("schema_hash"),
        "schema_raw_bytes": dry.get("schema_raw_bytes") or exe.get("schema_raw_bytes"),
        "schema_adapted_bytes": dry.get("schema_adapted_bytes")
        or exe.get("schema_adapted_bytes"),
        "model": dry.get("model"),
        "thinking": dry.get("thinking_mode"),
        "max_output": dry.get("max_output_tokens"),
        "input_ids": list(fixture.idea_input_ids),
        "all_input_ids": sorted(fixture.allowed_input_ids),
        "request_identity": dry.get("request_identity"),
        "authorization_scope": result.authorization_scope,
        "pastoral_content": False,
    }
    contract = {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "structured_parse": exe.get("structured_parse"),
        "transport_decoder": exe.get("transport_decoder"),
        "handle_validation": exe.get("handle_validation"),
        "global_validator": exe.get("global_validator"),
        "no_drop_validator": exe.get("no_drop_validator"),
        "traceability": exe.get("traceability"),
        "relation_validator": exe.get("relation_validator"),
        "canonical_reconstruction": exe.get("canonical_reconstruction"),
        "canonical_validation": exe.get("canonical_validation"),
        "deterministic_replay": exe.get("deterministic_replay"),
        "idea_disposition_coverage": exe.get("idea_disposition_coverage"),
        "silent_drops": exe.get("silent_drops"),
        "inventory": exe.get("inventory"),
        "classifications": exe.get("classifications"),
        "validation_errors": exe.get("validation_errors"),
        "result": exe.get("result"),
    }
    usage = {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "local_estimated_input": exe.get("local_input_estimate")
        or dry.get("local_input_estimate_tokens"),
        "actual_provider_input": exe.get("provider_input") or exe.get("input_tokens"),
        "ratio": exe.get("input_ratio"),
        "output": exe.get("output_tokens"),
        "thinking": exe.get("thinking_tokens"),
        "max_output": exe.get("max_output_canary") or dry.get("max_output_tokens"),
        "provider_elapsed_ms": exe.get("provider_elapsed_ms"),
        "cost": exe.get("cost"),
        "http_status": exe.get("http_status"),
        "request_id": exe.get("request_id"),
        "finish_reason": exe.get("finish_reason"),
    }
    readiness = {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "READY_FOR_REAL_GLOBAL_CONSOLIDATION_CANARY": exe.get(
            "ready_for_real_global_consolidation_canary"
        )
        or "NO",
        "next_call_name": "REAL GLOBAL CONSOLIDATION CANARY",
        "real_consolidation_executed": False,
        "real_pastoral_data_sent": False,
        "source_map": "NOT PUBLISHED",
        "phase_3b": "INCOMPLETE",
        "local_extraction_functionally_frozen": "YES",
        "relation_quality_technical_debt": "YES",
        "do_not_execute_automatically": True,
        "next_action": "HUMAN REVIEW",
    }
    header = {
        "result": exe.get("result") or ("BLOCKED_PRECALL" if result.blocked_precall else result.mode),
        "error": result.error,
        "engine_generate_attempts": result.engine_generate_attempts,
        "anthropic_post_attempts": result.anthropic_post_attempts,
        "tests": tests,
        **dict(extra_header or {}),
    }
    written = {
        "fixture": write_bytes_atomic(
            canary_artifact_path(project_name, FIXTURE_ARTIFACT, sortie_dir=sortie_dir),
            fixture_payload(),
        ),
        "request": write_bytes_atomic(
            canary_artifact_path(project_name, REQUEST_ARTIFACT, sortie_dir=sortie_dir),
            request_meta,
        ),
        "contract": write_bytes_atomic(
            canary_artifact_path(project_name, CONTRACT_ARTIFACT, sortie_dir=sortie_dir),
            contract,
        ),
        "dispositions": write_bytes_atomic(
            canary_artifact_path(project_name, DISPOSITION_ARTIFACT, sortie_dir=sortie_dir),
            exe.get("dispositions") or {},
        ),
        "canonical": write_bytes_atomic(
            canary_artifact_path(project_name, CANONICAL_ARTIFACT, sortie_dir=sortie_dir),
            exe.get("reconstruction") or {},
        ),
        "usage": write_bytes_atomic(
            canary_artifact_path(project_name, USAGE_ARTIFACT, sortie_dir=sortie_dir),
            usage,
        ),
        "readiness": write_bytes_atomic(
            canary_artifact_path(project_name, READINESS_ARTIFACT, sortie_dir=sortie_dir),
            readiness,
        ),
        "execution": write_bytes_atomic(
            canary_artifact_path(project_name, EXECUTION_ARTIFACT, sortie_dir=sortie_dir),
            result.to_dict(),
        ),
        "report": write_bytes_atomic(
            audit_dir(project_name, sortie_dir=sortie_dir) / REPORT_NAME,
            render_report(result, tests=tests, extra_header=header),
        ),
    }
    return written


__all__ = ["write_canary_artifacts"]
