"""Assemble le dossier A.39. 0 provider. 0 consolidation. 0 canary."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.source_analysis.writer import source_map_path
from app.source_analysis_v31_global_canary_forensics.prompt_v101 import prompt_v101_bundle
from app.source_analysis_v31_global_canary_forensics.transport_v11 import (
    measure_global_schema_v11,
)
from app.source_analysis_v31_global_output_architecture.constants import (
    A34_STATUS_PRESERVED,
    A35_STATUS_PRESERVED,
    A36_STATUS_PRESERVED,
    A37_STATUS_PRESERVED,
    A38_COST_USD,
    A38_INPUT_TOKENS,
    A38_OUTPUT_TOKENS,
    A38_REQUEST_ID,
    A38_ROOT_FAILURE,
    A38_STATUS_PRESERVED,
    LOCAL_EXTRACTION_FUNCTIONALLY_FROZEN,
    MODE,
    MODEL,
    NEW_GRAMMAR_CANARY_REQUIRED,
    NEXT_MAX_OUTPUT_TOKENS,
    NEXT_PROMPT_VERSION,
    NEXT_SCHEMA_ADAPTED_BYTES,
    NEXT_SCHEMA_HASH,
    NEXT_SCHEMA_RAW_BYTES,
    NEXT_TRANSPORT_VERSION,
    PHASE,
    PHASE_3B_STATUS,
    PROJECT_NAME,
    READINESS_DECISION,
    READY_FOR_REAL_GLOBAL_CONSOLIDATION_CANARY,
    REAL_CONSOLIDATION_CALLS,
    REAL_PROVIDER_CALLS_THIS_PHASE,
    REAL_WINDOW_CALLS,
    RELATION_QUALITY_TECHNICAL_DEBT,
    SCHEMA_CHANGED,
    SCHEMA_VERSION,
    SOURCE_MAP_STATUS,
    THINKING_MODE,
    V11_SCHEMA_ADAPTED_BYTES,
    V11_SCHEMA_HASH,
    V11_SCHEMA_RAW_BYTES,
)
from app.source_analysis_v31_global_output_architecture.costing import (
    a38_historical_cost,
    estimate_cost,
)
from app.source_analysis_v31_global_output_architecture.decision import (
    membership_contract,
    relation_decision,
    repetition_decision,
    selected_architecture,
)
from app.source_analysis_v31_global_output_architecture.estimator import estimate_output
from app.source_analysis_v31_global_output_architecture.evidence import (
    read_a38_raw_text,
    verify_a38_identity,
)
from app.source_analysis_v31_global_output_architecture.fixture import stress_report
from app.source_analysis_v31_global_output_architecture.forensics import (
    classify_a38_failures,
    idea_similarity_forensics,
    input_estimate_review,
    inspect_raw_prefix,
    output_estimate_review,
    transport_11_complete_output_range,
)
from app.source_analysis_v31_global_output_architecture.gate import pre_call_output_gate
from app.source_analysis_v31_global_output_architecture.local_input import (
    expected_global_idea_range,
    load_duplicate_artifact,
    load_normalized_artifact,
    local_ideas,
)
from app.source_analysis_v31_global_output_architecture.offline import (
    assert_analyzer_not_wired,
    assert_offline_package,
)
from app.source_analysis_v31_global_output_architecture.options import architecture_options
from app.source_analysis_v31_global_output_architecture.prompt_v20 import prompt_v20_bundle
from app.source_analysis_v31_global_output_architecture.transport_v20 import (
    measure_global_schema_v20,
)
from app.source_analysis_v31_global_output_architecture.volume import breakdown_from_prefix
from app.source_analysis_v31_global_output_architecture.paths import (
    production_source_map_present as _present,
)


def _public_schema(measured: dict[str, Any]) -> dict[str, Any]:
    skip = {"schema", "adapted_schema", "raw", "adapted"}
    return {key: value for key, value in measured.items() if key not in skip}


def build_bundle(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
    tests: str = "offline A.39",
    baseline_tests: str | None = None,
) -> dict[str, Any]:
    assert_offline_package()
    assert_analyzer_not_wired()
    identity = verify_a38_identity(project_name, sortie_dir=sortie_dir)
    raw_text = read_a38_raw_text(project_name, sortie_dir=sortie_dir)
    prefix = inspect_raw_prefix(raw_text)
    prefix_public = {
        key: value
        for key, value in prefix.items()
        if key != "complete_objects"
    }
    normalized = load_normalized_artifact(project_name, sortie_dir=sortie_dir)
    ideas = local_ideas(normalized)
    similarity = idea_similarity_forensics(prefix, ideas)
    duplicates = load_duplicate_artifact(project_name, sortie_dir=sortie_dir)
    idea_range = expected_global_idea_range(duplicates)
    if float(similarity.get("mean_best_ratio") or 0) >= 0.9:
        idea_range["interpretations"][
            "D_provider_copied_almost_every_local_idea"
        ] = "SUPPORTED"
    failures = classify_a38_failures()
    input_review = input_estimate_review()
    output_review = output_estimate_review()
    complete_11 = transport_11_complete_output_range(prefix)
    breakdown = breakdown_from_prefix(prefix, raw_text)
    estimate = estimate_output()
    all_distinct = estimate_output(topics=67, ideas=286, members_per_idea=1)
    mass_merge = estimate_output(topics=25, ideas=80, members_per_idea=4)
    gate = pre_call_output_gate(estimate)
    options = architecture_options(
        compact_expected=int(estimate["provider_planning_tokens"]["expected"]),
        compact_hard=int(estimate["provider_planning_tokens"]["hard"]),
        transport11_expected=int(complete_11["expected"]),
        transport11_high=int(complete_11["high"]),
    )
    selected = selected_architecture(estimate)
    membership = membership_contract()
    relation = relation_decision()
    repetition = repetition_decision()
    v11 = measure_global_schema_v11()
    v20 = measure_global_schema_v20()
    prompt_old = prompt_v101_bundle()
    prompt_new = prompt_v20_bundle()
    stress = stress_report()
    source_map_present = _present(
        project_name, sortie_dir=sortie_dir
    ) or source_map_path(project_name, sortie_dir=sortie_dir).is_file()
    v11_unchanged = (
        v11.get("raw_bytes") == V11_SCHEMA_RAW_BYTES
        and v11.get("adapted_bytes") == V11_SCHEMA_ADAPTED_BYTES
        and v11.get("hash") == V11_SCHEMA_HASH
        and prompt_old.get("prompt_version") == "global-consolidation-1.0.1"
    )
    v20_matches = (
        v20.get("raw_bytes") == NEXT_SCHEMA_RAW_BYTES
        and v20.get("adapted_bytes") == NEXT_SCHEMA_ADAPTED_BYTES
        and v20.get("hash") == NEXT_SCHEMA_HASH
        and not v20.get("unsupported_constructs")
    )
    pass_gate = all(
        [
            identity.get("ok"),
            failures.get("root_failure") == A38_ROOT_FAILURE,
            prefix.get("root_r_started") is False,
            prefix.get("root_d_started") is False,
            complete_11.get("feasibility_32000") == "NO",
            estimate.get("fits_safety"),
            all_distinct.get("fits_safety"),
            gate.get("allowed"),
            stress.get("ok"),
            v11_unchanged,
            v20_matches,
            REAL_PROVIDER_CALLS_THIS_PHASE == 0,
            not source_map_present,
            READY_FOR_REAL_GLOBAL_CONSOLIDATION_CANARY == "NO",
        ]
    )
    readiness = {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "decision": READINESS_DECISION,
        "READY_FOR_COMPACT_GLOBAL_GRAMMAR_CANARY": True,
        "READY_FOR_BOUNDED_MULTI_STAGE_GRAMMAR_CANARY": False,
        "NEEDS_MORE_OFFLINE_REDESIGN": False,
        "BLOCKED": not pass_gate,
        "READY_FOR_REAL_GLOBAL_CONSOLIDATION_CANARY": READY_FOR_REAL_GLOBAL_CONSOLIDATION_CANARY,
        "new_grammar_canary_required": NEW_GRAMMAR_CANARY_REQUIRED,
        "schema_changed": SCHEMA_CHANGED,
        "do_not_execute_automatically": True,
        "do_not_retry_a38": True,
        "next_action": "HUMAN REVIEW",
        "real_consolidation_executed": False,
        "source_map": SOURCE_MAP_STATUS,
        "phase_3b": PHASE_3B_STATUS,
    }
    header = {
        "result": "PASS" if pass_gate else "FAIL",
        "real_provider_calls": REAL_PROVIDER_CALLS_THIS_PHASE,
        "a38_request": A38_REQUEST_ID,
        "a38_root_failure": A38_ROOT_FAILURE,
        "selected_architecture": selected.get("selected"),
        "readiness": READINESS_DECISION,
        "new_failures": "pending" if tests == "offline A.39" else "0",
        "raw_prefix": {
            "topics": (prefix.get("kind_key_counts") or {}).get("TOPIC"),
            "ideas": (prefix.get("kind_key_counts") or {}).get("IDEA"),
            "relations_started": prefix.get("root_r_started"),
            "dispositions_started": prefix.get("root_d_started"),
        },
        "complete_11": complete_11,
        "schema": {
            "raw_bytes": v20.get("raw_bytes"),
            "adapted_bytes": v20.get("adapted_bytes"),
            "hash": v20.get("hash"),
        },
        "next_estimate": estimate,
        "notes": (
            "A.38 truncated at 32000 after ~281 IDEA keys and ~42 TOPIC keys. "
            "Transport 1.1 cannot fit this project. Compact inverse-membership "
            "2.0 is bounded; relations deferred; 286-IDEA accountability kept."
        ),
        "identity_ok": identity.get("ok"),
        "v11_unchanged": v11_unchanged,
        "v20_matches": v20_matches,
        "stress_ok": stress.get("ok"),
        "gate_allowed": gate.get("allowed"),
        "mode": MODE,
        "model": MODEL,
        "thinking": THINKING_MODE,
        "source_map_present": source_map_present,
    }
    forensics = {
        "identity": identity,
        "root_and_cascade": failures,
        "raw_prefix": prefix_public,
        "input_estimate": input_review,
        "output_estimate": output_review,
        "similarity": similarity,
        "expected_global_idea_range": idea_range,
        "a38_status": "FAIL unchanged",
        "request_id": A38_REQUEST_ID,
        "historical": {
            "A34": A34_STATUS_PRESERVED,
            "A35": A35_STATUS_PRESERVED,
            "A36": A36_STATUS_PRESERVED,
            "A37": A37_STATUS_PRESERVED,
            "A38": A38_STATUS_PRESERVED,
        },
        "repaired": False,
        "candidate_created": False,
    }
    budget = {
        "next_max_output": NEXT_MAX_OUTPUT_TOKENS,
        "safety_ratio": estimate.get("safety_ratio"),
        "safety_target": estimate.get("safety_target"),
        "expected": estimate.get("provider_planning_tokens"),
        "hard": estimate.get("provider_planning_tokens"),
        "all_distinct_286": all_distinct.get("provider_planning_tokens"),
        "mass_merge": mass_merge.get("provider_planning_tokens"),
        "gate": gate,
        "a38_cost": a38_historical_cost(),
        "next_cost_expected": estimate_cost(
            input_tokens=A38_INPUT_TOKENS,
            output_tokens=int(estimate["provider_planning_tokens"]["expected"]),
        ),
        "next_cost_hard": estimate_cost(
            input_tokens=A38_INPUT_TOKENS,
            output_tokens=int(estimate["provider_planning_tokens"]["hard"]),
        ),
        "input_not_bottleneck": True,
        "actual_a38_input": A38_INPUT_TOKENS,
        "actual_a38_output": A38_OUTPUT_TOKENS,
        "failed_a38_cost_usd": A38_COST_USD,
        "telemetry": {
            "future_reports_must_compare": [
                "predicted_output",
                "actual_output",
                "error_ratio",
            ]
        },
        "model": MODEL,
        "thinking": THINKING_MODE,
    }
    schema_public = {
        **_public_schema(v20),
        "prompt": prompt_new,
        "historical_1_1_unchanged": v11_unchanged,
    }
    return {
        "header": header,
        "forensics": forensics,
        "breakdown": breakdown,
        "options": options,
        "selected": selected,
        "membership": membership,
        "relation": relation,
        "repetition": repetition,
        "budget": budget,
        "stress": stress,
        "schema": schema_public,
        "readiness": readiness,
        "test_delta": {},
        "complete_objects_held_in_memory_only": True,
        "local_extraction_functionally_frozen": LOCAL_EXTRACTION_FUNCTIONALLY_FROZEN,
        "relation_quality_technical_debt": RELATION_QUALITY_TECHNICAL_DEBT,
        "real_provider_calls": REAL_PROVIDER_CALLS_THIS_PHASE,
        "real_window_calls": REAL_WINDOW_CALLS,
        "real_consolidation_calls": REAL_CONSOLIDATION_CALLS,
        "baseline_tests": baseline_tests,
        "next_prompt": NEXT_PROMPT_VERSION,
        "next_transport": NEXT_TRANSPORT_VERSION,
        "phase_3b": PHASE_3B_STATUS,
        "source_map": SOURCE_MAP_STATUS,
    }


__all__ = ["build_bundle"]
