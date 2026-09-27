"""
Observation des jetons contrôlés — avant decoder, sans réparation.

INTENT_KIND.v et AUDIENCE_KIND.v restent du texte libre.
"""

from __future__ import annotations

from typing import Any, Mapping

from app.source_analysis.canonical_vocabulary import (
    OBSERVED_3B43_INVALID_UNCERTAINTY_KINDS,
    VOCABULARY_CATEGORY_ORDER,
    canonical_allowed_vocabulary,
)
from app.source_analysis.ultra_compact_schema import (
    KIND_AUDIENCE_KIND,
    KIND_EXAMPLE,
    KIND_IDEA,
    KIND_INTENT_KIND,
    KIND_REFERENCE,
    KIND_RELATION,
    KIND_REPETITION,
    KIND_UNCERTAINTY,
    KIND_VOICE,
)


def _entry(vocabulary: str, value: Any, allowed: Mapping[str, tuple[str, ...]]) -> dict[str, Any]:
    token = "" if value is None else str(value)
    values = tuple(allowed.get(vocabulary) or ())
    return {
        "vocabulary": vocabulary,
        "value": token,
        "canonical": token in values,
    }


def observe_controlled_tokens(payload: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    """
    Jetons contrôlés réellement émis, dans l'ordre d'apparition.

    Ne classe pas INTENT_KIND.v / AUDIENCE_KIND.v.
    N'invente aucun jeton absent de la réponse.
    """
    if not isinstance(payload, Mapping):
        return []

    allowed = canonical_allowed_vocabulary()
    observed: list[dict[str, Any]] = []

    if "ic" in payload:
        observed.append(_entry("confidence", payload.get("ic"), allowed))
    if "ac" in payload:
        observed.append(_entry("confidence", payload.get("ac"), allowed))

    for record in payload.get("records") or []:
        if not isinstance(record, Mapping):
            continue
        kind = record.get("k")
        if kind is not None:
            observed.append(_entry("record.kind", kind, allowed))
        metadata = list(record.get("m") or [])
        if kind == KIND_IDEA:
            if len(metadata) >= 1:
                observed.append(_entry("idea.kind", metadata[0], allowed))
            if len(metadata) >= 2:
                observed.append(_entry("idea.importance", metadata[1], allowed))
        elif kind == KIND_RELATION:
            if "v" in record:
                observed.append(_entry("relation.type", record.get("v"), allowed))
        elif kind == KIND_EXAMPLE and metadata:
            observed.append(_entry("example.kind", metadata[0], allowed))
        elif kind == KIND_REFERENCE:
            if len(metadata) >= 1:
                observed.append(_entry("reference.kind", metadata[0], allowed))
            if len(metadata) >= 2:
                observed.append(_entry("reference.completeness", metadata[1], allowed))
        elif kind == KIND_UNCERTAINTY:
            if len(metadata) >= 1:
                observed.append(_entry("uncertainty.kind", metadata[0], allowed))
            if len(metadata) >= 2:
                observed.append(_entry("uncertainty.severity", metadata[1], allowed))
        elif kind == KIND_REPETITION and metadata:
            observed.append(_entry("repetition.character", metadata[0], allowed))
        elif kind == KIND_VOICE and metadata:
            observed.append(_entry("voice.field", metadata[0], allowed))
        elif kind in {KIND_INTENT_KIND, KIND_AUDIENCE_KIND}:
            continue

    return observed


def invalid_controlled_tokens(observed: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    allowed = canonical_allowed_vocabulary()
    invalid: list[dict[str, Any]] = []
    for item in observed:
        if item.get("canonical") is True:
            continue
        vocab = str(item.get("vocabulary") or "")
        invalid.append(
            {
                "vocabulary": vocab,
                "actual_token": item.get("value"),
                "allowed_values": list(allowed.get(vocab) or ()),
            }
        )
    return invalid


def reused_3b43_invalid_tokens(observed: list[Mapping[str, Any]]) -> list[str]:
    forbidden = set(OBSERVED_3B43_INVALID_UNCERTAINTY_KINDS)
    found: list[str] = []
    for item in observed:
        value = str(item.get("value") or "")
        if value in forbidden and value not in found:
            found.append(value)
    return found


def vocabulary_compliance_status(observed: list[Mapping[str, Any]]) -> str:
    if any(item.get("canonical") is not True for item in observed):
        return "FAIL"
    return "PASS"


def allowed_sets() -> dict[str, list[str]]:
    return {key: list(values) for key, values in canonical_allowed_vocabulary().items()}


def vocabularies_exercised(observed: list[Mapping[str, Any]]) -> list[str]:
    seen: list[str] = []
    for item in observed:
        key = str(item.get("vocabulary") or "")
        if key and key not in seen:
            seen.append(key)
    return [key for key in VOCABULARY_CATEGORY_ORDER if key in seen]
