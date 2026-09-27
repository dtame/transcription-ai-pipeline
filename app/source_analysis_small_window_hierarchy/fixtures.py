"""FakeAI fixtures for N-window + adaptive hierarchy. Not the pastoral corpus."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from app.ai.errors import AIError
from app.ai.providers.base import ProviderResult
from app.ai.providers.fake import FakeAIEngine, FakeReply
from app.ai.retry import no_delay_policy
from app.source_analysis.consolidation_fixtures import keep_all_ops
from app.source_analysis.consolidation_models import (
    STAGE_CONSOLIDATION,
    ConsolidationInput,
    requires_exclusive_disposition,
)
from app.source_analysis.hybrid_e2e_fixtures import (
    CONSOLIDATION_AUDIENCE,
    CONSOLIDATION_INTENT,
    CONSOLIDATION_THEME,
    CONSOLIDATION_VOICE,
)
from app.source_analysis.window_fixtures import (
    make_transcript,
    mapped_minimal_engine,
    minimal_transport,
    window_for,
    window_plan_from_inputs,
)
from app.source_analysis.window_models import STAGE_WINDOW
from app.source_analysis_hybrid.contracts import WindowInput, WindowPlan
from app.source_analysis_hybrid.planner import plan_windows_v2
from app.source_analysis_hybrid.config import WindowPlannerConfig
from app.source_analysis_small_window_hierarchy.constants import (
    CANDIDATE_PLANNER_VERSION,
    REGIONAL_CONTRACT_VERSION,
    ROUTE_DIRECT_GLOBAL,
    ROUTE_REGIONAL_THEN_GLOBAL,
)
from app.source_analysis_post_canary_architecture.synthetic import (
    result_from_transport,
    transport_for_scenario,
)


SPARSE_SEVEN_SRC = (
    "SRC000001",
    "SRC000003",
    "SRC000010",
    "SRC000020",
    "SRC000050",
    "SRC000080",
    "SRC000100",
)


def n_window_transcript(
    count: int,
    *,
    sparse: bool = False,
    transcript_id: str = "TR-SW-N",
    content_sha256: str = "e" * 64,
):
    texts = tuple(
        f"Faith window {index} teaches how a trial is crossed."
        for index in range(1, count + 1)
    )
    if sparse and count <= len(SPARSE_SEVEN_SRC):
        src_ids = SPARSE_SEVEN_SRC[:count]
    else:
        src_ids = tuple(f"SRC{index:06d}" for index in range(1, count + 1))
    return make_transcript(
        texts,
        src_ids=src_ids,
        transcript_id=transcript_id,
        content_sha256=content_sha256,
    )


def n_window_plan(count: int, *, sparse: bool = False) -> tuple:
    transcript = n_window_transcript(count, sparse=sparse)
    windows = tuple(
        window_for(
            transcript,
            owned=(src,),
            window_id=f"WIN{index:03d}",
        )
        for index, src in enumerate(transcript.src_ids(), start=1)
    )
    # stamp candidate planner version without changing production defaults
    stamped = []
    for window in windows:
        from dataclasses import replace

        stamped.append(replace(window, planner_version=CANDIDATE_PLANNER_VERSION))
    plan = window_plan_from_inputs(transcript, tuple(stamped))
    from dataclasses import replace as _replace

    plan = _replace(plan, planner_version=CANDIDATE_PLANNER_VERSION)
    return transcript, plan


def seven_window_sparse_plan():
    return n_window_plan(7, sparse=True)


def synthetic_plan_via_algorithm(
    count: int,
    *,
    target: int = 80,
    hard_max: int = 120,
    weight: int = 40,
):
    """N emerges from algorithm — used to prove 7 is not hardcoded."""
    transcript = n_window_transcript(count)
    config = WindowPlannerConfig(
        version=CANDIDATE_PLANNER_VERSION,
        target_input_tokens=target,
        hard_max_input_tokens=hard_max,
    )
    weights = tuple(weight for _ in transcript.segments)
    plan = plan_windows_v2(
        transcript,
        config=config,
        content_weights=weights,
        overhead=0,
        remeasure=False,
    )
    return transcript, plan


def _gm_from_input(consolidation_input: ConsolidationInput) -> dict[str, Any]:
    records = list(consolidation_input.all_records())
    by_kind: dict[str, list[str]] = {}
    for record in records:
        by_kind.setdefault(record.kind, []).append(record.record_id)
    theme = (by_kind.get("TOPIC") or by_kind.get("IDEA") or [records[0].record_id])[:2]
    intent = (by_kind.get("INTENT_KIND") or by_kind.get("IDEA") or theme)[:2]
    audience = (by_kind.get("AUDIENCE_KIND") or by_kind.get("IDEA") or theme)[:2]
    voice = (by_kind.get("VOICE") or theme)[:2]
    return {
        "th": CONSOLIDATION_THEME,
        "in": CONSOLIDATION_INTENT,
        "au": CONSOLIDATION_AUDIENCE,
        "vo": CONSOLIDATION_VOICE,
        "te": theme,
        "ie": intent,
        "ae": audience,
        "ve": voice,
    }


def keep_all_transport(consolidation_input: ConsolidationInput) -> dict[str, Any]:
    ids = [record.record_id for record in consolidation_input.all_records()]
    return {"gm": _gm_from_input(consolidation_input), "ops": keep_all_ops(*ids)}


def omit_one_transport(consolidation_input: ConsolidationInput) -> dict[str, Any]:
    ids = [record.record_id for record in consolidation_input.all_records()]
    if not ids:
        return keep_all_transport(consolidation_input)
    return {"gm": _gm_from_input(consolidation_input), "ops": keep_all_ops(*ids[1:])}


def invalid_merge_member_transport(
    consolidation_input: ConsolidationInput,
) -> dict[str, Any]:
    ids = [record.record_id for record in consolidation_input.all_records()]
    ops = [
        {"o": "MERGE", "m": [ids[0], "WIN999:R9999"], "v": "invalid member"},
        *keep_all_ops(*ids[1:]),
    ]
    return {"gm": _gm_from_input(consolidation_input), "ops": ops}


def duplicate_accounting_transport(
    consolidation_input: ConsolidationInput,
) -> dict[str, Any]:
    ids = [record.record_id for record in consolidation_input.all_records()]
    ops = keep_all_ops(*ids)
    if ids:
        ops.append({"o": "KEEP", "r": ids[0]})
    return {"gm": _gm_from_input(consolidation_input), "ops": ops}


def oversized_compatible_transport(*, owned_src: str) -> dict[str, Any]:
    """
    Granularity-legal dense window. No RELATION rows so MERGE-by-kind
    remains reconstructable (no self-loop endpoints).
    """
    topic = "Faith during trials and adversity now."
    idea = ("Faith changes how a trial is crossed when the path is the lesson. " * 3)[:280]
    example = ("A man still prayed each morning before the work began. " * 3)[:200]
    reference = ("Paul says somewhere that weakness becomes strength. " * 3)[:220]
    uncertainty = ("The cited Pauline wording is not located in the source. " * 3)[:280]
    repetition = ("The crossing claim is restated then developed. " * 3)[:200]
    records: list[dict[str, Any]] = []
    for _ in range(14):
        records.append(
            {
                "k": "TOPIC",
                "v": topic[:80],
                "s": [owned_src],
                "l": [],
                "m": ["How trust is revealed when hardship does not lift."],
            }
        )
    for index in range(64):
        records.append(
            {
                "k": "IDEA",
                "v": idea,
                "s": [owned_src],
                "l": [0],
                "m": ["claim", "central" if index == 0 else "supporting"],
            }
        )
    for _ in range(18):
        records.append(
            {
                "k": "EXAMPLE",
                "v": example,
                "s": [owned_src],
                "l": [14],
                "m": ["anecdote"],
            }
        )
    for _ in range(14):
        records.append(
            {
                "k": "REFERENCE",
                "v": reference,
                "s": [owned_src],
                "l": [],
                "m": ["biblical", "vague", ""],
            }
        )
    for _ in range(16):
        records.append(
            {
                "k": "UNCERTAINTY",
                "v": uncertainty,
                "s": [owned_src],
                "l": [],
                "m": ["incomplete_reference", "medium"],
            }
        )
    for _ in range(10):
        records.append(
            {
                "k": "REPETITION",
                "v": repetition,
                "s": [owned_src],
                "l": [14, 15],
                "m": ["rhetorical"],
            }
        )
    records.append({"k": "VOICE", "v": "didactic oral teaching", "s": [], "l": [], "m": ["tone"]})
    records.append({"k": "INTENT_KIND", "v": "enseigner", "s": [], "l": [], "m": []})
    records.append({"k": "AUDIENCE_KIND", "v": "croyants", "s": [], "l": [], "m": []})
    return {
        "theme": "Faith during trials",
        "intent": "Teach what faith does in hardship.",
        "ic": "high",
        "aud": "Believers facing trials.",
        "ac": "medium",
        "records": records,
    }


def constructed_merge_same_kind_transport(
    consolidation_input: ConsolidationInput,
) -> dict[str, Any]:
    """
    FakeAI constructed reply: MERGE same-kind exclusive records.

    This is an AI fixture decision, not production Python equivalence.
    """
    groups: dict[tuple[str, tuple[str, ...]], list] = {}
    leftovers: list[str] = []
    for record in consolidation_input.all_records():
        if record.kind == "RELATION":
            leftovers.append(record.record_id)
        elif requires_exclusive_disposition(record.kind):
            key = (record.kind, tuple(record.metadata))
            groups.setdefault(key, []).append(record)
        else:
            leftovers.append(record.record_id)
    ops: list[dict[str, Any]] = []
    for (kind, _meta), members in groups.items():
        if len(members) >= 2:
            ops.append(
                {
                    "o": "MERGE",
                    "m": [item.record_id for item in members],
                    "v": members[0].value or f"Merged {kind} constructed by FakeAI",
                }
            )
        else:
            ops.append({"o": "KEEP", "r": members[0].record_id})
    ops.extend(keep_all_ops(*leftovers))
    return {"gm": _gm_from_input(consolidation_input), "ops": ops}


def scenario_results_for_plan(plan: WindowPlan, scenario: str):
    transport = transport_for_scenario(scenario)
    results = []
    for index, window in enumerate(plan.windows, start=1):
        signature = f"{index:064x}"[-64:]
        results.append(result_from_transport(window, transport, signature=signature))
    return results


class HierarchyMappedFakeAI(FakeAIEngine):
    """
    Sequential FakeAI: window_id, then regional group_id, then global.

    No parallel. Scripted failures are not replayed.
    """

    def __init__(
        self,
        window_replies: dict[str, FakeReply | BaseException] | None = None,
        *,
        regional_factory=None,
        global_factory=None,
        regional_replies: dict[str, FakeReply | BaseException] | None = None,
        global_reply: FakeReply | BaseException | None = None,
        model: str | None = None,
    ):
        super().__init__(
            script=[],
            retry_policy=no_delay_policy(max_attempts=1),
            model=model,
        )
        self._window_replies = dict(window_replies or {})
        self._regional_replies = dict(regional_replies or {})
        self._global_reply = global_reply
        self.regional_factory = regional_factory
        self.global_factory = global_factory
        self.window_calls = 0
        self.regional_calls = 0
        self.global_calls = 0
        self.pending_regional_group_id: str | None = None
        self.last_regional_inputs: dict[str, ConsolidationInput] = {}
        self.last_global_input: ConsolidationInput | None = None

    def _invoke(self, request, model):
        self.requests.append(request)
        metadata = request.metadata or {}
        stage = metadata.get("stage")
        window_id = metadata.get("window_id")
        group_id = metadata.get("regional_group_id") or self.pending_regional_group_id
        route = metadata.get("hierarchy_route")
        if group_id:
            self.pending_regional_group_id = None
            self.regional_calls += 1
            return self._regional_result(group_id, model)
        if stage == STAGE_CONSOLIDATION or (
            window_id is None and stage != STAGE_WINDOW
        ):
            self.global_calls += 1
            return self._global_result(model, route)
        if window_id not in self._window_replies:
            raise AIError(f"aucune réponse FakeAI pour {window_id!r}")
        self.window_calls += 1
        return self._as_result(self._window_replies[window_id], model)

    def bind_regional_input(self, group_id: str, payload: ConsolidationInput) -> None:
        self.last_regional_inputs[group_id] = payload

    def bind_global_input(self, payload: ConsolidationInput) -> None:
        self.last_global_input = payload

    def _regional_result(self, group_id: str, model: str):
        if group_id in self._regional_replies:
            return self._as_result(self._regional_replies[group_id], model)
        payload = self.last_regional_inputs.get(group_id)
        if payload is None or self.regional_factory is None:
            raise AIError(f"aucune réponse régionale FakeAI pour {group_id!r}")
        return self._as_result(FakeReply(parsed=self.regional_factory(payload)), model)

    def _global_result(self, model: str, route):
        del route
        if self._global_reply is not None:
            return self._as_result(self._global_reply, model)
        if self.last_global_input is None or self.global_factory is None:
            raise AIError("aucune réponse globale FakeAI")
        return self._as_result(
            FakeReply(parsed=self.global_factory(self.last_global_input)), model
        )

    def _as_result(self, scripted, model):
        if isinstance(scripted, BaseException):
            raise scripted
        text = scripted.text
        if scripted.parsed is not None:
            import json

            text = json.dumps(scripted.parsed, ensure_ascii=False)
        return ProviderResult(
            text=text,
            input_tokens=scripted.input_tokens,
            output_tokens=scripted.output_tokens,
            total_tokens=scripted.total_tokens,
            finish_reason=scripted.finish_reason,
            request_id=scripted.request_id,
            model=scripted.model or model,
            raw_usage=dict(scripted.raw_usage),
        )


def mapped_n_window_engine(plan: WindowPlan) -> HierarchyMappedFakeAI:
    replies = {
        window.window_id: FakeReply(
            parsed=minimal_transport(owned_src=window.owned_src_refs[0])
        )
        for window in plan.windows
    }
    return HierarchyMappedFakeAI(
        replies,
        regional_factory=keep_all_transport,
        global_factory=keep_all_transport,
    )


__all__ = [
    "HierarchyMappedFakeAI",
    "constructed_merge_same_kind_transport",
    "duplicate_accounting_transport",
    "invalid_merge_member_transport",
    "keep_all_transport",
    "mapped_n_window_engine",
    "n_window_plan",
    "omit_one_transport",
    "scenario_results_for_plan",
    "seven_window_sparse_plan",
    "synthetic_plan_via_algorithm",
]
