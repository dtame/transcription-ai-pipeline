"""Adaptateur V2 transport validé → WindowSemanticResult intermédiaire."""

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
from app.source_analysis_local_v2.constants import (
    SEMANTIC_TRANSPORT_VERSION_V2,
    WINDOW_ANALYSIS_PROMPT_VERSION_V121,
)


def v2_transport_to_window_result(
    transport: Mapping[str, Any],
    window: WindowInput,
    *,
    signature: str,
    provider_metadata: WindowProviderMetadata,
) -> WindowSemanticResult:
    """
    Intermédiaire local. Pas un SourceMap canonique.
    N'invente pas REPETITION / VOICE / INTENT_KIND / AUDIENCE_KIND.
    """
    records_in = transport.get("records") or []
    if not isinstance(records_in, list):
        records_in = []
    records = assign_intermediate_records(records_in, window_id=window.window_id)
    candidates = WindowCandidateMetadata(
        theme=str(transport.get("theme") or ""),
        intent=str(transport.get("intent") or ""),
        intent_confidence=str(transport.get("ic") or ""),
        audience=str(transport.get("aud") or ""),
        audience_confidence=str(transport.get("ac") or ""),
        intent_kinds=(),
        audience_kinds=(),
    )
    return WindowSemanticResult(
        schema_version=WINDOW_RESULT_SCHEMA_VERSION,
        window_id=window.window_id,
        window_input_hash=window.input_hash,
        window_analysis_signature=signature,
        transport_version=SEMANTIC_TRANSPORT_VERSION_V2,
        prompt_version=WINDOW_ANALYSIS_PROMPT_VERSION_V121,
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
    from app.source_analysis_local_v2.constants import DEFERRED_KINDS

    bad = [record.kind for record in result.records if record.kind in DEFERRED_KINDS]
    if bad:
        raise ValueError(f"records différés dans résultat v2 : {bad}")
