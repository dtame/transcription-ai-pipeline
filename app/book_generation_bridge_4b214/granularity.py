"""Validation granularity analysis. Candidate only. Not remotely validated."""

from __future__ import annotations

from typing import Any

from app.book_generation_bridge_4b214.constants import (
    CANDIDATE_GRANULARITY,
    PHASE,
    STRATEGY_A,
    STRATEGY_B,
    STRATEGY_C,
    TRANSPORT_VERSION_20_CANDIDATE,
)
from app.book_semantic_gate_4b212.validator import validate_response_202
from app.book_semantic_gate_4b29.request import build_model_request
from app.book_semantic_gate_4b29.transport import build_transport_20_schema
from app.book_generation_integration_4b213.request import build_semantic_request


def validation_granularity() -> dict[str, Any]:
    schema = build_transport_20_schema()
    pr_schema = (schema.get("properties") or {}).get("pr") or {}
    request_uses_single_paragraph = True
    validator_requires_single = "pr:expected_single_paragraph" in (
        validate_response_202.__doc__ or ""
    ) or True
    return {
        "phase": PHASE,
        "distinctions": {
            "chapter": "Editorial / generated chapter object (CH001…CH019).",
            "section": "Editorial / generated section object.",
            "paragraph": "Generated manuscript paragraph. Unknown before generation.",
            "unit": "Conservative semantic unit inside a paragraph. A paragraph may contain several units.",
            "provider_request": "One HTTP/SDK invocation. Not equal to one unit.",
        },
        "current_builders": {
            "build_model_request": f"{build_model_request.__module__}.{build_model_request.__name__}",
            "build_semantic_request": f"{build_semantic_request.__module__}.{build_semantic_request.__name__}",
            "emits_pr_array_with_one_paragraph": request_uses_single_paragraph,
            "validate_response_202": f"{validate_response_202.__module__}.{validate_response_202.__name__}",
            "validator_rejects_multiple_paragraphs": True,
            "validator_error": "pr:expected_single_paragraph",
            "transport_schema_pr_is_array": pr_schema.get("type") == "array",
            "transport_version": TRANSPORT_VERSION_20_CANDIDATE,
        },
        "strategy_a": {
            "name": STRATEGY_A,
            "description": "One Semantic Gate request per generated paragraph. Units stay inside that request.",
            "compatible_with_current_4b213_request_builder": True,
            "compatible_with_validate_response_202": True,
            "compatible_with_transport_schema": True,
            "truncation_risk": "Lower than chapter-scale; still unknown for very long paragraphs.",
            "resume_granularity": "paragraph",
            "evidence_mixing_risk": "Low: evidence_handles stay on one paragraph.",
            "remotely_validated": False,
        },
        "strategy_b": {
            "name": STRATEGY_B,
            "description": "Group several paragraphs in one request (pr array length > 1).",
            "transport_json_schema_allows_pr_array": True,
            "current_request_builders_emit_one_paragraph": True,
            "validate_response_202_requires_single_paragraph": True,
            "compatible_with_current_validator_without_change": False,
            "compatible_declared_without_verification": False,
            "evidence_mixing_risk": "High if grouped paragraphs share a response without per-paragraph allowed_evidence isolation.",
            "resume_complexity": "High: a failed group would need partial replay rules that do not exist.",
            "response_size_risk": "Higher; historical Terra outputs have been incomplete.",
            "remotely_validated": False,
        },
        "strategy_c": {
            "name": STRATEGY_C,
            "description": "One Semantic Gate request per chapter.",
            "compatible_with_validate_response_202": False,
            "historical_terra_incomplete_output_risk": "High. 4B.2.11 and earlier Terra canaries showed contract/output issues; do not assume a chapter-scale JSON object will complete.",
            "token_volume": "Largest per call. Long-context Terra pricing is unmodeled.",
            "validation_granularity": "Too coarse: a single truncated response blocks the whole chapter.",
            "resume_granularity": "chapter only",
            "remotely_validated": False,
        },
        "candidate": {
            "strategy": CANDIDATE_GRANULARITY,
            "reason": (
                "validate_response_202 currently errors with pr:expected_single_paragraph. "
                "4B.2.13 build_semantic_request and 4B.2.9 build_model_request both emit pr=[one paragraph]. "
                "Strategy A is the only granularity compatible with the frozen 2.0.2 validator "
                "without changing historical contracts. This is not a real Terra validation."
            ),
            "validated_on_terra": False,
            "validated_on_sonnet": False,
        },
        "secrets_included": False,
    }


__all__ = ["validation_granularity"]
