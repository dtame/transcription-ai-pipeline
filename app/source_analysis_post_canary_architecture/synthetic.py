"""
Résultats de fenêtre synthétiques bornés + mesure ConsolidationInput.

Transports compatibles FakeAI. Aucun appel provider.
"""

from __future__ import annotations

import json
from typing import Any, Mapping, Sequence

from app.ai.estimation import estimate_tokens
from app.source_analysis.consolidation_input import build_consolidation_input_from_plan
from app.source_analysis.consolidation_models import (
    CONSOLIDATION_SAFE_INPUT_BUDGET_TOKENS,
)
from app.source_analysis.consolidation_prompt import (
    estimate_consolidation_request_tokens,
)
from app.source_analysis.errors import ConsolidationContextExceeded
from app.source_analysis.transcript_input import TranscriptInput
from app.source_analysis.window_granularity import (
    HARD_CEILINGS,
    SOFT_TARGETS,
    TOTAL_HARD_CEILING,
)
from app.source_analysis.window_models import (
    WINDOW_CANDIDATE_SCOPE,
    WINDOW_RESULT_SCHEMA_VERSION,
    WindowCandidateMetadata,
    WindowProviderMetadata,
    WindowSemanticResult,
    assign_intermediate_records,
    compute_coverage,
    compute_record_stats,
)
from app.source_analysis.window_prompt import WINDOW_ANALYSIS_PROMPT_VERSION
from app.source_analysis.window_validator import (
    decode_window_transport,
    validate_window_result,
)
from app.source_analysis_hybrid.contracts import WindowInput, WindowPlan, canonical_dumps
from app.source_analysis_window_output_bounding.size_study import (
    SCENARIO_SPECS,
    build_scenario_transport,
)
from app.source_analysis_post_canary_architecture.constants import (
    CONSOLIDATION_GUARD_EXPECTED,
    PHASE,
    SCHEMA_VERSION,
)

SUBSTANTIVE = frozenset(
    {"TOPIC", "IDEA", "EXAMPLE", "REFERENCE", "UNCERTAINTY", "REPETITION"}
)


def _remap_refs(refs: Sequence[Any], owned: Sequence[str]) -> list[str]:
    if not owned:
        return []
    remapped: list[str] = []
    for index, _ref in enumerate(refs):
        remapped.append(owned[index % len(owned)])
    # unique stable order, keep at least one
    seen: set[str] = set()
    ordered: list[str] = []
    for src in remapped:
        if src not in seen:
            seen.add(src)
            ordered.append(src)
    return ordered or [owned[0]]


def remap_transport_to_window(
    transport: Mapping[str, Any],
    window: WindowInput,
) -> dict[str, Any]:
    owned = list(window.owned_src_refs)
    records = []
    for item in transport.get("records") or []:
        kind = str(item.get("k") or "")
        refs = list(item.get("s") or [])
        if kind in SUBSTANTIVE:
            refs = _remap_refs(refs, owned)
        else:
            refs = _remap_refs(refs, owned) if refs else []
        records.append(
            {
                "k": kind,
                "v": item.get("v"),
                "s": refs,
                "l": list(item.get("l") or []),
                "m": list(item.get("m") or []),
            }
        )
    return {
        "theme": transport.get("theme"),
        "intent": transport.get("intent"),
        "ic": transport.get("ic"),
        "aud": transport.get("aud"),
        "ac": transport.get("ac"),
        "records": records,
    }


def transport_for_scenario(name: str) -> dict[str, Any]:
    spec = SCENARIO_SPECS[name]
    return build_scenario_transport(
        counts=spec["counts"],
        idea_refs=spec["idea_refs"],
        topic_refs=spec["topic_refs"],
        other_refs=spec["other_refs"],
        max_text=spec["max_text"],
    )


def result_from_transport(
    window: WindowInput,
    transport: Mapping[str, Any],
    *,
    signature: str,
) -> WindowSemanticResult:
    remapped = remap_transport_to_window(transport, window)
    decode_window_transport(remapped, window)
    records = assign_intermediate_records(
        remapped["records"], window_id=window.window_id
    )
    result = WindowSemanticResult(
        schema_version=WINDOW_RESULT_SCHEMA_VERSION,
        window_id=window.window_id,
        window_input_hash=window.input_hash,
        window_analysis_signature=signature,
        transport_version="semantic-transport-v1",
        prompt_version=WINDOW_ANALYSIS_PROMPT_VERSION,
        planner_version=window.planner_version,
        owned_src_refs=window.owned_src_refs,
        context_src_refs=window.context_src_refs,
        candidates=WindowCandidateMetadata(
            theme=str(remapped.get("theme") or ""),
            intent=str(remapped.get("intent") or ""),
            intent_confidence=str(remapped.get("ic") or ""),
            audience=str(remapped.get("aud") or ""),
            audience_confidence=str(remapped.get("ac") or ""),
            intent_kinds=tuple(
                record.value for record in records if record.kind == "INTENT_KIND"
            ),
            audience_kinds=tuple(
                record.value for record in records if record.kind == "AUDIENCE_KIND"
            ),
            scope=WINDOW_CANDIDATE_SCOPE,
        ),
        records=records,
        coverage=compute_coverage(window, records),
        stats=compute_record_stats(records),
        provider_metadata=WindowProviderMetadata(
            provider="fake",
            model="fake-model",
            input_tokens=10,
            output_tokens=10,
            total_tokens=20,
            usage_source="provider",
            finish_reason="stop",
        ),
        voice_evidence={"tone": ["didactic"]},
    )
    validate_window_result(result, window)
    return result


def _measure_input(payload, *, safe_budget: int) -> dict[str, Any]:
    serialized = canonical_dumps(payload.to_dict())
    encoded = serialized.encode("utf-8")
    request = estimate_consolidation_request_tokens(payload)
    return {
        "record_count": sum(len(window.records) for window in payload.windows),
        "window_count": len(payload.windows),
        "serialized_chars": len(serialized),
        "serialized_bytes": len(encoded),
        "consolidation_input_estimated_tokens": payload.estimated_tokens,
        "full_request_estimated_tokens": int(request["total_tokens"]),
        "system_tokens": int(request["system_tokens"]),
        "safe_budget": safe_budget,
        "guard": CONSOLIDATION_GUARD_EXPECTED,
        "exceeds_guard": payload.estimated_tokens > safe_budget,
        "truncated": False,
    }


def try_build_consolidation(
    plan: WindowPlan,
    results: Sequence[WindowSemanticResult],
    *,
    safe_budget: int = CONSOLIDATION_SAFE_INPUT_BUDGET_TOKENS,
) -> dict[str, Any]:
    try:
        built = build_consolidation_input_from_plan(
            plan, results, safe_budget=safe_budget
        )
        measured = _measure_input(built, safe_budget=safe_budget)
        measured["status"] = "WITHIN_GUARD"
        measured["payload"] = built
        return measured
    except ConsolidationContextExceeded as exc:
        # Fail-closed : aucune troncature. Mesure hors builder.
        from app.source_analysis.consolidation_input import _build_from_ordered
        from app.source_analysis.consolidation_input import _ordered_results_from_plan

        ordered = _ordered_results_from_plan(plan, results)
        oversized = _build_from_ordered(
            transcript_id=plan.transcript_id,
            planner_version=plan.planner_version,
            results=ordered,
            plan=plan,
            safe_budget=10**9,
        )
        measured = _measure_input(oversized, safe_budget=safe_budget)
        measured["status"] = "EXCEEDS_GUARD"
        measured["error"] = str(exc)
        measured["fail_closed"] = True
        measured["truncated"] = False
        measured["payload"] = oversized
        return measured


def synthetic_results_for_plan(
    plan: WindowPlan,
    *,
    scenario: str,
) -> list[WindowSemanticResult]:
    transport = transport_for_scenario(scenario)
    results: list[WindowSemanticResult] = []
    for index, window in enumerate(plan.windows, start=1):
        signature = f"{index:064x}"[-64:]
        results.append(result_from_transport(window, transport, signature=signature))
    return results


def regional_groups(window_count: int, *, max_per_group: int = 3) -> list[list[int]]:
    """Groupes déterministes, ordre source, pas de clustering sémantique."""
    groups: list[list[int]] = []
    current: list[int] = []
    for index in range(window_count):
        current.append(index)
        if len(current) >= max_per_group:
            groups.append(current)
            current = []
    if current:
        if groups and len(current) == 1 and len(groups[-1]) + 1 <= max_per_group + 1:
            groups[-1].extend(current)
        else:
            groups.append(current)
    return groups


def measure_plan_consolidation(
    transcript: TranscriptInput,
    plan_row: Mapping[str, Any],
    *,
    safe_budget: int = CONSOLIDATION_SAFE_INPUT_BUDGET_TOKENS,
) -> dict[str, Any]:
    del transcript
    plan = plan_row["plan"]
    normal_results = synthetic_results_for_plan(plan, scenario="MEDIUM")
    stress_results = synthetic_results_for_plan(plan, scenario="MAX_POLICY_VALID")
    normal = try_build_consolidation(plan, normal_results, safe_budget=safe_budget)
    stress = try_build_consolidation(plan, stress_results, safe_budget=safe_budget)
    groups = regional_groups(plan.window_count)
    regional_normal: list[dict[str, Any]] = []
    for group in groups:
        subset_windows = tuple(plan.windows[index] for index in group)
        subset_results = [normal_results[index] for index in group]
        subset_plan = WindowPlan(
            strategy=plan.strategy,
            planner_version=plan.planner_version,
            transcript_id=plan.transcript_id,
            transcript_sha256=plan.transcript_sha256,
            target_input_tokens=plan.target_input_tokens,
            hard_max_input_tokens=plan.hard_max_input_tokens,
            overlap_policy=plan.overlap_policy,
            prompt_overhead_tokens=plan.prompt_overhead_tokens,
            windows=subset_windows,
            owned_src_count=sum(window.owned_src_count for window in subset_windows),
            context_src_count=sum(window.context_src_count for window in subset_windows),
            window_count=len(subset_windows),
            estimated_input_tokens_min=min(
                window.estimated_input_tokens for window in subset_windows
            ),
            estimated_input_tokens_max=max(
                window.estimated_input_tokens for window in subset_windows
            ),
            estimated_input_tokens_mean=plan.estimated_input_tokens_mean,
            estimated_input_tokens_median=plan.estimated_input_tokens_median,
        )
        measured = try_build_consolidation(
            subset_plan, subset_results, safe_budget=safe_budget
        )
        regional_normal.append(
            {
                "window_ids": [window.window_id for window in subset_windows],
                "status": measured["status"],
                "consolidation_input_estimated_tokens": measured[
                    "consolidation_input_estimated_tokens"
                ],
                "exceeds_guard": measured["exceeds_guard"],
            }
        )
    normal_tokens = int(normal["consolidation_input_estimated_tokens"])
    stress_tokens = int(stress["consolidation_input_estimated_tokens"])
    hierarchy_required_normal = normal_tokens > safe_budget
    hierarchy_required_stress = stress_tokens > safe_budget
    return {
        "label": plan_row.get("label"),
        "window_count": plan.window_count,
        "scenario_normal": "MEDIUM",
        "scenario_stress": "MAX_POLICY_VALID",
        "stress_is_not_expected_case": True,
        "normal": {key: value for key, value in normal.items() if key != "payload"},
        "stress": {key: value for key, value in stress.items() if key != "payload"},
        "normal_record_count": normal["record_count"],
        "stress_record_count": stress["record_count"],
        "duplication_burden_note": (
            "More windows increase cross-window duplicate concept candidates. "
            "This measurement counts local records, not proven semantic duplicates."
        ),
        "hierarchy": {
            "regional_group_count": len(groups),
            "groups": [[plan.windows[index].window_id for index in group] for group in groups],
            "grouping": "deterministic source-ordered batches of 3",
            "semantic_python_clustering": False,
            "regional_normal": regional_normal,
            "required_if_normal_exceeds_guard": hierarchy_required_normal,
            "required_if_stress_exceeds_guard": hierarchy_required_stress,
            "adaptive_trigger": (
                "if ConsolidationInput.estimated_tokens > "
                f"{safe_budget} then regional then global; else direct global"
            ),
        },
        "payloads": {"normal": normal.get("payload"), "stress": stress.get("payload")},
        "results": {"normal": normal_results, "stress": stress_results},
    }


def run_consolidation_scaling(simulations: Mapping[str, Any]) -> dict[str, Any]:
    transcript = simulations["transcript_obj"]
    rows = [simulations["plans"]["current"], *simulations["plans"]["candidates"]]
    measured: list[dict[str, Any]] = []
    for row in rows:
        if not row.get("feasible", True) or "plan" not in row:
            measured.append(
                {
                    "label": row.get("label"),
                    "feasible": False,
                    "infeasible_reason": row.get("infeasible_reason"),
                }
            )
            continue
        measured.append(measure_plan_consolidation(transcript, row))
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": "OFFLINE_CONSOLIDATION_SCALING",
        "real_provider_calls": 0,
        "guard": CONSOLIDATION_SAFE_INPUT_BUDGET_TOKENS,
        "guard_matches_contract": (
            CONSOLIDATION_SAFE_INPUT_BUDGET_TOKENS == CONSOLIDATION_GUARD_EXPECTED
        ),
        "capacity_signaling": {
            "exists": True,
            "mechanism": "ConsolidationContextExceeded, fail-closed, no truncation",
            "debt_if_missing": False,
        },
        "soft_targets": dict(SOFT_TARGETS),
        "hard_ceilings": dict(HARD_CEILINGS),
        "total_hard_ceiling": TOTAL_HARD_CEILING,
        "plans": [
            {key: value for key, value in row.items() if key not in {"payloads", "results"}}
            for row in measured
        ],
        "internal": measured,
    }


def fakeai_compatible_transport_json(transport: Mapping[str, Any]) -> str:
    return json.dumps(dict(transport), ensure_ascii=False, separators=(",", ":"))
