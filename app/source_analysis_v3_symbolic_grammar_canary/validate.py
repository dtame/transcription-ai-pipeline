"""Parse / decoder / registry / resolver / validator V3. Pas de repair."""

from __future__ import annotations

from typing import Any

from app.ai.structured import parse_structured_output
from app.source_analysis_hybrid.contracts import WindowInput
from app.source_analysis_local_v2.constants import DEFERRED_KINDS, LOCAL_KINDS
from app.source_analysis_local_v2.validator import v2_capacity_signaled
from app.source_analysis_local_v3.decoder import decode_v3_transport
from app.source_analysis_local_v3.resolver import build_handle_registry, resolve_v3_handles
from app.source_analysis_local_v3.schema import build_semantic_transport_v3_schema
from app.source_analysis_local_v3.validator import validate_v3_transport
from app.source_analysis_v3_symbolic_grammar_canary.constants import SYNTHETIC_SRC_IDS
from app.source_analysis_v3_symbolic_grammar_canary.guard import SymbolicGrammarCanaryError
from app.source_analysis_v3_symbolic_grammar_canary.handles import (
    inspect_handle_metrics,
    reconstruct_diagnostic,
)


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
        raise SymbolicGrammarCanaryError(
            f"Non-synthetic source refs in response: {unknown}."
        )


def interpret_canary_response(
    parsed: dict[str, Any] | None,
    *,
    window: WindowInput,
    raw_text: str | None = None,
    signature: str = "",
) -> dict[str, Any]:
    schema = build_semantic_transport_v3_schema()
    structured = "FAIL"
    decoder = "FAIL"
    registry_status = "FAIL"
    resolution = "FAIL"
    validator = "FAIL"
    reconstruction: dict[str, Any] | None = None
    transport: dict[str, Any] | None = None
    errors: list[str] = []

    payload = parsed
    if payload is None and raw_text:
        try:
            payload = parse_structured_output(raw_text, schema)
            structured = "PASS"
        except Exception as exc:
            errors.append(str(exc))
            metrics = inspect_handle_metrics(None)
            return {
                "structured_parse": structured,
                "v3_decoder": decoder,
                "handle_registry": registry_status,
                "handle_resolution": resolution,
                "v3_validator": validator,
                "transport": None,
                "kinds": [],
                "source_refs": [],
                "deferred_kinds": [],
                "capacity_signal": False,
                "errors": errors,
                "handles": metrics,
                "reconstruction": None,
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
            "v3_decoder": decoder,
            "handle_registry": registry_status,
            "handle_resolution": resolution,
            "v3_validator": validator,
            "transport": None,
            "kinds": [],
            "source_refs": [],
            "deferred_kinds": [],
            "capacity_signal": False,
            "errors": errors,
            "handles": inspect_handle_metrics(None),
            "reconstruction": None,
        }

    metrics = inspect_handle_metrics(payload)
    allowed = set(window.owned_src_refs) | set(window.context_src_refs)
    try:
        transport = decode_v3_transport(payload, allowed_source_refs=allowed)
        decoder = "PASS"
    except Exception as exc:
        errors.append(str(exc))
        kinds = collect_kinds(payload)
        refs = collect_source_refs(payload)
        return {
            "structured_parse": structured,
            "v3_decoder": decoder,
            "handle_registry": registry_status,
            "handle_resolution": resolution,
            "v3_validator": validator,
            "transport": payload,
            "kinds": kinds,
            "source_refs": refs,
            "deferred_kinds": [kind for kind in kinds if kind in DEFERRED_KINDS],
            "capacity_signal": v2_capacity_signaled(payload),
            "errors": errors,
            "handles": metrics,
            "reconstruction": None,
        }

    registry_errors: list[str] = []
    try:
        build_handle_registry(transport.get("records") or [], registry_errors)
        if registry_errors:
            raise RuntimeError(" | ".join(registry_errors))
        registry_status = "PASS"
    except Exception as exc:
        errors.append(str(exc))

    try:
        resolve_v3_handles(transport)
        resolution = "PASS"
    except Exception as exc:
        errors.append(str(exc))

    try:
        validate_v3_transport(transport, window)
        validator = "PASS"
    except Exception as exc:
        errors.append(str(exc))

    kinds = collect_kinds(transport)
    refs = collect_source_refs(transport)
    deferred = [kind for kind in kinds if kind in DEFERRED_KINDS]
    try:
        assert_synthetic_refs_only(refs)
    except SymbolicGrammarCanaryError as exc:
        errors.append(str(exc))
        validator = "FAIL"

    unknown_kinds = [kind for kind in kinds if kind not in LOCAL_KINDS]
    if deferred or unknown_kinds:
        validator = "FAIL"
        errors.append(f"forbidden or unknown kinds: {deferred + unknown_kinds}")

    if (
        structured == "PASS"
        and decoder == "PASS"
        and registry_status == "PASS"
        and resolution == "PASS"
        and validator == "PASS"
    ):
        try:
            reconstruction = reconstruct_diagnostic(
                transport, window, signature=signature
            )
        except Exception as exc:
            errors.append(str(exc))
            reconstruction = None

    return {
        "structured_parse": structured,
        "v3_decoder": decoder,
        "handle_registry": registry_status,
        "handle_resolution": resolution,
        "v3_validator": validator,
        "transport": transport,
        "kinds": kinds,
        "source_refs": refs,
        "deferred_kinds": deferred,
        "capacity_signal": v2_capacity_signaled(transport),
        "errors": errors,
        "handles": inspect_handle_metrics(transport),
        "reconstruction": reconstruction,
    }


__all__ = [
    "assert_synthetic_refs_only",
    "collect_kinds",
    "collect_source_refs",
    "interpret_canary_response",
]
