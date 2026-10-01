"""Écriture atomique des artefacts A.38 — isolés, jamais production source_map."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from app.language_cleanup.transcript_source import audit_dir
from app.source_analysis.writer import source_map_path
from app.source_analysis_v2_grammar_canary.writer import write_bytes_atomic
from app.source_analysis_v31_global_real_consolidation.constants import (
    CANONICAL_ARTIFACT,
    COVERAGE_ARTIFACT,
    DISPOSITION_ARTIFACT,
    DROP_ARTIFACT,
    EXECUTION_ARTIFACT,
    MERGE_ARTIFACT,
    OTHER_ARTIFACT,
    PHASE,
    PREFLIGHT_ARTIFACT,
    RAW_INVENTORY_ARTIFACT,
    READINESS_ARTIFACT,
    RELATION_ARTIFACT,
    RELATION_QUALITY_TECHNICAL_DEBT,
    REPORT_NAME,
    REQUEST_ARTIFACT,
    SCHEMA_VERSION,
    SEMANTIC_ARTIFACT,
    USAGE_ARTIFACT,
)
from app.source_analysis_v31_global_real_consolidation.guard import reject_publication_path
from app.source_analysis_v31_global_real_consolidation.paths import (
    canary_artifact_path,
    candidate_source_map_path,
)
from app.source_analysis_v31_global_real_consolidation.report import render_report
from app.source_analysis_v31_global_real_consolidation.runner import ConsolidationRunResult


def write_consolidation_artifacts(
    project_name: str,
    result: ConsolidationRunResult,
    *,
    sortie_dir: Path | None = None,
    tests: str = "offline A.38",
    extra_header: Mapping[str, Any] | None = None,
) -> dict[str, Path]:
    production = source_map_path(project_name, sortie_dir=sortie_dir)
    exe = result.execution or {}
    dry = result.dry_run or {}
    pre = result.preflight or {}
    semantic = result.semantic or {}
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
        "max_output": dry.get("max_output_tokens") or exe.get("max_output"),
        "request_identity": dry.get("request_identity"),
        "input_hash": dry.get("input_hash"),
        "authorization_scope": result.authorization_scope,
        "raw_transcript": False,
        "ready_windows": dry.get("ready_windows"),
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
        "max_output": exe.get("max_output") or dry.get("max_output_tokens"),
        "output_headroom_tokens": exe.get("output_headroom_tokens"),
        "output_headroom_percent": exe.get("output_headroom_percent"),
        "provider_elapsed_ms": exe.get("provider_elapsed_ms"),
        "cost": exe.get("cost"),
        "http_status": exe.get("http_status"),
        "request_id": exe.get("request_id"),
        "finish_reason": exe.get("finish_reason"),
    }
    readiness = {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "result": exe.get("result") or result.mode,
        "real_consolidation_executed": bool(exe.get("real_consolidation_executed")),
        "source_map": "NOT PUBLISHED",
        "candidate_source_map": exe.get("candidate_source_map") or "NOT_CREATED",
        "phase_3b": "INCOMPLETE",
        "local_extraction_functionally_frozen": "YES",
        "relation_quality_technical_debt": RELATION_QUALITY_TECHNICAL_DEBT,
        "publication_authorized": False,
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
    preflight_safe = {
        key: value
        for key, value in pre.items()
        if key not in {"normalized", "loaded", "built"}
    }
    written = {
        "preflight": write_bytes_atomic(
            canary_artifact_path(project_name, PREFLIGHT_ARTIFACT, sortie_dir=sortie_dir),
            preflight_safe,
        ),
        "request": write_bytes_atomic(
            canary_artifact_path(project_name, REQUEST_ARTIFACT, sortie_dir=sortie_dir),
            request_meta,
        ),
        "raw_inventory": write_bytes_atomic(
            canary_artifact_path(project_name, RAW_INVENTORY_ARTIFACT, sortie_dir=sortie_dir),
            {
                "inventory": exe.get("inventory") or {},
                "global_topics": exe.get("global_topics"),
                "global_ideas": exe.get("global_ideas"),
                "global_relations": exe.get("global_relations"),
                "global_examples": exe.get("global_examples"),
                "global_references": exe.get("global_references"),
                "global_uncertainties": exe.get("global_uncertainties"),
                "global_repetitions": exe.get("global_repetitions"),
            },
        ),
        "dispositions": write_bytes_atomic(
            canary_artifact_path(project_name, DISPOSITION_ARTIFACT, sortie_dir=sortie_dir),
            {
                "validator": exe.get("dispositions") or {},
                "keep_count": exe.get("keep_count"),
                "merge_equivalent_count": exe.get("merge_equivalent_count"),
                "drop_count": exe.get("drop_count"),
                "other_count": exe.get("other_count"),
                "coverage": exe.get("idea_disposition_coverage"),
                "silent_drops": exe.get("silent_drops"),
                "enum_audit": exe.get("enum_audit") or {},
                "merge_source_union": exe.get("merge_source_union"),
            },
        ),
        "drops": write_bytes_atomic(
            canary_artifact_path(project_name, DROP_ARTIFACT, sortie_dir=sortie_dir),
            semantic.get("drops") or {},
        ),
        "others": write_bytes_atomic(
            canary_artifact_path(project_name, OTHER_ARTIFACT, sortie_dir=sortie_dir),
            semantic.get("others") or {},
        ),
        "merges": write_bytes_atomic(
            canary_artifact_path(project_name, MERGE_ARTIFACT, sortie_dir=sortie_dir),
            semantic.get("merges") or {},
        ),
        "relations": write_bytes_atomic(
            canary_artifact_path(project_name, RELATION_ARTIFACT, sortie_dir=sortie_dir),
            semantic.get("relations") or {},
        ),
        "semantic": write_bytes_atomic(
            canary_artifact_path(project_name, SEMANTIC_ARTIFACT, sortie_dir=sortie_dir),
            {
                "status": semantic.get("status"),
                "semantic_quality": semantic.get("semantic_quality"),
                "ideas": semantic.get("ideas") or {},
                "theme_fields": semantic.get("theme_fields") or {},
                "objects": semantic.get("objects") or {},
                "omissions": semantic.get("omissions") or {},
                "no_llm": True,
            },
        ),
        "coverage": write_bytes_atomic(
            canary_artifact_path(project_name, COVERAGE_ARTIFACT, sortie_dir=sortie_dir),
            {
                "window_coverage": semantic.get("window_coverage") or {},
                "src_coverage": semantic.get("src_coverage") or {},
                "cross_window": semantic.get("cross_window") or {},
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
    if exe.get("candidate_source_map") == "CREATED" and exe.get("reconstruction"):
        candidate = candidate_source_map_path(project_name, sortie_dir=sortie_dir)
        reject_publication_path(str(candidate))
        payload = dict(exe.get("reconstruction") or {})
        payload["source_map_published"] = False
        payload["candidate_only"] = True
        written["candidate"] = write_bytes_atomic(candidate, payload)
    if production.is_file():
        raise RuntimeError("A.38 writer must not create analysis/source_map.json.")
    return written


__all__ = ["write_consolidation_artifacts"]
