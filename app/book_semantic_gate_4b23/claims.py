"""Temporary semantic-audit claim representation. Not manuscript IDs."""

from __future__ import annotations

import re
from typing import Any, Mapping, Sequence

from app.book_semantic_gate_4b23.constants import (
    CLASS_NON_SUBSTANTIVE,
    CLASS_QUESTIONABLE,
    CLASS_SUPPORTED,
    CLASS_UNSUPPORTED,
    CLASSIFICATIONS,
    GRANULARITY,
)
from app.book_semantic_gate_4b23.reasons import REASON_CODES

_WS = re.compile(r"\s+")

CLAIM_FIELDS = (
    "paragraph_handle",
    "claim_index",
    "claim_text",
    "start_offset",
    "end_offset",
    "classification",
    "evidence_handles",
    "reason_codes",
    "explanation",
    "confidence",
)

CONFIDENCE_VALUES = ("HIGH", "MEDIUM", "LOW")


def claim_contract_payload() -> dict[str, Any]:
    return {
        "granularity": GRANULARITY,
        "claim_ids_are_canonical_manuscript_ids": False,
        "fields": list(CLAIM_FIELDS),
        "classifications": list(CLASSIFICATIONS),
        "confidence_values": list(CONFIDENCE_VALUES),
        "paragraph_anchoring": True,
        "text_spans_required": True,
        "coverage_approach": {
            "selected": "EXACT_PARAGRAPH_TEXT_SPANS",
            "rule": (
                "Every claim must carry start_offset/end_offset into the "
                "paragraph text. The union of spans must cover the entire "
                "paragraph except whitespace-only gaps."
            ),
            "why": (
                "Provider-generated claim decomposition can omit a suspicious "
                "clause. Local span coverage proves every substantive span "
                "was considered without overengineering a second model pass."
            ),
            "rejected_as_too_coarse": "paragraph PASS/FAIL alone",
            "rejected_as_too_complex": "token-level or tree-structured claims",
        },
        "decomposition_risk": (
            "The validator can silently skip a clause. Local coverage FAIL "
            "if any non-whitespace paragraph span is uncovered."
        ),
        "every_substantive_paragraph_must_have_a_result": True,
        "unknown_handles_fail": True,
        "schema_complexity_balance": (
            "Claim text + offsets + closed classification/reason enums. "
            "No hidden reasoning. No provider-generated canonical IDs."
        ),
    }


def normalize_whitespace(text: str) -> str:
    return _WS.sub(" ", (text or "").strip())


def uncovered_spans(text: str, claims: Sequence[Mapping[str, Any]]) -> list[tuple[int, int]]:
    """Return non-whitespace gaps not covered by claim offsets."""
    if not text:
        return []
    covered = [False] * len(text)
    for claim in claims:
        start = claim.get("start_offset")
        end = claim.get("end_offset")
        if not isinstance(start, int) or not isinstance(end, int):
            continue
        if start < 0 or end < start or end > len(text):
            continue
        for index in range(start, end):
            covered[index] = True
    gaps: list[tuple[int, int]] = []
    gap_start: int | None = None
    for index, char in enumerate(text):
        missing = (not covered[index]) and (not char.isspace())
        if missing and gap_start is None:
            gap_start = index
        elif not missing and gap_start is not None:
            gaps.append((gap_start, index))
            gap_start = None
    if gap_start is not None:
        gaps.append((gap_start, len(text)))
    return gaps


def claim_offsets_valid(text: str, claim: Mapping[str, Any]) -> bool:
    start = claim.get("start_offset")
    end = claim.get("end_offset")
    if not isinstance(start, int) or not isinstance(end, int):
        return False
    if start < 0 or end < start or end > len(text):
        return False
    snippet = text[start:end]
    claim_text = str(claim.get("claim_text") or "")
    if not snippet:
        return False
    return normalize_whitespace(snippet) == normalize_whitespace(claim_text) or (
        normalize_whitespace(claim_text) in normalize_whitespace(text)
    )


def paragraph_verdict_from_claims(classifications: Sequence[str]) -> str:
    labels = [str(item) for item in classifications]
    if CLASS_UNSUPPORTED in labels:
        return CLASS_UNSUPPORTED
    if CLASS_QUESTIONABLE in labels:
        return CLASS_QUESTIONABLE
    if labels and all(item == CLASS_NON_SUBSTANTIVE for item in labels):
        return CLASS_NON_SUBSTANTIVE
    if CLASS_SUPPORTED in labels:
        return CLASS_SUPPORTED
    return CLASS_QUESTIONABLE


__all__ = [
    "CLAIM_FIELDS",
    "CONFIDENCE_VALUES",
    "claim_contract_payload",
    "claim_offsets_valid",
    "normalize_whitespace",
    "paragraph_verdict_from_claims",
    "uncovered_spans",
]
