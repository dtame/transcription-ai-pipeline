"""Validateur strict semantic-transport-v2. Après parse. Pas de repair."""

from __future__ import annotations

from typing import Any, Mapping

from app.source_analysis.errors import (
    WindowSourceRefError,
    WindowTransportValidationError,
)
from app.source_analysis.models import forbidden_editorial_fields
from app.source_analysis.window_models import (
    OWNERSHIP_RULE,
    allowed_window_source_refs,
    owned_source_refs,
)
from app.source_analysis_hybrid.contracts import WindowInput
from app.source_analysis.semantic_transport_decoder import (
    _validate_links,
    _validate_relation_uniqueness,
)
from app.source_analysis_local_v2.constants import DEFERRED_KINDS, LOCAL_KINDS
from app.source_analysis_local_v2.links import validate_v2_link_semantics
from app.source_analysis_local_v2.granularity import (
    transport_signals_overflow,
    validate_v2_transport_granularity,
)

_SUBSTANTIVE = frozenset(
    {"TOPIC", "IDEA", "EXAMPLE", "REFERENCE", "UNCERTAINTY"}
)
_DEFERRED = frozenset(DEFERRED_KINDS)
_LOCAL = frozenset(LOCAL_KINDS)
_EDITORIAL_HINTS = (
    "chapter",
    "chapitre",
    "book title",
    "titre du livre",
    "outline",
    "table of contents",
)


def validate_v2_source_refs(
    transport: Mapping[str, Any],
    window: WindowInput,
) -> None:
    allowed = allowed_window_source_refs(window)
    owned = owned_source_refs(window)
    records = transport.get("records")
    if not isinstance(records, list):
        return
    errors: list[str] = []
    for index, item in enumerate(records):
        if not isinstance(item, Mapping):
            continue
        refs = item.get("s") or []
        if not isinstance(refs, list):
            continue
        kind = str(item.get("k") or "")
        present = [str(ref).strip() for ref in refs if isinstance(ref, str)]
        unknown = [ref for ref in present if ref not in allowed]
        if unknown:
            errors.append(f"records[{index}] : source_ref hors fenêtre {unknown}")
            continue
        if kind in _SUBSTANTIVE:
            if not present:
                errors.append(
                    f"records[{index}] : record substantif {kind} sans source_ref"
                )
                continue
            if not any(ref in owned for ref in present):
                errors.append(
                    f"records[{index}] : {kind} fondé uniquement sur CONTEXT-ONLY "
                    f"{present} — interdit ({OWNERSHIP_RULE})"
                )
    if errors:
        raise WindowSourceRefError(" | ".join(errors))


def validate_v2_kinds(transport: Mapping[str, Any]) -> None:
    records = transport.get("records")
    if not isinstance(records, list):
        raise WindowTransportValidationError("records absent")
    errors: list[str] = []
    for index, item in enumerate(records):
        if not isinstance(item, Mapping):
            errors.append(f"records[{index}] : objet attendu")
            continue
        kind = str(item.get("k") or "")
        if kind in _DEFERRED:
            errors.append(f"records[{index}] : kind différé {kind}")
        elif kind not in _LOCAL:
            errors.append(f"records[{index}] : kind inconnu {kind}")
    if errors:
        raise WindowTransportValidationError(" | ".join(errors))


def validate_v2_no_editorial_leakage(transport: Mapping[str, Any]) -> None:
    leaked = forbidden_editorial_fields(transport)
    if leaked:
        raise WindowTransportValidationError(
            f"fuite éditoriale : {leaked}"
        )
    blob = " ".join(
        [
            str(transport.get("theme") or ""),
            str(transport.get("intent") or ""),
            str(transport.get("aud") or ""),
        ]
    ).lower()
    hits = [hint for hint in _EDITORIAL_HINTS if hint in blob]
    if hits:
        raise WindowTransportValidationError(
            f"fuite éditoriale détectable dans les notes locales : {hits}"
        )


def validate_v2_links(transport: Mapping[str, Any]) -> None:
    """
    Validité sémantique des liens — distincte de la validité du schéma provider.

    Réapplique les règles v1 héritées plus l'auto-lien / doublon V2.
    """
    records = transport.get("records")
    if not isinstance(records, list):
        raise WindowTransportValidationError("records absent")
    parsed: list[dict[str, Any]] = []
    for index, item in enumerate(records):
        if not isinstance(item, Mapping):
            raise WindowTransportValidationError(f"records[{index}] : objet attendu")
        links = item.get("l") or []
        if not isinstance(links, list):
            raise WindowTransportValidationError(f"records[{index}].l : liste attendue")
        parsed.append(
            {
                "k": str(item.get("k") or ""),
                "v": str(item.get("v") or ""),
                "l": [int(link) for link in links if isinstance(link, int) and not isinstance(link, bool)],
            }
        )
    errors: list[str] = []
    kinds = [record["k"] for record in parsed]
    for position, record in enumerate(parsed):
        _validate_links(record, position, kinds, errors)
    validate_v2_link_semantics(parsed, errors)
    _validate_relation_uniqueness(parsed, errors)
    if errors:
        raise WindowTransportValidationError(" | ".join(errors))


def validate_v2_transport(
    transport: Mapping[str, Any],
    window: WindowInput,
) -> None:
    """
    Validateur complet. Overflow (capacité) prime sur les plafonds.

    Distingue : signal de capacité ≠ troncature max_tokens.
    """
    validate_v2_kinds(transport)
    validate_v2_no_editorial_leakage(transport)
    validate_v2_links(transport)
    validate_v2_source_refs(transport, window)
    validate_v2_transport_granularity(transport)


def v2_capacity_signaled(transport: Mapping[str, Any]) -> bool:
    return transport_signals_overflow(transport)
