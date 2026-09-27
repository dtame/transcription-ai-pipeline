"""Validateur strict semantic-transport-v3. Après parse + resolve. Pas de repair."""

from __future__ import annotations

from typing import Any, Mapping

from app.source_analysis.errors import WindowTransportValidationError
from app.source_analysis.semantic_transport_decoder import (
    _validate_links,
    _validate_relation_uniqueness,
)
from app.source_analysis_hybrid.contracts import WindowInput
from app.source_analysis_local_v2.granularity import validate_v2_transport_granularity
from app.source_analysis_local_v2.validator import (
    validate_v2_kinds,
    validate_v2_no_editorial_leakage,
    validate_v2_source_refs,
)
from app.source_analysis_local_v3.resolver import resolve_v3_handles


def validate_v3_handles(transport: Mapping[str, Any]) -> dict[str, Any]:
    """Résout et valide les handles. Lève si invalide. Aucune réparation."""
    return resolve_v3_handles(transport)


def validate_v3_resolved_links(resolved: Mapping[str, Any]) -> None:
    records = resolved.get("records")
    if not isinstance(records, list):
        raise WindowTransportValidationError("records absent")
    errors: list[str] = []
    kinds = [str(item.get("k") or "") for item in records]
    parsed = []
    for item in records:
        parsed.append(
            {
                "k": str(item.get("k") or ""),
                "v": str(item.get("v") or ""),
                "l": [int(link) for link in (item.get("l") or [])],
            }
        )
    for position, record in enumerate(parsed):
        _validate_links(record, position, kinds, errors)
    _validate_relation_uniqueness(parsed, errors)
    if errors:
        raise WindowTransportValidationError(" | ".join(errors))


def validate_v3_transport(
    transport: Mapping[str, Any],
    window: WindowInput,
) -> dict[str, Any]:
    """
    Validateur complet v3.

    Resolve handles puis réutilise source-ref / granularité / kinds v2
    sur la forme résolue. Ne décide aucune relation sémantique.
    """
    validate_v2_kinds(transport)
    validate_v2_no_editorial_leakage(transport)
    resolved = validate_v3_handles(transport)
    validate_v3_resolved_links(resolved)
    validate_v2_source_refs(resolved, window)
    validate_v2_transport_granularity(resolved)
    return resolved


__all__ = [
    "validate_v3_handles",
    "validate_v3_resolved_links",
    "validate_v3_transport",
]
