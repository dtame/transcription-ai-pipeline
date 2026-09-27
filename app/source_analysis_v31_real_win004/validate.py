"""Parse / decoder v3.1-local-lite / registry / resolver / validator + audit SRC."""

from __future__ import annotations

from typing import Any

from app.ai.structured import parse_structured_output
from app.source_analysis_hybrid.contracts import WindowInput
from app.source_analysis_local_v2.constants import DEFERRED_KINDS, LOCAL_KINDS
from app.source_analysis_local_v2.validator import v2_capacity_signaled
from app.source_analysis_local_v3.decoder import decode_v31_local_lite_transport
from app.source_analysis_local_v3.resolver import build_handle_registry, resolve_v3_handles
from app.source_analysis_local_v3.schema import build_semantic_transport_v31_local_lite_schema
from app.source_analysis_local_v3.validator import validate_v3_transport
from app.source_analysis_v3_a19_forensics.constants import EXAMPLE_POLICY
from app.source_analysis_v3_a19_forensics.forensic_validator import (
    collect_transport_violations,
)
from app.source_analysis_v3_a19_forensics.src_audit import audit_source_refs
from app.source_analysis_v3_hardened_win001.validate import src_success_metrics
from app.source_analysis_v3_real_win001.validate import collect_kinds, collect_source_refs
from app.source_analysis_v31_real_win004.constants import MODE, PHASE, SCHEMA_VERSION
from app.source_analysis_v31_real_win004.handles import (
    handle_gate_status,
    inspect_symbolic_refs,
)
from app.source_analysis_v31_real_win004.metadata import audit_local_lite_idea_metadata


def _empty_result(*, structured: str, errors: list[str], handles: dict[str, Any] | None = None):
    metrics = handles or inspect_symbolic_refs(None)
    return {
        "structured_parse": structured,
        "v31_decoder": "FAIL",
        "v3_decoder": "FAIL",
        "handle_registry": "FAIL",
        "handle_resolution": "FAIL",
        "v31_validator": "FAIL",
        "v3_validator": "FAIL",
        "transport": None,
        "kinds": [],
        "source_refs": [],
        "deferred_kinds": [],
        "capacity_signal": False,
        "errors": errors,
        "handles": metrics,
        "handle_gate": handle_gate_status(metrics),
        "metadata": audit_local_lite_idea_metadata(None),
    }


def interpret_local_lite_response(
    parsed: dict[str, Any] | None,
    *,
    window: WindowInput,
    raw_text: str | None = None,
) -> dict[str, Any]:
    schema = build_semantic_transport_v31_local_lite_schema()
    structured = "FAIL"
    decoder = "FAIL"
    registry_status = "FAIL"
    resolution = "FAIL"
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
            return _empty_result(structured=structured, errors=errors)
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
        return _empty_result(structured=structured, errors=errors)

    metrics = inspect_symbolic_refs(payload)
    allowed = set(window.owned_src_refs) | set(window.context_src_refs)
    try:
        transport = decode_v31_local_lite_transport(payload, allowed_source_refs=allowed)
        decoder = "PASS"
    except Exception as exc:
        errors.append(str(exc))
        kinds = collect_kinds(payload)
        refs = collect_source_refs(payload)
        metadata = audit_local_lite_idea_metadata(payload)
        src_audit = dict(audit_source_refs(payload, window))
        src_audit.update({"schema_version": SCHEMA_VERSION, "phase": PHASE, "mode": MODE})
        return {
            "structured_parse": structured,
            "v31_decoder": decoder,
            "v3_decoder": decoder,
            "handle_registry": registry_status,
            "handle_resolution": resolution,
            "v31_validator": validator,
            "v3_validator": validator,
            "transport": payload,
            "kinds": kinds,
            "source_refs": refs,
            "deferred_kinds": [kind for kind in kinds if kind in DEFERRED_KINDS],
            "capacity_signal": v2_capacity_signaled(payload),
            "errors": errors,
            "handles": metrics,
            "handle_gate": handle_gate_status(metrics),
            "metadata": metadata,
            "src_audit": src_audit,
            "src_forensic": src_success_metrics(src_audit),
            "inventory": {},
            "example_policy": EXAMPLE_POLICY,
            "normalized": False,
        }

    metrics = inspect_symbolic_refs(transport)
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
    unknown_kinds = [
        kind for kind in kinds if kind not in LOCAL_KINDS and kind not in DEFERRED_KINDS
    ]
    if deferred or unknown_kinds:
        validator = "FAIL"
        errors.append(f"forbidden or unknown kinds: {deferred + unknown_kinds}")

    gate = handle_gate_status(metrics)
    if not gate["handle_gate_pass"] and validator == "PASS":
        validator = "FAIL"
        errors.append("handle gate failed")

    src_audit = dict(audit_source_refs(transport, window))
    src_audit.update({"schema_version": SCHEMA_VERSION, "phase": PHASE, "mode": MODE})
    owned = set(window.owned_src_refs)
    inventory = dict(
        collect_transport_violations(
            transport,
            allowed=allowed,
            owned=owned,
            example_policy=EXAMPLE_POLICY,
        )
    )
    inventory.update({"schema_version": SCHEMA_VERSION, "phase": PHASE, "mode": MODE})
    metadata = audit_local_lite_idea_metadata(transport)
    if not metadata["local_lite_metadata_pass"] and validator == "PASS":
        validator = "FAIL"
        errors.append("local-lite IDEA metadata failed")

    return {
        "structured_parse": structured,
        "v31_decoder": decoder,
        "v3_decoder": decoder,
        "handle_registry": registry_status,
        "handle_resolution": resolution,
        "v31_validator": validator,
        "v3_validator": validator,
        "transport": transport,
        "kinds": kinds,
        "source_refs": refs,
        "deferred_kinds": deferred,
        "capacity_signal": v2_capacity_signaled(transport),
        "errors": errors,
        "handles": metrics,
        "handle_gate": gate,
        "src_audit": src_audit,
        "src_forensic": src_success_metrics(src_audit),
        "inventory": inventory,
        "metadata": metadata,
        "example_policy": EXAMPLE_POLICY,
        "normalized": False,
    }


interpret_hardened_response = interpret_local_lite_response


__all__ = [
    "interpret_hardened_response",
    "interpret_local_lite_response",
    "src_success_metrics",
]
