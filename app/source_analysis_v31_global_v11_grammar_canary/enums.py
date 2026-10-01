"""Audit brut d.o / d.w + matrice opération/raison. Aucune réparation."""

from __future__ import annotations

from collections import Counter
from typing import Any, Mapping

from app.source_analysis_v31_global_canary_forensics.transport_v11 import (
    DROP_REASON_CODES,
    NON_DROP_REASON_CODE,
    REASON_CODES,
    REPRESENTATION_OPS,
    RETIRED_OPS,
)


def audit_raw_enums(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    if isinstance(payload, Mapping):
        raw = payload.get("d") or []
        if isinstance(raw, list):
            rows = [item for item in raw if isinstance(item, dict)]

    op_counter: Counter[str] = Counter()
    reason_counter: Counter[str] = Counter()
    unknown_ops: list[str] = []
    unknown_reasons: list[str] = []
    free_text_reasons: list[dict[str, str]] = []
    retired: list[str] = []
    matrix_violations: list[str] = []
    observed_reasons: list[str] = []

    for index, row in enumerate(rows):
        loc = f"d[{index}]"
        op = str(row.get("o") or "")
        reason = str(row.get("w") or "")
        input_id = str(row.get("i") or "")
        op_counter[op] += 1
        reason_counter[reason] += 1
        observed_reasons.append(reason)
        if op in RETIRED_OPS:
            retired.append(f"{loc}:{input_id}:{op}")
            unknown_ops.append(op)
        elif op not in REPRESENTATION_OPS:
            unknown_ops.append(op)
        if reason not in REASON_CODES:
            unknown_reasons.append(reason)
            free_text_reasons.append({"i": input_id, "w": reason, "loc": loc})
        if op == "DROP":
            if reason == NON_DROP_REASON_CODE:
                matrix_violations.append(f"{loc} DROP + none")
            elif reason not in DROP_REASON_CODES:
                matrix_violations.append(f"{loc} DROP + invalid reason {reason!r}")
        elif op in REPRESENTATION_OPS:
            if reason != NON_DROP_REASON_CODE:
                matrix_violations.append(f"{loc} {op} + DROP reason {reason!r}")

    keep = int(op_counter.get("KEEP") or 0)
    merge = int(op_counter.get("MERGE_EQUIVALENT") or 0)
    drop = int(op_counter.get("DROP") or 0)
    other = int(op_counter.get("OTHER") or 0)
    link_related = int(op_counter.get("LINK_RELATED") or 0)
    ok = (
        link_related == 0
        and not free_text_reasons
        and not unknown_ops
        and not unknown_reasons
        and not matrix_violations
    )
    return {
        "ok": ok,
        "status": "PASS" if ok else "FAIL",
        "keep_count": keep,
        "merge_equivalent_count": merge,
        "drop_count": drop,
        "other_count": other,
        "link_related_count": link_related,
        "free_text_dw_count": len(free_text_reasons),
        "unknown_do_count": len(unknown_ops),
        "unknown_dw_count": len(unknown_reasons),
        "observed_dw_tokens": sorted(set(observed_reasons)),
        "reason_counts": dict(reason_counter),
        "op_counts": dict(op_counter),
        "free_text_dw": free_text_reasons,
        "unknown_ops": unknown_ops,
        "unknown_reasons": unknown_reasons,
        "matrix_violations": matrix_violations,
        "matrix_violation_count": len(matrix_violations),
        "matrix_status": "PASS" if not matrix_violations else "FAIL",
        "allowed_do": list(REPRESENTATION_OPS),
        "allowed_dw": list(REASON_CODES),
        "heuristic_normalization": False,
        "rows": rows,
    }


__all__ = ["audit_raw_enums"]
