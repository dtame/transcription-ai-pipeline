"""Acceptance policy. Semantic gate never rewrites manuscript."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from app.book_semantic_gate_4b23.claims import (
    claim_offsets_valid,
    paragraph_verdict_from_claims,
    uncovered_spans,
)
from app.book_semantic_gate_4b23.constants import (
    CLASS_NON_SUBSTANTIVE,
    CLASS_QUESTIONABLE,
    CLASS_SUPPORTED,
    CLASS_UNSUPPORTED,
    VERDICT_FAIL,
    VERDICT_PASS,
    VERDICT_REVIEW,
)
from app.book_semantic_gate_4b23.transport import decode_transport


def acceptance_policy_payload() -> dict[str, Any]:
    return {
        "clean_acceptance": {
            "UNSUPPORTED": 0,
            "QUESTIONABLE": 0,
            "unknown_handles": 0,
            "missing_paragraph_results": 0,
            "coverage_gaps": 0,
        },
        "QUESTIONABLE_accepted": False,
        "UNSUPPORTED_accepted": False,
        "QUESTIONABLE_policy": {
            "verdict": VERDICT_REVIEW,
            "review_required": True,
            "cache_acceptance": False,
            "silent_convert_to_pass": False,
        },
        "UNSUPPORTED_policy": {
            "verdict": VERDICT_FAIL,
            "review_required": True,
            "cache_acceptance": False,
        },
        "unknown_handles": VERDICT_FAIL,
        "missing_paragraph_result": VERDICT_FAIL,
        "coverage_gap": VERDICT_FAIL,
        "no_automatic_repair": True,
        "no_generator_feedback_loop": True,
        "future_repair_options_not_implemented": [
            "human correction",
            "explicit controlled regeneration",
            "versioned prompt change",
            "chapter rejection",
        ],
        "deterministic_validator_must_pass_first": True,
        "empty_paragraph_is_not_semantic_gate_work": True,
        "provider_kind_not_authoritative": True,
    }


def apply_acceptance(
    parsed: Mapping[str, Any] | None,
    *,
    required_handles: Sequence[str],
    paragraph_texts: Mapping[str, str],
    allowed_handles: Sequence[str] | None = None,
    deterministic_validator_pass: bool = True,
) -> dict[str, Any]:
    if not deterministic_validator_pass:
        return {
            "verdict": VERDICT_FAIL,
            "review_required": True,
            "cache_acceptance": False,
            "reason": "deterministic_validator_not_pass",
            "errors": ["semantic gate must not run on structurally invalid chapters"],
            "summary_counts": _empty_counts(),
            "unknown_handles": [],
            "paragraph_results": [],
            "canonical": None,
        }
    try:
        decoded = decode_transport(parsed)
    except Exception as exc:
        return {
            "verdict": VERDICT_FAIL,
            "review_required": True,
            "cache_acceptance": False,
            "reason": "transport_decode_fail",
            "errors": [str(exc)],
            "summary_counts": _empty_counts(),
            "unknown_handles": [],
            "paragraph_results": [],
            "canonical": None,
        }

    errors: list[str] = []
    unknown: list[str] = list(decoded.get("unknown_handles") or [])
    allowed = set(str(item) for item in (allowed_handles or []))
    required = [str(item) for item in required_handles]
    by_handle = {
        str(row.get("paragraph_handle") or ""): row
        for row in decoded.get("paragraph_results") or []
    }
    for handle in required:
        if handle not in by_handle:
            errors.append(f"missing paragraph result: {handle}")
    extra = sorted(key for key in by_handle if key and key not in required)
    if extra:
        unknown.extend(extra)
        errors.append("unknown paragraph handles: " + ", ".join(extra))

    claim_counts = {
        CLASS_SUPPORTED: 0,
        CLASS_QUESTIONABLE: 0,
        CLASS_UNSUPPORTED: 0,
        CLASS_NON_SUBSTANTIVE: 0,
    }
    paragraph_results = []
    for handle in required:
        row = by_handle.get(handle)
        if row is None:
            continue
        text = str(paragraph_texts.get(handle) or "")
        claims = list(row.get("claim_results") or [])
        if not claims:
            errors.append(f"{handle}: no claim decomposition")
        gaps = uncovered_spans(text, claims) if text else []
        if gaps:
            errors.append(f"{handle}: claim coverage gap {gaps}")
        for claim in claims:
            if text and not claim_offsets_valid(text, claim):
                errors.append(f"{handle}: invalid claim span {claim.get('claim_index')}")
            classification = str(claim.get("classification") or "")
            if classification in claim_counts:
                claim_counts[classification] += 1
            for ev in claim.get("evidence_handles") or []:
                if allowed and str(ev) not in allowed:
                    unknown.append(str(ev))
        derived = paragraph_verdict_from_claims(
            [str(claim.get("classification") or "") for claim in claims]
        )
        paragraph_results.append(
            {
                "paragraph_handle": handle,
                "verdict": derived,
                "claim_results": claims,
                "evidence_used": list(row.get("evidence_used") or []),
                "reason_codes": list(row.get("reason_codes") or []),
            }
        )

    unknown = sorted(set(item for item in unknown if item))
    if unknown:
        errors.append("unknown handles: " + ", ".join(unknown))

    questionable = claim_counts[CLASS_QUESTIONABLE]
    unsupported = claim_counts[CLASS_UNSUPPORTED]
    if errors or unsupported:
        verdict = VERDICT_FAIL
    elif questionable:
        verdict = VERDICT_REVIEW
    else:
        verdict = VERDICT_PASS
    review = verdict != VERDICT_PASS
    cache = verdict == VERDICT_PASS
    canonical = {
        "chapter_handle": decoded.get("chapter_handle"),
        "verdict": verdict,
        "paragraph_results": paragraph_results,
        "summary_counts": {
            "supported": claim_counts[CLASS_SUPPORTED],
            "questionable": questionable,
            "unsupported": unsupported,
            "non_substantive": claim_counts[CLASS_NON_SUBSTANTIVE],
        },
        "unknown_handles": unknown,
        "review_required": review,
        "cache_acceptance": cache,
    }
    return {
        "verdict": verdict,
        "review_required": review,
        "cache_acceptance": cache,
        "reason": "ok" if not errors else "policy_fail",
        "errors": errors,
        "summary_counts": canonical["summary_counts"],
        "unknown_handles": unknown,
        "paragraph_results": paragraph_results,
        "canonical": canonical,
    }


def canonical_audit(result: Mapping[str, Any]) -> dict[str, Any]:
    payload = dict(result.get("canonical") or {})
    payload["errors"] = list(result.get("errors") or [])
    payload["reason"] = result.get("reason")
    return payload


def _empty_counts() -> dict[str, int]:
    return {
        "supported": 0,
        "questionable": 0,
        "unsupported": 0,
        "non_substantive": 0,
    }


__all__ = [
    "acceptance_policy_payload",
    "apply_acceptance",
    "canonical_audit",
]
