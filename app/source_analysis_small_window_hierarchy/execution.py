"""
N-window + adaptive hierarchy FakeAI execution.

SEQUENTIAL. STOP_ON_FIRST_EXECUTION_FAILURE.
Separate call budgets for window / regional / global.
No real provider. No production analyzer wiring.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

from app.source_analysis.consolidation_analyzer import consolidate
from app.source_analysis.consolidation_input import build_consolidation_input_from_plan
from app.source_analysis.consolidation_models import (
    CONSOLIDATION_PROMPT_VERSION,
    ConsolidationSemanticResult,
)
from app.source_analysis.errors import (
    HierarchyCapacityExceeded,
    WindowsIncompleteError,
)
from app.source_analysis.hybrid_reconstructor import reconstruct_source_map
from app.source_analysis.orchestration_models import WindowOrchestrationResult
from app.source_analysis.transcript_input import TranscriptInput
from app.source_analysis.window_models import WindowSemanticResult
from app.source_analysis.window_orchestrator import orchestrate_windows
from app.source_analysis.window_prompt import WINDOW_ANALYSIS_PROMPT_VERSION
from app.source_analysis_hybrid.contracts import WindowPlan
from app.source_analysis_small_window_hierarchy.cache import (
    global_cache_identity,
    regional_cache_identity,
)
from app.source_analysis_small_window_hierarchy.constants import (
    CONSOLIDATION_GUARD,
    MAX_HIERARCHY_DEPTH,
    ROUTE_DIRECT_GLOBAL,
    ROUTE_REGIONAL_THEN_GLOBAL,
)
from app.source_analysis_small_window_hierarchy.regional import (
    REGIONAL_RECORD_ID_PATTERN,
    RegionalSemanticResult,
    build_global_input_from_regional,
    build_regional_input,
    flatten_global_result_to_window_members,
    validate_regional_decoded,
)
from app.source_analysis_small_window_hierarchy.router import (
    RouteDecision,
    route_consolidation,
)

def _load_consolidation_result(path: Path) -> ConsolidationSemanticResult:
    from app.source_analysis.consolidation_models import (
        ConsolidationGlobalMetadata,
        ConsolidationNode,
        ConsolidationProviderMetadata,
        ConsolidationRelation,
        ConsolidationRepetition,
        ConsolidationSemanticResult,
        CONSOLIDATION_RESULT_SCHEMA_VERSION,
    )

    payload = json.loads(path.read_text(encoding="utf-8"))
    metadata = payload["global_metadata"]
    provider = payload["provider_metadata"]
    nodes = tuple(
        ConsolidationNode(
            node_id=item["node_id"],
            operation=item["operation"],
            kind=item["kind"],
            value=item["value"],
            member_ids=tuple(item["member_ids"]),
            source_refs=tuple(item["source_refs"]),
            source_refs_are_local_union=bool(item.get("source_refs_are_local_union", True)),
        )
        for item in payload.get("nodes") or []
    )
    return ConsolidationSemanticResult(
        schema_version=payload.get("schema_version", CONSOLIDATION_RESULT_SCHEMA_VERSION),
        input_hash=payload["input_hash"],
        consolidation_signature=payload["consolidation_signature"],
        transport_version=payload["transport_version"],
        prompt_version=payload["prompt_version"],
        global_metadata=ConsolidationGlobalMetadata(
            main_theme=metadata["main_theme"],
            author_intent=metadata["author_intent"],
            target_audience=metadata["target_audience"],
            author_voice_profile=metadata["author_voice_profile"],
            theme_evidence=tuple(metadata.get("theme_evidence") or ()),
            intent_evidence=tuple(metadata.get("intent_evidence") or ()),
            audience_evidence=tuple(metadata.get("audience_evidence") or ()),
            voice_evidence=tuple(metadata.get("voice_evidence") or ()),
        ),
        nodes=nodes,
        relations=tuple(
            ConsolidationRelation(
                relation_type=item["relation_type"],
                left_ref=item["left_ref"],
                right_ref=item["right_ref"],
                left_node_id=item["left_node_id"],
                right_node_id=item["right_node_id"],
            )
            for item in payload.get("relations") or []
        ),
        repetitions=tuple(
            ConsolidationRepetition(
                character=item["character"],
                member_ids=tuple(item["member_ids"]),
                node_ids=tuple(item["node_ids"]),
                value=item.get("value") or "",
            )
            for item in payload.get("repetitions") or []
        ),
        provider_metadata=ConsolidationProviderMetadata(
            provider=provider.get("provider") or "fake",
            model=provider.get("model") or "fake",
            input_tokens=provider.get("input_tokens"),
            output_tokens=provider.get("output_tokens"),
            total_tokens=provider.get("total_tokens"),
            usage_source=provider.get("usage_source") or "provider",
            finish_reason=provider.get("finish_reason"),
        ),
        accounted_record_ids=tuple(payload.get("accounted_record_ids") or ()),
    )


@dataclass
class StageBudget:
    max_new_window_calls: int | None = None
    max_new_regional_calls: int | None = None
    max_new_global_calls: int | None = None


@dataclass
class HierarchyExecutionResult:
    orchestration: WindowOrchestrationResult
    route: RouteDecision | None = None
    regional_results: tuple[RegionalSemanticResult, ...] = ()
    regional_cache_hits: int = 0
    regional_generated: int = 0
    regional_failed: str | None = None
    global_result: ConsolidationSemanticResult | None = None
    global_cache_hit: bool = False
    source_map: Any = None
    window_calls: int = 0
    regional_calls: int = 0
    global_calls: int = 0
    real_provider_calls: int = 0
    error: str | None = None
    reporting: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "all_windows_ready": self.orchestration.all_windows_ready,
            "window_count": self.orchestration.total_windows,
            "ready_windows": self.orchestration.ready_windows,
            "route": None if self.route is None else self.route.to_dict(),
            "regional_group_count": 0 if self.route is None else len(self.route.regional_groups),
            "regional_ready": len(self.regional_results),
            "regional_cache_hits": self.regional_cache_hits,
            "regional_generated": self.regional_generated,
            "regional_failed": self.regional_failed,
            "global_ready": self.global_result is not None,
            "global_cache_hit": self.global_cache_hit,
            "canonical_ready": self.source_map is not None,
            "window_calls": self.window_calls,
            "regional_calls": self.regional_calls,
            "global_calls": self.global_calls,
            "real_provider_calls": self.real_provider_calls,
            "error": self.error,
            "reporting": dict(self.reporting),
        }


def _write_json(path: Path, payload: Mapping | dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(dict(payload), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _regional_cache_paths(root: Path, group_id: str) -> tuple[Path, Path]:
    folder = root / "regional" / group_id
    return folder / "signature.txt", folder / "result.json"


def _global_cache_paths(root: Path, route: str) -> tuple[Path, Path]:
    folder = root / "global" / route
    return folder / "signature.txt", folder / "result.json"


def execute_hierarchy(
    plan: WindowPlan,
    transcript: TranscriptInput,
    engine,
    *,
    windows_root: Path,
    hierarchy_root: Path,
    project_name: str = "fixture",
    budget: StageBudget | None = None,
    prompt_version: str = WINDOW_ANALYSIS_PROMPT_VERSION,
    reconstruct: bool = False,
    guard: int = CONSOLIDATION_GUARD,
    regional_factory_bind: bool = True,
) -> HierarchyExecutionResult:
    """
    Sequential FakeAI execution. 6/N ready blocks routing.
    """
    budget = budget or StageBudget()
    fake_before = int(getattr(engine, "call_count", 0) or 0)
    window_before = int(getattr(engine, "window_calls", 0) or 0)
    regional_before = int(getattr(engine, "regional_calls", 0) or 0)
    global_before = int(getattr(engine, "global_calls", 0) or 0)

    orch = orchestrate_windows(
        plan,
        transcript,
        windows_root=windows_root,
        engine=engine,
        project_name=project_name,
        max_new_calls=budget.max_new_window_calls,
        prompt_version=prompt_version,
    )
    result = HierarchyExecutionResult(orchestration=orch)
    result.window_calls = int(getattr(engine, "window_calls", 0) or 0) - window_before
    if not orch.all_windows_ready:
        result.error = "WINDOWS_INCOMPLETE"
        result.reporting = {
            "all_windows_ready": False,
            "route_evaluated": False,
        }
        return result

    decision = route_consolidation(
        plan, orch.get_ready_results_in_plan_order(), orchestration=orch, guard=guard
    )
    result.route = decision
    ready = orch.get_ready_results_in_plan_order()

    try:
        if decision.route == ROUTE_DIRECT_GLOBAL:
            _execute_direct(
                result,
                plan,
                ready,
                engine,
                hierarchy_root=hierarchy_root,
                project_name=project_name,
                budget=budget,
                guard=guard,
            )
        else:
            _execute_regional_then_global(
                result,
                plan,
                ready,
                engine,
                hierarchy_root=hierarchy_root,
                project_name=project_name,
                budget=budget,
                guard=guard,
                bind=regional_factory_bind,
            )
        if reconstruct and result.global_result is not None:
            result.source_map = reconstruct_after_hierarchy(
                transcript, plan, ready, result
            )
    except (
        HierarchyCapacityExceeded,
        WindowsIncompleteError,
        Exception,
    ) as exc:
        if result.error is None:
            result.error = f"{type(exc).__name__}: {exc}"
        if type(exc).__name__ in {
            "HierarchyCapacityExceeded",
            "ConsolidationCapacityExceeded",
            "RegionalConsolidationValidationError",
            "HierarchyDepthExceeded",
            "SmallWindowPlanningError",
            "WindowsIncompleteError",
        }:
            pass
        elif type(exc).__name__ in {"AIError", "AITimeoutError", "AIResponseError"}:
            raise
        else:
            # capacity / validation stay local; unexpected still recorded
            pass

    result.regional_calls = int(getattr(engine, "regional_calls", 0) or 0) - regional_before
    result.global_calls = int(getattr(engine, "global_calls", 0) or 0) - global_before
    result.real_provider_calls = 0
    result.reporting = {
        "all_windows_ready": True,
        "route": None if result.route is None else result.route.route,
        "window_calls": result.window_calls,
        "regional_calls": result.regional_calls,
        "global_calls": result.global_calls,
        "fake_ai_calls": int(getattr(engine, "call_count", 0) or 0) - fake_before,
        "max_hierarchy_depth": MAX_HIERARCHY_DEPTH,
    }
    return result


def _execute_direct(
    result: HierarchyExecutionResult,
    plan: WindowPlan,
    ready: Sequence[WindowSemanticResult],
    engine,
    *,
    hierarchy_root: Path,
    project_name: str,
    budget: StageBudget,
    guard: int,
) -> None:
    if budget.max_new_global_calls is not None and budget.max_new_global_calls < 1:
        if not _try_global_hit(result, plan, ready, hierarchy_root, guard, ROUTE_DIRECT_GLOBAL):
            result.error = "GLOBAL_BUDGET_EXHAUSTED"
        return
    payload = build_consolidation_input_from_plan(plan, ready, safe_budget=guard)
    identity = global_cache_identity(
        ROUTE_DIRECT_GLOBAL,
        payload,
        source_hashes=[item.result_sha256() for item in ready],
        provider="fake",
        model="fake-model",
        max_output_tokens=16000,
        prompt_version=CONSOLIDATION_PROMPT_VERSION,
    )
    sig_path, res_path = _global_cache_paths(hierarchy_root, ROUTE_DIRECT_GLOBAL)
    if sig_path.is_file() and res_path.is_file():
        if sig_path.read_text(encoding="utf-8").strip() == identity.digest():
            result.global_result = _load_consolidation_result(res_path)
            result.global_cache_hit = True
            return
    if getattr(engine, "bind_global_input", None):
        engine.bind_global_input(payload)
    generated = consolidate(
        payload,
        engine,
        consolidation_root=hierarchy_root / "global" / ROUTE_DIRECT_GLOBAL,
        project_name=project_name,
    )
    _write_json(res_path, generated.to_dict())
    sig_path.parent.mkdir(parents=True, exist_ok=True)
    sig_path.write_text(identity.digest() + "\n", encoding="utf-8")
    result.global_result = generated


def _try_global_hit(result, plan, ready, hierarchy_root, guard, route) -> bool:
    try:
        payload = build_consolidation_input_from_plan(
            plan, ready, safe_budget=guard, enforce_budget=False
        )
    except Exception:
        return False
    identity = global_cache_identity(
        route,
        payload,
        source_hashes=[item.result_sha256() for item in ready],
        provider="fake",
        model="fake-model",
        max_output_tokens=16000,
        prompt_version=CONSOLIDATION_PROMPT_VERSION,
    )
    sig_path, res_path = _global_cache_paths(hierarchy_root, route)
    if sig_path.is_file() and res_path.is_file():
        if sig_path.read_text(encoding="utf-8").strip() == identity.digest():
            result.global_result = _load_consolidation_result(res_path)
            result.global_cache_hit = True
            return True
    return False


def _execute_regional_then_global(
    result: HierarchyExecutionResult,
    plan: WindowPlan,
    ready: Sequence[WindowSemanticResult],
    engine,
    *,
    hierarchy_root: Path,
    project_name: str,
    budget: StageBudget,
    guard: int,
    bind: bool,
) -> None:
    assert result.route is not None
    regional: list[RegionalSemanticResult] = []
    stop = False
    generated = 0
    for group in result.route.regional_groups:
        if stop:
            break
        windows = tuple(w for w in plan.windows if w.window_id in set(group.window_ids))
        subset_results = tuple(r for r in ready if r.window_id in set(group.window_ids))
        regional_input = build_regional_input(plan, ready, group, guard=guard)
        identity = regional_cache_identity(
            group.group_id,
            windows,
            subset_results,
            regional_input,
            provider="fake",
            model="fake-model",
            max_output_tokens=16000,
        )
        sig_path, res_path = _regional_cache_paths(hierarchy_root, group.group_id)
        if sig_path.is_file() and res_path.is_file():
            if sig_path.read_text(encoding="utf-8").strip() == identity.digest():
                payload = _read_json(res_path)
                regional.append(_regional_from_dict(payload))
                result.regional_cache_hits += 1
                continue
        if budget.max_new_regional_calls is not None and generated >= budget.max_new_regional_calls:
            result.error = "REGIONAL_BUDGET_EXHAUSTED"
            stop = True
            break
        try:
            if bind and getattr(engine, "bind_regional_input", None):
                engine.bind_regional_input(group.group_id, regional_input)
                engine.pending_regional_group_id = group.group_id
            decoded = consolidate(
                regional_input,
                engine,
                consolidation_root=hierarchy_root / "regional" / group.group_id,
                project_name=f"{project_name}-{group.group_id}",
            )
            regional_result = validate_regional_decoded(
                decoded,
                regional_input,
                group=group,
                signature=identity.digest(),
            )
            _write_json(res_path, regional_result.to_dict())
            sig_path.parent.mkdir(parents=True, exist_ok=True)
            sig_path.write_text(identity.digest() + "\n", encoding="utf-8")
            regional.append(regional_result)
            generated += 1
            result.regional_generated += 1
        except Exception as exc:
            result.regional_failed = group.group_id
            result.error = type(exc).__name__
            stop = True
    result.regional_results = tuple(regional)
    if len(regional) != len(result.route.regional_groups):
        return
    if budget.max_new_global_calls is not None and budget.max_new_global_calls < 1:
        result.error = result.error or "GLOBAL_BUDGET_EXHAUSTED"
        return
    global_input = build_global_input_from_regional(
        plan, regional, guard=guard, enforce_budget=True
    )
    if result.route is not None:
        object.__setattr__(
            result.route,
            "final_global_estimated_tokens",
            global_input.estimated_tokens,
        )
    identity = global_cache_identity(
        ROUTE_REGIONAL_THEN_GLOBAL,
        global_input,
        source_hashes=[item.result_sha256() for item in regional],
        provider="fake",
        model="fake-model",
        max_output_tokens=16000,
        prompt_version=CONSOLIDATION_PROMPT_VERSION,
    )
    sig_path, res_path = _global_cache_paths(hierarchy_root, ROUTE_REGIONAL_THEN_GLOBAL)
    if sig_path.is_file() and res_path.is_file():
        if sig_path.read_text(encoding="utf-8").strip() == identity.digest():
            result.global_result = _load_consolidation_result(res_path)
            result.global_cache_hit = True
            return
    if getattr(engine, "bind_global_input", None):
        engine.bind_global_input(global_input)
    generated_global = consolidate(
        global_input,
        engine,
        consolidation_root=hierarchy_root / "global" / ROUTE_REGIONAL_THEN_GLOBAL,
        project_name=f"{project_name}-GLOBAL",
        allowed_record_id_pattern=REGIONAL_RECORD_ID_PATTERN,
    )
    _write_json(res_path, generated_global.to_dict())
    sig_path.parent.mkdir(parents=True, exist_ok=True)
    sig_path.write_text(identity.digest() + "\n", encoding="utf-8")
    result.global_result = generated_global


def _regional_from_dict(payload: dict) -> RegionalSemanticResult:
    from app.source_analysis_small_window_hierarchy.regional import RegionalNode

    nodes = tuple(
        RegionalNode(
            record_id=item["record_id"],
            operation=item["operation"],
            kind=item["kind"],
            value=item["value"],
            member_ids=tuple(item["member_ids"]),
            origin_record_ids=tuple(item["origin_record_ids"]),
            source_refs=tuple(item["source_refs"]),
            window_ids=tuple(item["window_ids"]),
        )
        for item in payload.get("nodes") or []
    )
    return RegionalSemanticResult(
        schema_version=payload["schema_version"],
        group_id=payload["group_id"],
        contract_version=payload["contract_version"],
        input_hash=payload["input_hash"],
        regional_signature=payload["regional_signature"],
        transport_version=payload["transport_version"],
        window_ids=tuple(payload["window_ids"]),
        nodes=nodes,
        accounted_record_ids=tuple(payload.get("accounted_record_ids") or ()),
    )


def reconstruct_after_hierarchy(
    transcript: TranscriptInput,
    plan: WindowPlan,
    window_results: Sequence[WindowSemanticResult],
    execution: HierarchyExecutionResult,
):
    if execution.global_result is None or execution.route is None:
        raise WindowsIncompleteError("consolidation globale absente.")
    if execution.route.route == ROUTE_DIRECT_GLOBAL:
        direct = build_consolidation_input_from_plan(plan, window_results)
        return reconstruct_source_map(
            transcript,
            plan,
            window_results,
            execution.global_result,
            consolidation_input=direct,
        )
    direct = build_consolidation_input_from_plan(
        plan, window_results, enforce_budget=False
    )
    flattened = flatten_global_result_to_window_members(
        execution.global_result,
        execution.regional_results,
        direct,
    )
    return reconstruct_source_map(
            transcript,
            plan,
            window_results,
            flattened,
            consolidation_input=direct,
            enforce_budget=False,
        )


__all__ = [
    "HierarchyExecutionResult",
    "StageBudget",
    "execute_hierarchy",
    "reconstruct_after_hierarchy",
]
