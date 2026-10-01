"""Assemble le dossier A.43. 0 provider. 0 consolidation. 0 canary."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.source_analysis.writer import source_map_path
from app.source_analysis_v31_global_drop_domain.prompt_v201 import prompt_v201_bundle
from app.source_analysis_v31_global_output_architecture.transport_v20 import (
    measure_global_schema_v20,
)
from app.source_analysis_v31_global_reuse_output.breakdown import v20_hard_component_breakdown
from app.source_analysis_v31_global_reuse_output.constants import (
    A34_STATUS_PRESERVED,
    A35_STATUS_PRESERVED,
    A36_STATUS_PRESERVED,
    A37_STATUS_PRESERVED,
    A38_STATUS_PRESERVED,
    A39_STATUS_PRESERVED,
    A40_STATUS_PRESERVED,
    A41_STATUS_PRESERVED,
    A42_CONTRACT_PROOF,
    A42_REQUEST_ID,
    A42_STATUS_PRESERVED,
    CURRENT_PROMPT,
    CURRENT_TRANSPORT,
    LOCAL_EXTRACTION_FUNCTIONALLY_FROZEN,
    MODE,
    MODEL,
    MULTI_MEMBER_POLICY,
    NEW_GRAMMAR_CANARY_REQUIRED,
    NEXT_PROMPT_VERSION,
    NEXT_SCHEMA_ADAPTED_BYTES,
    NEXT_SCHEMA_HASH,
    NEXT_SCHEMA_RAW_BYTES,
    NEXT_TRANSPORT_VERSION,
    PHASE,
    PHASE_3B_STATUS,
    PRODUCTION_MAX_OUTPUT_TOKENS,
    PROJECT_NAME,
    PROVIDER_IDEA_TEXT_REQUIRED_FOR,
    READY_FOR_REAL_GLOBAL_CONSOLIDATION_CANARY,
    READY_FOR_REUSE_ARCHITECTURE_GRAMMAR_CANARY,
    REAL_ANTHROPIC_CALLS,
    REAL_CONSOLIDATION_CALLS,
    REAL_OPENAI_CALLS,
    REAL_PROVIDER_CALLS_THIS_PHASE,
    RELATION_QUALITY_TECHNICAL_DEBT,
    REWRITE_EXCEPTION_POLICY,
    SAFETY_70,
    SAFETY_75,
    SAFETY_80,
    SCHEMA_CHANGED,
    SCHEMA_VERSION,
    SELECTED_ARCHITECTURE,
    SELECTED_OPTION,
    SINGLE_MEMBER_POLICY,
    SOURCE_MAP_STATUS,
    THINKING_MODE,
    V20_CONSERVATIVE_OUTPUT,
    V20_EXPECTED_OUTPUT,
    V20_HARD_OUTPUT,
    V20_OUTPUT_RISK,
    V20_SCHEMA_HASH,
)
from app.source_analysis_v31_global_reuse_output.costing import production_cost_estimate
from app.source_analysis_v31_global_reuse_output.estimator import (
    reuse_savings_vs_v20,
    revised_reuse_budget,
)
from app.source_analysis_v31_global_reuse_output.evidence import verify_a42_identity
from app.source_analysis_v31_global_reuse_output.fakeai import (
    catalog_fakeai_cases,
    full_scale_stress,
)
from app.source_analysis_v31_global_reuse_output.fixture import future_grammar_canary_fixture
from app.source_analysis_v31_global_reuse_output.forensics import reuse_by_reference_analysis
from app.source_analysis_v31_global_reuse_output.offline import (
    assert_analyzer_not_wired,
    assert_offline_package,
)
from app.source_analysis_v31_global_reuse_output.options import (
    architecture_options,
    selected_architecture,
)
from app.source_analysis_v31_global_reuse_output.paths import production_source_map_present
from app.source_analysis_v31_global_reuse_output.prompt_v30 import prompt_v30_bundle
from app.source_analysis_v31_global_reuse_output.quality import assess_local_idea_reuse_quality
from app.source_analysis_v31_global_reuse_output.transport_v30 import measure_global_schema_v30


def build_bundle(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
    tests: str = "offline A.43",
    test_delta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    assert_offline_package()
    assert_analyzer_not_wired()
    identity = verify_a42_identity(project_name, sortie_dir=sortie_dir)
    quality = assess_local_idea_reuse_quality(project_name)
    reuse = reuse_by_reference_analysis(project_name, sortie_dir=sortie_dir)
    breakdown = v20_hard_component_breakdown()
    budget = revised_reuse_budget()
    savings = reuse_savings_vs_v20()
    options = architecture_options(budget)
    selected = selected_architecture(quality, budget)
    fakeai = catalog_fakeai_cases()
    stress = full_scale_stress()
    schema = measure_global_schema_v30()
    schema_v20 = measure_global_schema_v20()
    prompt_old = prompt_v201_bundle()
    prompt_new = prompt_v30_bundle()
    cost = production_cost_estimate(budget)
    next_fixture = future_grammar_canary_fixture()
    source_map_present = production_source_map_present(
        project_name, sortie_dir=sortie_dir
    ) or source_map_path(project_name, sortie_dir=sortie_dir).is_file()
    schema_ok = (
        schema.get("raw_bytes") == NEXT_SCHEMA_RAW_BYTES
        and schema.get("adapted_bytes") == NEXT_SCHEMA_ADAPTED_BYTES
        and schema.get("hash") == NEXT_SCHEMA_HASH
        and not schema.get("unsupported_constructs")
        and schema.get("conditional_schema_used") is False
        and schema_v20.get("hash") == V20_SCHEMA_HASH
        and prompt_old.get("prompt_version") == CURRENT_PROMPT
        and prompt_new.get("prompt_version") == NEXT_PROMPT_VERSION
        and prompt_new.get("previous_prompt_mutated") is False
    )
    contract_ok = all(
        [
            identity.get("ok"),
            quality.get("high_reuse_quality"),
            quality.get("material_degradation_if_hard_reuse") is False,
            selected.get("needs_alternative_output_architecture") is False,
            fakeai.get("valid_passes"),
            fakeai.get("negatives_fail"),
            stress.get("ok"),
            schema_ok,
            REAL_PROVIDER_CALLS_THIS_PHASE == 0,
            not source_map_present,
            READY_FOR_REAL_GLOBAL_CONSOLIDATION_CANARY == "NO",
            int(budget.get("hard_planning") or 10**9) < V20_HARD_OUTPUT,
        ]
    )
    new_failures = int((test_delta or {}).get("new_failure_count") or 0)
    tests_failed = int((test_delta or {}).get("failed") or 0)
    if contract_ok and new_failures == 0 and tests_failed == 0:
        result = "PASS"
        readiness = "READY_FOR_REUSE_ARCHITECTURE_GRAMMAR_CANARY"
    elif contract_ok:
        result = "PARTIAL"
        readiness = "BLOCKED_BY_TEST_SUITE"
    elif selected.get("needs_alternative_output_architecture"):
        result = "FAIL"
        readiness = "NEEDS_ALTERNATIVE_OUTPUT_ARCHITECTURE"
    else:
        result = "FAIL"
        readiness = "BLOCKED"

    sample_counts = quality.get("sample_counts") or {}
    census = quality.get("census_counts") or {}
    a38 = (reuse.get("a38") or {})
    classes = a38.get("classes") or {}
    readiness_payload = {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "decision": readiness,
        "READY_FOR_REUSE_ARCHITECTURE_GRAMMAR_CANARY": (
            READY_FOR_REUSE_ARCHITECTURE_GRAMMAR_CANARY
            if readiness == "READY_FOR_REUSE_ARCHITECTURE_GRAMMAR_CANARY"
            else "NO"
        ),
        "READY_FOR_REAL_GLOBAL_CONSOLIDATION_CANARY": "NO",
        "NEEDS_ALTERNATIVE_OUTPUT_ARCHITECTURE": readiness
        == "NEEDS_ALTERNATIVE_OUTPUT_ARCHITECTURE",
        "new_grammar_canary_required": NEW_GRAMMAR_CANARY_REQUIRED,
        "schema_changed": SCHEMA_CHANGED,
        "do_not_execute_automatically": True,
        "do_not_call_provider": True,
        "next_action": "HUMAN REVIEW",
        "real_consolidation_executed": False,
        "source_map": SOURCE_MAP_STATUS,
        "phase_3b": PHASE_3B_STATUS,
    }
    header = {
        "result": result,
        "real_provider_calls": REAL_PROVIDER_CALLS_THIS_PHASE,
        "a42_status": f"{A42_STATUS_PRESERVED} unchanged",
        "a42_request": A42_REQUEST_ID,
        "a42_contract_proof": A42_CONTRACT_PROOF,
        "current_transport": CURRENT_TRANSPORT,
        "current_prompt": CURRENT_PROMPT,
        "current_expected_output": V20_EXPECTED_OUTPUT,
        "current_conservative_output": V20_CONSERVATIVE_OUTPUT,
        "current_hard_output": V20_HARD_OUTPUT,
        "current_output_risk": V20_OUTPUT_RISK,
        "local_idea_sample_size": quality.get("sample_size"),
        "ready_for_reuse": sample_counts.get("READY_FOR_REUSE", 0),
        "needs_normalization": sample_counts.get("NEEDS_NORMALIZATION", 0),
        "not_self_contained": sample_counts.get("NOT_SELF_CONTAINED", 0),
        "census_ready": census.get("READY_FOR_REUSE", 0),
        "census_needs_normalization": census.get("NEEDS_NORMALIZATION", 0),
        "a38_near_copy_evidence": classes,
        "selected_architecture": SELECTED_ARCHITECTURE,
        "selected_option": SELECTED_OPTION,
        "single_member_policy": SINGLE_MEMBER_POLICY,
        "multi_member_policy": MULTI_MEMBER_POLICY,
        "rewrite_exception_policy": REWRITE_EXCEPTION_POLICY,
        "provider_idea_text_required_for": PROVIDER_IDEA_TEXT_REQUIRED_FOR,
        "derived_src": "YES",
        "relations": "DEFERRED",
        "next_prompt": NEXT_PROMPT_VERSION,
        "next_transport": NEXT_TRANSPORT_VERSION,
        "next_schema_raw_adapted": f"{NEXT_SCHEMA_RAW_BYTES} / {NEXT_SCHEMA_ADAPTED_BYTES}",
        "next_schema_hash": NEXT_SCHEMA_HASH,
        "new_grammar_canary_required": "YES" if NEW_GRAMMAR_CANARY_REQUIRED else "NO",
        "expected_global_ideas": (reuse.get("a38") or {}).get("expected_production"),
        "revised_expected": budget.get("p50_expected"),
        "revised_conservative": budget.get("conservative"),
        "revised_hard": budget.get("hard_planning"),
        "max_output": PRODUCTION_MAX_OUTPUT_TOKENS,
        "limit_70": SAFETY_70,
        "limit_75": SAFETY_75,
        "limit_80": SAFETY_80,
        "hard_utilization": budget.get("utilization_hard"),
        "absolute_headroom": budget.get("absolute_headroom"),
        "output_risk": budget.get("output_risk"),
        "estimated_real_input": cost.get("estimated_real_input"),
        "estimated_real_output": cost.get("estimated_real_output_expected"),
        "estimated_real_cost": (cost.get("expected") or {}).get("display"),
        "all_distinct_286_reuse_stress": (stress.get("all_distinct_286_reuse") or {}).get(
            "status"
        ),
        "mixed_full_scale_stress": (stress.get("mixed_full_scale") or {}).get("status"),
        "canonical_reconstruction": (fakeai.get("valid_reuse_and_merge") or {}).get(
            "canonical_reconstruction"
        ),
        "canonical_validation": (fakeai.get("valid_reuse_and_merge") or {}).get(
            "canonical_validation"
        ),
        "idea_accountability": (fakeai.get("valid_reuse_and_merge") or {}).get(
            "idea_accountability"
        ),
        "tests": tests,
        "new_failures": (test_delta or {}).get("new_failure_count", "pending"),
        "readiness": readiness,
        "identity_ok": identity.get("ok"),
        "model": MODEL,
        "thinking": THINKING_MODE,
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
        },
    }
    return {
        "header": header,
        "reuse_analysis": reuse,
        "quality": quality,
        "breakdown": breakdown,
        "savings": savings,
        "options": options,
        "selected": selected,
        "budget": budget,
        "stress": stress,
        "schema": {
            "raw_bytes": schema.get("raw_bytes"),
            "adapted_bytes": schema.get("adapted_bytes"),
            "hash": schema.get("hash"),
            "unsupported_constructs": schema.get("unsupported_constructs"),
            "adapted_unsupported": schema.get("adapted_unsupported"),
            "conditional_schema_used": schema.get("conditional_schema_used"),
            "v20_hash_unchanged": schema_v20.get("hash") == V20_SCHEMA_HASH,
            "field_meanings": schema.get("field_meanings"),
            "schema": schema.get("schema"),
            "adapted_schema": schema.get("adapted_schema"),
        },
        "cost": cost,
        "fakeai": fakeai,
        "next_fixture": {
            key: value
            for key, value in next_fixture.items()
            if key not in {"inventory", "expected_valid_transport"}
        },
        "prompt": {
            "old_version": prompt_old.get("prompt_version"),
            "new_version": prompt_new.get("prompt_version"),
            "previous_mutated": prompt_new.get("previous_prompt_mutated"),
            "new_hash": prompt_new.get("combined_sha256"),
            "old_hash": prompt_old.get("combined_sha256"),
        },
        "readiness": readiness_payload,
        "test_delta": test_delta,
        "guards": {
            "real_provider_calls": REAL_PROVIDER_CALLS_THIS_PHASE,
            "real_anthropic_calls": REAL_ANTHROPIC_CALLS,
            "real_openai_calls": REAL_OPENAI_CALLS,
            "real_consolidation_calls": REAL_CONSOLIDATION_CALLS,
            "source_map_present": source_map_present,
            "local_extraction_functionally_frozen": LOCAL_EXTRACTION_FUNCTIONALLY_FROZEN,
            "relation_quality_technical_debt": RELATION_QUALITY_TECHNICAL_DEBT,
            "phase_3b": PHASE_3B_STATUS,
        },
        "contract_ok": contract_ok,
        "schema_ok": schema_ok,
    }


__all__ = ["build_bundle"]
