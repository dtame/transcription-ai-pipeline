"""Parse / decoder / validator V2 après l'unique tentative. Pas de repair."""

from __future__ import annotations

from typing import Any

from app.ai.structured import parse_structured_output
from app.source_analysis_hybrid.contracts import WindowInput
from app.source_analysis_local_v2.constants import DEFERRED_KINDS, LOCAL_KINDS
from app.source_analysis_local_v2.decoder import decode_v2_transport
from app.source_analysis_local_v2.schema import build_semantic_transport_v2_schema
from app.source_analysis_local_v2.validator import validate_v2_transport, v2_capacity_signaled
from app.source_analysis_v2_real_win001.metrics import link_metrics


def interpret_response(
    parsed: dict[str, Any] | None,
    *,
    window: WindowInput,
    raw_text: str | None = None,
) -> dict[str, Any]:
    schema = build_semantic_transport_v2_schema()
    structured = "FAIL"
    decoder = "FAIL"
    validator = "FAIL"
    transport: dict[str, Any] | None = None
    errors: list[str] = []

    payload = parsed
    if payload is None and raw_text:
        try:
            payload = parse_structured_output(raw_text, schema)
            structured = "PASS"
        except Exception as exc:
            errors.append(str(exc))
            return {
                "structured_parse": structured,
                "v2_decoder": decoder,
                "v2_validator": validator,
                "transport": None,
                "kinds": [],
                "source_refs": [],
                "deferred_kinds": [],
                "capacity_signal": False,
                "links": link_metrics(None),
                "errors": errors,
            }
    elif payload is not None:
        if raw_text:
            try:
                parse_structured_output(raw_text, schema)
                structured = "PASS"
            except Exception as exc:
                errors.append(str(exc))
                structured = "FAIL"
        else:
            structured = "PASS"

    if not isinstance(payload, dict):
        errors.append("parsed payload is not an object")
        return {
            "structured_parse": structured,
            "v2_decoder": decoder,
            "v2_validator": validator,
            "transport": None,
            "kinds": [],
            "source_refs": [],
            "deferred_kinds": [],
            "capacity_signal": False,
            "links": link_metrics(None),
            "errors": errors,
        }

    allowed = set(window.owned_src_refs) | set(window.context_src_refs)
    try:
        transport = decode_v2_transport(payload, allowed_source_refs=allowed)
        decoder = "PASS"
    except Exception as exc:
        errors.append(str(exc))
        return {
            "structured_parse": structured,
            "v2_decoder": decoder,
            "v2_validator": validator,
            "transport": payload,
            "kinds": [
                str(item.get("k"))
                for item in (payload.get("records") or [])
                if isinstance(item, dict)
            ],
            "source_refs": [],
            "deferred_kinds": [],
            "capacity_signal": v2_capacity_signaled(payload),
            "links": link_metrics(payload),
            "errors": errors,
        }

    try:
        validate_v2_transport(transport, window)
        validator = "PASS"
    except Exception as exc:
        errors.append(str(exc))

    kinds = [
        str(item.get("k"))
        for item in (transport.get("records") or [])
        if isinstance(item, dict)
    ]
    refs: list[str] = []
    for item in transport.get("records") or []:
        if not isinstance(item, dict):
            continue
        for ref in item.get("s") or []:
            if isinstance(ref, str) and ref.strip():
                refs.append(ref.strip())
    deferred = [kind for kind in kinds if kind in DEFERRED_KINDS]
    unknown = [kind for kind in kinds if kind not in LOCAL_KINDS and kind not in DEFERRED_KINDS]
    if deferred or unknown:
        validator = "FAIL"
        errors.append(f"forbidden or unknown kinds: {deferred + unknown}")
    links = link_metrics(transport)
    if not links["links_valid"] and validator == "PASS":
        validator = "FAIL"
        errors.append("link graph invalid")
    return {
        "structured_parse": structured,
        "v2_decoder": decoder,
        "v2_validator": validator,
        "transport": transport,
        "kinds": kinds,
        "source_refs": refs,
        "deferred_kinds": deferred,
        "capacity_signal": v2_capacity_signaled(transport),
        "links": links,
        "errors": errors,
    }


__all__ = ["interpret_response"]
