"""Adaptateur V3 transport résolu → WindowSemanticResult intermédiaire."""

from __future__ import annotations

from typing import Any, Mapping

from app.source_analysis.window_models import (
    WINDOW_RESULT_SCHEMA_VERSION,
    WindowCandidateMetadata,
    WindowProviderMetadata,
    WindowSemanticResult,
    assign_intermediate_records,
    compute_coverage,
    compute_record_stats,
)
from app.source_analysis_hybrid.contracts import WindowInput
from app.source_analysis_local_v2.constants import DEFERRED_KINDS
from app.source_analysis_local_v3.constants import (
    SEMANTIC_TRANSPORT_VERSION_V3,
    SEMANTIC_TRANSPORT_VERSION_V31_LOCAL_LITE,
    WINDOW_ANALYSIS_PROMPT_VERSION_V13,
    WINDOW_ANALYSIS_PROMPT_VERSION_V140,
)
from app.source_analysis_local_v3.resolver import reconstruction_records


def v3_transport_to_window_result(
    resolved: Mapping[str, Any],
    window: WindowInput,
    *,
    signature: str,
    provider_metadata: WindowProviderMetadata,
) -> WindowSemanticResult:
    """
    Intermédiaire local. Pas un SourceMap canonique.
    Les handles ne fuient pas dans les IDs canoniques.
    """
    records = assign_intermediate_records(
        reconstruction_records(resolved),
        window_id=window.window_id,
    )
    candidates = WindowCandidateMetadata(
        theme=str(resolved.get("theme") or ""),
        intent=str(resolved.get("intent") or ""),
        intent_confidence=str(resolved.get("ic") or ""),
        audience=str(resolved.get("aud") or ""),
        audience_confidence=str(resolved.get("ac") or ""),
        intent_kinds=(),
        audience_kinds=(),
    )
    return WindowSemanticResult(
        schema_version=WINDOW_RESULT_SCHEMA_VERSION,
        window_id=window.window_id,
        window_input_hash=window.input_hash,
        window_analysis_signature=signature,
        transport_version=SEMANTIC_TRANSPORT_VERSION_V3,
        prompt_version=WINDOW_ANALYSIS_PROMPT_VERSION_V13,
        planner_version=window.planner_version,
        owned_src_refs=window.owned_src_refs,
        context_src_refs=window.context_src_refs,
        candidates=candidates,
        records=records,
        coverage=compute_coverage(window, records),
        stats=compute_record_stats(records),
        provider_metadata=provider_metadata,
        voice_evidence={},
    )


def v31_transport_to_window_result(
    resolved: Mapping[str, Any],
    window: WindowInput,
    *,
    signature: str,
    provider_metadata: WindowProviderMetadata,
) -> WindowSemanticResult:
    records = assign_intermediate_records(
        reconstruction_records(resolved),
        window_id=window.window_id,
    )
    candidates = WindowCandidateMetadata(
        theme=str(resolved.get("theme") or ""),
        intent=str(resolved.get("intent") or ""),
        intent_confidence=str(resolved.get("ic") or ""),
        audience=str(resolved.get("aud") or ""),
        audience_confidence=str(resolved.get("ac") or ""),
        intent_kinds=(),
        audience_kinds=(),
    )
    return WindowSemanticResult(
        schema_version=WINDOW_RESULT_SCHEMA_VERSION,
        window_id=window.window_id,
        window_input_hash=window.input_hash,
        window_analysis_signature=signature,
        transport_version=SEMANTIC_TRANSPORT_VERSION_V31_LOCAL_LITE,
        prompt_version=WINDOW_ANALYSIS_PROMPT_VERSION_V140,
        planner_version=window.planner_version,
        owned_src_refs=window.owned_src_refs,
        context_src_refs=window.context_src_refs,
        candidates=candidates,
        records=records,
        coverage=compute_coverage(window, records),
        stats=compute_record_stats(records),
        provider_metadata=provider_metadata,
        voice_evidence={},
    )


def assert_no_deferred_records(result: WindowSemanticResult) -> None:
    bad = [record.kind for record in result.records if record.kind in DEFERRED_KINDS]
    if bad:
        raise ValueError(f"records différés dans résultat v3 : {bad}")
