"""Assemble le dossier A.41. 0 provider. 0 consolidation. 0 canary."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.source_analysis.writer import source_map_path
from app.source_analysis_v31_global_drop_domain.analysis import (
    evaluate_root_causes,
    field_rename_analysis,
    schema_pattern_analysis,
    smallest_hardening_decision,
    validation_order_review,
)
from app.source_analysis_v31_global_drop_domain.constants import (
    A34_STATUS_PRESERVED,
    A35_STATUS_PRESERVED,
    A36_STATUS_PRESERVED,
    A37_STATUS_PRESERVED,
    A38_STATUS_PRESERVED,
    A39_STATUS_PRESERVED,
    A40_COST_USD,
    A40_ELAPSED_MS,
    A40_ESTIMATOR_ERROR_PERCENT,
    A40_FINISH_REASON,
    A40_GLOBAL_VALIDATOR,
    A40_GRAMMAR,
    A40_HTTP_STATUS,
    A40_INPUT_TOKENS,
    A40_OUTPUT_TOKENS,
    A40_PREDICTED_OUTPUT,
    A40_REQUEST_ID,
    A40_ROOT_VALIDATOR_ERROR,
    A40_STATUS_PRESERVED,
    A40_THINKING_TOKENS,
    A40_TRANSPORT_DECODER,
    A40_VIOLATING_ID,
    DROP_DOMAIN,
    LOCAL_EXTRACTION_FUNCTIONALLY_FROZEN,
    MODE,
    MODEL,
    NEW_GRAMMAR_CANARY_REQUIRED,
    NEXT_PROMPT_VERSION,
    NEXT_TRANSPORT_VERSION,
    OLD_PROMPT_VERSION,
    OLD_TRANSPORT_VERSION,
    PHASE,
    PHASE_3B_STATUS,
    PRODUCTION_MAX_OUTPUT_TOKENS,
    PROJECT_NAME,
    READY_FOR_COMPACT_GLOBAL_REAL_CALL_PREFLIGHT,
    READY_FOR_REAL_GLOBAL_CONSOLIDATION_CANARY,
    REAL_ANTHROPIC_CALLS,
    REAL_CONSOLIDATION_CALLS,
    REAL_PROVIDER_CALLS_THIS_PHASE,
    RELATION_QUALITY_TECHNICAL_DEBT,
    SCHEMA_CHANGED,
    SCHEMA_VERSION,
    SECOND_COMPACT_CONTRACT_CANARY_REQUIRED,
    SELECTED_HARDENING,
    SOURCE_MAP_STATUS,
    THINKING_MODE,
    V20_SCHEMA_ADAPTED_BYTES,
    V20_SCHEMA_HASH,
    V20_SCHEMA_RAW_BYTES,
)
from app.source_analysis_v31_global_drop_domain.estimator import (
    a40_estimator_audit,
    revised_production_budget,
)
from app.source_analysis_v31_global_drop_domain.evidence import verify_a40_identity
from app.source_analysis_v31_global_drop_domain.fakeai import catalog_fakeai_cases
from app.source_analysis_v31_global_drop_domain.fixture import next_compact_canary_fixture
from app.source_analysis_v31_global_drop_domain.hang import (
    classify_hang,
    static_hang_evidence,
)
from app.source_analysis_v31_global_drop_domain.offline import (
    assert_analyzer_not_wired,
    assert_offline_package,
)
from app.source_analysis_v31_global_drop_domain.paths import production_source_map_present
from app.source_analysis_v31_global_drop_domain.policy import local_object_kind_policy
from app.source_analysis_v31_global_drop_domain.prompt_v201 import prompt_v201_bundle
from app.source_analysis_v31_global_drop_domain.replay import (
    replay_a40_counterfactual,
    replay_a40_frozen,
)
from app.source_analysis_v31_global_output_architecture.prompt_v20 import prompt_v20_bundle
from app.source_analysis_v31_global_output_architecture.transport_v20 import (
    measure_global_schema_v20,
)


def _public_replay(replay: dict[str, Any]) -> dict[str, Any]:
    skip = {"transport", "interpreted"}
    public = {key: value for key, value in replay.items() if key not in skip}
    public["interpreted"] = replay.get("interpreted")
    return public


def build_bundle(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
    tests: str = "offline A.41",
    hang_probes: dict[str, Any] | None = None,
    hang_full: dict[str, Any] | None = None,
    test_delta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    assert_offline_package()
    assert_analyzer_not_wired()
    identity = verify_a40_identity(project_name, sortie_dir=sortie_dir)
    frozen = replay_a40_frozen(project_name, sortie_dir=sortie_dir)
    counterfactual = replay_a40_counterfactual(project_name, sortie_dir=sortie_dir)
    policy = local_object_kind_policy()
    causes = evaluate_root_causes(fixture_has_relation=True)
    schema_opt = schema_pattern_analysis()
    rename = field_rename_analysis()
    order = validation_order_review()
    hardening = smallest_hardening_decision()
    fakeai = catalog_fakeai_cases()
    estimator = a40_estimator_audit()
    budget = revised_production_budget()
    prompt_old = prompt_v20_bundle()
    prompt_new = prompt_v201_bundle()
    schema = measure_global_schema_v20()
    next_fixture = next_compact_canary_fixture()
    hang_static = static_hang_evidence(project_name)
    hang_class = classify_hang(
        static=hang_static,
        probes=hang_probes or {},
        full=hang_full,
    )
    source_map_present = production_source_map_present(
        project_name, sortie_dir=sortie_dir
    ) or source_map_path(project_name, sortie_dir=sortie_dir).is_file()
    schema_unchanged = (
        schema.get("raw_bytes") == V20_SCHEMA_RAW_BYTES
        and schema.get("adapted_bytes") == V20_SCHEMA_ADAPTED_BYTES
        and schema.get("hash") == V20_SCHEMA_HASH
        and prompt_old.get("combined_sha256") == identity.get("prompt_hash")
        and prompt_old.get("prompt_version") == OLD_PROMPT_VERSION
        and prompt_new.get("prompt_version") == NEXT_PROMPT_VERSION
        and prompt_new.get("previous_prompt_mutated") is False
    )
    contract_ok = all(
        [
            identity.get("ok"),
            frozen.get("root_error_reproduced"),
            frozen.get("global_validator") == "FAIL",
            frozen.get("structured_parse") == "PASS",
            frozen.get("decoder") == "PASS",
            counterfactual.get("a40_remains_fail") is True,
            fakeai.get("valid_passes"),
            fakeai.get("all_negatives_fail"),
            schema_unchanged,
            REAL_PROVIDER_CALLS_THIS_PHASE == 0,
            not source_map_present,
            READY_FOR_REAL_GLOBAL_CONSOLIDATION_CANARY == "NO",
            READY_FOR_COMPACT_GLOBAL_REAL_CALL_PREFLIGHT == "NO",
        ]
    )
    full_ok = False
    if hang_full:
        full_ok = (
            not hang_full.get("timed_out")
            and int(hang_full.get("failed") or 0) == 0
            and int(hang_full.get("passed") or 0) > 0
        )
    if contract_ok and full_ok:
        result = "PASS"
        readiness = "READY_FOR_SECOND_COMPACT_CONTRACT_CANARY"
    elif contract_ok and not full_ok:
        result = "PARTIAL"
        readiness = "BLOCKED_BY_TEST_SUITE"
    else:
        result = "FAIL"
        readiness = "BLOCKED"

    readiness_payload = {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "decision": readiness,
        "READY_FOR_SECOND_COMPACT_CONTRACT_CANARY": readiness
        == "READY_FOR_SECOND_COMPACT_CONTRACT_CANARY",
        "NEEDS_MORE_OFFLINE_REDESIGN": readiness == "NEEDS_MORE_OFFLINE_REDESIGN",
        "BLOCKED_BY_TEST_SUITE": readiness == "BLOCKED_BY_TEST_SUITE",
        "BLOCKED": readiness == "BLOCKED",
        "READY_FOR_REAL_GLOBAL_CONSOLIDATION_CANARY": READY_FOR_REAL_GLOBAL_CONSOLIDATION_CANARY,
        "READY_FOR_COMPACT_GLOBAL_REAL_CALL_PREFLIGHT": READY_FOR_COMPACT_GLOBAL_REAL_CALL_PREFLIGHT,
        "new_grammar_canary_required": NEW_GRAMMAR_CANARY_REQUIRED,
        "second_compact_contract_canary_required": SECOND_COMPACT_CONTRACT_CANARY_REQUIRED,
        "schema_changed": SCHEMA_CHANGED,
        "do_not_execute_automatically": True,
        "do_not_rerun_a40": True,
        "next_action": "HUMAN REVIEW",
        "real_consolidation_executed": False,
        "source_map": SOURCE_MAP_STATUS,
        "phase_3b": PHASE_3B_STATUS,
    }

    kinds = policy.get("kinds") or {}
    header = {
        "result": result,
        "real_provider_calls": REAL_PROVIDER_CALLS_THIS_PHASE,
        "a40_status": f"{A40_STATUS_PRESERVED} unchanged",
        "a40_request": A40_REQUEST_ID,
        "a40_grammar": A40_GRAMMAR,
        "a40_transport_decoder": A40_TRANSPORT_DECODER,
        "a40_root_validator_failure": A40_ROOT_VALIDATOR_ERROR,
        "a40_sole_technical_root": "YES" if counterfactual.get("sole_technical_root") else "NO",
        "counterfactual": counterfactual.get("global_validator"),
        "drop_domain": DROP_DOMAIN,
        "local_relation_policy": kinds.get("RELATION", {}).get("treatment"),
        "local_topic_policy": kinds.get("TOPIC", {}).get("treatment"),
        "local_example_policy": kinds.get("EXAMPLE", {}).get("treatment"),
        "local_reference_policy": kinds.get("REFERENCE", {}).get("treatment"),
        "local_uncertainty_policy": kinds.get("UNCERTAINTY", {}).get("treatment"),
        "selected_hardening": SELECTED_HARDENING,
        "old_prompt": OLD_PROMPT_VERSION,
        "next_prompt": NEXT_PROMPT_VERSION,
        "old_transport": OLD_TRANSPORT_VERSION,
        "next_transport": NEXT_TRANSPORT_VERSION,
        "schema_changed": "YES" if SCHEMA_CHANGED else "NO",
        "next_schema_raw_adapted": f"{V20_SCHEMA_RAW_BYTES} / {V20_SCHEMA_ADAPTED_BYTES}",
        "next_schema_hash": V20_SCHEMA_HASH,
        "new_grammar_canary_required": "YES" if NEW_GRAMMAR_CANARY_REQUIRED else "NO",
        "second_compact_contract_canary_required": (
            "YES" if SECOND_COMPACT_CONTRACT_CANARY_REQUIRED else "NO"
        ),
        "a40_predicted_output": A40_PREDICTED_OUTPUT,
        "a40_actual_output": A40_OUTPUT_TOKENS,
        "a40_estimator_error": f"+{A40_ESTIMATOR_ERROR_PERCENT}%",
        "revised_expected": budget.get("p50_expected"),
        "revised_conservative": budget.get("conservative"),
        "revised_hard": budget.get("hard_planning"),
        "production_max_output": PRODUCTION_MAX_OUTPUT_TOKENS,
        "margin_70": budget.get("margin_70"),
        "margin_75": budget.get("margin_75"),
        "margin_80": budget.get("margin_80"),
        "output_risk": budget.get("output_risk"),
        "full_suite_hang_root": hang_class.get("root"),
        "full_suite_status": (
            hang_full.get("summary")
            if hang_full
            else hang_static.get("a40_split_note")
        ),
        "tests": tests,
        "new_failures": (test_delta or {}).get("new_failure_count", "pending"),
        "readiness": readiness,
        "identity_ok": identity.get("ok"),
        "http": A40_HTTP_STATUS,
        "finish": A40_FINISH_REASON,
        "thinking_tokens": A40_THINKING_TOKENS,
        "input_tokens": A40_INPUT_TOKENS,
        "cost": A40_COST_USD,
        "elapsed_ms": A40_ELAPSED_MS,
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
        },
    }

    return {
        "header": header,
        "forensics": {
            "identity": identity,
            "replay": _public_replay(frozen),
            "root_causes": causes,
            "validation_order": order,
            "violating_id": A40_VIOLATING_ID,
            "provider_vs_contract": frozen.get("provider_success_vs_contract_failure"),
        },
        "counterfactual": {
            key: value
            for key, value in counterfactual.items()
            if key != "transport"
        },
        "policy": policy,
        "hardening": {
            **hardening,
            "schema_option": schema_opt,
            "field_rename": rename,
            "prompt_old_hash": prompt_old.get("combined_sha256"),
            "prompt_new_hash": prompt_new.get("combined_sha256"),
            "prompt_2_0_immutable": prompt_old.get("prompt_version") == OLD_PROMPT_VERSION,
        },
        "fakeai": fakeai,
        "estimator": estimator,
        "budget": budget,
        "hang": {
            "static": hang_static,
            "probes": hang_probes or {},
            "full": hang_full or {},
            "classification": hang_class,
        },
        "next_fixture": next_fixture,
        "readiness": readiness_payload,
        "test_delta": test_delta,
        "schema_metrics": {
            "raw_bytes": schema.get("raw_bytes"),
            "adapted_bytes": schema.get("adapted_bytes"),
            "hash": schema.get("hash"),
            "unchanged": schema_unchanged,
        },
        "guards": {
            "real_provider_calls": REAL_PROVIDER_CALLS_THIS_PHASE,
            "real_anthropic_calls": REAL_ANTHROPIC_CALLS,
            "real_consolidation_calls": REAL_CONSOLIDATION_CALLS,
            "source_map_present": source_map_present,
            "local_extraction_functionally_frozen": LOCAL_EXTRACTION_FUNCTIONALLY_FROZEN,
            "relation_quality_technical_debt": RELATION_QUALITY_TECHNICAL_DEBT,
            "phase_3b": PHASE_3B_STATUS,
        },
    }


__all__ = ["build_bundle"]
