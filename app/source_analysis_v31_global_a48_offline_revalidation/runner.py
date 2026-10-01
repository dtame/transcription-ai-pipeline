"""Assemble le dossier A.48. 0 provider. 0 publication. 0 mutation A.46."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.file_utils import content_hash
from app.source_analysis.writer import source_map_path
from app.source_analysis_v31_global_a47_contract_forensics.contract import (
    contract_matrix,
    corrected_text_limits,
)
from app.source_analysis_v31_global_a47_contract_forensics.evidence import (
    protected_a47_historical_hashes,
)
from app.source_analysis_v31_global_a48_offline_revalidation.constants import (
    A34_STATUS_PRESERVED,
    A35_STATUS_PRESERVED,
    A36_STATUS_PRESERVED,
    A37_STATUS_PRESERVED,
    A38_STATUS_PRESERVED,
    A39_INTENT_COMPACTNESS_BOUND,
    A39_STATUS_PRESERVED,
    A40_STATUS_PRESERVED,
    A41_STATUS_PRESERVED,
    A42_STATUS_PRESERVED,
    A43_STATUS_PRESERVED,
    A44_STATUS_PRESERVED,
    A45_EXPECTED_OUTPUT_ERROR_PERCENT,
    A45_INPUT_ESTIMATE_ERROR_PERCENT,
    A45_NORMALIZED_INPUT_HASH,
    A45_REQUEST_HASH,
    A45_STATUS_PRESERVED,
    A46_COST_USD,
    A46_ELAPSED_SECONDS,
    A46_INPUT_TOKENS,
    A46_INTENT_LENGTH,
    A46_OUTPUT_TOKENS,
    A46_OUTPUT_UTILIZATION_PERCENT,
    A46_STATUS_PRESERVED,
    A47_STATUS_PRESERVED,
    A48_COST_USD,
    EXPECTED_IDEA,
    FUTURE_PROMPT,
    GLOBAL_INTENT_MAX_CHARS,
    HISTORICAL_240_ORIGIN,
    HISTORICAL_PROMPT,
    LIMIT_JUSTIFICATION,
    LOCAL_EXTRACTION_FUNCTIONALLY_FROZEN,
    MODE,
    NEW_GRAMMAR_CANARY_REQUIRED,
    NEW_PROVIDER_CANARY_REQUIRED_FOR_A46,
    NEXT_PHASE_AFTER_PASS,
    PHASE,
    PHASE_3B_STATUS,
    PROJECT_NAME,
    RELATION_QUALITY_TECHNICAL_DEBT,
    SCHEMA_ADAPTED_BYTES,
    SCHEMA_HASH,
    SCHEMA_RAW_BYTES,
    SCHEMA_VERSION,
    SOURCE_MAP_STATUS,
    TEXT_LIMITS,
    TRANSPORT_VERSION,
)
from app.source_analysis_v31_global_a48_offline_revalidation.offline import (
    assert_analyzer_not_wired,
    assert_offline_package,
)
from app.source_analysis_v31_global_a48_offline_revalidation.replay import (
    replay_a46_under_corrected_contract,
)
from app.source_analysis_v31_global_reuse_output.prompt_v30 import prompt_v30_bundle
from app.source_analysis_v31_global_reuse_output.prompt_v301 import prompt_v301_bundle
from app.source_analysis_v31_global_reuse_output.transport_v30 import measure_global_schema_v30


def _status(ok: bool) -> str:
    return "PASS" if ok else "FAIL"


def _gate_table(replay: dict[str, Any], *, published: bool) -> dict[str, Any]:
    semantic = replay.get("semantic") or {}
    editorial = replay.get("editorial") or {}
    structural = replay.get("structural") or {}
    identity = replay.get("identity") or {}
    intent = replay.get("intent") or {}
    reuse_audit = replay.get("reuse_text_audit") or {}
    completeness = semantic.get("completeness") or {}
    accountability = str(replay.get("idea_accountability") or "")
    reuse_exact = float(replay.get("reuse_text_exact_equality") or 0)
    expected_acc = f"{EXPECTED_IDEA} / {EXPECTED_IDEA}"
    no_forbidden = editorial.get("a46_actual_forbidden_editorial_structure") == "NO"
    gates = {
        "raw_response_identity": _status(bool(identity.get("ok"))),
        "parse": replay.get("structured_parse"),
        "decoder": replay.get("decoder"),
        "handles": replay.get("handle_validation"),
        "accountability_286": _status(accountability == expected_acc),
        "reuse_contract": _status(
            replay.get("keep_count") == EXPECTED_IDEA
            and replay.get("merge_equivalent_count") == 0
            and replay.get("drop_count") == 0
        ),
        "reuse_text_exact": _status(
            reuse_exact >= 100.0 and bool(reuse_audit.get("all_canonical_equals_local"))
        ),
        "derived_src": replay.get("derived_src"),
        "corrected_global_validator": replay.get("global_validator"),
        "canonical_reconstruction": replay.get("canonical_reconstruction"),
        "canonical_validation": replay.get("canonical_validation"),
        "structural_scanner": structural.get("status"),
        "deterministic_replay": _status(
            replay.get("deterministic_replay") == "PASS"
            and replay.get("independent_replay") == "PASS"
        ),
        "theme_review": semantic.get("theme_review"),
        "intent_review": intent.get("review_status"),
        "audience_review": semantic.get("audience_review"),
        "voice_review": semantic.get("voice_review"),
        "topic_review": (semantic.get("topics") or {}).get("status"),
        "example_review": (semantic.get("examples") or {}).get("status"),
        "reference_review": (semantic.get("references") or {}).get("status"),
        "uncertainty_preservation": (semantic.get("uncertainty") or {}).get("status"),
        "completeness": completeness.get("status"),
        "no_forbidden_editorial_structure": _status(no_forbidden and structural.get("ok")),
        "semantic_review": semantic.get("status"),
        "source_map_not_published": _status(not published),
        "a46_historical_fail_preserved": _status(A46_STATUS_PRESERVED == "FAIL"),
        "zero_provider_calls": _status(True),
    }
    all_pass = all(value == "PASS" for value in gates.values())
    return {"gates": gates, "all_pass": all_pass}


def build_bundle(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
    tests: str = "offline A.48",
    test_delta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    assert_offline_package()
    assert_analyzer_not_wired()
    replay = replay_a46_under_corrected_contract(project_name, sortie_dir=sortie_dir)
    published = source_map_path(project_name, sortie_dir=sortie_dir).is_file()
    gate = _gate_table(replay, published=published)
    prompt_frozen = prompt_v30_bundle()
    prompt_next = prompt_v301_bundle()
    measured = measure_global_schema_v30()
    matrix = contract_matrix()
    new_failures = int((test_delta or {}).get("new_failure_count") or 0)
    tests_ok = new_failures == 0
    publication_eligible = gate["all_pass"] and tests_ok and not published
    freeze = publication_eligible
    result = "PASS" if publication_eligible else "PARTIAL"
    semantic = replay.get("semantic") or {}
    editorial = replay.get("editorial") or {}
    structural = replay.get("structural") or {}
    identity = replay.get("identity") or {}
    intent = replay.get("intent") or {}
    candidate = replay.get("candidate_payload") or {}
    candidate_json = replay.get("candidate_canonical_json") or ""
    header = {
        "result": result,
        "phase": PHASE,
        "mode": MODE,
        "real_provider_calls": 0,
        "real_anthropic_calls": 0,
        "real_openai_calls": 0,
        "a46_historical_status": A46_STATUS_PRESERVED,
        "a47_status": A47_STATUS_PRESERVED,
        "a46_raw_response_identity": "MATCH" if identity.get("ok") else "MISMATCH",
        "a46_input": A46_INPUT_TOKENS,
        "a46_output": A46_OUTPUT_TOKENS,
        "a46_historical_cost": A46_COST_USD,
        "a48_cost": A48_COST_USD,
        "a46_elapsed": A46_ELAPSED_SECONDS,
        "historical_prompt": HISTORICAL_PROMPT,
        "future_prompt": FUTURE_PROMPT,
        "transport": TRANSPORT_VERSION,
        "schema_raw": SCHEMA_RAW_BYTES,
        "schema_adapted": SCHEMA_ADAPTED_BYTES,
        "schema_hash": SCHEMA_HASH,
        "schema_identity_unchanged": measured.get("hash") == SCHEMA_HASH,
        "prompt_identity_affects_request_not_schema": True,
        "historical_request_hash": A45_REQUEST_HASH,
        "future_request_hash": (
            "NOT_REUSED — prompt 3.0.1 changes request identity; "
            "schema identity remains 3.0"
        ),
        "normalized_input_hash": A45_NORMALIZED_INPUT_HASH,
        "global_intent_limit": GLOBAL_INTENT_MAX_CHARS,
        "a46_intent_length": A46_INTENT_LENGTH,
        "a46_intent_unchanged": "YES" if intent.get("unchanged") else "NO",
        "structured_parse": replay.get("structured_parse"),
        "transport_decoder": replay.get("decoder"),
        "handle_validation": replay.get("handle_validation"),
        "idea_accountability": replay.get("idea_accountability"),
        "reuse_merge_drop": (
            f"{replay.get('keep_count')} / {replay.get('merge_equivalent_count')} / "
            f"{replay.get('drop_count')}"
        ),
        "reuse_text_exact": (
            f"{int(round(float(replay.get('reuse_text_exact_equality') or 0) / 100.0 * EXPECTED_IDEA))}"
            f" / {EXPECTED_IDEA}"
        ),
        "SINGLE_MEMBER_WITH_V": replay.get("SINGLE_MEMBER_WITH_V"),
        "MULTI_MEMBER_WITHOUT_V": replay.get("MULTI_MEMBER_WITHOUT_V"),
        "multi_member_global_ideas": replay.get("multi_member_global_ideas"),
        "NON_IDEA_IN_MEMBERS": replay.get("NON_IDEA_IN_MEMBERS"),
        "NON_IDEA_IN_DROP": replay.get("NON_IDEA_IN_DROP"),
        "unknown_handles": replay.get("unknown_handles"),
        "duplicate_membership": replay.get("duplicate_membership"),
        "missing_ideas": replay.get("missing_ideas"),
        "member_drop_overlap": replay.get("member_drop_overlap"),
        "derived_src": replay.get("derived_src"),
        "corrected_global_validator": replay.get("global_validator"),
        "canonical_reconstruction": replay.get("canonical_reconstruction"),
        "canonical_validation": replay.get("canonical_validation"),
        "structural_editorial_scanner": structural.get("status"),
        "forbidden_editorial_structure": editorial.get(
            "a46_actual_forbidden_editorial_structure"
        ),
        "deterministic_replay": replay.get("deterministic_replay"),
        "theme_review": semantic.get("theme_review"),
        "intent_review": intent.get("review_status"),
        "audience_review": semantic.get("audience_review"),
        "voice_review": semantic.get("voice_review"),
        "topic_review": (semantic.get("topics") or {}).get("status"),
        "example_review": semantic.get("example_review")
        if semantic.get("example_review")
        else (semantic.get("examples") or {}).get("status"),
        "reference_review": (semantic.get("references") or {}).get("status"),
        "uncertainty_preservation": (semantic.get("uncertainty") or {}).get("status"),
        "completeness": (semantic.get("completeness") or {}).get("status"),
        "semantic_review": semantic.get("status"),
        "publication_eligible": "YES" if publication_eligible else "NO",
        "global_consolidation_core_architecture_functionally_frozen": (
            "YES" if freeze else "NO"
        ),
        "new_grammar_canary_required": NEW_GRAMMAR_CANARY_REQUIRED,
        "new_provider_canary_required_for_a46": NEW_PROVIDER_CANARY_REQUIRED_FOR_A46,
        "a46_output_utilization": f"{A46_OUTPUT_UTILIZATION_PERCENT}%",
        "a45_input_estimate_error": f"+{A45_INPUT_ESTIMATE_ERROR_PERCENT}%",
        "a45_expected_output_error": f"+{A45_EXPECTED_OUTPUT_ERROR_PERCENT}%",
        "relation_quality_technical_debt": RELATION_QUALITY_TECHNICAL_DEBT,
        "tests": tests,
        "new_failures": (test_delta or {}).get("new_failure_count", "pending"),
        "source_map": SOURCE_MAP_STATUS,
        "ready_for_controlled_source_map_publication": (
            "YES" if publication_eligible else "NO"
        ),
        "phase_3b": PHASE_3B_STATUS,
        "next_action": "HUMAN REVIEW",
        "next_phase_after_pass": NEXT_PHASE_AFTER_PASS,
        "frozen_prompt_hash": prompt_frozen.get("combined_sha256"),
        "future_prompt_hash": prompt_next.get("combined_sha256"),
        "live_intent_limit": TEXT_LIMITS["intent"],
        "a39_compactness_bound": A39_INTENT_COMPACTNESS_BOUND,
        "limit_justification": LIMIT_JUSTIFICATION,
        "historical_240_origin": HISTORICAL_240_ORIGIN,
    }
    contract = {
        "historical_request_contract": replay.get("historical_request_contract"),
        "corrected_product_contract": replay.get("corrected_product_contract"),
        "global_intent_max": GLOBAL_INTENT_MAX_CHARS,
        "live_text_limits": dict(TEXT_LIMITS),
        "corrected_text_limits": corrected_text_limits(),
        "competing_live_limits": TEXT_LIMITS["intent"] != GLOBAL_INTENT_MAX_CHARS,
        "canonical_model_has_intent_max": False,
        "anthropic_schema_enforces_bound": False,
        "prompt_3_0_mutated": False,
        "prompt_3_0_1_created": True,
        "transport_3_0_mutated": False,
        "schema_3_0_mutated": False,
        "schema_hash": measured.get("hash"),
        "historical_schema_hash": SCHEMA_HASH,
        "matrix_selected_limit": matrix.get("selected_limit"),
        "historical_240_origin": HISTORICAL_240_ORIGIN,
        "limit_justification": LIMIT_JUSTIFICATION,
        "do_not_reuse_a45_request_hash": True,
    }
    technical = {
        key: replay.get(key)
        for key in (
            "structured_parse",
            "decoder",
            "handle_validation",
            "idea_accountability",
            "keep_count",
            "merge_equivalent_count",
            "drop_count",
            "SINGLE_MEMBER_WITH_V",
            "MULTI_MEMBER_WITHOUT_V",
            "multi_member_global_ideas",
            "NON_IDEA_IN_MEMBERS",
            "NON_IDEA_IN_DROP",
            "unknown_handles",
            "duplicate_membership",
            "missing_ideas",
            "member_drop_overlap",
            "reuse_text_exact_equality",
            "reuse_text_audit",
            "derived_src",
            "global_validator",
            "canonical_reconstruction",
            "canonical_validation",
            "deterministic_replay",
            "independent_replay",
            "technical_pass",
            "historical_request_contract",
            "corrected_product_contract",
        )
    }
    technical["interpreted"] = replay.get("interpreted")
    technical["candidate_hash"] = content_hash(candidate_json) if candidate_json else ""
    architecture = {
        "GLOBAL_CONSOLIDATION_CORE_ARCHITECTURE_FUNCTIONALLY_FROZEN": (
            "YES" if freeze else "NO"
        ),
        "inverse_membership": True,
        "single_member_reuse": True,
        "multi_member_synthesis_only": True,
        "derived_src": True,
        "idea_accountability": True,
        "relations_deferred": True,
        "transport_3_0": True,
        "canonical_reconstruction": True,
        "future_prompt_identity": FUTURE_PROMPT,
        "historical_prompt_identity": HISTORICAL_PROMPT,
        "condition": "all A.48 gates pass",
        "frozen": freeze,
    }
    readiness = {
        "READY_FOR_CONTROLLED_SOURCE_MAP_PUBLICATION": (
            "YES" if publication_eligible else "NO"
        ),
        "PUBLICATION_ELIGIBLE": "YES" if publication_eligible else "NO",
        "GLOBAL_CONSOLIDATION_CORE_ARCHITECTURE_FUNCTIONALLY_FROZEN": (
            "YES" if freeze else "NO"
        ),
        "NEW_GRAMMAR_CANARY_REQUIRED": NEW_GRAMMAR_CANARY_REQUIRED,
        "NEW_PROVIDER_CANARY_REQUIRED_FOR_A46": NEW_PROVIDER_CANARY_REQUIRED_FOR_A46,
        "A46_HISTORICAL_STATUS": A46_STATUS_PRESERVED,
        "A47_STATUS": A47_STATUS_PRESERVED,
        "source_map": SOURCE_MAP_STATUS,
        "phase_3b": PHASE_3B_STATUS,
        "local_extraction_functionally_frozen": LOCAL_EXTRACTION_FUNCTIONALLY_FROZEN,
        "relation_quality_technical_debt": RELATION_QUALITY_TECHNICAL_DEBT,
        "do_not_publish": True,
        "do_not_call_provider": True,
        "do_not_start_phase_4": True,
        "next_action": "HUMAN REVIEW",
        "next_phase_after_pass": NEXT_PHASE_AFTER_PASS,
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
            "A.47": A47_STATUS_PRESERVED,
        },
    }
    publication = {
        "PUBLICATION_ELIGIBLE": "YES" if publication_eligible else "NO",
        "source_map_published": published,
        "a48_must_not_publish": True,
        "gates": gate["gates"],
        "all_gates_pass": gate["all_pass"],
        "tests_ok": tests_ok,
    }
    semantic_audit = {
        "status": semantic.get("status"),
        "reuse": {
            "count": EXPECTED_IDEA,
            "provider_generated_idea_text": False,
            "exact_local_inheritance": (replay.get("reuse_text_audit") or {}).get(
                "all_canonical_equals_local"
            ),
            "status": (semantic.get("reuse") or {}).get("status"),
        },
        "merges": {"count": 0, "status": (semantic.get("merges") or {}).get("status")},
        "drops": {"count": 0, "status": (semantic.get("drops") or {}).get("status")},
        "completeness": semantic.get("completeness"),
        "topics": semantic.get("topics"),
        "metadata": semantic.get("metadata"),
        "examples": {
            "status": (semantic.get("examples") or {}).get("status"),
            "external_fact_check": False,
        },
        "references": {
            "status": (semantic.get("references") or {}).get("status"),
            "external_fact_check": False,
        },
        "uncertainty": semantic.get("uncertainty"),
        "editorial": semantic.get("editorial"),
        "intent": intent,
        "theme_review": semantic.get("theme_review"),
        "audience_review": semantic.get("audience_review"),
        "voice_review": semantic.get("voice_review"),
        "relations": "DEFERRED",
        "relation_quality_technical_debt": RELATION_QUALITY_TECHNICAL_DEBT,
        "no_forbidden_editorial_structure": editorial.get(
            "a46_actual_forbidden_editorial_structure"
        ),
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "header": header,
        "contract": contract,
        "identity": identity,
        "technical": technical,
        "structural": {
            **editorial,
            "scan": structural,
        },
        "semantic": semantic_audit,
        "publication": publication,
        "architecture": architecture,
        "readiness": readiness,
        "candidate_payload": candidate,
        "protected_historical": protected_a47_historical_hashes(
            project_name, sortie_dir=sortie_dir
        ),
        "prompt_v301": {
            "prompt_version": prompt_next.get("prompt_version"),
            "activated_production": prompt_next.get("activated_production"),
            "sent_to_provider": prompt_next.get("sent_to_provider"),
            "previous_prompt_mutated": prompt_next.get("previous_prompt_mutated"),
            "intent_limit": prompt_next.get("intent_limit"),
            "combined_sha256": prompt_next.get("combined_sha256"),
            "schema_identity_unchanged": prompt_next.get("schema_identity_unchanged"),
        },
        "test_delta": test_delta or {},
        "result": result,
        "publication_eligible": publication_eligible,
    }


__all__ = ["build_bundle"]
