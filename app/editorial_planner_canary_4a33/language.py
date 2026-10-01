"""Post-response language audit. No translation. No second call."""

from __future__ import annotations

from typing import Any, Mapping

from app.editorial_planning.language_validate import validate_editorial_language
from app.language_cleanup.models import LANGUAGE_EN, LANGUAGE_FR, LANGUAGE_MIXED, LANGUAGE_UNKNOWN


def language_audit(
    plan: Mapping[str, Any] | None,
    *,
    canonical_document_language: str,
) -> dict[str, Any]:
    if not isinstance(plan, Mapping):
        return {
            "editorial_language_match": "FAIL",
            "status": "FAIL",
            "canonical_document_language": canonical_document_language,
            "reason": "no reconstructed plan",
            "translated": False,
            "repaired": False,
            "second_provider_call": False,
        }
    raw = validate_editorial_language(
        plan, canonical_document_language=canonical_document_language
    )
    measurement = dict(raw.get("measurement") or {})
    fields = dict(measurement.get("fields") or {})
    combined = dict(measurement.get("combined") or {})

    char_counts = {
        "combined_classified_chars": int(combined.get("chars") or 0),
        "field_chars": {
            name: int(row.get("chars") or 0)
            for name, row in fields.items()
            if isinstance(row, Mapping)
        },
    }
    en_fields = [
        name
        for name, row in fields.items()
        if isinstance(row, Mapping) and row.get("language") == LANGUAGE_EN
    ]
    fr_fields = [
        name
        for name, row in fields.items()
        if isinstance(row, Mapping) and row.get("language") == LANGUAGE_FR
    ]
    mixed_fields = [
        name
        for name, row in fields.items()
        if isinstance(row, Mapping) and row.get("language") == LANGUAGE_MIXED
    ]
    unknown_fields = [
        name
        for name, row in fields.items()
        if isinstance(row, Mapping)
        and row.get("language") in {LANGUAGE_UNKNOWN, "", None}
    ]
    policy = dict(raw.get("policy") or {})
    return {
        **raw,
        "classified_character_counts": char_counts,
        "en_evidence": {
            "combined_language": combined.get("language"),
            "combined_confidence": combined.get("confidence"),
            "fields": en_fields,
        },
        "fr_evidence": {"fields": fr_fields},
        "mixed_unknown_evidence": {
            "mixed_fields": mixed_fields,
            "unknown_fields": unknown_fields,
        },
        "fields_inspected": sorted(fields),
        "fields_excluded": [
            "machine identifiers",
            "inherited IDEA/TOP/EX/REF/UNC/SRC/CH/SEC refs",
        ],
        "thresholds_used": policy.get("thresholds"),
        "translated": False,
        "repaired": False,
        "second_provider_call": False,
        "publication_requires": "EDITORIAL_LANGUAGE_MATCH=PASS",
    }


__all__ = ["language_audit"]
