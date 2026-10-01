"""Interprétation A.38 : decoder 1.1 + validator v11 + enums + canonical."""

from __future__ import annotations

from typing import Any, Mapping

from app.ai.structured import validate_payload
from app.source_analysis.transcript_input import TranscriptInput
from app.source_analysis_v31_global_canary_forensics.transport_v11 import (
    NEXT_TRANSPORT_VERSION,
    build_global_consolidation_schema_v11,
)
from app.source_analysis_v31_global_canary_forensics.validator_v11 import (
    validate_global_transport_v11,
)
from app.source_analysis_v31_global_grammar_canary.decoder import decode_global_transport
from app.source_analysis_v31_global_grammar_canary.handles import inspect_global_handles
from app.source_analysis_v31_global_v11_grammar_canary.enums import audit_raw_enums
from app.source_analysis_v31_global_real_consolidation.constants import (
    EXPECTED_IDEA,
    IDEA_DISPOSITION_COVERAGE_REQUIRED,
)
from app.source_analysis_v31_global_real_consolidation.input_contract import (
    allowed_input_ids,
    allowed_source_refs,
    local_src_by_input,
)
from app.source_analysis_v31_global_real_consolidation.reconstruct import (
    reconstruct_source_map,
    replay_reconstruction,
    source_map_public_view,
)


def audit_traceability(
    transport: Mapping[str, Any] | None,
    *,
    allowed_refs: set[str],
) -> dict[str, Any]:
    errors: list[str] = []
    unknown_src: list[str] = []
    missing: list[str] = []
    if not isinstance(transport, Mapping):
        return {"ok": False, "status": "FAIL", "errors": ["transport missing"]}
    for index, node in enumerate(transport.get("n") or []):
        if not isinstance(node, dict):
            continue
        kind = str(node.get("k") or "")
        refs = [str(item) for item in (node.get("s") or [])]
        if kind in {"TOPIC", "IDEA", "EXAMPLE", "REFERENCE", "UNCERTAINTY", "REPETITION"}:
            if not refs:
                missing.append(f"n[{index}] {kind}")
            for ref in refs:
                if ref not in allowed_refs:
                    unknown_src.append(ref)
    ok = not errors and not unknown_src and not missing
    return {
        "ok": ok,
        "status": "PASS" if ok else "FAIL",
        "unknown_source_refs": unknown_src,
        "missing_source_evidence": missing,
        "errors": errors,
    }


def merge_source_union_status(validator: Mapping[str, Any]) -> str:
    errors = [str(err) for err in (validator.get("errors") or [])]
    if any("missing SRC union" in err for err in errors):
        return "FAIL"
    return "PASS" if validator.get("ok") else (
        "FAIL" if any("MERGE_EQUIVALENT" in err and "SRC" in err for err in errors) else "PASS"
    )


def interpret_real_response(
    parsed: dict[str, Any] | None,
    *,
    normalized: Mapping[str, Any],
    transcript: TranscriptInput,
    raw_text: str | None = None,
    signature: str = "",
    finish_reason: str | None = None,
) -> dict[str, Any]:
    if str(finish_reason or "") == "max_tokens":
        return {
            "structured_parse": "FAIL",
            "decoder": "FAIL",
            "handle_validation": "FAIL",
            "global_validator": "FAIL",
            "canonical_reconstruction": "FAIL",
            "canonical_validation": "FAIL",
            "deterministic_replay": "FAIL",
            "idea_disposition_coverage": 0.0,
            "silent_drops": EXPECTED_IDEA,
            "errors": ["max_tokens finish — partial JSON is not success"],
            "transport": None,
            "max_tokens_failure": True,
        }
    decoded = decode_global_transport(parsed, raw_text=raw_text)
    working = (
        decoded.get("transport") if isinstance(decoded.get("transport"), dict) else parsed
    )
    schema = build_global_consolidation_schema_v11()
    structured = "FAIL"
    if isinstance(working, dict):
        try:
            validate_payload(working, schema)
            structured = "PASS"
        except Exception as exc:  # noqa: BLE001 — forensic, no repair
            structured = "FAIL"
            decoded.setdefault("errors", []).append(str(exc))
    transport = working if isinstance(working, dict) else None
    handles = inspect_global_handles(transport)
    idea_ids = list(normalized.get("idea_input_ids") or [])
    local_src = local_src_by_input(dict(normalized))
    allowed_ids = allowed_input_ids(dict(normalized))
    allowed_refs = allowed_source_refs(dict(normalized))
    validator = (
        validate_global_transport_v11(
            transport,
            idea_input_ids=idea_ids,
            allowed_input_ids=allowed_ids,
            allowed_source_refs=allowed_refs,
            local_src_by_input=local_src,
        )
        if isinstance(transport, dict)
        else {
            "ok": False,
            "errors": ["transport missing"],
            "idea_disposition_coverage": 0.0,
            "silent_drop_count": len(idea_ids) or EXPECTED_IDEA,
            "silent_drops": list(idea_ids),
        }
    )
    enums = audit_raw_enums(transport)
    traceability = audit_traceability(transport, allowed_refs=allowed_refs)
    reconstruction = None
    replay = None
    if isinstance(transport, dict):
        reconstruction = reconstruct_source_map(
            transport, transcript, signature=signature or "a38"
        )
        replay = replay_reconstruction(
            transport, transcript, signature=signature or "a38"
        )
    silent = int(validator.get("silent_drop_count") or 0)
    coverage = float(validator.get("idea_disposition_coverage") or 0)
    merge_union = merge_source_union_status(validator)
    if enums.get("status") != "PASS":
        validator = dict(validator)
        validator["ok"] = False
        validator.setdefault("errors", []).extend(enums.get("matrix_violations") or [])
    idea_rows = [
        row
        for row in (enums.get("rows") or [])
        if str(row.get("i") or "") in set(idea_ids)
    ]
    keep = sum(1 for row in idea_rows if row.get("o") == "KEEP")
    merge = sum(1 for row in idea_rows if row.get("o") == "MERGE_EQUIVALENT")
    drop = sum(1 for row in idea_rows if row.get("o") == "DROP")
    other = sum(1 for row in idea_rows if row.get("o") == "OTHER")
    return {
        "structured_parse": structured,
        "decoder": decoded.get("decoder"),
        "handle_validation": handles.get("handle_validation"),
        "handles": handles,
        "global_validator": "PASS" if validator.get("ok") else "FAIL",
        "validator": validator,
        "idea_disposition_coverage": coverage,
        "coverage_required": IDEA_DISPOSITION_COVERAGE_REQUIRED,
        "silent_drops": silent,
        "silent_drop_ids": validator.get("silent_drops") or [],
        "no_drop_validator": "PASS" if silent == 0 else "FAIL",
        "traceability": traceability.get("status"),
        "traceability_detail": traceability,
        "canonical_reconstruction": (
            "PASS" if reconstruction and reconstruction.get("ok") else "FAIL"
        ),
        "canonical_validation": (
            reconstruction.get("validate_source_map") if reconstruction else "FAIL"
        ),
        "deterministic_replay": replay.get("status") if replay else "FAIL",
        "reconstruction": (
            source_map_public_view(reconstruction) if reconstruction else None
        ),
        "reconstruction_raw": reconstruction,
        "replay": replay,
        "enum_audit": enums,
        "d_o_enum": "PASS" if enums.get("unknown_do_count") == 0 else "FAIL",
        "d_w_enum": "PASS" if enums.get("unknown_dw_count") == 0 else "FAIL",
        "free_text_drop_reason": enums.get("free_text_dw_count"),
        "link_related_count": enums.get("link_related_count"),
        "operation_reason_matrix": enums.get("matrix_status"),
        "matrix_violations": enums.get("matrix_violations"),
        "keep_count": keep,
        "merge_equivalent_count": merge,
        "drop_count": drop,
        "other_count": other,
        "observed_dw_tokens": enums.get("observed_dw_tokens"),
        "merge_source_union": merge_union,
        "inventory": decoded.get("inventory"),
        "errors": list(decoded.get("errors") or []) + list(validator.get("errors") or []),
        "transport": transport,
        "repaired": False,
        "transport_version": NEXT_TRANSPORT_VERSION,
        "max_tokens_failure": False,
    }


__all__ = [
    "audit_traceability",
    "interpret_real_response",
    "merge_source_union_status",
]
