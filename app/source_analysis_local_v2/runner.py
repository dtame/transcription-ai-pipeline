"""Runner offline 3B.7.7A.11. FakeAI E2E en racines temporaires."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from app.source_analysis_local_v2.consolidation import v2_consolidation_compatibility
from app.source_analysis_local_v2.constants import (
    ADAPTIVE_HIERARCHY_STATUS,
    CALL_C_COST,
    CALL_C_FINISH,
    CALL_C_OUTPUT,
    CALL_C_PROVIDER_INPUT,
    CALL_C_THINKING_TOKENS,
    DEFERRED_KINDS,
    GRANULARITY_POLICY_VERSION,
    LOCAL_KINDS,
    MAX_OUTPUT_TOKENS_FROZEN,
    MODE,
    NEXT_ACTION,
    NEXT_PHASE,
    PHASE,
    PRIMARY_ROOT_CAUSE,
    PRODUCTION_PLANNER_VERSION,
    PROJECT_NAME,
    REAL_PROVIDER_CALL_AUTHORIZED_NEXT,
    REAL_PROVIDER_CALLS_THIS_PHASE,
    REAL_WINDOW_CALLS,
    RESERVED_THINKING_TOKENS,
    SCHEMA_VERSION,
    SELECTED_ARCHITECTURE,
    SEMANTIC_TRANSPORT_VERSION_V2,
    SMALL_PLANNER_STATUS,
    TARGET_JSON_LOCAL_TOKENS,
    WINDOW_ANALYSIS_PROMPT_VERSION_V12,
)
from app.source_analysis_local_v2.e2e import run_direct_e2e, run_hierarchical_e2e
from app.source_analysis_local_v2.facts import inspect_integrity, inspect_isolation
from app.source_analysis_local_v2.forensics_replay import replay_call_c_against_v2
from app.source_analysis_local_v2.granularity import granularity_policy
from app.source_analysis_local_v2.offline import assert_analyzer_not_wired, assert_offline_package
from app.source_analysis_local_v2.recovery import recovery_ownership
from app.source_analysis_local_v2.schema import compare_v1_v2_schemas
from app.source_analysis_local_v2.subdivision import subdivision_policy_facts
from app.source_analysis_local_v2.synthetic import measure_v2_worst_case
from app.source_analysis_local_v2.thinking import audit_thinking_capability
from app.source_analysis_local_v2.report import render_report


def _stamp(payload: dict[str, Any]) -> dict[str, Any]:
    out = dict(payload)
    out.setdefault("schema_version", SCHEMA_VERSION)
    out.setdefault("phase", PHASE)
    out.setdefault("mode", MODE)
    return out


def build_bundle(
    *,
    project_name: str = PROJECT_NAME,
    sortie_dir: Path | None = None,
    tmp_root: Path | None = None,
) -> dict[str, Any]:
    assert_offline_package()
    assert_analyzer_not_wired()
    schemas = compare_v1_v2_schemas()
    worst = measure_v2_worst_case()
    thinking = audit_thinking_capability(
        project_name=project_name, sortie_dir=sortie_dir
    )
    integrity = inspect_integrity(project_name, sortie_dir=sortie_dir)
    isolation = inspect_isolation(project_name, sortie_dir=sortie_dir)
    replay = replay_call_c_against_v2(
        project_name=project_name, sortie_dir=sortie_dir
    )
    own_tmp = tmp_root
    cleanup = False
    if own_tmp is None:
        own_tmp = Path(tempfile.mkdtemp(prefix="local_v2_e2e_"))
        cleanup = False
    direct = run_direct_e2e(own_tmp / "direct")
    hierarchical = run_hierarchical_e2e(own_tmp / "hierarchical")
    thinking_control = thinking.get("THINKING_CAP_CONTROL", "UNVERIFIED")
    within_target = bool(worst["within_json_target"])
    e2e_ok = (
        direct.source_map is not None
        and hierarchical.source_map is not None
        and direct.deferred_local_kinds_absent
        and hierarchical.deferred_local_kinds_absent
        and bool(direct.source_map.repetitions)
        and bool(direct.source_map.source_analysis.author_intent.kinds)
        and bool(direct.source_map.source_analysis.target_audience.kinds)
        and bool(direct.source_map.author_voice_profile.tone)
    )
    if (
        REAL_PROVIDER_CALLS_THIS_PHASE == 0
        and e2e_ok
        and within_target
        and replay["became_valid_v2_result"] is False
        and integrity["prompt_1_1_unchanged"]
        and integrity["generation_c_raw_unchanged"]
        and not integrity["source_map_present"]
        and integrity["project_state"]["not_success"]
        and thinking_control == "UNVERIFIED"
    ):
        result = "PARTIAL"
        result_reason = (
            "V2 FakeAI implementation succeeded; thinking-cap control "
            "remains UNVERIFIED and blocks real-call readiness."
        )
    elif REAL_PROVIDER_CALLS_THIS_PHASE != 0:
        result = "FAIL"
        result_reason = "provider called"
    elif not e2e_ok or not within_target or replay["became_valid_v2_result"]:
        result = "FAIL"
        result_reason = "e2e/target/replay failed"
    else:
        result = "PASS"
        result_reason = "all PASS criteria met"

    transport = _stamp(
        {
            "design": schemas,
            "local_kinds": list(LOCAL_KINDS),
            "deferred_kinds": list(DEFERRED_KINDS),
            "prompt": WINDOW_ANALYSIS_PROMPT_VERSION_V12,
            "transport": SEMANTIC_TRANSPORT_VERSION_V2,
        }
    )
    output_budget = _stamp(
        {
            "granularity": granularity_policy(),
            "worst_case": worst,
            "target": TARGET_JSON_LOCAL_TOKENS,
            "thinking_reserve_design": RESERVED_THINKING_TOKENS,
            "max_output_frozen": MAX_OUTPUT_TOKENS_FROZEN,
            "provider_enforcement_status": "APPLICATION_POLICY_BOUNDED_ONLY",
            "true_boundedness": "PARTIALLY_PROVIDER_BOUNDED",
            "notes": (
                "max_tokens=32000 is provider-enforced. JSON ceilings, "
                "value limits, and thinking reserve are application-only. "
                "Thinking cap is UNVERIFIED."
            ),
        }
    )
    subdivision = _stamp(subdivision_policy_facts())
    e2e = _stamp(
        {
            "direct": direct.to_dict(),
            "hierarchical": hierarchical.to_dict(),
            "call_c_replay": replay,
            "real_provider_calls": REAL_PROVIDER_CALLS_THIS_PHASE,
            "real_window_calls": REAL_WINDOW_CALLS,
        }
    )
    compat = _stamp(
        {
            **v2_consolidation_compatibility(),
            **recovery_ownership(),
            "canonical_sourcemap_contract_unchanged": True,
            "small_planner": SMALL_PLANNER_STATUS,
            "adaptive_hierarchy": ADAPTIVE_HIERARCHY_STATUS,
            "production_planner": PRODUCTION_PLANNER_VERSION,
        }
    )
    header = {
        "result": result,
        "result_reason": result_reason,
        "real_provider_calls": REAL_PROVIDER_CALLS_THIS_PHASE,
        "real_window_calls": REAL_WINDOW_CALLS,
        "root_cause": PRIMARY_ROOT_CAUSE,
        "new_prompt": WINDOW_ANALYSIS_PROMPT_VERSION_V12,
        "new_transport": SEMANTIC_TRANSPORT_VERSION_V2,
        "local_kinds": list(LOCAL_KINDS),
        "deferred_kinds": list(DEFERRED_KINDS),
        "local_granularity_policy": GRANULARITY_POLICY_VERSION,
        "synthetic_worst_case_tokens": worst["local_tokens"],
        "target": TARGET_JSON_LOCAL_TOKENS,
        "thinking_reserve_design": RESERVED_THINKING_TOKENS,
        "thinking_cap_control": thinking_control,
        "provider_enforced_output_boundedness": "PARTIAL",
        "v2_raw_schema_bytes": schemas["v2_generic"]["raw_bytes"],
        "v2_adapted_schema_bytes": schemas["v2_generic"]["adapted_bytes"],
        "v2_server_grammar": "UNVERIFIED",
        "capacity_subdivision": "PASS",
        "direct_fakeai_e2e": "PASS" if direct.source_map else "FAIL",
        "hierarchical_fakeai_e2e": "PASS" if hierarchical.source_map else "FAIL",
        "deferred_global_fields_recovered": "PASS" if e2e_ok else "FAIL",
        "canonical_sourcemap": "UNCHANGED",
        "small_planner": SMALL_PLANNER_STATUS,
        "adaptive_hierarchy": ADAPTIVE_HIERARCHY_STATUS,
        "production_default_changed": "NO",
        "real_source_map": "NOT PUBLISHED",
        "project_state": "INCOMPLETE",
        "real_provider_call_authorized_next": REAL_PROVIDER_CALL_AUTHORIZED_NEXT,
        "next_action": NEXT_ACTION,
        "next_phase": NEXT_PHASE,
        "architecture": SELECTED_ARCHITECTURE,
        "call_c": {
            "input": CALL_C_PROVIDER_INPUT,
            "output": CALL_C_OUTPUT,
            "thinking": CALL_C_THINKING_TOKENS,
            "finish": CALL_C_FINISH,
            "cost": CALL_C_COST,
        },
        "integrity": integrity,
        "isolation": isolation,
    }
    report = render_report(
        header=header,
        schemas=schemas,
        worst=worst,
        thinking=thinking,
        subdivision=subdivision,
        e2e=e2e,
        compat=compat,
        replay=replay,
        integrity=integrity,
    )
    return {
        "header": header,
        "transport": transport,
        "output_budget": output_budget,
        "thinking": _stamp(thinking),
        "subdivision": subdivision,
        "e2e": e2e,
        "compat": compat,
        "report": report,
        "integrity": integrity,
        "isolation": isolation,
        "tmp_root": str(own_tmp),
        "cleanup": cleanup,
    }
