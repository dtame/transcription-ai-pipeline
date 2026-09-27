"""Fixtures synthétiques de consolidation — pas le corpus pastoral."""

from __future__ import annotations

from app.ai.providers.fake import FakeAIEngine, FakeReply
from app.ai.retry import no_delay_policy
from app.source_analysis.consolidation_models import (
    CONSOLIDATION_RESULT_SCHEMA_VERSION,
    ConsolidationInput,
    ConsolidationProviderMetadata,
)
from app.source_analysis.orchestration_models import (
    CACHE_HIT,
    EXECUTION_GENERATED,
    EXECUTION_NONE,
    EXECUTION_ORDER_SEQUENTIAL,
    FAILURE_POLICY_STOP_ON_FIRST,
    READINESS_PENDING,
    READINESS_READY,
    WindowOrchestrationResult,
    WindowOrchestrationStatus,
)
from app.source_analysis.window_fixtures import (
    make_transcript,
    three_window_fixture,
    window_for,
    window_plan_from_inputs,
)
from app.source_analysis.window_models import (
    WINDOW_CANDIDATE_SCOPE,
    WindowCandidateMetadata,
    WindowCoverage,
    WindowIntermediateRecord,
    WindowProviderMetadata,
    WindowRecordStats,
    WindowSemanticResult,
    compute_coverage,
    compute_record_stats,
)
from app.source_analysis_hybrid.contracts import WindowInput, WindowPlan


def _record(
    record_id: str,
    kind: str,
    value: str,
    source_refs: tuple[str, ...] = (),
    *,
    index: int = 0,
    links: tuple[int, ...] = (),
    link_ids: tuple[str, ...] = (),
    metadata: tuple[str, ...] = (),
) -> WindowIntermediateRecord:
    return WindowIntermediateRecord(
        record_id=record_id,
        transport_index=index,
        kind=kind,
        value=value,
        source_refs=source_refs,
        links=links,
        link_record_ids=link_ids,
        metadata=metadata,
    )


def _candidates(
    *,
    theme: str = "Faith during trials",
    intent: str = "Teach believers to keep walking.",
    audience: str = "Believers facing hardship.",
) -> WindowCandidateMetadata:
    return WindowCandidateMetadata(
        theme=theme,
        intent=intent,
        intent_confidence="high",
        audience=audience,
        audience_confidence="medium",
        intent_kinds=("enseigner",),
        audience_kinds=("croyants",),
        scope=WINDOW_CANDIDATE_SCOPE,
    )


def make_window_result(
    window: WindowInput,
    records: tuple[WindowIntermediateRecord, ...],
    *,
    signature: str = "b" * 64,
    theme: str = "Faith during trials",
    intent: str = "Teach believers to keep walking.",
    audience: str = "Believers facing hardship.",
    voice_evidence: dict | None = None,
) -> WindowSemanticResult:
    return WindowSemanticResult(
        schema_version=CONSOLIDATION_RESULT_SCHEMA_VERSION,
        window_id=window.window_id,
        window_input_hash=window.input_hash,
        window_analysis_signature=signature,
        transport_version="semantic-transport-v1",
        prompt_version="window-analysis-1.0",
        planner_version=window.planner_version,
        owned_src_refs=window.owned_src_refs,
        context_src_refs=window.context_src_refs,
        candidates=_candidates(theme=theme, intent=intent, audience=audience),
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
        voice_evidence=voice_evidence or {"tone": ["didactic"]},
    )


def two_window_plan():
    transcript = make_transcript(
        (
            "Faith during trials changes the crossing.",
            "Using faith in adversity reveals trust.",
        )
    )
    windows = (
        window_for(transcript, owned=("SRC000001",), window_id="WIN001"),
        window_for(transcript, owned=("SRC000002",), window_id="WIN002"),
    )
    return transcript, window_plan_from_inputs(transcript, windows)


def three_window_plan():
    return three_window_fixture()


def win001_keep_records() -> tuple[WindowIntermediateRecord, ...]:
    return (
        _record("WIN001:R0001", "TOPIC", "Faith during trials", ("SRC000001",), index=0),
        _record(
            "WIN001:R0002",
            "IDEA",
            "Faith changes how a trial is crossed.",
            ("SRC000001",),
            index=1,
            metadata=("claim", "central"),
        ),
        _record("WIN001:R0003", "VOICE", "didactic", (), index=2, metadata=("tone",)),
        _record("WIN001:R0004", "INTENT_KIND", "enseigner", (), index=3),
        _record("WIN001:R0005", "AUDIENCE_KIND", "croyants", (), index=4),
    )


def win002_keep_records() -> tuple[WindowIntermediateRecord, ...]:
    return (
        _record(
            "WIN002:R0001",
            "TOPIC",
            "Using faith in adversity",
            ("SRC000002",),
            index=0,
        ),
        _record(
            "WIN002:R0002",
            "IDEA",
            "Trust is revealed only in hardship.",
            ("SRC000002",),
            index=1,
            metadata=("claim", "central"),
        ),
        _record(
            "WIN002:R0003",
            "EXAMPLE",
            "A man who still prayed each morning.",
            ("SRC000002",),
            index=2,
            metadata=("anecdote",),
        ),
        _record("WIN002:R0004", "VOICE", "oral accessible", (), index=3, metadata=("register",)),
        _record("WIN002:R0005", "INTENT_KIND", "encourager", (), index=4),
        _record("WIN002:R0006", "AUDIENCE_KIND", "croyants", (), index=5),
    )


def win003_keep_records() -> tuple[WindowIntermediateRecord, ...]:
    return (
        _record(
            "WIN003:R0001",
            "IDEA",
            "Keep walking through the valley.",
            ("SRC000003",),
            index=0,
            metadata=("instruction", "central"),
        ),
        _record(
            "WIN003:R0002",
            "REPETITION",
            "The crossing claim returns as a recap.",
            ("SRC000003",),
            index=1,
            metadata=("recap",),
        ),
        _record("WIN003:R0003", "VOICE", "direct address", (), index=2, metadata=("tone",)),
        _record("WIN003:R0004", "INTENT_KIND", "enseigner", (), index=3),
        _record("WIN003:R0005", "AUDIENCE_KIND", "croyants", (), index=4),
    )


def ready_results_two() -> tuple:
    transcript, plan = two_window_plan()
    results = (
        make_window_result(plan.windows[0], win001_keep_records(), signature="1" * 64),
        make_window_result(plan.windows[1], win002_keep_records(), signature="2" * 64),
    )
    return transcript, plan, results


def ready_results_three() -> tuple:
    transcript, plan = three_window_plan()
    results = (
        make_window_result(plan.windows[0], win001_keep_records(), signature="1" * 64),
        make_window_result(plan.windows[1], win002_keep_records(), signature="2" * 64),
        make_window_result(plan.windows[2], win003_keep_records(), signature="3" * 64),
    )
    return transcript, plan, results


def make_orchestration(
    plan: WindowPlan,
    results: tuple[WindowSemanticResult, ...],
    *,
    all_ready: bool | None = None,
) -> WindowOrchestrationResult:
    ready = results if all_ready is not False and len(results) == plan.window_count else results
    all_windows_ready = (
        all_ready
        if all_ready is not None
        else len(results) == plan.window_count
    )
    statuses = []
    result_by_id = {item.window_id: item for item in results}
    for window in plan.windows:
        item = result_by_id.get(window.window_id)
        if item is None:
            statuses.append(
                WindowOrchestrationStatus(
                    window_id=window.window_id,
                    expected_signature="",
                    cache_state="MISS",
                    execution_kind=EXECUTION_NONE,
                    execution_attempted=False,
                    call_consumed=False,
                    transport_present=False,
                    transport_recovered=False,
                    result_valid=False,
                    readiness=READINESS_PENDING,
                )
            )
            continue
        statuses.append(
            WindowOrchestrationStatus(
                window_id=window.window_id,
                expected_signature=item.window_analysis_signature,
                cache_state=CACHE_HIT,
                execution_kind=EXECUTION_GENERATED,
                execution_attempted=True,
                call_consumed=True,
                transport_present=True,
                transport_recovered=False,
                result_valid=True,
                readiness=READINESS_READY,
            )
        )
    ready_tuple = results if all_windows_ready else ()
    if all_windows_ready:
        ordered = []
        for window in plan.windows:
            ordered.append(result_by_id[window.window_id])
        ready_tuple = tuple(ordered)
    return WindowOrchestrationResult(
        plan_sha256=plan.plan_sha256(),
        planner_version=plan.planner_version,
        transcript_id=plan.transcript_id,
        total_windows=plan.window_count,
        ready_windows=len(ready_tuple) if all_windows_ready else len(results),
        generated_windows=len(results),
        cache_hit_windows=0,
        transport_recovered_windows=0,
        failed_windows=0,
        pending_windows=plan.window_count - len(results),
        all_windows_ready=all_windows_ready,
        new_calls_consumed=len(results),
        max_new_calls=None,
        execution_order=EXECUTION_ORDER_SEQUENTIAL,
        failure_policy=FAILURE_POLICY_STOP_ON_FIRST,
        statuses=tuple(statuses),
        ready_results=ready_tuple if all_windows_ready else (),
        fake_ai_calls=len(results),
    )


def _gm(
    *,
    theme_ev: list[str],
    intent_ev: list[str],
    audience_ev: list[str],
    voice_ev: list[str],
    theme: str = "Faith during trials",
    intent: str = "Teach believers to keep walking through hardship.",
    audience: str = "Believers facing adversity.",
    voice: str = "Didactic oral teaching, direct address.",
) -> dict:
    return {
        "th": theme,
        "in": intent,
        "au": audience,
        "vo": voice,
        "te": theme_ev,
        "ie": intent_ev,
        "ae": audience_ev,
        "ve": voice_ev,
    }


def keep_all_ops(*record_ids: str) -> list[dict]:
    return [{"o": "KEEP", "r": record_id} for record_id in record_ids]


def two_window_ids() -> tuple[str, ...]:
    return (
        "WIN001:R0001",
        "WIN001:R0002",
        "WIN002:R0001",
        "WIN002:R0002",
        "WIN002:R0003",
    )


def three_window_ids() -> tuple[str, ...]:
    return two_window_ids() + ("WIN003:R0001", "WIN003:R0002")


def evidence_two() -> dict:
    return _gm(
        theme_ev=["WIN001:R0001", "WIN002:R0001"],
        intent_ev=["WIN001:R0004", "WIN002:R0005"],
        audience_ev=["WIN001:R0005", "WIN002:R0006"],
        voice_ev=["WIN001:R0003", "WIN002:R0004"],
    )


def evidence_three() -> dict:
    return _gm(
        theme_ev=["WIN001:R0001", "WIN002:R0001"],
        intent_ev=["WIN001:R0004", "WIN002:R0005", "WIN003:R0004"],
        audience_ev=["WIN001:R0005", "WIN002:R0006", "WIN003:R0005"],
        voice_ev=["WIN001:R0003", "WIN002:R0004", "WIN003:R0003"],
    )


def keep_two_window_transport() -> dict:
    return {
        "gm": evidence_two(),
        "ops": keep_all_ops(*two_window_ids()),
    }


def merge_topics_transport() -> dict:
    return {
        "gm": evidence_two(),
        "ops": [
            {
                "o": "MERGE",
                "m": ["WIN001:R0001", "WIN002:R0001"],
                "v": "Faith during trials and adversity",
            },
            {"o": "KEEP", "r": "WIN001:R0002"},
            {"o": "KEEP", "r": "WIN002:R0002"},
            {"o": "KEEP", "r": "WIN002:R0003"},
        ],
    }


def non_merge_transport() -> dict:
    return keep_two_window_transport()


def cross_window_relation_transport() -> dict:
    return {
        "gm": evidence_three(),
        "ops": keep_all_ops(*three_window_ids())
        + [
            {
                "o": "REL",
                "t": "supports",
                "a": "WIN001:R0002",
                "b": "WIN003:R0001",
            }
        ],
    }


def example_cross_window_transport() -> dict:
    return {
        "gm": evidence_two(),
        "ops": keep_all_ops(*two_window_ids())
        + [
            {
                "o": "REL",
                "t": "illustrates",
                "a": "WIN002:R0003",
                "b": "WIN001:R0002",
            }
        ],
    }


def global_repetition_transport() -> dict:
    return {
        "gm": evidence_three(),
        "ops": keep_all_ops(*three_window_ids())
        + [
            {
                "o": "REP",
                "c": "rhetorical",
                "m": ["WIN001:R0002", "WIN003:R0001"],
                "v": "The walking claim returns.",
            }
        ],
    }


def global_metadata_transport() -> dict:
    return cross_window_relation_transport()


def unknown_record_transport() -> dict:
    payload = keep_two_window_transport()
    payload["ops"].append({"o": "KEEP", "r": "WIN999:R9999"})
    return payload


def incompatible_merge_transport() -> dict:
    return {
        "gm": evidence_two(),
        "ops": [
            {
                "o": "MERGE",
                "m": ["WIN001:R0001", "WIN001:R0002"],
                "v": "Illegal topic+idea merge",
            },
            {"o": "KEEP", "r": "WIN002:R0001"},
            {"o": "KEEP", "r": "WIN002:R0002"},
            {"o": "KEEP", "r": "WIN002:R0003"},
        ],
    }


def singleton_merge_transport() -> dict:
    return {
        "gm": evidence_two(),
        "ops": [
            {"o": "MERGE", "m": ["WIN001:R0001"], "v": "singleton"},
            {"o": "KEEP", "r": "WIN001:R0002"},
            {"o": "KEEP", "r": "WIN002:R0001"},
            {"o": "KEEP", "r": "WIN002:R0002"},
            {"o": "KEEP", "r": "WIN002:R0003"},
        ],
    }


def duplicate_disposition_transport() -> dict:
    payload = merge_topics_transport()
    payload["ops"].append({"o": "KEEP", "r": "WIN001:R0001"})
    return payload


def unaccounted_transport() -> dict:
    return {
        "gm": evidence_two(),
        "ops": [
            {"o": "KEEP", "r": "WIN001:R0001"},
            {"o": "KEEP", "r": "WIN001:R0002"},
            {"o": "KEEP", "r": "WIN002:R0002"},
            {"o": "KEEP", "r": "WIN002:R0003"},
        ],
    }


def drop_transport() -> dict:
    payload = keep_two_window_transport()
    payload["ops"].append({"o": "DROP", "r": "WIN002:R0002"})
    return payload


def invalid_relation_type_transport() -> dict:
    payload = keep_two_window_transport()
    payload["ops"].append(
        {"o": "REL", "t": "implies", "a": "WIN001:R0002", "b": "WIN002:R0002"}
    )
    return payload


def invalid_repetition_type_transport() -> dict:
    payload = keep_two_window_transport()
    payload["ops"].append(
        {
            "o": "REP",
            "c": "echo",
            "m": ["WIN001:R0002", "WIN002:R0002"],
        }
    )
    return payload


def invalid_metadata_evidence_transport() -> dict:
    payload = keep_two_window_transport()
    payload["gm"]["te"] = ["WIN999:R9999"]
    return payload


def unsupported_synthesis_transport() -> dict:
    return {
        "gm": evidence_two(),
        "ops": [
            {"o": "MERGE", "m": [], "v": "no members"},
            {"o": "KEEP", "r": "WIN001:R0001"},
            {"o": "KEEP", "r": "WIN001:R0002"},
            {"o": "KEEP", "r": "WIN002:R0001"},
            {"o": "KEEP", "r": "WIN002:R0002"},
            {"o": "KEEP", "r": "WIN002:R0003"},
        ],
    }


def editorial_leak_transport() -> dict:
    payload = keep_two_window_transport()
    payload["chapters"] = [{"title": "Chapter 1"}]
    return payload


def forward_ref_transport() -> dict:
    payload = keep_two_window_transport()
    payload["ops"].append(
        {"o": "REL", "t": "supports", "a": "C0009", "b": "WIN002:R0002"}
    )
    return payload


def duplicate_merge_member_transport() -> dict:
    return {
        "gm": evidence_two(),
        "ops": [
            {
                "o": "MERGE",
                "m": ["WIN001:R0001", "WIN001:R0001"],
                "v": "duplicate member",
            },
            {"o": "KEEP", "r": "WIN001:R0002"},
            {"o": "KEEP", "r": "WIN002:R0001"},
            {"o": "KEEP", "r": "WIN002:R0002"},
            {"o": "KEEP", "r": "WIN002:R0003"},
        ],
    }


def multiple_merge_membership_transport() -> dict:
    return {
        "gm": evidence_two(),
        "ops": [
            {
                "o": "MERGE",
                "m": ["WIN001:R0001", "WIN002:R0001"],
                "v": "first merge",
            },
            {
                "o": "MERGE",
                "m": ["WIN001:R0001", "WIN002:R0002"],
                "v": "second merge of same record",
            },
            {"o": "KEEP", "r": "WIN001:R0002"},
            {"o": "KEEP", "r": "WIN002:R0003"},
        ],
    }


def fake_engine(transport: dict) -> FakeAIEngine:
    return FakeAIEngine(
        script=[FakeReply(parsed=transport)],
        retry_policy=no_delay_policy(max_attempts=1),
    )


def default_provider_metadata() -> ConsolidationProviderMetadata:
    return ConsolidationProviderMetadata(
        provider="fake",
        model="fake-model",
        input_tokens=8,
        output_tokens=8,
        total_tokens=16,
        usage_source="provider",
        finish_reason="stop",
    )


__all__ = [
    "cross_window_relation_transport",
    "default_provider_metadata",
    "drop_transport",
    "duplicate_disposition_transport",
    "duplicate_merge_member_transport",
    "editorial_leak_transport",
    "example_cross_window_transport",
    "fake_engine",
    "forward_ref_transport",
    "global_metadata_transport",
    "global_repetition_transport",
    "incompatible_merge_transport",
    "invalid_metadata_evidence_transport",
    "invalid_relation_type_transport",
    "invalid_repetition_type_transport",
    "keep_two_window_transport",
    "make_orchestration",
    "make_window_result",
    "merge_topics_transport",
    "multiple_merge_membership_transport",
    "non_merge_transport",
    "ready_results_three",
    "ready_results_two",
    "singleton_merge_transport",
    "three_window_plan",
    "two_window_plan",
    "unaccounted_transport",
    "unknown_record_transport",
    "unsupported_synthesis_transport",
]
