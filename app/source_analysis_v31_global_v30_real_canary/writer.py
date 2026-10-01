"""Écriture atomique des artefacts A.46 — isolés, jamais production source_map."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from app.language_cleanup.transcript_source import audit_dir
from app.source_analysis.writer import source_map_path
from app.source_analysis_v2_grammar_canary.writer import write_bytes_atomic
from app.source_analysis_v31_global_v30_real_canary.constants import (
    ACCOUNTABILITY_ARTIFACT,
    CANONICAL_VALIDATION_ARTIFACT,
    CANDIDATE_SOURCE_MAP_NAME,
    CONNECT_TIMEOUT_SECONDS,
    DROP_ARTIFACT,
    EXECUTION_ARTIFACT,
    HUMAN_AUTH_ARTIFACT,
    MERGE_ARTIFACT,
    METADATA_ARTIFACT,
    PHASE,
    PRECALL_ARTIFACT,
    PRODUCTION_MAX_OUTPUT_TOKENS,
    PUBLICATION_ARTIFACT,
    READINESS_ARTIFACT,
    READ_TIMEOUT_SECONDS,
    READY_FOR_ONE_REAL_GLOBAL_CONSOLIDATION_CANARY,
    REPORT_NAME,
    REUSE_ARTIFACT,
    SCHEMA_VERSION,
    TOPIC_ARTIFACT,
    TRANSPORT_ARTIFACT,
    USAGE_ARTIFACT,
)
from app.source_analysis_v31_global_v30_real_canary.guard import reject_publication_path
from app.source_analysis_v31_global_v30_real_canary.paths import (
    canary_artifact_path,
    candidate_source_map_path,
)
from app.source_analysis_v31_global_v30_real_canary.report import render_report
from app.source_analysis_v31_global_v30_real_canary.runner import CanaryRunResult


def write_precall_manifest(
    project_name: str,
    preflight: Mapping[str, Any],
    *,
    sortie_dir: Path | None = None,
) -> Path:
    payload = {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "timestamp_phase": PHASE,
        "authorization_scope": preflight.get("authorization_scope"),
        "human_authorization": preflight.get("human_authorization"),
        "window_identities": {
            "ready_windows": preflight.get("ready_windows"),
            "window_set_sha256": (preflight.get("windows") or {}).get("window_set_sha256"),
            "windows": (preflight.get("windows") or {}).get("windows"),
        },
        "inventory": preflight.get("inventory"),
        "normalized_input_hash": preflight.get("normalized_input_hash"),
        "request_hash": preflight.get("request_hash"),
        "schema_hash": (preflight.get("payload_audit") or {}).get("schema_hash"),
        "model": preflight.get("model"),
        "prompt": preflight.get("prompt_version"),
        "transport": preflight.get("transport_version"),
        "thinking": preflight.get("thinking_mode"),
        "max_output": preflight.get("max_output") or PRODUCTION_MAX_OUTPUT_TOKENS,
        "connect_timeout_seconds": CONNECT_TIMEOUT_SECONDS,
        "read_timeout_seconds": READ_TIMEOUT_SECONDS,
        "estimated_input": preflight.get("estimated_input"),
        "expected_output": preflight.get("expected_output"),
        "conservative_output": preflight.get("conservative_output"),
        "hard_output": preflight.get("hard_output"),
        "estimated_costs": preflight.get("cost"),
        "a45_ready": READY_FOR_ONE_REAL_GLOBAL_CONSOLIDATION_CANARY,
        "provider_called": False,
    }
    return write_bytes_atomic(
        canary_artifact_path(project_name, PRECALL_ARTIFACT, sortie_dir=sortie_dir),
        payload,
    )


def write_canary_artifacts(
    project_name: str,
    result: CanaryRunResult,
    *,
    sortie_dir: Path | None = None,
    tests: str = "offline A.46",
    extra_header: Mapping[str, Any] | None = None,
) -> dict[str, Path]:
    production = source_map_path(project_name, sortie_dir=sortie_dir)
    reject_publication_path(str(candidate_source_map_path(project_name, sortie_dir=sortie_dir)))
    assert not str(production).replace("\\", "/").endswith(
        str(candidate_source_map_path(project_name, sortie_dir=sortie_dir)).replace("\\", "/")
    )
    exe = result.execution or {}
    dry = result.dry_run or {}
    pre = result.preflight or {}
    semantic = result.semantic or {}
    validation = exe.get("validation") or {}
    if not pre and dry.get("preflight"):
        pre = dry["preflight"]
    write_precall_manifest(project_name, pre, sortie_dir=sortie_dir)
    human = {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "A45_READY_FOR_ONE_REAL_GLOBAL_CONSOLIDATION_CANARY": (
            READY_FOR_ONE_REAL_GLOBAL_CONSOLIDATION_CANARY
        ),
        "A46_EXECUTES_THAT_EXACT_APPROVED_REQUEST": True,
        "second_request_authorized": False,
        "do_not_generalize": True,
    }
    usage = {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "a45_estimated_input": exe.get("a45_estimated_input"),
        "actual_provider_input": exe.get("input_tokens"),
        "input_estimate_error": exe.get("input_estimate_error"),
        "a45_expected_output": exe.get("a45_expected_output"),
        "a45_conservative_output": exe.get("a45_conservative_output"),
        "a45_hard_output": exe.get("a45_hard_output"),
        "actual_output": exe.get("output_tokens"),
        "output_band": exe.get("output_band"),
        "output_utilization": exe.get("output_utilization"),
        "output_headroom": exe.get("output_headroom"),
        "actual_chars_per_token": exe.get("actual_chars_per_token"),
        "thinking": exe.get("thinking_tokens"),
        "elapsed_ms": exe.get("provider_elapsed_ms"),
        "elapsed_seconds": exe.get("elapsed_seconds"),
        "cost": exe.get("cost"),
        "actual_cost": exe.get("actual_cost"),
        "actual_cost_position": exe.get("actual_cost_position"),
        "http_status": exe.get("http_status"),
        "request_id": exe.get("request_id"),
        "finish_reason": exe.get("finish_reason"),
        "raw_text_chars": exe.get("raw_text_chars"),
        "raw_text_bytes": exe.get("raw_text_bytes"),
        "raw_response_hash": exe.get("raw_response_hash"),
    }
    transport = {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "structured_parse": exe.get("structured_parse"),
        "decoder": exe.get("transport_decoder"),
        "handle_validation": exe.get("handle_validation"),
        "global_validator": exe.get("global_validator"),
        "errors": (validation.get("errors") or []),
        "inventory": exe.get("inventory"),
        "repaired": False,
    }
    accountability = {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "idea_accountability": exe.get("idea_accountability"),
        "unknown_members": exe.get("unknown_members"),
        "duplicate_members": exe.get("duplicate_members"),
        "missing_members": exe.get("missing_members"),
        "member_drop_overlap": exe.get("member_drop_overlap"),
        "NON_IDEA_IN_MEMBERS": exe.get("NON_IDEA_IN_MEMBERS"),
        "NON_IDEA_IN_DROP": exe.get("NON_IDEA_IN_DROP"),
        "keep_count": exe.get("keep_count"),
        "merge_equivalent_count": exe.get("merge_equivalent_count"),
        "drop_count": exe.get("drop_count"),
        "membership": exe.get("membership"),
    }
    reuse = {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        **(semantic.get("reuse") or {}),
        "SINGLE_MEMBER_WITH_V": exe.get("SINGLE_MEMBER_WITH_V"),
        "reuse_text_exact_equality": (validation.get("reuse_text_exact_equality")),
    }
    canonical = {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "canonical_reconstruction": exe.get("canonical_reconstruction"),
        "canonical_validation": exe.get("canonical_validation"),
        "deterministic_replay": exe.get("deterministic_replay"),
        "empty_relations_valid": exe.get("empty_relations_valid"),
        "candidate_path": exe.get("candidate_source_map"),
        "candidate_name": CANDIDATE_SOURCE_MAP_NAME,
        "production_source_map": "NOT PUBLISHED",
        "errors": ((validation.get("reconstruction") or {}).get("errors") or []),
    }
    publication = {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "PUBLICATION_ELIGIBLE": exe.get("publication_eligible") or "NO",
        "provider_success": bool(exe.get("http_success")),
        "parse": exe.get("structured_parse"),
        "decoder": exe.get("transport_decoder"),
        "handles": exe.get("handle_validation"),
        "accountability": exe.get("idea_accountability"),
        "global_validator": exe.get("global_validator"),
        "canonical_reconstruction": exe.get("canonical_reconstruction"),
        "canonical_validation": exe.get("canonical_validation"),
        "merges_supported": (semantic.get("merges") or {}).get("all_supported"),
        "drops_supported": (semantic.get("drops") or {}).get("all_supported"),
        "topic_review": (semantic.get("topics") or {}).get("status"),
        "metadata_review": (semantic.get("metadata") or {}).get("status"),
        "uncertainty_preservation": (semantic.get("uncertainty") or {}).get("status"),
        "completeness": (semantic.get("completeness") or {}).get("status"),
        "semantic_review": semantic.get("status"),
        "source_map_published": False,
        "a46_must_not_publish": True,
    }
    readiness = {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "result": exe.get("result") or result.mode,
        "READY_FOR_SOURCE_MAP_PUBLICATION_REVIEW": exe.get(
            "ready_for_source_map_publication_review"
        )
        or "NO",
        "PUBLICATION_ELIGIBLE": exe.get("publication_eligible") or "NO",
        "source_map": "NOT PUBLISHED",
        "phase_3b": "INCOMPLETE",
        "local_extraction_functionally_frozen": "YES",
        "relation_quality_technical_debt": "YES",
        "do_not_publish_automatically": True,
        "do_not_start_phase_4": True,
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
        "human_auth": write_bytes_atomic(
            canary_artifact_path(project_name, HUMAN_AUTH_ARTIFACT, sortie_dir=sortie_dir),
            human,
        ),
        "transport": write_bytes_atomic(
            canary_artifact_path(project_name, TRANSPORT_ARTIFACT, sortie_dir=sortie_dir),
            transport,
        ),
        "accountability": write_bytes_atomic(
            canary_artifact_path(
                project_name, ACCOUNTABILITY_ARTIFACT, sortie_dir=sortie_dir
            ),
            accountability,
        ),
        "reuse": write_bytes_atomic(
            canary_artifact_path(project_name, REUSE_ARTIFACT, sortie_dir=sortie_dir),
            reuse,
        ),
        "merges": write_bytes_atomic(
            canary_artifact_path(project_name, MERGE_ARTIFACT, sortie_dir=sortie_dir),
            {"schema_version": SCHEMA_VERSION, "phase": PHASE, **(semantic.get("merges") or {})},
        ),
        "drops": write_bytes_atomic(
            canary_artifact_path(project_name, DROP_ARTIFACT, sortie_dir=sortie_dir),
            {"schema_version": SCHEMA_VERSION, "phase": PHASE, **(semantic.get("drops") or {})},
        ),
        "metadata": write_bytes_atomic(
            canary_artifact_path(project_name, METADATA_ARTIFACT, sortie_dir=sortie_dir),
            {
                "schema_version": SCHEMA_VERSION,
                "phase": PHASE,
                **(semantic.get("metadata") or {}),
            },
        ),
        "topics": write_bytes_atomic(
            canary_artifact_path(project_name, TOPIC_ARTIFACT, sortie_dir=sortie_dir),
            {"schema_version": SCHEMA_VERSION, "phase": PHASE, **(semantic.get("topics") or {})},
        ),
        "canonical": write_bytes_atomic(
            canary_artifact_path(
                project_name, CANONICAL_VALIDATION_ARTIFACT, sortie_dir=sortie_dir
            ),
            canonical,
        ),
        "usage": write_bytes_atomic(
            canary_artifact_path(project_name, USAGE_ARTIFACT, sortie_dir=sortie_dir),
            usage,
        ),
        "publication": write_bytes_atomic(
            canary_artifact_path(project_name, PUBLICATION_ARTIFACT, sortie_dir=sortie_dir),
            publication,
        ),
        "readiness": write_bytes_atomic(
            canary_artifact_path(project_name, READINESS_ARTIFACT, sortie_dir=sortie_dir),
            readiness,
        ),
        "execution": write_bytes_atomic(
            canary_artifact_path(project_name, EXECUTION_ARTIFACT, sortie_dir=sortie_dir),
            {
                "schema_version": SCHEMA_VERSION,
                "phase": PHASE,
                "dry_run": {
                    key: value
                    for key, value in dry.items()
                    if key not in {"payload_audit", "preflight"}
                },
                "execution": {
                    key: value
                    for key, value in exe.items()
                    if key not in {"validation"}
                },
                "header": header,
            },
        ),
        "report": write_bytes_atomic(
            audit_dir(project_name, sortie_dir=sortie_dir) / REPORT_NAME,
            render_report(result, tests=tests, extra_header=extra_header),
        ),
    }
    candidate = candidate_source_map_path(project_name, sortie_dir=sortie_dir)
    if candidate.is_file():
        written["candidate"] = candidate
    return written


__all__ = ["write_canary_artifacts", "write_precall_manifest"]
