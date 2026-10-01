"""
Post-response editorial language validation. No LLM. No new dependency.

Reuses the existing language_cleanup classifier (function words, diacritics,
elisions, contractions). That classifier is EN/FR-capable. Other languages
cannot be confirmed and return REVIEW rather than a fabricated score.
"""

from __future__ import annotations

from typing import Any, Mapping

from app.editorial_planner_forensics_4a31.language import (
    collect_plan_prose,
    measure_plan_language,
    strip_inherited_ids,
)
from app.editorial_planning.constants import (
    VALIDATION_FAIL,
    VALIDATION_PASS,
    VALIDATION_REVIEW,
)
from app.editorial_planning.language_policy import normalize_language_code
from app.language_cleanup.models import LANGUAGE_EN, LANGUAGE_FR, LANGUAGE_MIXED

LANGUAGE_VALIDATE_VERSION = "editorial-language-validate-1.0"
MECHANISM = "EXISTING_LANGUAGE_CLEANUP_CLASSIFIER"
PASS_CONFIDENCE = 0.80
FAIL_CONFIDENCE = 0.80

_CANONICAL_TO_DETECTED = {
    "en": LANGUAGE_EN,
    "fr": LANGUAGE_FR,
}

FUTURE_PUBLICATION_GATE = "EDITORIAL_LANGUAGE_MATCH"
FUTURE_PUBLICATION_REQUIRED = VALIDATION_PASS


def future_publication_eligibility_requirements() -> dict[str, Any]:
    """Gates the next real English planner call must satisfy before publication."""
    return {
        FUTURE_PUBLICATION_GATE: FUTURE_PUBLICATION_REQUIRED,
        "ready_for_editorial_plan_publication": False,
        "audit_only_candidate_first": True,
        "automatic_publication": False,
    }


def detector_supports(canonical_document_language: str) -> bool:
    return normalize_language_code(canonical_document_language) in _CANONICAL_TO_DETECTED


def language_validation_policy() -> dict[str, Any]:
    return {
        "version": LANGUAGE_VALIDATE_VERSION,
        "mechanism": MECHANISM,
        "dependency_added": False,
        "fragile_word_list": False,
        "scope": "provider-generated editorial prose only; IDs and inherited refs excluded",
        "supported_scoring_languages": sorted(_CANONICAL_TO_DETECTED),
        "unsupported_language_result": VALIDATION_REVIEW,
        "thresholds": {
            "pass_confidence": PASS_CONFIDENCE,
            "fail_confidence": FAIL_CONFIDENCE,
            "pass": (
                "combined classification matches canonical language, "
                f"confidence >= {PASS_CONFIDENCE}, and dominant field language matches"
            ),
            "fail": (
                "combined classification is the opposite supported language "
                f"(EN vs FR) with confidence >= {FAIL_CONFIDENCE}"
            ),
            "review": (
                "mixed, unknown, low confidence, unsupported canonical language, "
                "or conflicting field-level scores"
            ),
        },
        "results": (VALIDATION_PASS, VALIDATION_REVIEW, VALIDATION_FAIL),
        "future_publication_gate": FUTURE_PUBLICATION_GATE,
        "future_publication_requires": FUTURE_PUBLICATION_REQUIRED,
        "future_publication_eligibility": future_publication_eligibility_requirements(),
        "note": (
            "Gross EN/FR mismatch is the A.3 failure mode this layer must catch. "
            "It is not a translation detector and does not score semantic fidelity."
        ),
    }


def validate_editorial_language(
    plan: Mapping[str, Any],
    *,
    canonical_document_language: str,
) -> dict[str, Any]:
    code = normalize_language_code(canonical_document_language)
    policy = language_validation_policy()
    measurement = measure_plan_language(plan)
    combined = dict(measurement.get("combined") or {})
    detected = str(combined.get("language") or "")
    confidence = float(combined.get("confidence") or 0.0)
    expected = _CANONICAL_TO_DETECTED.get(code)
    editorial = str(measurement.get("editorial_plan_language") or "")

    if not code:
        status = VALIDATION_FAIL
        reason = "canonical_document_language missing"
    elif expected is None:
        status = VALIDATION_REVIEW
        reason = (
            f"Existing classifier cannot confirm language {code!r}; "
            "REVIEW_REQUIRED rather than an unreliable detector."
        )
    elif detected == expected and confidence >= PASS_CONFIDENCE:
        opposite = LANGUAGE_FR if expected == LANGUAGE_EN else LANGUAGE_EN
        opposite_fields = [
            name
            for name, row in (measurement.get("fields") or {}).items()
            if isinstance(row, Mapping) and row.get("language") == opposite
        ]
        if opposite_fields:
            status = VALIDATION_REVIEW
            reason = (
                "Combined score matches canonical language but some prose "
                f"fields classified as {opposite}: {opposite_fields}"
            )
        else:
            status = VALIDATION_PASS
            reason = (
                f"Editorial prose matches canonical language {code} "
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
        reason = "Mixed EN/FR editorial prose"
    else:
        status = VALIDATION_REVIEW
        reason = (
            f"Insufficient or unknown language signal "
            f"(detected={detected}, confidence={confidence})"
        )

    return {
        "policy": policy,
        "canonical_document_language": code,
        "detector_supports_canonical": expected is not None,
        "measurement": measurement,
        "detected_combined": detected,
        "confidence": confidence,
        "editorial_plan_language": editorial,
        "status": status,
        "editorial_language_match": status,
        "reason": reason,
        "ids_excluded": True,
        "id_strip_example": strip_inherited_ids("IDEA001 remains"),
        "prose_fields": sorted(collect_plan_prose(plan)),
    }


__all__ = [
    "FUTURE_PUBLICATION_GATE",
    "FUTURE_PUBLICATION_REQUIRED",
    "LANGUAGE_VALIDATE_VERSION",
    "MECHANISM",
    "detector_supports",
    "future_publication_eligibility_requirements",
    "language_validation_policy",
    "validate_editorial_language",
]
