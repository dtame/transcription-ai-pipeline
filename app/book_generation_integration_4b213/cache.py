"""Isolated test cache. Never writes the production ChapterCache."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Mapping

from app.book_generation_integration_4b213.constants import (
    CACHE_GENERATION_OBTAINED,
    CACHE_INTERRUPTED,
    CACHE_TECHNICAL_ERROR,
    CACHE_VALIDATION_BLOCK,
    CACHE_VALIDATION_PASS,
    CACHE_VALIDATION_PENDING,
    CACHE_VALIDATION_REVIEW,
    CODE_VERSION,
    DECISION_BLOCK,
    DECISION_PASS,
    DECISION_REVIEW,
    INTEGRATION_CONTRACT_VERSION,
    ISOLATED_CACHE_VERSION,
    PHASE,
    PREPARATION_ALGORITHM_VERSION,
    PRODUCTION_CACHE_ACCEPTANCE,
    PROMPT_VERSION_202_CANDIDATE,
    TRANSPORT_VERSION_20_CANDIDATE,
    VALIDATOR_IMPLEMENTATION_VERSION,
)
from app.file_utils import content_hash


def validation_key(
    *,
    generated_text_sha256: str,
    chapter_id: str,
    paragraph_ids: list[str],
    source_map_sha256: str,
    editorial_plan_sha256: str,
    evidence_bundle_sha256: str,
    semantic_contract_version: str = PROMPT_VERSION_202_CANDIDATE,
    semantic_transport_version: str = TRANSPORT_VERSION_20_CANDIDATE,
    preparation_algorithm_version: str = PREPARATION_ALGORITHM_VERSION,
    validator_implementation_version: str = VALIDATOR_IMPLEMENTATION_VERSION,
    integration_contract_version: str = INTEGRATION_CONTRACT_VERSION,
    code_version: str = CODE_VERSION,
) -> str:
    payload = {
        "generated_text_sha256": generated_text_sha256,
        "chapter_id": chapter_id,
        "paragraph_ids": list(paragraph_ids),
        "source_map_sha256": source_map_sha256,
        "editorial_plan_sha256": editorial_plan_sha256,
        "evidence_bundle_sha256": evidence_bundle_sha256,
        "semantic_contract_version": semantic_contract_version,
        "semantic_transport_version": semantic_transport_version,
        "preparation_algorithm_version": preparation_algorithm_version,
        "validator_implementation_version": validator_implementation_version,
        "integration_contract_version": integration_contract_version,
        "code_version": code_version,
        "cache_version": ISOLATED_CACHE_VERSION,
    }
    return content_hash(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def state_from_decision(decision: str, *, interrupted: bool = False, error: bool = False) -> str:
    if interrupted:
        return CACHE_INTERRUPTED
    if error:
        return CACHE_TECHNICAL_ERROR
    if decision == DECISION_PASS:
        return CACHE_VALIDATION_PASS
    if decision == DECISION_REVIEW:
        return CACHE_VALIDATION_REVIEW
    if decision == DECISION_BLOCK:
        return CACHE_VALIDATION_BLOCK
    return CACHE_TECHNICAL_ERROR


@dataclass
class IsolatedChapterCache:
    """In-memory cache for 4B.2.13 tests only."""

    records: dict[str, dict[str, Any]] = field(default_factory=dict)
    production_writes: int = 0

    def store(self, key: str, record: Mapping[str, Any]) -> dict[str, Any]:
        stored = dict(record)
        stored["isolated"] = True
        stored["production_cache_write"] = False
        stored["cache_version"] = ISOLATED_CACHE_VERSION
        stored["phase"] = PHASE
        self.records[key] = stored
        return stored

    def lookup(self, key: str) -> dict[str, Any] | None:
        record = self.records.get(key)
        return dict(record) if record else None

    def reusable_as_pass(self, key: str) -> bool:
        record = self.lookup(key)
        if not record:
            return False
        if record.get("state") != CACHE_VALIDATION_PASS:
            return False
        if record.get("decision") != DECISION_PASS:
            return False
        if record.get("historical_partial_converted"):
            return False
        return True

    def presented_as_validated(self, key: str) -> bool:
        record = self.lookup(key)
        if not record:
            return False
        return bool(record.get("presented_as_validated_chapter"))

    def to_dict(self) -> dict[str, Any]:
        return {
            "phase": PHASE,
            "isolated": True,
            "production_cache_acceptance": PRODUCTION_CACHE_ACCEPTANCE,
            "production_writes": self.production_writes,
            "states_observed": sorted(
                {str(item.get("state") or "") for item in self.records.values()}
            ),
            "record_count": len(self.records),
            "pass_only_acceptance_candidate": True,
            "review_never_validated": True,
            "block_never_validated": True,
            "historical_partial_never_converted_to_pass": True,
            "secrets_included": False,
        }


def cache_document() -> dict[str, Any]:
    return {
        "phase": PHASE,
        "isolated": True,
        "states": [
            CACHE_GENERATION_OBTAINED,
            CACHE_VALIDATION_PENDING,
            CACHE_VALIDATION_PASS,
            CACHE_VALIDATION_REVIEW,
            CACHE_VALIDATION_BLOCK,
            CACHE_TECHNICAL_ERROR,
            CACHE_INTERRUPTED,
        ],
        "acceptance_rule": "Only VALIDATION_PASS may become a future-acceptance candidate.",
        "review_and_block_never_validated": True,
        "production_cache": "UNCHANGED",
        "key_dependencies": [
            "generated_text_sha256",
            "chapter_id",
            "paragraph_ids",
            "source_map_sha256",
            "editorial_plan_sha256",
            "evidence_bundle_sha256",
            "semantic_contract_version",
            "semantic_transport_version",
            "preparation_algorithm_version",
            "validator_implementation_version",
            "integration_contract_version",
            "code_version",
        ],
        "historical_partial_never_pass": True,
        "secrets_included": False,
    }


__all__ = [
    "IsolatedChapterCache",
    "cache_document",
    "state_from_decision",
    "validation_key",
]
