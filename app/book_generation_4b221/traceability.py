"""IDEA handle review. Does not rewrite paras[].e."""

from __future__ import annotations

from typing import Any, Mapping

from app.book_generation.evidence import classify_handle
from app.book_generation_4b221.constants import (
    EXPECTED_IDEA_COUNT,
    EXPECTED_IDEA_IDS,
    PHASE,
    TARGET_CHAPTER_ID,
)


def idea_traceability_review(
    *,
    candidate_payload: Mapping[str, Any] | None,
    raw_parsed: Mapping[str, Any] | None,
    structural: Mapping[str, Any],
    allowed_handles: list[str],
) -> dict[str, Any]:
    checks = dict(structural.get("checks") or {})
    raw_e: list[str] = []
    if isinstance(raw_parsed, Mapping):
        for section in raw_parsed.get("sections") or []:
            if not isinstance(section, Mapping):
                continue
            for paragraph in section.get("paras") or []:
                if not isinstance(paragraph, Mapping):
                    continue
                for handle in paragraph.get("e") or []:
                    if classify_handle(str(handle)) == "IDEA":
                        raw_e.append(str(handle))
    candidate_e: list[str] = []
    if isinstance(candidate_payload, Mapping):
        for section in candidate_payload.get("sections") or []:
            for paragraph in section.get("paragraphs") or []:
                for handle in paragraph.get("evidence_handles") or []:
                    if classify_handle(str(handle)) == "IDEA":
                        candidate_e.append(str(handle))
    found = sorted(set(raw_e) | set(candidate_e) | set(checks.get("ideas_in_paragraph_evidence") or []))
    invalid = [handle for handle in found if handle not in set(EXPECTED_IDEA_IDS)]
    unknown = [handle for handle in found if handle not in set(allowed_handles)]
    missing = [idea_id for idea_id in EXPECTED_IDEA_IDS if idea_id not in set(found)]
    return {
        "phase": PHASE,
        "chapter_id": TARGET_CHAPTER_ID,
        "ideas_expected": list(EXPECTED_IDEA_IDS),
        "ideas_expected_count": EXPECTED_IDEA_COUNT,
        "ideas_found_in_paras_e": found,
        "ideas_found_count": len(found),
        "ideas_missing_from_paras_e": missing,
        "ideas_invalid": invalid,
        "ideas_unknown": unknown,
        "ideas_in_section_metadata_only": list(checks.get("ideas_metadata_only") or []),
        "src_handles_invalid": list(checks.get("invalid_src") or []),
        "unknown_identifiers": list(checks.get("unknown_identifiers") or []),
        "provider_response_modified": False,
        "handles_auto_filled": False,
        "identifier_alone_is_not_restatement": True,
        "semantic_certification": "NOT PERFORMED",
        "note": (
            "This review checks contract handles in paras[].e. "
            "It does not certify that the 11 ideas were faithfully restated."
        ),
        "secrets_included": False,
    }


__all__ = ["idea_traceability_review"]
