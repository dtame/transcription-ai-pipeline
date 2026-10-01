"""Future accepted-chapter cache contract. Not a production write."""

from __future__ import annotations

from typing import Any, Mapping

from app.book_semantic_gate_4b23.constants import (
    DETERMINISTIC_VALIDATOR_VERSION,
    GENERATOR_PROMPT_VERSION,
    SEMANTIC_GATE_MODEL,
    SEMANTIC_GATE_PROVIDER,
    SEMANTIC_GATE_SETTINGS_VERSION,
    SEMANTIC_VALIDATION_TRANSPORT_VERSION,
    SEMANTIC_VALIDATOR_PROMPT_VERSION,
)
from app.file_utils import content_hash
import json


CACHE_FIELDS = (
    "chapter_id",
    "canonical_language",
    "generator_provider",
    "generator_model",
    "generator_prompt_version",
    "generator_prompt_sha256",
    "generator_transport_version",
    "generator_schema_sha256",
    "generator_signature",
    "deterministic_validator_version",
    "deterministic_validator_status",
    "semantic_gate_provider",
    "semantic_gate_model",
    "semantic_gate_prompt_version",
    "semantic_gate_prompt_sha256",
    "semantic_gate_transport_version",
    "semantic_gate_schema_sha256",
    "semantic_gate_status",
    "candidate_sha256",
    "evidence_bundle_sha256",
    "gate_input_sha256",
    "semantic_audit_sha256",
    "settings_version",
)


def cache_record_template() -> dict[str, Any]:
    return {field: None for field in CACHE_FIELDS}


def cache_contract_payload() -> dict[str, Any]:
    return {
        "accepted_chapter_requires": list(CACHE_FIELDS),
        "cache_acceptance_requires_semantic_pass": True,
        "questionable_blocks_cache": True,
        "unsupported_blocks_cache": True,
        "4b22_candidate_production_cache": "NOT ACCEPTED",
        "invalidation": {
            "candidate_bytes_change": "semantic PASS becomes invalid",
            "evidence_change": "semantic PASS becomes invalid",
            "semantic_validator_contract_change": (
                "revalidation policy must be explicit; do not reuse a PASS "
                "from a prior prompt/transport/schema identity"
            ),
        },
        "revalidation_policy": {
            "prompt_change": "REVALIDATE",
            "transport_change": "REVALIDATE",
            "schema_change": "REVALIDATE",
            "model_change": "REVALIDATE",
            "evidence_change": "INVALIDATE",
            "candidate_change": "INVALIDATE",
        },
        "no_production_write_this_phase": True,
        "identities": {
            "generator_prompt": GENERATOR_PROMPT_VERSION,
            "deterministic_validator": DETERMINISTIC_VALIDATOR_VERSION,
            "semantic_gate_provider": SEMANTIC_GATE_PROVIDER,
            "semantic_gate_model": SEMANTIC_GATE_MODEL,
            "semantic_gate_prompt": SEMANTIC_VALIDATOR_PROMPT_VERSION,
            "semantic_gate_transport": SEMANTIC_VALIDATION_TRANSPORT_VERSION,
            "settings_version": SEMANTIC_GATE_SETTINGS_VERSION,
        },
    }


def semantic_pass_valid(
    *,
    candidate_sha256: str,
    recorded_candidate_sha256: str,
    evidence_sha256: str,
    recorded_evidence_sha256: str,
    contract_sha256: str,
    recorded_contract_sha256: str,
) -> bool:
    return (
        candidate_sha256 == recorded_candidate_sha256
        and evidence_sha256 == recorded_evidence_sha256
        and contract_sha256 == recorded_contract_sha256
    )


def contract_identity(payload: Mapping[str, Any]) -> str:
    return content_hash(json.dumps(dict(payload), ensure_ascii=False, sort_keys=True))


__all__ = [
    "CACHE_FIELDS",
    "cache_contract_payload",
    "cache_record_template",
    "contract_identity",
    "semantic_pass_valid",
]
