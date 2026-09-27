"""Parse / decoder / validator V2 après l'unique tentative. Pas de repair."""

from __future__ import annotations

from typing import Any

from app.ai.structured import parse_structured_output
from app.source_analysis_hybrid.contracts import WindowInput
from app.source_analysis_local_v2.constants import DEFERRED_KINDS, LOCAL_KINDS
from app.source_analysis_local_v2.decoder import decode_v2_transport
from app.source_analysis_local_v2.schema import build_semantic_transport_v2_schema
from app.source_analysis_local_v2.validator import validate_v2_transport, v2_capacity_signaled
from app.source_analysis_v2_grammar_canary.constants import SYNTHETIC_SRC_IDS
from app.source_analysis_v2_grammar_canary.guard import GrammarCanaryError


def collect_kinds(transport: dict[str, Any]) -> list[str]:
    records = transport.get("records") or []
    kinds: list[str] = []
    for item in records:
        if isinstance(item, dict) and item.get("k"):
            kinds.append(str(item["k"]))
    return kinds


def collect_source_refs(transport: dict[str, Any]) -> list[str]:
    refs: list[str] = []
    for item in transport.get("records") or []:
        if not isinstance(item, dict):
            continue
        for ref in item.get("s") or []:
            if isinstance(ref, str) and ref.strip():
                refs.append(ref.strip())
    return refs


def assert_synthetic_refs_only(refs: list[str]) -> None:
    unknown = [ref for ref in refs if ref not in SYNTHETIC_SRC_IDS]
    if unknown:
        raise GrammarCanaryError(
            f"Non-synthetic source refs in response: {unknown}."
        )


def interpret_canary_response(
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
            "errors": errors,
        }

    allowed = set(window.owned_src_refs) | set(window.context_src_refs)
    try:
        transport = decode_v2_transport(payload, allowed_source_refs=allowed)
        decoder = "PASS"
    except Exception as exc:
        errors.append(str(exc))
        kinds = collect_kinds(payload)
        refs = collect_source_refs(payload)
        return {
            "structured_parse": structured,
            "v2_decoder": decoder,
            "v2_validator": validator,
            "transport": payload,
            "kinds": kinds,
            "source_refs": refs,
            "deferred_kinds": [kind for kind in kinds if kind in DEFERRED_KINDS],
            "capacity_signal": v2_capacity_signaled(payload),
            "errors": errors,
        }

    try:
        validate_v2_transport(transport, window)
        validator = "PASS"
    except Exception as exc:
        errors.append(str(exc))

    kinds = collect_kinds(transport)
    refs = collect_source_refs(transport)
    deferred = [kind for kind in kinds if kind in DEFERRED_KINDS]
    try:
        assert_synthetic_refs_only(refs)
    except GrammarCanaryError as exc:
        errors.append(str(exc))
        validator = "FAIL"

    unknown_kinds = [kind for kind in kinds if kind not in LOCAL_KINDS]
    if deferred or unknown_kinds:
        validator = "FAIL"
        errors.append(f"forbidden or unknown kinds: {deferred + unknown_kinds}")

    return {
        "structured_parse": structured,
        "v2_decoder": decoder,
        "v2_validator": validator,
        "transport": transport,
        "kinds": kinds,
        "source_refs": refs,
        "deferred_kinds": deferred,
        "capacity_signal": v2_capacity_signaled(transport),
        "errors": errors,
    }


__all__ = [
    "assert_synthetic_refs_only",
    "collect_kinds",
    "collect_source_refs",
    "interpret_canary_response",
]
