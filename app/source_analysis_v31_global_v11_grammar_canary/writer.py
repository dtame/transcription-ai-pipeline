"""Écriture atomique des artefacts A.37 — canary isolé, jamais production."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from app.language_cleanup.transcript_source import audit_dir
from app.source_analysis_v2_grammar_canary.writer import write_bytes_atomic
from app.source_analysis_v31_global_canary_forensics.fixture import next_fixture_payload
from app.source_analysis_v31_global_v11_grammar_canary.constants import (
    CANONICAL_ARTIFACT,
    DISPOSITION_ARTIFACT,
    ENUM_ARTIFACT,
    EXECUTION_ARTIFACT,
    FIXTURE_ARTIFACT,
    PHASE,
    READINESS_ARTIFACT,
    REPORT_NAME,
    REQUEST_ARTIFACT,
    SCHEMA_VERSION,
    USAGE_ARTIFACT,
    VALIDATOR_ARTIFACT,
)
from app.source_analysis_v31_global_v11_grammar_canary.paths import canary_artifact_path
from app.source_analysis_v31_global_v11_grammar_canary.report import render_report
from app.source_analysis_v31_global_v11_grammar_canary.runner import CanaryRunResult


def write_canary_artifacts(
    project_name: str,
    result: CanaryRunResult,
    *,
    sortie_dir: Path | None = None,
    tests: str = "offline A.37",
    extra_header: Mapping[str, Any] | None = None,
) -> dict[str, Path]:
    exe = result.execution or {}
    dry = result.dry_run or {}
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
        "request_identity": dry.get("request_identity"),
        "dry_run_identity": dry.get("dry_run_identity"),
        "authorization_scope": result.authorization_scope,
        "pastoral_content": False,
        "fixture_hash": dry.get("synthetic_fixture_hash"),
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
        "production_provider_adjusted": dry.get("production_provider_adjusted"),
        "production_max_output": dry.get("production_max_output_tokens"),
        "production_worst_case_output": dry.get("production_worst_case_output"),
        "production_output_headroom": dry.get("production_output_headroom"),
        "production_output_headroom_percent": dry.get("production_output_headroom_percent"),
        "production_output_headroom_label": dry.get("production_output_headroom_label"),
        "estimated_real_consolidation_cost": dry.get("estimated_real_consolidation_cost"),
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
        "a37_does_not_authorize_real_consolidation": True,
        "next_action": "HUMAN REVIEW",
    }
    header = {
        "result": exe.get("result")
        or ("BLOCKED_PRECALL" if result.blocked_precall else result.mode),
        "error": result.error,
        "engine_generate_attempts": result.engine_generate_attempts,
        "anthropic_post_attempts": result.anthropic_post_attempts,
        "tests": tests,
        **dict(extra_header or {}),
    }
    written = {
        "fixture": write_bytes_atomic(
            canary_artifact_path(project_name, FIXTURE_ARTIFACT, sortie_dir=sortie_dir),
            next_fixture_payload(),
        ),
        "request": write_bytes_atomic(
            canary_artifact_path(project_name, REQUEST_ARTIFACT, sortie_dir=sortie_dir),
            request_meta,
        ),
        "enums": write_bytes_atomic(
            canary_artifact_path(project_name, ENUM_ARTIFACT, sortie_dir=sortie_dir),
            exe.get("enum_audit") or {},
        ),
        "dispositions": write_bytes_atomic(
            canary_artifact_path(project_name, DISPOSITION_ARTIFACT, sortie_dir=sortie_dir),
            {
                "validator": exe.get("dispositions") or {},
                "keep_count": exe.get("keep_count"),
                "merge_equivalent_count": exe.get("merge_equivalent_count"),
                "drop_count": exe.get("drop_count"),
                "other_count": exe.get("other_count"),
                "observed_dw_tokens": exe.get("observed_dw_tokens"),
                "drop_token_ok": exe.get("drop_token_ok"),
                "merge_ok": exe.get("merge_ok"),
                "keep_ok": exe.get("keep_ok"),
                "keep_plus_independent_relation": exe.get("keep_plus_independent_relation"),
                "merge_source_union": exe.get("merge_source_union"),
                "coverage": exe.get("idea_disposition_coverage"),
                "silent_drops": exe.get("silent_drops"),
            },
        ),
        "validator": write_bytes_atomic(
            canary_artifact_path(project_name, VALIDATOR_ARTIFACT, sortie_dir=sortie_dir),
            {
                "global_validator": exe.get("global_validator"),
                "structured_parse": exe.get("structured_parse"),
                "transport_decoder": exe.get("transport_decoder"),
                "handle_validation": exe.get("handle_validation"),
                "traceability": exe.get("traceability"),
                "operation_reason_matrix": exe.get("operation_reason_matrix"),
                "errors": exe.get("validation_errors"),
                "classifications": exe.get("classifications"),
            },
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
