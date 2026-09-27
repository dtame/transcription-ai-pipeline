"""Parse / decoder / registry / resolver / validator V3 + audit SRC exhaustif."""

from __future__ import annotations

from typing import Any

from app.source_analysis_hybrid.contracts import WindowInput
from app.source_analysis_v3_a19_forensics.constants import EXAMPLE_POLICY
from app.source_analysis_v3_a19_forensics.forensic_validator import (
    collect_transport_violations,
)
from app.source_analysis_v3_a19_forensics.src_audit import audit_source_refs
from app.source_analysis_v3_hardened_win001.constants import (
    A19_MALFORMED_TOKEN,
    MODE,
    PHASE,
    SCHEMA_VERSION,
)
from app.source_analysis_v3_real_win001.validate import interpret_response


def src_success_metrics(src_audit: dict[str, Any]) -> dict[str, Any]:
    malformed = list(src_audit.get("malformed_lexical_refs") or [])
    wrong_case = list(src_audit.get("wrong_case_refs") or [])
    unknown = list(src_audit.get("unknown_well_formed_refs") or [])
    out_of_window = list(src_audit.get("out_of_window_refs") or [])
    duplicates = list(src_audit.get("duplicate_refs_within_records") or [])
    tokens = [row.get("token") for row in malformed + wrong_case if row.get("token")]
    if (
        not malformed
        and not wrong_case
        and not unknown
        and not out_of_window
        and not duplicates
    ):
        typo_class = "ELIMINATED"
    elif A19_MALFORMED_TOKEN in tokens:
        typo_class = "PERSISTS"
    else:
        typo_class = "DIFFERENT_SRC_FAILURE"
    return {
        "total_src_occurrences": src_audit.get("total_src_reference_occurrences", 0),
        "valid_src_occurrences": src_audit.get("valid_canonical_owned_occurrences", 0),
        "distinct_canonical_refs": src_audit.get("distinct_canonical_owned_src_refs", 0),
        "distinct_src_refs_raw": src_audit.get("distinct_src_refs_raw", 0),
        "malformed_src": len(malformed),
        "wrong_case_src": len(wrong_case),
        "unknown_src": len(unknown),
        "out_of_window_src": len(out_of_window),
        "duplicate_src": len(duplicates),
        "empty_s_by_kind": src_audit.get("empty_s_by_kind") or {},
        "src_success": (
            not malformed
            and not wrong_case
            and not unknown
            and not out_of_window
            and not duplicates
        ),
        "a19_src_typo_class": typo_class,
        "normalized": False,
    }


def interpret_hardened_response(
    parsed: dict[str, Any] | None,
    *,
    window: WindowInput,
    raw_text: str | None = None,
) -> dict[str, Any]:
    base = interpret_response(parsed, window=window, raw_text=raw_text)
    payload = base.get("transport")
    if not isinstance(payload, dict) and isinstance(parsed, dict):
        payload = parsed
    src_audit = dict(
        audit_source_refs(payload if isinstance(payload, dict) else None, window)
    )
    src_audit["schema_version"] = SCHEMA_VERSION
    src_audit["phase"] = PHASE
    src_audit["mode"] = MODE
    allowed = set(window.owned_src_refs) | set(window.context_src_refs)
    owned = set(window.owned_src_refs)
    inventory = dict(
        collect_transport_violations(
            payload if isinstance(payload, dict) else None,
            allowed=allowed,
            owned=owned,
            example_policy=EXAMPLE_POLICY,
        )
    )
    inventory["schema_version"] = SCHEMA_VERSION
    inventory["phase"] = PHASE
    inventory["mode"] = MODE
    src_metrics = src_success_metrics(src_audit)
    return {
        **base,
        "src_audit": src_audit,
        "src_forensic": src_metrics,
        "inventory": inventory,
        "example_policy": EXAMPLE_POLICY,
        "normalized": False,
    }


__all__ = [
    "interpret_hardened_response",
    "src_success_metrics",
]
