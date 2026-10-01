"""Écriture atomique des artefacts A.44 — canary isolé, jamais production."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from app.language_cleanup.transcript_source import audit_dir
from app.source_analysis_v2_grammar_canary.writer import write_bytes_atomic
from app.source_analysis_v31_global_v30_grammar_canary.constants import (
    CANONICAL_ARTIFACT,
    DERIVED_SRC_ARTIFACT,
    ESTIMATOR_ARTIFACT,
    EXECUTION_ARTIFACT,
    FIXTURE_ARTIFACT,
    MEMBERSHIP_ARTIFACT,
    PHASE,
    PRODUCTION_ABSOLUTE_HEADROOM,
    PRODUCTION_CONSERVATIVE_OUTPUT_TOKENS,
    PRODUCTION_EXPECTED_OUTPUT_TOKENS,
    PRODUCTION_HARD_PLANNING_TOKENS,
    PRODUCTION_HARD_UTILIZATION,
    PRODUCTION_MAX_OUTPUT_TOKENS,
    PRODUCTION_OUTPUT_RISK,
    READINESS_ARTIFACT,
    REPORT_NAME,
    REQUEST_ARTIFACT,
    REUSE_SYNTHESIS_ARTIFACT,
    SCHEMA_VERSION,
    USAGE_ARTIFACT,
    VALIDATOR_ARTIFACT,
)
from app.source_analysis_v31_global_v30_grammar_canary.fixture import fixture_payload
from app.source_analysis_v31_global_v30_grammar_canary.paths import canary_artifact_path
from app.source_analysis_v31_global_v30_grammar_canary.report import render_report
from app.source_analysis_v31_global_v30_grammar_canary.runner import CanaryRunResult


def write_canary_artifacts(
    project_name: str,
    result: CanaryRunResult,
    *,
    sortie_dir: Path | None = None,
    tests: str = "offline A.44",
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
        "output_estimate": dry.get("output_estimate") or exe.get("output_estimate"),
        "predicted_output": (
            (dry.get("output_estimate") or {}).get("expected_provider_tokens")
            or exe.get("predicted_canary_output")
        ),
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
        "raw_text_chars": exe.get("raw_text_chars"),
        "raw_text_bytes": exe.get("raw_text_bytes"),
        "predicted_canary_output": exe.get("predicted_canary_output"),
        "actual_canary_output": exe.get("actual_canary_output"),
        "estimator_error": exe.get("estimator_error"),
        "actual_chars_per_token": exe.get("actual_chars_per_token"),
        "production_max_output": PRODUCTION_MAX_OUTPUT_TOKENS,
        "production_expected": PRODUCTION_EXPECTED_OUTPUT_TOKENS,
        "production_conservative": PRODUCTION_CONSERVATIVE_OUTPUT_TOKENS,
        "production_hard": PRODUCTION_HARD_PLANNING_TOKENS,
        "production_output_risk": PRODUCTION_OUTPUT_RISK,
        "production_hard_utilization": PRODUCTION_HARD_UTILIZATION,
        "production_absolute_headroom": PRODUCTION_ABSOLUTE_HEADROOM,
    }
    readiness = {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "READY_FOR_REAL_GLOBAL_CONSOLIDATION_PREFLIGHT": exe.get(
            "ready_for_real_global_consolidation_preflight"
        )
        or "NO",
        "READY_FOR_REAL_GLOBAL_CONSOLIDATION_CANARY": "NO",
        "real_consolidation_executed": False,
        "real_pastoral_data_sent": False,
        "source_map": "NOT PUBLISHED",
        "phase_3b": "INCOMPLETE",
        "local_extraction_functionally_frozen": "YES",
        "relation_quality_technical_debt": "YES",
        "do_not_execute_automatically": True,
        "a44_does_not_authorize_real_consolidation": True,
        "production_output_risk": PRODUCTION_OUTPUT_RISK,
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
            fixture_payload(),
        ),
        "request": write_bytes_atomic(
            canary_artifact_path(project_name, REQUEST_ARTIFACT, sortie_dir=sortie_dir),
            request_meta,
        ),
        "reuse_synthesis": write_bytes_atomic(
            canary_artifact_path(
                project_name, REUSE_SYNTHESIS_ARTIFACT, sortie_dir=sortie_dir
            ),
            exe.get("reuse_synthesis") or {},
        ),
        "membership": write_bytes_atomic(
            canary_artifact_path(project_name, MEMBERSHIP_ARTIFACT, sortie_dir=sortie_dir),
            exe.get("membership") or {},
        ),
        "derived_src": write_bytes_atomic(
            canary_artifact_path(project_name, DERIVED_SRC_ARTIFACT, sortie_dir=sortie_dir),
            exe.get("derived_src") or {},
        ),
        "validator": write_bytes_atomic(
            canary_artifact_path(project_name, VALIDATOR_ARTIFACT, sortie_dir=sortie_dir),
            {
                "global_validator": exe.get("global_validator"),
                "structured_parse": exe.get("structured_parse"),
                "transport_decoder": exe.get("transport_decoder"),
                "handle_validation": exe.get("handle_validation"),
                "drop_enum": exe.get("drop_enum"),
                "errors": exe.get("validation_errors"),
                "classifications": exe.get("classifications"),
                "invalid_transport_publication_gate": exe.get(
                    "invalid_transport_publication_gate"
                ),
                "publication": exe.get("publication"),
            },
        ),
        "canonical": write_bytes_atomic(
            canary_artifact_path(project_name, CANONICAL_ARTIFACT, sortie_dir=sortie_dir),
            exe.get("reconstruction") or {},
        ),
        "estimator": write_bytes_atomic(
            canary_artifact_path(project_name, ESTIMATOR_ARTIFACT, sortie_dir=sortie_dir),
            {
                "predicted": exe.get("predicted_canary_output")
                or ((dry.get("output_estimate") or {}).get("expected_provider_tokens")),
                "actual": exe.get("actual_canary_output") or exe.get("output_tokens"),
                "error": exe.get("estimator_error"),
                "actual_chars_per_token": exe.get("actual_chars_per_token"),
                "preflight": dry.get("output_estimate") or exe.get("output_estimate"),
                "production_expected": PRODUCTION_EXPECTED_OUTPUT_TOKENS,
                "production_conservative": PRODUCTION_CONSERVATIVE_OUTPUT_TOKENS,
                "production_hard": PRODUCTION_HARD_PLANNING_TOKENS,
                "production_max_output": PRODUCTION_MAX_OUTPUT_TOKENS,
                "production_output_risk": PRODUCTION_OUTPUT_RISK,
                "limitation": (
                    "Tiny-canary estimator accuracy does not prove production "
                    "estimator accuracy. A.44 cannot automatically promote "
                    "real-call readiness."
                ),
            },
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
