"""Evaluator-side label-leak audit. Human labels must not reach Terra."""

from __future__ import annotations

import json
import re
from typing import Any, Mapping

from app.book_semantic_gate_4b24.constants import (
    EXCLUDED_FROM_SCORE,
    NEGATIVE_CASE_IDS,
    POSITIVE_CASE_IDS,
    SCORED_CASE_ORDER,
)

# Human-label / answer-encoding tokens. Classification vocabulary in the
# frozen prompt is allowed; these tokens reveal benchmark answers.
_LEAK_TOKENS = (
    "expected_class",
    "expected_reason",
    "expected_reason_codes",
    "accepted_classes",
    "human_label",
    "human_verdict",
    "human-labeled",
    "human_label_authority",
    "ground_truth",
    "positive_cases",
    "negative_cases",
    "positive_or_non_substantive",
    "invented_funeral",
    "unsupported_connective",
    "new_causal",
    "reference_completion",
    "4b22_p2_supported",
    "4b22_p4_supported",
    "4b22_p5_supported",
    "4b22_p6_supported",
    "4b22_p7_supported",
    "4b2_p2_supported",
    "4b22_p3_new_causal",
    "4b22_p8_reference_completion",
    "4b2_p8_invented_funeral",
    "4b2_p13_unsupported_connective",
    "4b22_p1_connective",
    "idea224 supported paraphrase",
    "invented funeral illustration",
    "causal clause unsupported",
    "sting wording completes",
    "provider kind=con is not authoritative",
    "historical 4b.2 idea224 supported paragraph",
    "human: connective_non_substantive",
)

_ROLE_PATTERNS = (
    re.compile(r"\brole\s*[\"']?\s*:\s*[\"']positive\b", re.I),
    re.compile(r"\brole\s*[\"']?\s*:\s*[\"']negative\b", re.I),
    re.compile(r"\bknown (?:failure|positive|negative)s?\b", re.I),
    re.compile(r"\bexpected classification\b", re.I),
    re.compile(r"\bexpected verdict\b", re.I),
)


def _request_blob(payload: Mapping[str, Any], request: Mapping[str, Any] | None) -> str:
    parts: list[str] = [json.dumps(dict(payload), ensure_ascii=False)]
    if request:
        parts.append(str(request.get("system_prompt") or ""))
        parts.append(str(request.get("prompt") or ""))
    return "\n".join(parts)


def audit_label_leak(
    payload: Mapping[str, Any],
    *,
    request: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    blob = _request_blob(payload, request)
    lowered = blob.lower()
    hits: list[str] = []
    for token in _LEAK_TOKENS:
        if token.lower() in lowered:
            hits.append(token)
    for pattern in _ROLE_PATTERNS:
        if pattern.search(blob):
            hits.append(pattern.pattern)
    handle_leaks = []
    for opaque, case_id in SCORED_CASE_ORDER:
        if any(
            marker in opaque.lower()
            for marker in ("positive", "negative", "invented", "unsupported")
        ):
            handle_leaks.append(opaque)
        if case_id.lower() in lowered:
            hits.append(case_id)
    for case_id in list(POSITIVE_CASE_IDS) + list(NEGATIVE_CASE_IDS) + list(
        EXCLUDED_FROM_SCORE
    ):
        if case_id.lower() in lowered and case_id not in hits:
            hits.append(case_id)
    unique = sorted(set(hits))
    return {
        "label_leakage": len(unique),
        "hits": unique,
        "opaque_handle_leaks": handle_leaks,
        "scanned_chars": len(blob),
        "human_labels_sent": False if not unique else True,
        "case_roles_sent": False,
        "expected_classes_sent": False,
        "pass": len(unique) == 0 and not handle_leaks,
    }


__all__ = ["audit_label_leak"]
