"""Deterministic chapter cache signature and resumable generation state."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Mapping

from app.book_generation.constants import (
    BOOK_GENERATION_TRANSPORT_VERSION,
    BOOK_GENERATOR_PROMPT_VERSION,
    BOOK_GENERATOR_SETTINGS_VERSION,
    BOOK_SCHEMA_VERSION,
)
from app.file_utils import content_hash


@dataclass(frozen=True)
class ChapterSignatureInputs:
    source_map_sha256: str
    editorial_plan_sha256: str
    chapter_id: str
    prompt_version: str
    prompt_sha256: str
    transport_version: str
    schema_version: str
    response_schema_sha256: str
    provider: str
    model: str
    thinking_mode: str
    effort: str
    max_output_tokens: int | None
    canonical_language: str
    evidence_bundle_sha256: str
    settings_version: str = BOOK_GENERATOR_SETTINGS_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "canonical_language": self.canonical_language,
            "chapter_id": self.chapter_id,
            "editorial_plan_sha256": self.editorial_plan_sha256,
            "effort": self.effort,
            "evidence_bundle_sha256": self.evidence_bundle_sha256,
            "max_output_tokens": self.max_output_tokens,
            "model": self.model,
            "prompt_sha256": self.prompt_sha256,
            "prompt_version": self.prompt_version,
            "provider": self.provider,
            "response_schema_sha256": self.response_schema_sha256,
            "schema_version": self.schema_version,
            "settings_version": self.settings_version,
            "source_map_sha256": self.source_map_sha256,
            "thinking_mode": self.thinking_mode,
            "transport_version": self.transport_version,
        }


def build_chapter_signature(inputs: ChapterSignatureInputs) -> str:
    return content_hash(json.dumps(inputs.to_dict(), ensure_ascii=False, sort_keys=True))


def default_chapter_signature_inputs(
    *,
    source_map_sha256: str,
    editorial_plan_sha256: str,
    chapter_id: str,
    prompt_sha256: str,
    response_schema_sha256: str,
    provider: str,
    model: str,
    thinking_mode: str,
    effort: str | None,
    max_output_tokens: int | None,
    canonical_language: str,
    evidence_bundle_sha256: str,
) -> ChapterSignatureInputs:
    return ChapterSignatureInputs(
        source_map_sha256=source_map_sha256,
        editorial_plan_sha256=editorial_plan_sha256,
        chapter_id=chapter_id,
        prompt_version=BOOK_GENERATOR_PROMPT_VERSION,
        prompt_sha256=prompt_sha256,
        transport_version=BOOK_GENERATION_TRANSPORT_VERSION,
        schema_version=BOOK_SCHEMA_VERSION,
        response_schema_sha256=response_schema_sha256,
        provider=provider,
        model=model,
        thinking_mode=thinking_mode or "",
        effort=effort or "",
        max_output_tokens=max_output_tokens,
        canonical_language=canonical_language,
        evidence_bundle_sha256=evidence_bundle_sha256,
    )


@dataclass
class ChapterCache:
    _hits: dict[str, str] = field(default_factory=dict)

    def remember(self, signature: str, candidate_sha256: str) -> None:
        self._hits[signature] = candidate_sha256

    def lookup(self, signature: str) -> str | None:
        return self._hits.get(signature)

    def is_hit(self, signature: str) -> bool:
        return signature in self._hits

    def to_dict(self) -> dict[str, str]:
        return dict(self._hits)


@dataclass
class GenerationState:
    """Resumable per-chapter state. A later failure does not drop earlier hits."""

    validated: dict[str, dict[str, str]] = field(default_factory=dict)
    failed: dict[str, str] = field(default_factory=dict)

    def remember_validated(
        self, chapter_id: str, signature: str, candidate_sha256: str
    ) -> None:
        self.validated[chapter_id] = {
            "signature": signature,
            "candidate_sha256": candidate_sha256,
            "status": "validated",
        }

    def remember_failed(self, chapter_id: str, reason: str) -> None:
        self.failed[chapter_id] = reason

    def reusable(self, chapter_id: str, signature: str) -> bool:
        record = self.validated.get(chapter_id) or {}
        return record.get("signature") == signature

    def to_dict(self) -> dict[str, Any]:
        return {"validated": dict(self.validated), "failed": dict(self.failed)}

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any] | None) -> "GenerationState":
        state = cls()
        if not isinstance(payload, Mapping):
            return state
        validated = payload.get("validated")
        if isinstance(validated, Mapping):
            for chapter_id, record in validated.items():
                if isinstance(record, Mapping):
                    state.validated[str(chapter_id)] = {
                        "signature": str(record.get("signature") or ""),
                        "candidate_sha256": str(record.get("candidate_sha256") or ""),
                        "status": str(record.get("status") or "validated"),
                    }
        failed = payload.get("failed")
        if isinstance(failed, Mapping):
            state.failed = {str(key): str(value) for key, value in failed.items()}
        return state
