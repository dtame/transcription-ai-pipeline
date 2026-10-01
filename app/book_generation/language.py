"""Canonical document language + manuscript language gate."""

from __future__ import annotations

from typing import Any, Iterable

from app.book_generation.constants import (
    LANGUAGE_POLICY,
    VALIDATION_FAIL,
    VALIDATION_PASS,
    VALIDATION_REVIEW,
)
from app.editorial_planning.language_policy import (
    DOCUMENT_LANGUAGE_POLICY,
    normalize_language_code,
    resolve_document_language,
)
from app.editorial_planner_forensics_4a31.language import (
    classify_editorial_prose,
    strip_inherited_ids,
)
from app.language_cleanup.models import LANGUAGE_EN, LANGUAGE_FR, LANGUAGE_MIXED

_CANONICAL_TO_DETECTED = {
    "en": LANGUAGE_EN,
    "fr": LANGUAGE_FR,
}

PASS_CONFIDENCE = 0.80
FAIL_CONFIDENCE = 0.80


def resolve_canonical_language(
    *,
    source_map_primary_language: str | None,
    transcript_primary_language: str | None = None,
) -> str:
    resolution = resolve_document_language(
        transcript_primary_language=transcript_primary_language,
        source_map_primary_language=source_map_primary_language,
    )
    return resolution.require()


def language_policy_dict() -> dict[str, Any]:
    return {
        "policy": LANGUAGE_POLICY,
        "document_language_policy": DOCUMENT_LANGUAGE_POLICY,
        "translation_during_book_generation": False,
        "provider_may_choose_language": False,
        "reuse": "editorial_planning.language_policy + language_cleanup classifier",
    }


def validate_manuscript_language(
    texts: Iterable[str],
    *,
    canonical_document_language: str,
) -> dict[str, Any]:
    code = normalize_language_code(canonical_document_language)
    joined = strip_inherited_ids("\n".join(text for text in texts if text)).strip()
    measurement = classify_editorial_prose(joined)
    detected = str(measurement.get("language") or "")
    confidence = float(measurement.get("confidence") or 0.0)
    expected = _CANONICAL_TO_DETECTED.get(code)

    if not code:
        status = VALIDATION_FAIL
        reason = "canonical_document_language missing"
    elif expected is None:
        status = VALIDATION_REVIEW
        reason = (
            f"Existing classifier cannot confirm language {code!r}; "
            "REVIEW rather than an unreliable detector."
        )
    elif not joined:
        status = VALIDATION_FAIL
        reason = "no manuscript prose to classify"
    elif detected == expected and confidence >= PASS_CONFIDENCE:
        status = VALIDATION_PASS
        reason = (
            f"Manuscript prose matches canonical language {code} "
            f"(detected {detected}, confidence {confidence})"
        )
    elif detected in {LANGUAGE_EN, LANGUAGE_FR} and detected != expected:
        if confidence >= FAIL_CONFIDENCE:
            status = VALIDATION_FAIL
            reason = (
                f"Gross language mismatch: canonical={code}, "
                f"detected={detected}, confidence={confidence}"
            )
        else:
            status = VALIDATION_REVIEW
            reason = (
                f"Possible mismatch canonical={code} detected={detected} "
                f"below fail confidence {FAIL_CONFIDENCE}"
            )
    elif detected == LANGUAGE_MIXED:
        status = VALIDATION_REVIEW
        reason = "Mixed EN/FR manuscript prose"
    else:
        status = VALIDATION_REVIEW
        reason = (
            f"Insufficient or unknown language signal "
            f"(detected={detected}, confidence={confidence})"
        )

    return {
        "canonical_document_language": code,
        "detected": detected,
        "confidence": confidence,
        "status": status,
        "reason": reason,
        "chars": len(joined),
    }
