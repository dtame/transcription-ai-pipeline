"""
Signature de consolidation — identité déterministe 3B.7.4.

Ordre WindowPlan : les hashes de fenêtres ne sont PAS triés lexicalement.
Aucun timestamp, aucune latence, aucun request_id.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from app.file_utils import content_hash
from app.source_analysis.consolidation_models import (
    CONSOLIDATION_OUTPUT_LANGUAGE,
    STAGE_CONSOLIDATION,
    ConsolidationInput,
)
from app.source_analysis.consolidation_prompt import (
    CONSOLIDATION_ANALYSIS_PROMPT_VERSION,
)
from app.source_analysis_hybrid.constants import (
    CONSOLIDATION_TRANSPORT_VERSION,
)


@dataclass(frozen=True)
class ConsolidationSignatureInputs:
    consolidation_input_hash: str
    window_result_hashes: tuple[str, ...]
    window_analysis_signatures: tuple[str, ...]
    prompt_version: str
    prompt_sha256: str
    transport_version: str
    response_schema_sha256: str
    provider: str
    model: str
    temperature: float | None
    max_output_tokens: int | None
    output_language: str
    context_safety_ratio: float
    stage: str = STAGE_CONSOLIDATION

    def to_dict(self) -> dict:
        return {
            "consolidation_input_hash": self.consolidation_input_hash,
            "context_safety_ratio": self.context_safety_ratio,
            "max_output_tokens": self.max_output_tokens,
            "model": self.model,
            "output_language": self.output_language,
            "prompt_sha256": self.prompt_sha256,
            "prompt_version": self.prompt_version,
            "provider": self.provider,
            "response_schema_sha256": self.response_schema_sha256,
            "stage": self.stage,
            "temperature": self.temperature,
            "transport_version": self.transport_version,
            "window_analysis_signatures": list(self.window_analysis_signatures),
            "window_result_hashes": list(self.window_result_hashes),
        }


def build_consolidation_signature(inputs: ConsolidationSignatureInputs) -> str:
    payload = json.dumps(inputs.to_dict(), ensure_ascii=False, sort_keys=True)
    return content_hash(payload)


def signature_inputs_for(
    consolidation_input: ConsolidationInput,
    *,
    prompt_sha256: str,
    response_schema_sha256: str,
    provider: str,
    model: str,
    temperature: float | None,
    max_output_tokens: int | None,
    context_safety_ratio: float,
    output_language: str = CONSOLIDATION_OUTPUT_LANGUAGE,
) -> ConsolidationSignatureInputs:
    return ConsolidationSignatureInputs(
        consolidation_input_hash=consolidation_input.input_hash,
        window_result_hashes=consolidation_input.window_result_hashes_in_order(),
        window_analysis_signatures=consolidation_input.window_signatures_in_order(),
        prompt_version=CONSOLIDATION_ANALYSIS_PROMPT_VERSION,
        prompt_sha256=prompt_sha256,
        transport_version=CONSOLIDATION_TRANSPORT_VERSION,
        response_schema_sha256=response_schema_sha256,
        provider=provider,
        model=model,
        temperature=temperature,
        max_output_tokens=max_output_tokens,
        output_language=output_language,
        context_safety_ratio=float(context_safety_ratio),
    )


__all__ = [
    "ConsolidationSignatureInputs",
    "build_consolidation_signature",
    "signature_inputs_for",
]
