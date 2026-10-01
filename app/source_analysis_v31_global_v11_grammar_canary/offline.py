"""Replay OFFLINE de la réponse A.37 persistée. 0 provider. 0 retry."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.source_analysis_v31_global_grammar_canary.costing import actual_cost
from app.source_analysis_v31_global_grammar_canary.fixture import build_synthetic_fixture
from app.source_analysis_v31_global_v11_grammar_canary.constants import (
    AUTHORIZATION_SCOPE,
    CANARY_MAX_OUTPUT_TOKENS,
    CANARY_WINDOW_ID,
    PROJECT_NAME,
    PROMPT_VERSION,
    PROVIDER,
    TRANSPORT_VERSION,
)
from app.source_analysis_v31_global_v11_grammar_canary.paths import canary_root
from app.source_analysis_v31_global_v11_grammar_canary.runner import (
    CanaryRunResult,
    _classify,
    dry_run_canary,
)
from app.source_analysis_v31_global_v11_grammar_canary.validate import (
    interpret_canary_response_v11,
)
from app.source_analysis_v31_global_v11_grammar_canary.writer import write_canary_artifacts


def saved_forensic_dir(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
    request_identity: str | None = None,
) -> Path:
    root = canary_root(project_name, sortie_dir=sortie_dir) / "provider_forensics" / CANARY_WINDOW_ID
    if request_identity:
        return root / request_identity
    candidates = sorted(path for path in root.iterdir() if path.is_dir()) if root.is_dir() else []
    if not candidates:
        raise FileNotFoundError(f"No saved A.37 forensics under {root}")
    return candidates[0]


def replay_saved_response(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
    tests: str = "offline replay A.37",
    write: bool = True,
) -> CanaryRunResult:
    dry = dry_run_canary(
        project_name,
        authorization_scope=AUTHORIZATION_SCOPE,
        sortie_dir=sortie_dir,
    )
    identity = str(dry.get("request_identity") or "")
    forensic = saved_forensic_dir(
        project_name, sortie_dir=sortie_dir, request_identity=identity
    )
    raw_path = forensic / "provider_raw_response.bin"
    envelope_path = forensic / "provider_http_envelope.json"
    raw = json.loads(raw_path.read_bytes())
    envelope = json.loads(envelope_path.read_text(encoding="utf-8"))
    text = "".join(
        str(block.get("text") or "")
        for block in (raw.get("content") or [])
        if isinstance(block, dict) and block.get("type") == "text"
    )
    parsed = json.loads(text)
    fixture = build_synthetic_fixture()
    validation = interpret_canary_response_v11(
        parsed, fixture=fixture, raw_text=text, signature=identity
    )
    input_tokens = int(envelope.get("input_tokens") or 0)
    output_tokens = int(envelope.get("output_tokens") or 0)
    thinking_tokens = 0
    usage = envelope.get("usage") or {}
    details = usage.get("output_tokens_details") if isinstance(usage, dict) else None
    if isinstance(details, dict) and details.get("thinking_tokens") is not None:
        thinking_tokens = int(details.get("thinking_tokens") or 0)
    cost = actual_cost(input_tokens=input_tokens, output_tokens=output_tokens)
    local_est = dry.get("local_input_estimate_tokens")
    ratio = (
        input_tokens / local_est
        if isinstance(local_est, int) and local_est
        else None
    )
    http_success = bool(envelope.get("http_success"))
    finish_reason = envelope.get("finish_reason")
    enum_audit = validation.get("enum_audit") or {}
    verdict = _classify(
        generate_attempts=1,
        post_attempts=1,
        http_success=http_success,
        finish_reason=finish_reason,
        thinking_tokens=thinking_tokens,
        structured=validation.get("structured_parse", "FAIL"),
        decoder=validation.get("decoder", "FAIL"),
        handles=validation.get("handle_validation", "FAIL"),
        coverage=float(validation.get("idea_disposition_coverage") or 0),
        silent_drops=int(validation.get("silent_drops") or 0),
        traceability=validation.get("traceability", "FAIL"),
        global_validator=validation.get("global_validator", "FAIL"),
        no_drop=validation.get("no_drop_validator", "FAIL"),
        reconstruction=validation.get("canonical_reconstruction", "FAIL"),
        canonical=validation.get("canonical_validation", "FAIL"),
        replay=validation.get("deterministic_replay", "FAIL"),
        semantic=(validation.get("semantic_review") or {}).get("status", "FAIL"),
        enum_status=enum_audit.get("status", "FAIL"),
        matrix=validation.get("operation_reason_matrix", "FAIL"),
        free_text_dw=int(validation.get("free_text_drop_reason") or 0),
        link_related=int(validation.get("link_related_count") or 0),
        merge_union=str(validation.get("merge_source_union") or "FAIL"),
        pastoral=False,
        source_map_published=bool(dry.get("source_map_present")),
        error=None,
    )
    a35_defect = (
        "ELIMINATED_BY_SCHEMA_AND_PROMPT_CONTRACT"
        if int(validation.get("free_text_drop_reason") or 0) == 0
        and validation.get("drop_token_ok")
        else "PERSISTS"
    )
    result = CanaryRunResult(
        mode="OFFLINE_REPLAY",
        project_name=project_name,
        authorization_scope=AUTHORIZATION_SCOPE,
        accepted=True,
        blocked_precall=False,
        engine_generate_attempts=1,
        anthropic_post_attempts=1,
        dry_run=dry,
        payload_audit=dry.get("payload_audit") or {},
        schema_metrics=dry.get("schema_metrics") or {},
    )
    result.execution = {
        "result": verdict,
        "authorization_scope": AUTHORIZATION_SCOPE,
        "provider": PROVIDER,
        "model": dry.get("model"),
        "thinking_mode": dry.get("thinking_mode"),
        "engine_generate_attempts": 1,
        "anthropic_post_attempts": 1,
        "authorized_calls": 1,
        "actual_calls": 1,
        "successful_calls": 1 if http_success else 0,
        "failed_calls": 0 if http_success else 1,
        "retry_calls": 0,
        "http": envelope,
        "http_status": envelope.get("http_status"),
        "request_id": envelope.get("request_id"),
        "http_success": http_success,
        "provider_elapsed_ms": envelope.get("elapsed_ms"),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "thinking_tokens": thinking_tokens,
        "finish_reason": finish_reason,
        "schema_identity": dry.get("schema_identity"),
        "schema_hash": dry.get("schema_hash"),
        "schema_raw_bytes": dry.get("schema_raw_bytes"),
        "schema_adapted_bytes": dry.get("schema_adapted_bytes"),
        "prompt_version": PROMPT_VERSION,
        "transport_version": TRANSPORT_VERSION,
        "max_output_canary": CANARY_MAX_OUTPUT_TOKENS,
        "local_input_estimate": local_est,
        "provider_input": input_tokens,
        "input_ratio": ratio,
        "structured_parse": validation.get("structured_parse"),
        "transport_decoder": validation.get("decoder"),
        "handle_validation": validation.get("handle_validation"),
        "inventory": validation.get("inventory"),
        "idea_disposition_coverage": validation.get("idea_disposition_coverage"),
        "silent_drops": validation.get("silent_drops"),
        "traceability": validation.get("traceability"),
        "global_validator": validation.get("global_validator"),
        "canonical_reconstruction": validation.get("canonical_reconstruction"),
        "canonical_validation": validation.get("canonical_validation"),
        "deterministic_replay": validation.get("deterministic_replay"),
        "semantic_fixture_review": (validation.get("semantic_review") or {}).get("status"),
        "d_o_enum": validation.get("d_o_enum"),
        "d_w_enum": validation.get("d_w_enum"),
        "free_text_drop_reason": validation.get("free_text_drop_reason"),
        "link_related": validation.get("link_related_count"),
        "operation_reason_matrix": validation.get("operation_reason_matrix"),
        "merge_source_union": validation.get("merge_source_union"),
        "keep_plus_independent_relation": validation.get("keep_plus_independent_relation"),
        "drop_token_ok": validation.get("drop_token_ok"),
        "merge_ok": validation.get("merge_ok"),
        "keep_ok": validation.get("keep_ok"),
        "keep_count": validation.get("keep_count"),
        "merge_equivalent_count": validation.get("merge_equivalent_count"),
        "drop_count": validation.get("drop_count"),
        "other_count": validation.get("other_count"),
        "observed_dw_tokens": validation.get("observed_dw_tokens"),
        "a35_root_defect": a35_defect,
        "global_transport_1_1_grammar_proof": "PASS" if http_success else "FAIL",
        "validation_errors": validation.get("errors") or [],
        "handles": validation.get("handles"),
        "dispositions": validation.get("validator"),
        "enum_audit": enum_audit,
        "reconstruction": validation.get("reconstruction"),
        "replay": validation.get("replay"),
        "semantic_review": validation.get("semantic_review"),
        "cost": cost,
        "forensic_path": str(forensic),
        "pastoral_content_sent": False,
        "real_consolidation_executed": False,
        "source_map": "NOT PUBLISHED",
        "ready_for_real_global_consolidation_canary": "YES" if verdict == "PASS" else "NO",
        "offline_replay": True,
        "second_provider_call": False,
        "classifications": {
            "GRAMMAR_ACCEPTED": http_success,
            "TRANSPORT_VALID": validation.get("decoder") == "PASS",
            "VALIDATOR_VALID": validation.get("global_validator") == "PASS",
            "CANONICAL_RECONSTRUCTION_VALID": validation.get("canonical_reconstruction")
            == "PASS",
            "SEMANTIC_FIXTURE_REASONABLE": (validation.get("semantic_review") or {}).get(
                "status"
            )
            == "PASS",
        },
    }
    if write:
        write_canary_artifacts(project_name, result, sortie_dir=sortie_dir, tests=tests)
    return result


__all__ = ["replay_saved_response", "saved_forensic_dir"]
