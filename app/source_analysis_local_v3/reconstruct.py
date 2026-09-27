"""Reconstruction canonique depuis fenêtres V3 + consolidation + recovery."""

from __future__ import annotations

from typing import Sequence

from app.source_analysis.consolidation_models import (
    ConsolidationInput,
    ConsolidationSemanticResult,
)
from app.source_analysis.consolidation_prompt import (
    build_consolidation_system_prompt,
    build_consolidation_user_prompt,
    consolidation_prompt_fingerprint,
)
from app.source_analysis.consolidation_schema import consolidation_schema_fingerprint
from app.source_analysis.consolidation_validator import validate_consolidation_result
from app.source_analysis.errors import HybridPreconditionError, SourceMapEditorialLeakError
from app.source_analysis.hybrid_reconstructor import (
    _assert_canonical_ids,
    _record_table,
    build_raw_canonical_candidate,
)
from app.source_analysis.hybrid_signature import (
    HYBRID_STRATEGY,
    build_hybrid_signature,
    hybrid_signature_inputs_for,
)
from app.source_analysis.models import (
    SOURCE_MAP_SCHEMA_VERSION,
    AnalysisProvenance,
    SourceMap,
    forbidden_editorial_fields,
)
from app.source_analysis.normalizer import normalize_source_map
from app.source_analysis.transcript_input import TranscriptInput
from app.source_analysis.validator import ensure_valid_source_map
from app.source_analysis.window_models import WindowSemanticResult
from app.source_analysis_hybrid.constants import CONSOLIDATION_PROMPT_VERSION
from app.source_analysis_hybrid.contracts import WindowPlan
from app.source_analysis_local_v2.recovery import (
    GlobalRecoveryPayload,
    apply_recovery_to_raw,
)
from app.source_analysis_local_v3.consolidation import (
    build_v3_consolidation_input,
    build_v31_consolidation_input,
)
from app.source_analysis_local_v3.constants import (
    IDEA_METADATA_LAYOUT_LOCAL_LITE,
    WINDOW_ANALYSIS_PROMPT_VERSION_V13,
    WINDOW_ANALYSIS_PROMPT_VERSION_V140,
)
from app.source_analysis_local_v3.prompt import (
    build_window_system_prompt_v13,
    build_window_system_prompt_v140,
    build_window_user_prompt_v13,
    build_window_user_prompt_v140,
    window_prompt_v13_fingerprint,
    window_prompt_v140_fingerprint,
)
from app.source_analysis_local_v3.schema import (
    semantic_transport_v3_fingerprint,
    semantic_transport_v31_local_lite_fingerprint,
)


def reconstruct_source_map_from_v3(
    transcript: TranscriptInput,
    window_plan: WindowPlan,
    window_results: Sequence[WindowSemanticResult],
    consolidation_result: ConsolidationSemanticResult,
    recovery: GlobalRecoveryPayload,
    *,
    consolidation_input: ConsolidationInput | None = None,
    enforce_budget: bool = True,
) -> SourceMap:
    rebuilt = build_v3_consolidation_input(
        window_plan, window_results, enforce_budget=enforce_budget
    )
    if consolidation_input is not None and consolidation_input.input_hash != rebuilt.input_hash:
        raise HybridPreconditionError(
            "ConsolidationInput fourni ≠ fenêtres V3 courantes"
        )
    if consolidation_result.input_hash != rebuilt.input_hash:
        raise HybridPreconditionError(
            "ConsolidationSemanticResult.input_hash ≠ ConsolidationInput V3"
        )
    validate_consolidation_result(consolidation_result, rebuilt)
    raw = build_raw_canonical_candidate(
        transcript, tuple(window_results), consolidation_result
    )
    table = _record_table(window_results)
    raw = apply_recovery_to_raw(raw, recovery, table)
    leaked = forbidden_editorial_fields(raw)
    if leaked:
        raise SourceMapEditorialLeakError(leaked, location="v3 raw canonical")
    first = window_plan.windows[0]
    system = build_window_system_prompt_v13(transcript.primary_language)
    user = build_window_user_prompt_v13(transcript, first)
    cons_system = build_consolidation_system_prompt("en")
    cons_user = build_consolidation_user_prompt(rebuilt)
    inputs = hybrid_signature_inputs_for(
        transcript,
        window_plan,
        rebuilt,
        consolidation_result,
        window_prompt_sha256=window_prompt_v13_fingerprint(system, user),
        window_schema_sha256=semantic_transport_v3_fingerprint(),
        consolidation_prompt_sha256=consolidation_prompt_fingerprint(
            cons_system, cons_user
        ),
        consolidation_schema_sha256=consolidation_schema_fingerprint(),
        window_provider=window_results[0].provider_metadata.provider,
        window_model=window_results[0].provider_metadata.model,
        window_max_output_tokens=None,
        consolidation_provider=consolidation_result.provider_metadata.provider,
        consolidation_model=consolidation_result.provider_metadata.model,
        consolidation_max_output_tokens=None,
        window_prompt_version=WINDOW_ANALYSIS_PROMPT_VERSION_V13,
    )
    provenance = AnalysisProvenance(
        prompt_version=f"{WINDOW_ANALYSIS_PROMPT_VERSION_V13}+{CONSOLIDATION_PROMPT_VERSION}+{recovery.version}",
        schema_version=SOURCE_MAP_SCHEMA_VERSION,
        provider=consolidation_result.provider_metadata.provider,
        model=consolidation_result.provider_metadata.model,
        strategy=HYBRID_STRATEGY,
        signature=build_hybrid_signature(inputs),
    )
    source_map = normalize_source_map(raw, transcript, provenance=provenance)
    ensure_valid_source_map(source_map, transcript)
    _assert_canonical_ids(source_map)
    return source_map


def reconstruct_source_map_from_v31(
    transcript: TranscriptInput,
    window_plan: WindowPlan,
    window_results: Sequence[WindowSemanticResult],
    consolidation_result: ConsolidationSemanticResult,
    recovery: GlobalRecoveryPayload,
    *,
    consolidation_input: ConsolidationInput | None = None,
    enforce_budget: bool = True,
) -> SourceMap:
    rebuilt = build_v31_consolidation_input(
        window_plan, window_results, enforce_budget=enforce_budget
    )
    if consolidation_input is not None and consolidation_input.input_hash != rebuilt.input_hash:
        raise HybridPreconditionError(
            "ConsolidationInput fourni ≠ fenêtres V3.1 local-lite courantes"
        )
    if consolidation_result.input_hash != rebuilt.input_hash:
        raise HybridPreconditionError(
            "ConsolidationSemanticResult.input_hash ≠ ConsolidationInput V3.1"
        )
    validate_consolidation_result(consolidation_result, rebuilt)
    raw = build_raw_canonical_candidate(
        transcript,
        tuple(window_results),
        consolidation_result,
        idea_metadata_layout=IDEA_METADATA_LAYOUT_LOCAL_LITE,
    )
    table = _record_table(window_results)
    raw = apply_recovery_to_raw(raw, recovery, table)
    leaked = forbidden_editorial_fields(raw)
    if leaked:
        raise SourceMapEditorialLeakError(leaked, location="v3.1 local-lite raw canonical")
    first = window_plan.windows[0]
    system = build_window_system_prompt_v140(transcript.primary_language)
    user = build_window_user_prompt_v140(transcript, first)
    cons_system = build_consolidation_system_prompt("en")
    cons_user = build_consolidation_user_prompt(rebuilt)
    inputs = hybrid_signature_inputs_for(
        transcript,
        window_plan,
        rebuilt,
        consolidation_result,
        window_prompt_sha256=window_prompt_v140_fingerprint(system, user),
        window_schema_sha256=semantic_transport_v31_local_lite_fingerprint(),
        consolidation_prompt_sha256=consolidation_prompt_fingerprint(
            cons_system, cons_user
        ),
        consolidation_schema_sha256=consolidation_schema_fingerprint(),
        window_provider=window_results[0].provider_metadata.provider,
        window_model=window_results[0].provider_metadata.model,
        window_max_output_tokens=None,
        consolidation_provider=consolidation_result.provider_metadata.provider,
        consolidation_model=consolidation_result.provider_metadata.model,
        consolidation_max_output_tokens=None,
        window_prompt_version=WINDOW_ANALYSIS_PROMPT_VERSION_V140,
    )
    provenance = AnalysisProvenance(
        prompt_version=(
            f"{WINDOW_ANALYSIS_PROMPT_VERSION_V140}+"
            f"{CONSOLIDATION_PROMPT_VERSION}+{recovery.version}"
        ),
        schema_version=SOURCE_MAP_SCHEMA_VERSION,
        provider=consolidation_result.provider_metadata.provider,
        model=consolidation_result.provider_metadata.model,
        strategy=HYBRID_STRATEGY,
        signature=build_hybrid_signature(inputs),
    )
    source_map = normalize_source_map(raw, transcript, provenance=provenance)
    ensure_valid_source_map(source_map, transcript)
    _assert_canonical_ids(source_map)
    return source_map
