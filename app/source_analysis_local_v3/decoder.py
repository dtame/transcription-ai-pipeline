"""Decoder strict semantic-transport-v3. Parse symbolique. Aucune réparation."""

from __future__ import annotations

from typing import Any, Mapping

from app.source_analysis.errors import (
    SourceMapEditorialLeakError,
    SourceMapValidationError,
    WindowTransportValidationError,
)
from app.source_analysis.models import IDEA_KINDS, IMPORTANCE_LEVELS, forbidden_editorial_fields
from app.source_analysis.semantic_transport_decoder import (
    _metadata,
    _reject_unknown,
    _validate_kind_payload,
)
from app.source_analysis.ultra_compact_schema import KIND_IDEA
from app.source_analysis_local_v2.constants import DEFERRED_KINDS, LOCAL_KINDS
from app.source_analysis_local_v3.constants import (
    IDEA_METADATA_LAYOUT_LOCAL_LITE,
    IDEA_METADATA_LAYOUT_V3,
    SEMANTIC_TRANSPORT_VERSION_V3,
    SEMANTIC_TRANSPORT_VERSION_V31_LOCAL_LITE,
)
from app.source_analysis_local_v3.handles import owner_handle_for_kind, parse_link_handle
from app.source_analysis_local_v3.schema import V3_RECORD_FIELDS, V3_ROOT_FIELDS
from app.source_analysis_local_v3.source_refs import collect_v3_source_refs

_KNOWN_ROOT = frozenset(V3_ROOT_FIELDS)
_KNOWN_RECORD = frozenset(V3_RECORD_FIELDS)
_LOCAL = frozenset(LOCAL_KINDS)
_DEFERRED = frozenset(DEFERRED_KINDS)


def _validate_idea_payload_v31(
    *,
    value: str,
    source_refs: list[str],
    metadata: list[str],
    context: str,
    errors: list[str],
) -> None:
    if not source_refs:
        errors.append(f"{context} : s (source_refs) requis et non vide")
    if not value:
        errors.append(f"{context} : summary IDEA vide")
    if len(metadata) != 1:
        errors.append(f"{context} : IDEA local-lite exige m=[importance]")
        if len(metadata) >= 2:
            errors.append(
                f"{context} : IDEA local-lite refuse un sous-type « {metadata[0]} »"
            )
        return
    token = metadata[0]
    if token not in IMPORTANCE_LEVELS:
        errors.append(f"{context} : importance invalide « {token} »")
    if token in IDEA_KINDS:
        errors.append(
            f"{context} : IDEA local-lite refuse un sous-type « {token} » dans m[0]"
        )


def _parse_v3_record(
    item: Any,
    position: int,
    errors: list[str],
    allowed_source_refs: set[str] | None,
    *,
    idea_metadata_layout: str = IDEA_METADATA_LAYOUT_V3,
) -> dict | None:
    context = f"records[{position}]"
    if not isinstance(item, Mapping):
        errors.append(f"{context} : un objet est attendu")
        return None
    leaked = forbidden_editorial_fields(item)
    if leaked:
        raise SourceMapEditorialLeakError(
            leaked, location=f"semantic-transport-v3 / {context}"
        )
    try:
        _reject_unknown(item, _KNOWN_RECORD, context)
    except SourceMapValidationError as exc:
        errors.extend(exc.errors)
        return None

    kind = item.get("k")
    if not isinstance(kind, str) or not kind.strip():
        errors.append(f"{context} : k absent ou vide")
        return None
    kind = kind.strip()
    if kind in _DEFERRED:
        errors.append(f"{context} : kind différé interdit en v3 « {kind} »")
        return None
    if kind not in _LOCAL:
        errors.append(f"{context} : kind inconnu « {kind} »")
        return None

    value = item.get("v")
    if not isinstance(value, str):
        errors.append(f"{context} : v doit être une chaîne")
        return None
    value = value.strip()

    source_refs = collect_v3_source_refs(
        item.get("s"), context, errors, allowed_source_refs
    )
    metadata = _metadata(item.get("m"), context, errors)

    handle, handle_err = owner_handle_for_kind(kind, item.get("h"))
    if handle_err:
        errors.append(f"{context}.h : {handle_err}")
        handle = ""

    raw_links = item.get("l")
    link_handles: list[str] = []
    if raw_links is None:
        raw_links = []
    if not isinstance(raw_links, list):
        errors.append(f"{context}.l : une liste de handles est attendue")
        raw_links = []
    for index, raw in enumerate(raw_links):
        parsed, err = parse_link_handle(raw)
        if err:
            errors.append(f"{context}.l[{index}] : {err}")
            continue
        assert parsed is not None
        link_handles.append(parsed)

    if idea_metadata_layout == IDEA_METADATA_LAYOUT_LOCAL_LITE and kind == KIND_IDEA:
        _validate_idea_payload_v31(
            value=value,
            source_refs=source_refs,
            metadata=metadata,
            context=context,
            errors=errors,
        )
    else:
        _validate_kind_payload(
            kind=kind,
            value=value,
            source_refs=source_refs,
            links=link_handles,
            metadata=metadata,
            context=context,
            errors=errors,
        )

    return {
        "k": kind,
        "v": value,
        "s": source_refs,
        "h": handle or "",
        "l": link_handles,
        "m": metadata,
    }


def decode_v3_transport(
    payload: Mapping[str, Any],
    *,
    allowed_source_refs: set[str] | None = None,
) -> dict[str, Any]:
    """
    Parse strict symbolique. Pas de salvage JSON. Pas de resolve ici.

    Retourne le transport symbolique (h + l string). Le resolver est séparé.
    """
    if not isinstance(payload, Mapping):
        raise WindowTransportValidationError(
            f"réponse v3 inattendue : {type(payload).__name__}"
        )
    leaked = forbidden_editorial_fields(payload)
    if leaked:
        raise SourceMapEditorialLeakError(leaked, location="semantic-transport-v3")
    extra = [name for name in payload if name not in _KNOWN_ROOT]
    editorial_extra = forbidden_editorial_fields({key: True for key in extra})
    if editorial_extra:
        raise SourceMapEditorialLeakError(
            editorial_extra, location="semantic-transport-v3"
        )
    if extra:
        raise WindowTransportValidationError(f"champs racine inconnus : {extra}")

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
            record = _parse_v3_record(
                item,
                position,
                errors,
                allowed_source_refs,
                idea_metadata_layout=IDEA_METADATA_LAYOUT_V3,
            )
        except SourceMapValidationError as exc:
            errors.extend(exc.errors)
            continue
        if record is None:
            continue
        parsed.append(record)

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


def decode_v31_local_lite_transport(
    payload: Mapping[str, Any],
    *,
    allowed_source_refs: set[str] | None = None,
) -> dict[str, Any]:
    """
    Parse strict local-lite. IDEA.m = [importance] uniquement.
    Refuse silencieusement les anciens m=[subtype, importance].
    """
    if not isinstance(payload, Mapping):
        raise WindowTransportValidationError(
            f"réponse v3.1 inattendue : {type(payload).__name__}"
        )
    leaked = forbidden_editorial_fields(payload)
    if leaked:
        raise SourceMapEditorialLeakError(
            leaked, location="semantic-transport-v3.1-local-lite"
        )
    extra = [name for name in payload if name not in _KNOWN_ROOT]
    editorial_extra = forbidden_editorial_fields({key: True for key in extra})
    if editorial_extra:
        raise SourceMapEditorialLeakError(
            editorial_extra, location="semantic-transport-v3.1-local-lite"
        )
    if extra:
        raise WindowTransportValidationError(f"champs racine inconnus : {extra}")

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
            record = _parse_v3_record(
                item,
                position,
                errors,
                allowed_source_refs,
                idea_metadata_layout=IDEA_METADATA_LAYOUT_LOCAL_LITE,
            )
        except SourceMapValidationError as exc:
            errors.extend(exc.errors)
            continue
        if record is None:
            continue
        parsed.append(record)

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


def decode_transport(
    payload: Mapping[str, Any],
    *,
    transport_version: str,
    allowed_source_refs: set[str] | None = None,
) -> dict[str, Any]:
    """
    Décodage versionné. Aucune détection heuristique depuis le contenu.
    """
    if transport_version == SEMANTIC_TRANSPORT_VERSION_V3:
        return decode_v3_transport(payload, allowed_source_refs=allowed_source_refs)
    if transport_version == SEMANTIC_TRANSPORT_VERSION_V31_LOCAL_LITE:
        return decode_v31_local_lite_transport(
            payload, allowed_source_refs=allowed_source_refs
        )
    raise WindowTransportValidationError(
        f"transport version inconnue « {transport_version} » — "
        "aucune détection heuristique."
    )


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


__all__ = [
    "decode_transport",
    "decode_v3_transport",
    "decode_v31_local_lite_transport",
    "looks_like_truncated_json",
]
