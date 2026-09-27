"""
Signature hybride finale — identité déterministe 3B.7.5.

Composée des identités transcript / plan / fenêtres / consolidation /
prompts / transports / schéma canonique. Aucun timestamp, aucune
latence, aucun request_id, aucun mtime.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Sequence

from app.file_utils import content_hash
from app.source_analysis.consolidation_models import (
    ConsolidationInput,
    ConsolidationSemanticResult,
)
from app.source_analysis.models import SOURCE_MAP_SCHEMA_VERSION
from app.source_analysis.transcript_input import TranscriptInput
from app.source_analysis.window_prompt import WINDOW_ANALYSIS_PROMPT_VERSION
from app.source_analysis_hybrid.constants import (
    CONSOLIDATION_PROMPT_VERSION,
    CONSOLIDATION_TRANSPORT_VERSION,
    PLANNER_VERSION,
    WINDOW_PROMPT_VERSION,
    WINDOW_TRANSPORT_VERSION,
)
from app.source_analysis_hybrid.contracts import WindowPlan

RECONSTRUCTOR_VERSION = "hybrid-canonical-reconstructor-1.0"
HYBRID_STRATEGY = "hybrid_window_plus_global_consolidation"
HYBRID_PROMPT_VERSION = (
    f"{WINDOW_ANALYSIS_PROMPT_VERSION}+{CONSOLIDATION_PROMPT_VERSION}"
)
HISTORICAL_HYBRID_PROMPT_VERSION = (
    f"{WINDOW_PROMPT_VERSION}+{CONSOLIDATION_PROMPT_VERSION}"
)
NORMALIZER_IDENTITY = "normalize_source_map"


@dataclass(frozen=True)
class HybridSignatureInputs:
    transcript_id: str
    transcript_sha256: str
    plan_sha256: str
    planner_version: str
    window_result_hashes: tuple[str, ...]
    window_analysis_signatures: tuple[str, ...]
    consolidation_input_hash: str
    consolidation_result_sha256: str
    consolidation_signature: str
    window_prompt_version: str
    window_prompt_sha256: str
    window_transport_version: str
    window_schema_sha256: str
    consolidation_prompt_version: str
    consolidation_prompt_sha256: str
    consolidation_transport_version: str
    consolidation_schema_sha256: str
    window_provider: str
    window_model: str
    window_max_output_tokens: int | None
    consolidation_provider: str
    consolidation_model: str
    consolidation_max_output_tokens: int | None
    canonical_schema_version: str
    reconstructor_version: str
    normalizer: str
    hybrid_strategy: str

    def to_dict(self) -> dict:
        return {
            "canonical_schema_version": self.canonical_schema_version,
            "consolidation_input_hash": self.consolidation_input_hash,
            "consolidation_max_output_tokens": self.consolidation_max_output_tokens,
            "consolidation_model": self.consolidation_model,
            "consolidation_prompt_sha256": self.consolidation_prompt_sha256,
            "consolidation_prompt_version": self.consolidation_prompt_version,
            "consolidation_provider": self.consolidation_provider,
            "consolidation_result_sha256": self.consolidation_result_sha256,
            "consolidation_schema_sha256": self.consolidation_schema_sha256,
            "consolidation_signature": self.consolidation_signature,
            "consolidation_transport_version": self.consolidation_transport_version,
            "hybrid_strategy": self.hybrid_strategy,
            "normalizer": self.normalizer,
            "plan_sha256": self.plan_sha256,
            "planner_version": self.planner_version,
            "reconstructor_version": self.reconstructor_version,
            "transcript_id": self.transcript_id,
            "transcript_sha256": self.transcript_sha256,
            "window_analysis_signatures": list(self.window_analysis_signatures),
            "window_max_output_tokens": self.window_max_output_tokens,
            "window_model": self.window_model,
            "window_prompt_sha256": self.window_prompt_sha256,
            "window_prompt_version": self.window_prompt_version,
            "window_provider": self.window_provider,
            "window_result_hashes": list(self.window_result_hashes),
            "window_schema_sha256": self.window_schema_sha256,
            "window_transport_version": self.window_transport_version,
        }


def build_hybrid_signature(inputs: HybridSignatureInputs) -> str:
    payload = json.dumps(inputs.to_dict(), ensure_ascii=False, sort_keys=True)
    return content_hash(payload)


def hybrid_signature_inputs_for(
    transcript: TranscriptInput,
    plan: WindowPlan,
    consolidation_input: ConsolidationInput,
    consolidation_result: ConsolidationSemanticResult,
    *,
    window_prompt_sha256: str,
    window_schema_sha256: str,
    consolidation_prompt_sha256: str,
    consolidation_schema_sha256: str,
    window_provider: str,
    window_model: str,
    window_max_output_tokens: int | None,
    consolidation_provider: str,
    consolidation_model: str,
    consolidation_max_output_tokens: int | None,
    window_prompt_version: str | None = None,
) -> HybridSignatureInputs:
    chosen_window_prompt = window_prompt_version or WINDOW_ANALYSIS_PROMPT_VERSION
    return HybridSignatureInputs(
        transcript_id=transcript.transcript_id,
        transcript_sha256=transcript.content_sha256,
        plan_sha256=plan.plan_sha256(),
        planner_version=plan.planner_version or PLANNER_VERSION,
        window_result_hashes=consolidation_input.window_result_hashes_in_order(),
        window_analysis_signatures=consolidation_input.window_signatures_in_order(),
        consolidation_input_hash=consolidation_input.input_hash,
        consolidation_result_sha256=consolidation_result.result_sha256(),
        consolidation_signature=consolidation_result.consolidation_signature,
        window_prompt_version=chosen_window_prompt,
        window_prompt_sha256=window_prompt_sha256,
        window_transport_version=WINDOW_TRANSPORT_VERSION,
        window_schema_sha256=window_schema_sha256,
        consolidation_prompt_version=CONSOLIDATION_PROMPT_VERSION,
        consolidation_prompt_sha256=consolidation_prompt_sha256,
        consolidation_transport_version=CONSOLIDATION_TRANSPORT_VERSION,
        consolidation_schema_sha256=consolidation_schema_sha256,
        window_provider=window_provider,
        window_model=window_model,
        window_max_output_tokens=window_max_output_tokens,
        consolidation_provider=consolidation_provider,
        consolidation_model=consolidation_model,
        consolidation_max_output_tokens=consolidation_max_output_tokens,
        canonical_schema_version=SOURCE_MAP_SCHEMA_VERSION,
        reconstructor_version=RECONSTRUCTOR_VERSION,
        normalizer=NORMALIZER_IDENTITY,
        hybrid_strategy=HYBRID_STRATEGY,
    )


def window_hashes_in_plan_order(
    plan: WindowPlan,
    results: Sequence,
) -> tuple[str, ...]:
    by_id = {result.window_id: result for result in results}
    return tuple(by_id[window.window_id].result_sha256() for window in plan.windows)


def window_signatures_in_plan_order(
    plan: WindowPlan,
    results: Sequence,
) -> tuple[str, ...]:
    by_id = {result.window_id: result for result in results}
    return tuple(
        by_id[window.window_id].window_analysis_signature for window in plan.windows
    )


__all__ = [
    "HYBRID_PROMPT_VERSION",
    "HYBRID_STRATEGY",
    "NORMALIZER_IDENTITY",
    "RECONSTRUCTOR_VERSION",
    "HybridSignatureInputs",
    "build_hybrid_signature",
    "hybrid_signature_inputs_for",
    "window_hashes_in_plan_order",
    "window_signatures_in_plan_order",
]
