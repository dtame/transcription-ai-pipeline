"""Interprétation canary A.37 : decoder 1.1 + validator v11 + enums + canonical."""

from __future__ import annotations

from typing import Any

from app.ai.structured import validate_payload
from app.source_analysis_v31_global_canary_forensics.fixture import (
    interpret_transport_v11,
    next_expected_dispositions,
    review_semantic_v11,
)
from app.source_analysis_v31_global_canary_forensics.transport_v11 import (
    NEXT_TRANSPORT_VERSION,
    build_global_consolidation_schema_v11,
)
from app.source_analysis_v31_global_grammar_canary.decoder import decode_global_transport
from app.source_analysis_v31_global_grammar_canary.fixture import (
    SyntheticConsolidationFixture,
)
from app.source_analysis_v31_global_v11_grammar_canary.enums import audit_raw_enums


def interpret_canary_response_v11(
    parsed: dict[str, Any] | None,
    *,
    fixture: SyntheticConsolidationFixture,
    raw_text: str | None = None,
    signature: str = "",
) -> dict[str, Any]:
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
    interpreted = interpret_transport_v11(
        working if isinstance(working, dict) else None,
        raw_text=raw_text,
        signature=signature or "a37-v11",
    )
    interpreted["structured_parse"] = structured
    enums = audit_raw_enums(interpreted.get("transport"))
    semantic = review_semantic_v11(interpreted.get("transport"))
    transport = interpreted.get("transport")
    relations = []
    if isinstance(transport, dict):
        relations = [item for item in (transport.get("r") or []) if isinstance(item, dict)]
    if not relations:
        semantic = dict(semantic)
        notes = list(semantic.get("notes") or [])
        notes.append("fixture expects an independent r[] relation")
        semantic["notes"] = notes
        semantic["status"] = "FAIL"
    semantic["link_related_required"] = False
    semantic["repetition_required"] = False
    expected = next_expected_dispositions()
    dispositions = []
    if isinstance(transport, dict):
        dispositions = [item for item in (transport.get("d") or []) if isinstance(item, dict)]
    by_id = {str(row.get("i") or ""): row for row in dispositions}
    drop_row = by_id.get("SYN001:I3") or {}
    drop_ok = (
        drop_row.get("o") == "DROP"
        and drop_row.get("w") == "non_substantive_fragment"
        and not drop_row.get("g")
    )
    merge_a = by_id.get("SYN001:I2") or {}
    merge_b = by_id.get("SYN002:I1") or {}
    merge_ok = (
        merge_a.get("o") == "MERGE_EQUIVALENT"
        and merge_b.get("o") == "MERGE_EQUIVALENT"
        and merge_a.get("g")
        and merge_a.get("g") == merge_b.get("g")
    )
    keep_watering = (by_id.get("SYN001:I1") or {}).get("o") == "KEEP"
    keep_companion = (by_id.get("SYN002:I2") or {}).get("o") == "KEEP"
    keep_in_relation = False
    watering_handle = str((by_id.get("SYN001:I1") or {}).get("g") or "")
    for rel in relations:
        if watering_handle and watering_handle in {rel.get("a"), rel.get("b")}:
            keep_in_relation = True
            break
    validator = interpreted.get("validator") or {}
    merge_union = "PASS"
    if any("missing SRC union" in str(err) for err in (validator.get("errors") or [])):
        merge_union = "FAIL"
    elif not merge_ok:
        merge_union = "FAIL"
    interpreted.update(
        {
            "structured_parse": structured,
            "enum_audit": enums,
            "d_o_enum": "PASS" if enums.get("unknown_do_count") == 0 else "FAIL",
            "d_w_enum": "PASS" if enums.get("unknown_dw_count") == 0 else "FAIL",
            "free_text_drop_reason": enums.get("free_text_dw_count"),
            "link_related_count": enums.get("link_related_count"),
            "operation_reason_matrix": enums.get("matrix_status"),
            "matrix_violations": enums.get("matrix_violations"),
            "keep_count": enums.get("keep_count"),
            "merge_equivalent_count": enums.get("merge_equivalent_count"),
            "drop_count": enums.get("drop_count"),
            "other_count": enums.get("other_count"),
            "observed_dw_tokens": enums.get("observed_dw_tokens"),
            "drop_token_ok": drop_ok,
            "merge_ok": merge_ok,
            "keep_ok": keep_watering and keep_companion,
            "keep_plus_independent_relation": keep_in_relation and keep_watering,
            "merge_source_union": merge_union,
            "repetition_count": int(
                ((interpreted.get("inventory") or {}).get("REPETITION") or 0)
            ),
            "repetition_required": False,
            "expected_dispositions": expected,
            "semantic_review": semantic,
            "transport_version": NEXT_TRANSPORT_VERSION,
            "repaired": False,
        }
    )
    if enums.get("status") != "PASS":
        interpreted["global_validator"] = "FAIL"
        interpreted.setdefault("errors", []).extend(enums.get("matrix_violations") or [])
    return interpreted


__all__ = ["interpret_canary_response_v11"]
