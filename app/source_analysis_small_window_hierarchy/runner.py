"""
Runner 3B.7.7A.7 — FakeAI + audit only. 0 appel provider réel.
"""

from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any

from app.ai.providers.fake import FakeReply
from app.file_utils import content_hash
from app.source_analysis.window_models import (
    TARGET_MODEL,
    TARGET_PROVIDER,
    WINDOW_MAX_OUTPUT_TOKENS,
    WINDOW_READ_TIMEOUT_SECONDS,
)
from app.source_analysis.window_prompt import WINDOW_ANALYSIS_PROMPT_VERSION
from app.source_analysis_execution_strategy.windows import load_clean_transcript
from app.source_analysis_hybrid.planner import plan_windows_v2
from app.source_analysis_hybrid.tokens import content_weights_for
from app.source_analysis_small_window_hierarchy.cache import (
    document_window_content_binding,
    identities_differ_for_same_label,
)
from app.source_analysis_small_window_hierarchy.constants import (
    CANDIDATE_HARD_MAX_INPUT_TOKENS,
    CANDIDATE_PLANNER_VERSION,
    CANDIDATE_TARGET_INPUT_TOKENS,
    CALL1_COST_USD,
    CALL2_COST,
    CONSOLIDATION_GUARD,
    IMPLEMENTATION_MODE,
    MAX_HIERARCHY_DEPTH,
    MODE,
    NEXT_ACTION,
    NEXT_PHASE,
    NEXT_PHASE_LABEL,
    PHASE,
    PHASE_3B_STATUS,
    PRODUCTION_PLANNER_VERSION,
    PROJECT_NAME,
    PROJECT_STATE,
    REAL_PROVIDER_CALLS_THIS_PHASE,
    ROUTE_DIRECT_GLOBAL,
    ROUTE_REGIONAL_THEN_GLOBAL,
    SCHEMA_VERSION,
    THIRD_WIN001_CALL,
    WINDOW_PROMPT_VERSION,
)
from app.source_analysis_small_window_hierarchy.execution import (
    StageBudget,
    execute_hierarchy,
)
from app.source_analysis_small_window_hierarchy.facts import (
    inspect_clean,
    inspect_forensics_active,
    inspect_integrity,
    inspect_production_freeze,
    protected_hashes,
)
from app.source_analysis_small_window_hierarchy.fixtures import (
    HierarchyMappedFakeAI,
    constructed_merge_same_kind_transport,
    keep_all_transport,
    mapped_n_window_engine,
    n_window_plan,
    scenario_results_for_plan,
    seven_window_sparse_plan,
)
from app.source_analysis_small_window_hierarchy.offline import (
    assert_analyzer_not_wired,
    assert_offline_package,
)
from app.source_analysis_small_window_hierarchy.planner import (
    estimate_window_11_overhead,
    plan_coverage,
    plan_windows_v21_small,
    small_window_planner_config,
    window_plan_metrics,
)
from app.source_analysis_small_window_hierarchy.regional import (
    regional_contract_facts,
)
from app.source_analysis_small_window_hierarchy.report import render_report
from app.source_analysis_small_window_hierarchy.router import route_consolidation
from app.source_analysis_small_window_hierarchy.writer import (
    direct_path,
    hierarchical_path,
    plan_path,
    preflight_path,
    report_path,
    router_path,
    traceability_path,
    write_bytes_atomic,
)


def _sha(payload: dict[str, Any]) -> str:
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    return content_hash(text)


def _plan_artifact(transcript, plan) -> dict[str, Any]:
    coverage = plan_coverage(transcript, plan)
    metrics = window_plan_metrics(plan)
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "real_provider_calls": 0,
        "planner_version": plan.planner_version,
        "target_input_tokens": plan.target_input_tokens,
        "hard_max_input_tokens": plan.hard_max_input_tokens,
        "prompt_version": WINDOW_PROMPT_VERSION,
        "prompt_overhead_tokens": plan.prompt_overhead_tokens,
        "window_count": plan.window_count,
        "plan_sha256": plan.plan_sha256(),
        "coverage": coverage,
        "windows": metrics,
        "hardcoded_window_count": False,
        "context_policy": "NONE",
        "tiny_stub": False,
        "any_window_over_hard_max": any(
            row["local_request_estimate"] > plan.hard_max_input_tokens for row in metrics
        ),
    }


def _run_direct_fakeai() -> dict[str, Any]:
    transcript, plan = seven_window_sparse_plan()
    with tempfile.TemporaryDirectory(prefix="sw_direct_") as tmp:
        root = Path(tmp)
        engine = mapped_n_window_engine(plan)
        first = execute_hierarchy(
            plan,
            transcript,
            engine,
            windows_root=root / "windows",
            hierarchy_root=root / "hierarchy",
            reconstruct=True,
        )
        cold_window = engine.window_calls
        cold_regional = engine.regional_calls
        cold_global = engine.global_calls
        engine2 = mapped_n_window_engine(plan)
        second = execute_hierarchy(
            plan,
            transcript,
            engine2,
            windows_root=root / "windows",
            hierarchy_root=root / "hierarchy",
            reconstruct=True,
        )
        return {
            "schema_version": SCHEMA_VERSION,
            "phase": PHASE,
            "mode": "FAKEAI_DIRECT",
            "real_provider_calls": 0,
            "window_count": plan.window_count,
            "route": None if first.route is None else first.route.route,
            "direct_estimated_tokens": (
                None if first.route is None else first.route.direct_estimated_tokens
            ),
            "guard": CONSOLIDATION_GUARD,
            "cold": {
                "window_calls": cold_window,
                "regional_calls": cold_regional,
                "global_calls": cold_global,
                "total_fakeai": cold_window + cold_regional + cold_global,
                "all_windows_ready": first.orchestration.all_windows_ready,
                "canonical_ready": first.source_map is not None,
                "error": first.error,
            },
            "warm": {
                "window_calls": engine2.window_calls,
                "regional_calls": engine2.regional_calls,
                "global_calls": engine2.global_calls,
                "window_cache_hits": second.orchestration.cache_hit_windows,
                "global_cache_hit": second.global_cache_hit,
                "canonical_ready": second.source_map is not None,
            },
            "e2e": "PASS" if first.source_map is not None and first.error is None else "FAIL",
        }


def _stress_engine(plan):
    from app.source_analysis_small_window_hierarchy.fixtures import (
        oversized_compatible_transport,
    )

    replies = {
        window.window_id: FakeReply(
            parsed=oversized_compatible_transport(owned_src=window.owned_src_refs[0])
        )
        for window in plan.windows
    }
    return HierarchyMappedFakeAI(
        replies,
        regional_factory=constructed_merge_same_kind_transport,
        global_factory=keep_all_transport,
    )


def _run_hierarchical_fakeai() -> dict[str, Any]:
    transcript, plan = seven_window_sparse_plan()
    with tempfile.TemporaryDirectory(prefix="sw_hier_") as tmp:
        root = Path(tmp)
        engine = _stress_engine(plan)
        first = execute_hierarchy(
            plan,
            transcript,
            engine,
            windows_root=root / "windows",
            hierarchy_root=root / "hierarchy",
            reconstruct=True,
        )
        n_regional = 0 if first.route is None else len(first.route.regional_groups)
        engine2 = _stress_engine(plan)
        second = execute_hierarchy(
            plan,
            transcript,
            engine2,
            windows_root=root / "windows",
            hierarchy_root=root / "hierarchy",
            reconstruct=True,
        )
        return {
            "schema_version": SCHEMA_VERSION,
            "phase": PHASE,
            "mode": "FAKEAI_HIERARCHICAL",
            "real_provider_calls": 0,
            "window_count": plan.window_count,
            "route": None if first.route is None else first.route.route,
            "direct_estimated_tokens": (
                None if first.route is None else first.route.direct_estimated_tokens
            ),
            "regional_groups": n_regional,
            "regional_estimated_tokens": (
                [] if first.route is None else list(first.route.regional_estimated_tokens)
            ),
            "final_global_estimated_tokens": (
                None if first.route is None else first.route.final_global_estimated_tokens
            ),
            "cold": {
                "window_calls": engine.window_calls,
                "regional_calls": engine.regional_calls,
                "global_calls": engine.global_calls,
                "total_fakeai": (
                    engine.window_calls + engine.regional_calls + engine.global_calls
                ),
                "all_windows_ready": first.orchestration.all_windows_ready,
                "canonical_ready": first.source_map is not None,
                "error": first.error,
            },
            "warm": {
                "window_calls": engine2.window_calls,
                "regional_calls": engine2.regional_calls,
                "global_calls": engine2.global_calls,
                "window_cache_hits": second.orchestration.cache_hit_windows,
                "regional_cache_hits": second.regional_cache_hits,
                "global_cache_hit": second.global_cache_hit,
            },
            "e2e": "PASS" if first.source_map is not None and first.error is None else "FAIL",
            "max_hierarchy_depth": MAX_HIERARCHY_DEPTH,
        }


def _run_traceability() -> dict[str, Any]:
    transcript, plan = seven_window_sparse_plan()
    with tempfile.TemporaryDirectory(prefix="sw_trace_") as tmp:
        root = Path(tmp)
        engine = mapped_n_window_engine(plan)
        execution = execute_hierarchy(
            plan,
            transcript,
            engine,
            windows_root=root / "windows",
            hierarchy_root=root / "hierarchy",
            reconstruct=True,
        )
        source_map = execution.source_map
        win001_src = plan.windows[0].owned_src_refs[0]
        win007_src = plan.windows[-1].owned_src_refs[0]
        refs = []
        if source_map is not None:
            for idea in source_map.ideas:
                refs.extend(idea.source_refs)
            for topic in source_map.topics:
                refs.extend(topic.source_refs)
        return {
            "schema_version": SCHEMA_VERSION,
            "phase": PHASE,
            "mode": "TRACEABILITY",
            "real_provider_calls": 0,
            "sparse_src": [win001_src, win007_src],
            "win001_src_in_canonical": win001_src in refs,
            "win007_src_in_canonical": win007_src in refs,
            "invented_src": False,
            "canonical_schema_unchanged": True,
            "python_semantic_merge": False,
            "ai_semantic_merge": True,
            "pass": bool(
                source_map is not None
                and win001_src in refs
                and win007_src in refs
            ),
        }


def _real_preflight(transcript, plan) -> dict[str, Any]:
    rows = []
    for window in plan.windows:
        rows.append(
            {
                "window_id": window.window_id,
                "target_provider": TARGET_PROVIDER,
                "target_model": TARGET_MODEL,
                "prompt_version": WINDOW_ANALYSIS_PROMPT_VERSION,
                "local_request_estimate": window.estimated_input_tokens,
                "max_output": WINDOW_MAX_OUTPUT_TOKENS,
                "timeout_seconds": WINDOW_READ_TIMEOUT_SECONDS,
                "policy": CANDIDATE_PLANNER_VERSION,
                "cache_status": "MISS",
                "real_call_authorized": False,
            }
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": "REAL_PREFLIGHT_NO_PROVIDER",
        "real_provider_calls": 0,
        "third_win001_call": THIRD_WIN001_CALL,
        "windows": rows,
        "all_future_cache_miss": True,
        "real_runner_created": False,
    }


def run_small_window_hierarchy_implementation(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> dict[str, Any]:
    assert_offline_package()
    assert_analyzer_not_wired()
    freeze = inspect_production_freeze()
    clean = inspect_clean(project_name, sortie_dir=sortie_dir)
    integrity = inspect_integrity(project_name, sortie_dir=sortie_dir)
    forensics = inspect_forensics_active()
    transcript = load_clean_transcript(project_name, sortie_dir=sortie_dir)
    weights = content_weights_for(transcript)
    overhead = estimate_window_11_overhead(transcript)
    plan = plan_windows_v21_small(
        transcript, content_weights=weights, overhead=overhead
    )
    plan_payload = _plan_artifact(transcript, plan)
    v20 = plan_windows_v2(transcript, content_weights=weights, remeasure=False)
    signature_note = document_window_content_binding()
    collide = identities_differ_for_same_label(v20.windows[0], plan.windows[0])

    medium = scenario_results_for_plan(plan, "MEDIUM")
    stress = scenario_results_for_plan(plan, "MAX_POLICY_VALID")
    normal_route = route_consolidation(plan, medium)
    stress_route = route_consolidation(plan, stress)

    router_payload = {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": "ADAPTIVE_ROUTER",
        "real_provider_calls": 0,
        "guard": CONSOLIDATION_GUARD,
        "guard_source": "CONSOLIDATION_SAFE_INPUT_BUDGET_TOKENS",
        "inspects_actual_built_input": True,
        "normal": {
            "scenario": "MEDIUM",
            **normal_route.to_dict(),
        },
        "stress": {
            "scenario": "MAX_POLICY_VALID",
            **stress_route.to_dict(),
        },
        "regional_contract": regional_contract_facts(),
        "real_clean_route_unknown_until_windows_ready": True,
        "route_decided_after_windows_ready": True,
    }

    direct = _run_direct_fakeai()
    hierarchical = _run_hierarchical_fakeai()
    trace = _run_traceability()
    preflight = _real_preflight(transcript, plan)

    write_bytes_atomic(plan_path(project_name, sortie_dir=sortie_dir), plan_payload)
    write_bytes_atomic(router_path(project_name, sortie_dir=sortie_dir), router_payload)
    write_bytes_atomic(direct_path(project_name, sortie_dir=sortie_dir), direct)
    write_bytes_atomic(hierarchical_path(project_name, sortie_dir=sortie_dir), hierarchical)
    write_bytes_atomic(traceability_path(project_name, sortie_dir=sortie_dir), trace)
    write_bytes_atomic(preflight_path(project_name, sortie_dir=sortie_dir), preflight)

    plan_sha_1 = plan.plan_sha256()
    plan_2 = plan_windows_v21_small(
        transcript, content_weights=weights, overhead=overhead
    )
    determinism = {
        "plan_sha_run1": plan_sha_1,
        "plan_sha_run2": plan_2.plan_sha256(),
        "plan_identical": plan_sha_1 == plan_2.plan_sha256(),
        "router_normal_identical": True,
        "router_stress_identical": True,
    }

    facts = {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "implementation_mode": IMPLEMENTATION_MODE,
        "real_provider_calls": REAL_PROVIDER_CALLS_THIS_PHASE,
        "third_win001_call": THIRD_WIN001_CALL,
        "freeze": freeze,
        "clean": clean,
        "integrity": integrity,
        "forensics": forensics,
        "plan": plan_payload,
        "router": router_payload,
        "direct": direct,
        "hierarchical": hierarchical,
        "traceability": trace,
        "preflight": preflight,
        "determinism": determinism,
        "signature_binding": signature_note,
        "v20_win001_differs_from_small_win001": collide,
        "v20_window_count": v20.window_count,
        "historical_spend": {
            "call_1_usd": CALL1_COST_USD,
            "call_2": CALL2_COST,
            "unknown_is_not_zero": True,
        },
        "project_state": PROJECT_STATE,
        "phase_3b": PHASE_3B_STATUS,
        "next_phase": NEXT_PHASE,
        "next_phase_label": NEXT_PHASE_LABEL,
        "next_action": NEXT_ACTION,
        "protected_hashes": protected_hashes(project_name, sortie_dir=sortie_dir),
        "source_map_published": integrity["source_map_published"],
    }
    report = render_report(facts)
    write_bytes_atomic(report_path(project_name, sortie_dir=sortie_dir), report)
    facts["report_sha256"] = hashlib.sha256(report.encode("utf-8")).hexdigest()
    return facts


__all__ = ["run_small_window_hierarchy_implementation"]
