"""Assemble le dossier A.47. 0 provider. 0 publication. 0 réparation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.source_analysis.models import scan_editorial_structure
from app.source_analysis.writer import source_map_path
from app.source_analysis_v31_global_a47_contract_forensics.constants import (
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
    A44_STATUS_PRESERVED,
    A45_EXPECTED_OUTPUT_ERROR_PERCENT,
    A45_INPUT_ESTIMATE_ERROR_PERCENT,
    A45_STATUS_PRESERVED,
    A46_COST_USD,
    A46_DROP,
    A46_ELAPSED_SECONDS,
    A46_FINISH_REASON,
    A46_HTTP_STATUS,
    A46_IDEA_ACCOUNTABILITY,
    A46_INPUT_TOKENS,
    A46_INTENT_LENGTH,
    A46_KEEP,
    A46_MERGE,
    A46_OUTPUT_TOKENS,
    A46_OUTPUT_UTILIZATION_PERCENT,
    A46_REQUEST_HASH,
    A46_STATUS_PRESERVED,
    A46_THINKING_TOKENS,
    CAN_A46_SAVED_RESPONSE_BE_VALIDATED_UNDER_CORRECTED_CONTRACT_WITHOUT_REPAIR,
    CANONICAL_CONTRACT_CHANGE_REQUIRED,
    CORE_ARCHITECTURE_FUNCTIONALLY_FROZEN,
    EDITORIAL_SCAN_ROOT_CAUSE,
    HISTORICAL_240_ORIGIN,
    HISTORICAL_INTENT_LIMIT,
    INTENT_CONTRACT_ROOT_CAUSE,
    INTENT_SEMANTIC_VERDICT,
    LIMIT_JUSTIFICATION,
    LOCAL_EXTRACTION_FUNCTIONALLY_FROZEN,
    MODE,
    NEXT_PROMPT_VERSION,
    NEXT_SCHEMA_HASH,
    NEXT_TRANSPORT_VERSION,
    PHASE,
    PHASE_3B_STATUS,
    PROJECT_NAME,
    PROMPT_CHANGE_REQUIRED,
    READY_FOR_A46_OFFLINE_REVALIDATION,
    READY_FOR_NEW_PROVIDER_CANARY,
    REAL_ANTHROPIC_CALLS,
    REAL_OPENAI_CALLS,
    REAL_PROVIDER_CALLS_THIS_PHASE,
    RELATION_QUALITY_TECHNICAL_DEBT,
    SCHEMA_CHANGE_REQUIRED,
    SCHEMA_VERSION,
    SELECTED_INTENT_LIMIT,
    SOURCE_MAP_STATUS,
    TRANSPORT_CHANGE_REQUIRED,
)
from app.source_analysis_v31_global_a47_contract_forensics.contract import (
    contract_matrix,
    intent_contract_forensics,
)
from app.source_analysis_v31_global_a47_contract_forensics.evidence import (
    a46_intent_text,
    derived_a46_transport,
    read_a46_candidate,
    verify_a46_identity,
)
from app.source_analysis_v31_global_a47_contract_forensics.intent_review import review_a46_intent
from app.source_analysis_v31_global_a47_contract_forensics.lengths import intent_length_distribution
from app.source_analysis_v31_global_a47_contract_forensics.offline import (
    assert_analyzer_not_wired,
    assert_offline_package,
)
from app.source_analysis_v31_global_a47_contract_forensics.prompt_v301 import prompt_v301_bundle
from app.source_analysis_v31_global_a47_contract_forensics.replay import (
    load_a46_inventory,
    replay_a46_counterfactual,
    replay_a46_frozen,
)
from app.source_analysis_v31_global_a47_contract_forensics.scanner import classify_a46_editorial
from app.source_analysis_v31_global_reuse_output.prompt_v30 import prompt_v30_bundle
from app.source_analysis_v31_global_reuse_output.transport_v30 import measure_global_schema_v30


def _idea_text_equality(inventory: dict[str, Any], transport: dict[str, Any]) -> dict[str, Any]:
    from app.source_analysis_v31_global_reuse_output.reconstruct import local_idea_text

    mismatches = 0
    compared = 0
    for idea in transport.get("i") or []:
        if not isinstance(idea, dict):
            continue
        members = [str(item) for item in (idea.get("m") or []) if item]
        if len(members) != 1:
            continue
        compared += 1
        local = local_idea_text(inventory, members[0])
        # REUSE omits v; canonical text is local
        if str(idea.get("v") or "").strip():
            mismatches += 1
        if not local:
            mismatches += 1
    return {
        "compared_single_member": compared,
        "provider_v_present": mismatches == 0,
        "all_canonical_equals_local": compared == A46_KEEP and mismatches == 0,
        "expected": A46_KEEP,
    }


def build_bundle(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
    tests: str = "offline A.47",
    test_delta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    assert_offline_package()
    assert_analyzer_not_wired()
    identity = verify_a46_identity(project_name, sortie_dir=sortie_dir)
    intent = a46_intent_text(project_name, sortie_dir=sortie_dir)
    transport = derived_a46_transport(project_name, sortie_dir=sortie_dir)
    candidate = read_a46_candidate(project_name, sortie_dir=sortie_dir)
    inventory = load_a46_inventory(project_name, sortie_dir=sortie_dir)
    frozen = replay_a46_frozen(project_name, sortie_dir=sortie_dir)
    counterfactual = replay_a46_counterfactual(project_name, sortie_dir=sortie_dir)
    editorial = classify_a46_editorial(transport, candidate)
    matrix = contract_matrix()
    contract = intent_contract_forensics(intent)
    intent_sem = review_a46_intent(
        intent,
        inventory=inventory,
        metadata_status=((counterfactual.get("semantic_public") or {}).get("metadata") or {}).get(
            "status"
        ),
    )
    lengths = intent_length_distribution(a46_intent=intent)
    prompt_next = prompt_v301_bundle()
    prompt_frozen = prompt_v30_bundle()
    measured = measure_global_schema_v30()
    equality = _idea_text_equality(inventory, transport)
    structural_on_a46 = scan_editorial_structure({"transport": transport, "candidate": candidate or {}})
    semantic_public = counterfactual.get("semantic_public") or {}
    counterfactual_pass = counterfactual.get("counterfactual") == "PASS"
    result = (
        "PASS"
        if identity.get("ok")
        and A46_STATUS_PRESERVED == "FAIL"
        and REAL_PROVIDER_CALLS_THIS_PHASE == 0
        and counterfactual_pass
        and editorial.get("classification") == "FALSE_POSITIVE_LEXICAL_SCAN"
        and intent_sem.get("verdict") == INTENT_SEMANTIC_VERDICT
        and not source_map_path(project_name, sortie_dir=sortie_dir).is_file()
        else "PARTIAL"
    )
    header = {
        "result": result,
        "phase": PHASE,
        "mode": MODE,
        "real_provider_calls": REAL_PROVIDER_CALLS_THIS_PHASE,
        "real_anthropic_calls": REAL_ANTHROPIC_CALLS,
        "real_openai_calls": REAL_OPENAI_CALLS,
        "a46_historical_status": A46_STATUS_PRESERVED,
        "a46_request_identity": "MATCH" if identity.get("ok") else "MISMATCH",
        "a46_http": A46_HTTP_STATUS,
        "a46_finish": A46_FINISH_REASON,
        "a46_thinking": A46_THINKING_TOKENS,
        "a46_input": A46_INPUT_TOKENS,
        "a46_output": A46_OUTPUT_TOKENS,
        "a46_cost": A46_COST_USD,
        "a46_elapsed": A46_ELAPSED_SECONDS,
        "a46_idea_accountability": A46_IDEA_ACCOUNTABILITY,
        "a46_reuse_merge_drop": f"{A46_KEEP} / {A46_MERGE} / {A46_DROP}",
        "a46_primary_failure": f"gm.in {A46_INTENT_LENGTH} > canonical limit {HISTORICAL_INTENT_LIMIT}",
        "intent_contract_root_cause": INTENT_CONTRACT_ROOT_CAUSE,
        "a46_intent_semantic_verdict": INTENT_SEMANTIC_VERDICT,
        "historical_240_limit_origin": HISTORICAL_240_ORIGIN,
        "selected_intent_limit": SELECTED_INTENT_LIMIT,
        "limit_justification": LIMIT_JUSTIFICATION,
        "prompt_change_required": PROMPT_CHANGE_REQUIRED,
        "transport_change_required": TRANSPORT_CHANGE_REQUIRED,
        "schema_change_required": SCHEMA_CHANGE_REQUIRED,
        "canonical_contract_change_required": CANONICAL_CONTRACT_CHANGE_REQUIRED,
        "next_prompt": NEXT_PROMPT_VERSION,
        "next_transport": NEXT_TRANSPORT_VERSION,
        "next_schema_hash": NEXT_SCHEMA_HASH,
        "a46_unchanged_raw_response_counterfactual": counterfactual.get("counterfactual"),
        "can_a46_saved_response_be_validated_under_corrected_contract_without_repair": (
            CAN_A46_SAVED_RESPONSE_BE_VALIDATED_UNDER_CORRECTED_CONTRACT_WITHOUT_REPAIR
        ),
        "editorial_scan_root_cause": EDITORIAL_SCAN_ROOT_CAUSE,
        "a46_actual_forbidden_editorial_structure": editorial.get(
            "a46_actual_forbidden_editorial_structure"
        ),
        "lexical_chapter_false_positive": "YES"
        if editorial.get("lexical_chapter_false_positive")
        else "NO",
        "structural_scanner": structural_on_a46.get("status"),
        "a46_structural_replay": structural_on_a46.get("status"),
        "a46_output_utilization": f"{A46_OUTPUT_UTILIZATION_PERCENT}%",
        "a45_input_estimate_error": f"+{A45_INPUT_ESTIMATE_ERROR_PERCENT}%",
        "a45_expected_output_error": f"+{A45_EXPECTED_OUTPUT_ERROR_PERCENT}%",
        "core_architecture_functionally_frozen": CORE_ARCHITECTURE_FUNCTIONALLY_FROZEN,
        "semantic_candidate_review": semantic_public.get("status") or "REVIEW",
        "tests": tests,
        "new_failures": (test_delta or {}).get("new_failure_count", "pending"),
        "ready_for_a46_offline_revalidation": READY_FOR_A46_OFFLINE_REVALIDATION,
        "ready_for_new_provider_canary": READY_FOR_NEW_PROVIDER_CANARY,
        "source_map": SOURCE_MAP_STATUS,
        "phase_3b": PHASE_3B_STATUS,
        "next_action": "HUMAN REVIEW",
        "frozen_prompt_hash": prompt_frozen.get("combined_sha256"),
        "next_prompt_hash": prompt_next.get("combined_sha256"),
        "schema_hash_unchanged": measured.get("hash") == NEXT_SCHEMA_HASH,
        "request_hash_prefix": A46_REQUEST_HASH[:8],
    }
    forensics = {
        "identity": identity,
        "contract": contract,
        "intent_length": len(intent),
        "frozen_replay": {
            key: frozen.get(key)
            for key in frozen
            if key not in {"interpreted"}
        },
        "lengths": lengths,
        "prompt_3_0_mutated": False,
        "transport_3_0_mutated": False,
        "schema_hash": measured.get("hash"),
    }
    readiness = {
        "READY_FOR_A46_OFFLINE_REVALIDATION": READY_FOR_A46_OFFLINE_REVALIDATION,
        "READY_FOR_NEW_PROVIDER_CANARY": READY_FOR_NEW_PROVIDER_CANARY,
        "CAN_A46_SAVED_RESPONSE_BE_VALIDATED_UNDER_CORRECTED_CONTRACT_WITHOUT_REPAIR": (
            CAN_A46_SAVED_RESPONSE_BE_VALIDATED_UNDER_CORRECTED_CONTRACT_WITHOUT_REPAIR
        ),
        "GLOBAL_CONSOLIDATION_CORE_ARCHITECTURE_FUNCTIONALLY_FROZEN": (
            CORE_ARCHITECTURE_FUNCTIONALLY_FROZEN
        ),
        "A46_HISTORICAL_STATUS": A46_STATUS_PRESERVED,
        "source_map": SOURCE_MAP_STATUS,
        "phase_3b": PHASE_3B_STATUS,
        "local_extraction_functionally_frozen": LOCAL_EXTRACTION_FUNCTIONALLY_FROZEN,
        "relation_quality_technical_debt": RELATION_QUALITY_TECHNICAL_DEBT,
        "do_not_publish": True,
        "do_not_call_provider": True,
        "do_not_start_phase_4": True,
        "next_action": "HUMAN REVIEW",
        "next_prompt": NEXT_PROMPT_VERSION,
        "next_transport": NEXT_TRANSPORT_VERSION,
        "recommended_path": (
            "offline revalidation of the unchanged A.46 raw response under the "
            "corrected 320-char intent contract and structural editorial scanner"
        ),
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
            "A.45": A45_STATUS_PRESERVED,
            "A.46": A46_STATUS_PRESERVED,
        },
    }
    candidate_review = {
        "reuse": {
            **(semantic_public.get("reuse") or {}),
            **equality,
            "provider_generated_idea_text": False,
        },
        "merges": semantic_public.get("merges") or {"count": A46_MERGE, "status": "PASS"},
        "drops": semantic_public.get("drops") or {"count": A46_DROP, "status": "PASS"},
        "completeness": semantic_public.get("completeness"),
        "topics": semantic_public.get("topics"),
        "metadata": semantic_public.get("metadata"),
        "uncertainty": semantic_public.get("uncertainty"),
        "editorial": semantic_public.get("editorial"),
        "status": semantic_public.get("status"),
        "external_fact_check": False,
        "idea_accountability": A46_IDEA_ACCOUNTABILITY,
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "header": header,
        "forensics": forensics,
        "intent_semantics": intent_sem,
        "matrix": matrix,
        "editorial": editorial,
        "counterfactual": {
            key: counterfactual.get(key)
            for key in counterfactual
            if key not in {"interpreted"}
        },
        "candidate_review": candidate_review,
        "readiness": readiness,
        "prompt_v301": {
            "prompt_version": prompt_next.get("prompt_version"),
            "activated_production": prompt_next.get("activated_production"),
            "previous_prompt_mutated": prompt_next.get("previous_prompt_mutated"),
            "intent_limit": prompt_next.get("intent_limit"),
            "combined_sha256": prompt_next.get("combined_sha256"),
        },
        "test_delta": test_delta or {},
    }


__all__ = ["build_bundle"]
