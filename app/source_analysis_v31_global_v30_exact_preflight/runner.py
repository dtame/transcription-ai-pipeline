"""Assemble le dossier A.45. 0 provider. 0 consolidation. 0 generate."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.source_analysis.writer import source_map_path
from app.source_analysis_execution_strategy.windows import load_clean_transcript
from app.source_analysis_v31_global_v30_exact_preflight.audit import (
    audit_prompt_consistency,
    audit_request_redundancy,
)
from app.source_analysis_v31_global_v30_exact_preflight.consistency import (
    decoder_schema_consistency,
    publication_gate_plan,
    reconstructor_consistency,
    validator_consistency,
)
from app.source_analysis_v31_global_v30_exact_preflight.constants import (
    A34_STATUS_PRESERVED,
    A35_STATUS_PRESERVED,
    A36_STATUS_PRESERVED,
    A37_STATUS_PRESERVED,
    A38_STATUS_PRESERVED,
    A39_STATUS_PRESERVED,
    A40_STATUS_PRESERVED,
    A41_STATUS_PRESERVED,
    A42_STATUS_PRESERVED,
    A43_STATUS_PRESERVED,
    A44_REQUEST_ID,
    A44_STATUS_PRESERVED,
    AUTHORIZATION_SCOPE,
    CONNECT_TIMEOUT_SECONDS,
    FUTURE_AUTHORIZATION_SCOPE,
    GLOBAL_CONSOLIDATION_3_0_REUSE_CONTRACT_CANARY,
    GLOBAL_TRANSPORT_3_0_GRAMMAR_PROOF,
    GRAMMAR_CANARY_CALLS,
    LOCAL_EXTRACTION_FUNCTIONALLY_FROZEN,
    MAX_ANTHROPIC_POST,
    MAX_ATTEMPTS,
    MAX_ENGINE_GENERATE,
    MODE,
    MODEL,
    PHASE,
    PHASE_3B_STATUS,
    PRODUCTION_MAX_OUTPUT_TOKENS,
    PROJECT_NAME,
    PROMPT_VERSION,
    READ_TIMEOUT_SECONDS,
    READY_WINDOWS,
    REAL_ANTHROPIC_CALLS,
    REAL_CONSOLIDATION_CALLS,
    REAL_OPENAI_CALLS,
    REAL_PROVIDER_CALLS_THIS_PHASE,
    RELATION_QUALITY_TECHNICAL_DEBT,
    SAFETY_70,
    SAFETY_75,
    SAFETY_80,
    SCHEMA_ADAPTED_BYTES,
    SCHEMA_HASH,
    SCHEMA_RAW_BYTES,
    SCHEMA_VERSION,
    SOURCE_MAP_STATUS,
    THINKING_MODE,
    TRANSPORT_VERSION,
)
from app.source_analysis_v31_global_v30_exact_preflight.costing import (
    production_cost_estimate,
)
from app.source_analysis_v31_global_v30_exact_preflight.estimator import (
    calibrated_output_budget,
    classify_output_gate,
    input_budget,
)
from app.source_analysis_v31_global_v30_exact_preflight.evidence import verify_a44_identity
from app.source_analysis_v31_global_v30_exact_preflight.fakeai import (
    full_scale_production_stress,
    production_inventory,
    reconstruct_twice,
)
from app.source_analysis_v31_global_v30_exact_preflight.guard import future_call_guard_spec
from app.source_analysis_v31_global_v30_exact_preflight.inventory import (
    exact_inventory_payload,
    idea_handle_identity,
    load_exact_windows,
    verify_idea_source_refs,
    window_manifest,
)
from app.source_analysis_v31_global_v30_exact_preflight.offline import (
    GlobalExactPreflightError,
    assert_analyzer_not_wired,
    assert_offline_package,
)
from app.source_analysis_v31_global_v30_exact_preflight.payload import (
    build_audited_request,
    dry_run_identity_tuple,
)
from app.source_analysis_v31_global_v30_exact_preflight.paths import (
    production_source_map_present,
)
from app.source_analysis_v31_global_v30_exact_preflight.semantic import semantic_review_plan


def build_bundle(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
    tests: str = "offline A.45",
    test_delta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    assert_offline_package()
    assert_analyzer_not_wired()
    a44 = verify_a44_identity(project_name, sortie_dir=sortie_dir)
    windows = load_exact_windows(project_name, sortie_dir=sortie_dir)
    normalized = windows["normalized"]
    idea_identity = idea_handle_identity(normalized)
    src_audit = verify_idea_source_refs(normalized)
    window_rows = window_manifest(windows["loaded"], normalized)
    inventory_payload = exact_inventory_payload(
        inventory_check=windows["inventory_check"],
        idea_identity=idea_identity,
        src_audit=src_audit,
        window_rows=window_rows,
    )
    built_a = build_audited_request(
        normalized,
        window_set_sha256=str(window_rows["window_set_sha256"]),
        project_name=project_name,
        sortie_dir=sortie_dir,
    )
    built_b = build_audited_request(
        normalized,
        window_set_sha256=str(window_rows["window_set_sha256"]),
        project_name=project_name,
        sortie_dir=sortie_dir,
    )
    if dry_run_identity_tuple(built_a["audit"]) != dry_run_identity_tuple(built_b["audit"]):
        raise GlobalExactPreflightError(
            "BLOCKED: exact production request is not deterministic."
        )
    if built_a["audit"]["provider_visible_hash"] != built_b["audit"]["provider_visible_hash"]:
        raise GlobalExactPreflightError(
            "BLOCKED: provider-visible request bytes are not deterministic."
        )
    audit = built_a["audit"]
    output_budget = calibrated_output_budget()
    inputs = input_budget(
        local_prompt_tokens=int(audit.get("local_input_estimate_tokens") or 0),
        payload_tokens=int(audit.get("payload_local_estimate_tokens") or 0),
        request_chars=int(audit.get("provider_visible_chars") or 0),
        request_bytes=int(audit.get("provider_visible_bytes") or 0),
        compact_chars=int(audit.get("compact_chars") or 0),
    )
    cost = production_cost_estimate(
        input_tokens=int(inputs["primary_estimated_input"]),
        budget=output_budget,
    )
    redundancy = audit_request_redundancy(
        compact=normalized.get("compact") or {},
        user_text=built_a["request"].prompt,
        system_text=built_a["request"].system_prompt or "",
    )
    prompt_schema = audit_prompt_consistency()
    decoder = decoder_schema_consistency()
    validator = validator_consistency()
    reconstructor = reconstructor_consistency()
    publication = publication_gate_plan()
    transcript = load_clean_transcript(project_name, sortie_dir=sortie_dir)
    inventory = production_inventory(normalized, transcript)
    fakeai = full_scale_production_stress(inventory)
    replay = reconstruct_twice(inventory)
    semantic = semantic_review_plan()
    guard = future_call_guard_spec(
        normalized_input_hash=str(audit.get("normalized_input_hash") or ""),
        request_hash=str(audit.get("request_identity") or ""),
        provider_visible_hash=str(audit.get("provider_visible_hash") or ""),
        window_set_sha256=str(window_rows.get("window_set_sha256") or ""),
        prompt_hash=str(audit.get("prompt_hash") or ""),
        schema_hash=str(audit.get("schema_hash") or ""),
        hard_planning=int(output_budget.get("hard_planning") or 0),
        estimated_input=int(inputs.get("primary_estimated_input") or 0),
    )
    source_map_present = production_source_map_present(
        project_name, sortie_dir=sortie_dir
    ) or source_map_path(project_name, sortie_dir=sortie_dir).is_file()
    schema_ok = (
        audit.get("raw_bytes") == SCHEMA_RAW_BYTES
        and audit.get("adapted_bytes") == SCHEMA_ADAPTED_BYTES
        and audit.get("schema_hash") == SCHEMA_HASH
        and built_a["schema_metrics"].get("schema_identity") == "MATCH"
    )
    new_failures = int((test_delta or {}).get("new_failure_count") or 0)
    tests_failed = int((test_delta or {}).get("failed") or 0)
    output_gate = classify_output_gate(int(output_budget.get("hard_planning") or 10**9))
    fakeai_ok = bool(fakeai.get("ok")) and bool(replay.get("ok"))
    contract_ok = all(
        [
            a44.get("ok"),
            schema_ok,
            windows["determinism"].get("ok"),
            audit.get("secrets_included") is False,
            not audit.get("secret_hits"),
            inputs.get("inside_usable_budget"),
            output_budget.get("single_member_v_absent_in_all_scenarios"),
            prompt_schema.get("ok"),
            decoder.get("status") == "PASS",
            validator.get("status") == "PASS",
            reconstructor.get("status") == "PASS",
            publication.get("status") == "PASS",
            fakeai_ok,
            redundancy.get("readiness") == "CLEAN",
            REAL_PROVIDER_CALLS_THIS_PHASE == 0,
            not source_map_present,
            GLOBAL_TRANSPORT_3_0_GRAMMAR_PROOF == "PASS",
            GLOBAL_CONSOLIDATION_3_0_REUSE_CONTRACT_CANARY == "PASS",
        ]
    )
    if contract_ok and new_failures == 0 and tests_failed == 0:
        result = "PASS"
    elif contract_ok:
        result = "PARTIAL"
    else:
        result = "FAIL"
    ready_flag = "NO"
    if result == "PASS" and output_gate == "READY_FOR_ONE_REAL_GLOBAL_CONSOLIDATION_CANARY":
        ready_flag = "YES"
    elif result == "PASS" and output_gate == "SAFE_BUT_REVIEW_REQUIRED":
        ready_flag = "NO"
    observed = inventory_payload.get("observed") or {}
    scenarios = fakeai.get("scenarios") or {}
    header = {
        "result": result,
        "real_provider_calls": REAL_PROVIDER_CALLS_THIS_PHASE,
        "a44_status": f"{A44_STATUS_PRESERVED} unchanged",
        "a44_request": A44_REQUEST_ID,
        "ready_windows": window_rows.get("ready_count"),
        "local_records": observed.get("total_records"),
        "local_topics": observed.get("TOPIC"),
        "local_ideas": observed.get("IDEA"),
        "local_relations": observed.get("RELATION"),
        "local_examples": observed.get("EXAMPLE"),
        "local_references": observed.get("REFERENCE"),
        "local_uncertainties": observed.get("UNCERTAINTY"),
        "prompt": PROMPT_VERSION,
        "transport": TRANSPORT_VERSION,
        "schema_raw_adapted": f"{SCHEMA_RAW_BYTES} / {SCHEMA_ADAPTED_BYTES}",
        "schema_hash": SCHEMA_HASH,
        "schema_identity": built_a["schema_metrics"].get("schema_identity"),
        "model": MODEL,
        "thinking": THINKING_MODE,
        "max_output": PRODUCTION_MAX_OUTPUT_TOKENS,
        "normalized_input_hash": audit.get("normalized_input_hash"),
        "exact_request_hash": audit.get("request_identity"),
        "provider_visible_hash": audit.get("provider_visible_hash"),
        "request_determinism": "PASS",
        "request_chars": audit.get("provider_visible_chars"),
        "request_bytes": audit.get("provider_visible_bytes"),
        "estimated_input_tokens": inputs.get("primary_estimated_input"),
        "input_safety": inputs.get("input_safety"),
        "expected_output": output_budget.get("p50_expected"),
        "conservative_output": output_budget.get("conservative"),
        "hard_planning_output": output_budget.get("hard_planning"),
        "limit_70": SAFETY_70,
        "limit_75": SAFETY_75,
        "limit_80": SAFETY_80,
        "hard_utilization": output_budget.get("hard_utilization_percent"),
        "absolute_headroom": output_budget.get("absolute_headroom"),
        "output_safety": output_budget.get("output_safety"),
        "largest_output_component": output_budget.get("largest_output_component"),
        "all_distinct_286_reuse_stress": (scenarios.get("all_distinct_286_reuse") or {}).get(
            "status"
        ),
        "expected_mix_stress": (scenarios.get("expected_mix") or {}).get("status"),
        "merge_stress": (scenarios.get("merge_stress") or {}).get("status"),
        "drop_stress": (scenarios.get("drop_stress") or {}).get("status"),
        "fakeai_idea_accountability": fakeai.get("idea_accountability"),
        "fakeai_canonical_reconstruction": fakeai.get("canonical_reconstruction"),
        "fakeai_canonical_validation": fakeai.get("canonical_validation"),
        "prompt_schema_consistency": prompt_schema.get("status"),
        "decoder_consistency": decoder.get("status"),
        "validator_consistency": validator.get("status"),
        "reconstructor_consistency": reconstructor.get("status"),
        "publication_gate": publication.get("status"),
        "request_hash_lock": "PASS",
        "window_hash_lock": window_rows.get("window_set_sha256"),
        "future_call_count": 1,
        "future_retries": 0,
        "future_connect_timeout": CONNECT_TIMEOUT_SECONDS,
        "future_read_timeout": READ_TIMEOUT_SECONDS,
        "estimated_expected_cost": (cost.get("expected") or {}).get("display"),
        "estimated_conservative_cost": (cost.get("conservative") or {}).get("display"),
        "estimated_hard_cost": (cost.get("hard") or {}).get("display"),
        "local_extraction_functionally_frozen": LOCAL_EXTRACTION_FUNCTIONALLY_FROZEN,
        "relation_quality_technical_debt": RELATION_QUALITY_TECHNICAL_DEBT,
        "tests": tests,
        "new_failures": (test_delta or {}).get("new_failure_count", "pending"),
        "ready_for_one_real_global_consolidation_canary": ready_flag,
        "output_gate": output_gate,
        "source_map": SOURCE_MAP_STATUS,
        "phase_3b": PHASE_3B_STATUS,
        "next_action": "HUMAN REVIEW",
        "mode": MODE,
        "historical": {
            "A.34": A34_STATUS_PRESERVED,
            "A.35": A35_STATUS_PRESERVED,
            "A.36": A36_STATUS_PRESERVED,
            "A.37": A37_STATUS_PRESERVED,
            "A.38": A38_STATUS_PRESERVED,
            "A.39": A39_STATUS_PRESERVED,
            "A.40": A40_STATUS_PRESERVED,
            "A.41": A41_STATUS_PRESERVED,
            "A.42": A42_STATUS_PRESERVED,
            "A.43": A43_STATUS_PRESERVED,
            "A.44": A44_STATUS_PRESERVED,
        },
    }
    readiness = {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "decision": output_gate if result == "PASS" else "BLOCKED",
        "READY_FOR_ONE_REAL_GLOBAL_CONSOLIDATION_CANARY": ready_flag,
        "SAFE_BUT_REVIEW_REQUIRED": output_gate == "SAFE_BUT_REVIEW_REQUIRED",
        "NEEDS_MORE_OUTPUT_WORK": output_gate == "NEEDS_MORE_OUTPUT_WORK",
        "NEEDS_REQUEST_CLEANUP": redundancy.get("readiness") == "NEEDS_REQUEST_CLEANUP",
        "a45_recommendation_only": True,
        "a45_must_not_perform_real_call": True,
        "future_authorization_scope": FUTURE_AUTHORIZATION_SCOPE,
        "do_not_execute_automatically": True,
        "real_consolidation_executed": False,
        "source_map": SOURCE_MAP_STATUS,
        "phase_3b": PHASE_3B_STATUS,
        "next_action": "HUMAN REVIEW",
    }
    normalized_manifest = {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "contract": normalized.get("contract"),
        "compact_sha256": normalized.get("compact_sha256"),
        "compact_chars": normalized.get("compact_chars"),
        "compact_bytes": normalized.get("compact_bytes"),
        "idea_handle_set_sha256": idea_identity.get("handle_set_sha256"),
        "idea_count": idea_identity.get("count"),
        "window_set_sha256": window_rows.get("window_set_sha256"),
        "deterministic": windows["determinism"].get("ok"),
        "sampling": False,
        "truncation": False,
        "synthetic_substitution": False,
    }
    request_identity_payload = {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "normalized_input_hash": audit.get("normalized_input_hash"),
        "provider_visible_hash": audit.get("provider_visible_hash"),
        "request_identity": audit.get("request_identity"),
        "identity_fields": audit.get("identity_fields"),
        "determinism": "PASS",
        "constructed_twice": True,
        "byte_equivalent_provider_visible": True,
        "window_set_sha256": window_rows.get("window_set_sha256"),
        "future_authorization_scope": FUTURE_AUTHORIZATION_SCOPE,
        "preflight_scope": AUTHORIZATION_SCOPE,
    }
    exact_request = {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "secrets_included": False,
        "secret_hits": [],
        "provider_visible": built_a["payload"],
        "model": audit.get("model"),
        "thinking": audit.get("thinking"),
        "max_tokens": audit.get("max_tokens"),
        "prompt_version": PROMPT_VERSION,
        "transport_version": TRANSPORT_VERSION,
        "schema_hash": audit.get("schema_hash"),
        "normalized_input_hash": audit.get("normalized_input_hash"),
        "provider_visible_hash": audit.get("provider_visible_hash"),
        "request_identity": audit.get("request_identity"),
        "ready_windows": list(READY_WINDOWS),
        "connect_timeout_seconds": CONNECT_TIMEOUT_SECONDS,
        "read_timeout_seconds": READ_TIMEOUT_SECONDS,
        "max_engine_generate": MAX_ENGINE_GENERATE,
        "max_anthropic_post": MAX_ANTHROPIC_POST,
        "max_attempts": MAX_ATTEMPTS,
        "retries": 0,
        "note": (
            "Sanitized Anthropic JSON body from production build_payload(). "
            "Credential material and HTTP auth fields omitted."
        ),
    }
    return {
        "header": header,
        "inventory": inventory_payload,
        "window_manifest": window_rows,
        "normalized_input": normalized_manifest,
        "exact_request": exact_request,
        "request_identity": request_identity_payload,
        "input_budget": inputs,
        "output_budget": output_budget,
        "output_components": output_budget.get("breakdown"),
        "cost": cost,
        "contract": {
            "prompt_schema": prompt_schema,
            "decoder": decoder,
            "validator": validator,
            "reconstructor": reconstructor,
            "redundancy": redundancy,
            "a44": a44,
        },
        "publication": publication,
        "future_guard": guard,
        "fakeai": fakeai,
        "replay": replay,
        "semantic_review_plan": semantic,
        "readiness": readiness,
        "test_delta": test_delta,
        "payload_audit": {
            key: value
            for key, value in audit.items()
            if key not in {"identity_fields"}
        },
        "guards": {
            "real_provider_calls": REAL_PROVIDER_CALLS_THIS_PHASE,
            "real_anthropic_calls": REAL_ANTHROPIC_CALLS,
            "real_openai_calls": REAL_OPENAI_CALLS,
            "grammar_canary_calls": GRAMMAR_CANARY_CALLS,
            "real_consolidation_calls": REAL_CONSOLIDATION_CALLS,
            "source_map_present": source_map_present,
            "engine_generate": False,
        },
        "contract_ok": contract_ok,
        "schema_ok": schema_ok,
        "idea_handles": {
            "count": idea_identity.get("count"),
            "handle_set_sha256": idea_identity.get("handle_set_sha256"),
            "first": idea_identity.get("first"),
            "last": idea_identity.get("last"),
        },
    }


__all__ = ["build_bundle"]
