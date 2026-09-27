"""Decoder strict semantic-transport-v2. Aucune réparation."""

from __future__ import annotations

from typing import Any, Mapping

from app.source_analysis.errors import (
    SourceMapEditorialLeakError,
    SourceMapValidationError,
    WindowTransportValidationError,
)
from app.source_analysis.models import forbidden_editorial_fields
from app.source_analysis.semantic_transport_decoder import (
    _parse_record,
    _validate_links,
    _validate_relation_uniqueness,
)
from app.source_analysis_local_v2.constants import DEFERRED_KINDS, LOCAL_KINDS
from app.source_analysis_local_v2.links import validate_v2_link_semantics
from app.source_analysis_local_v2.schema import V2_ROOT_FIELDS

_KNOWN_ROOT = frozenset(V2_ROOT_FIELDS)
_LOCAL = frozenset(LOCAL_KINDS)
_DEFERRED = frozenset(DEFERRED_KINDS)


def decode_v2_transport(
    payload: Mapping[str, Any],
    *,
    allowed_source_refs: set[str] | None = None,
) -> dict[str, Any]:
    """
    Parse strict. Pas de salvage JSON. Pas de repair de prefix.

    Retourne le transport normalisé (records parsés), pas un SourceMap.
    """
    if not isinstance(payload, Mapping):
        raise WindowTransportValidationError(
            f"réponse v2 inattendue : {type(payload).__name__}"
        )
    leaked = forbidden_editorial_fields(payload)
    if leaked:
        raise SourceMapEditorialLeakError(leaked, location="semantic-transport-v2")
    extra = [name for name in payload if name not in _KNOWN_ROOT]
    editorial_extra = forbidden_editorial_fields({key: True for key in extra})
    if editorial_extra:
        raise SourceMapEditorialLeakError(
            editorial_extra, location="semantic-transport-v2"
        )
    if extra:
        raise WindowTransportValidationError(
            f"champs racine inconnus : {extra}"
        )

    errors: list[str] = []
    for field in ("theme", "intent", "ic", "aud", "ac"):
        value = payload.get(field)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{field} vide")

    raw_records = payload.get("records")
    if not isinstance(raw_records, list):
        errors.append("records : une liste est attendue")
        raw_records = []

    parsed: list[dict] = []
    for position, item in enumerate(raw_records):
        try:
            record = _parse_record(item, position, errors, allowed_source_refs)
        except SourceMapValidationError as exc:
            errors.extend(exc.errors)
            continue
        if record is None:
            continue
        kind = record["k"]
        if kind in _DEFERRED:
            errors.append(
                f"records[{position}] : kind différé interdit en v2 « {kind} »"
            )
            continue
        if kind not in _LOCAL:
            errors.append(f"records[{position}] : kind inconnu « {kind} »")
            continue
        parsed.append(record)

    kinds = [record["k"] for record in parsed]
    for position, record in enumerate(parsed):
        _validate_links(record, position, kinds, errors)
    validate_v2_link_semantics(parsed, errors)
    _validate_relation_uniqueness(parsed, errors)

    if errors:
        raise WindowTransportValidationError(" | ".join(errors))

    return {
        "theme": str(payload.get("theme") or "").strip(),
        "intent": str(payload.get("intent") or "").strip(),
        "ic": str(payload.get("ic") or "").strip(),
        "aud": str(payload.get("aud") or "").strip(),
        "ac": str(payload.get("ac") or "").strip(),
        "records": parsed,
    }


def looks_like_truncated_json(text: str) -> bool:
    raw = (text or "").strip()
    if not raw:
        return True
    try:
        import json

        json.loads(raw)
        return False
    except Exception:
        return True
