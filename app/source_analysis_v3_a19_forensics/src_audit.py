"""Audit SRC exhaustif du transport A.19 brut. Aucune normalisation."""

from __future__ import annotations

from typing import Any, Mapping

from app.source_analysis_hybrid.contracts import WindowInput
from app.source_analysis_local_v3.source_refs import (
    SRC_CANONICAL_PATTERN,
    classify_src_token,
    is_canonical_src,
    per_kind_empty_s_rules,
    src_existence,
    walk_src_like_fields,
)
from app.source_analysis_v3_a19_forensics.constants import (
    A19_MALFORMED_SRC,
    MODE,
    PHASE,
    SCHEMA_VERSION,
)


def audit_source_refs(
    payload: Mapping[str, Any] | None,
    window: WindowInput,
) -> dict[str, Any]:
    allowed = set(window.owned_src_refs) | set(window.context_src_refs)
    owned = set(window.owned_src_refs)
    records = []
    if isinstance(payload, Mapping) and isinstance(payload.get("records"), list):
        records = [item for item in payload["records"] if isinstance(item, Mapping)]

    occurrences: list[dict[str, Any]] = []
    empty_by_kind: dict[str, list[int]] = {}
    for index, item in enumerate(records):
        kind = str(item.get("k") or "")
        raw = item.get("s")
        refs = raw if isinstance(raw, list) else []
        if not refs:
            empty_by_kind.setdefault(kind, []).append(index)
        seen: set[str] = set()
        for pos, token in enumerate(refs):
            token_class = classify_src_token(token)
            text = token if isinstance(token, str) else None
            existence = (
                src_existence(text, allowed=allowed, owned=owned)
                if isinstance(text, str)
                else "not_applicable"
            )
            duplicate = isinstance(text, str) and text in seen
            if isinstance(text, str):
                seen.add(text)
            occurrences.append(
                {
                    "record_index": index,
                    "kind": kind,
                    "position": pos,
                    "token": text,
                    "token_class": token_class,
                    "existence": existence,
                    "duplicate_in_record": duplicate,
                    "normalized": False,
                }
            )

    canonical = [
        row for row in occurrences if row["token_class"] == "canonical"
        and row["existence"] == "owned_or_allowed"
        and not row["duplicate_in_record"]
    ]
    malformed = [row for row in occurrences if row["token_class"] != "canonical"]
    wrong_case = [row for row in occurrences if row["token_class"] == "wrong_case"]
    unknown = [
        row
        for row in occurrences
        if row["token_class"] == "canonical" and row["existence"] == "unknown"
    ]
    out_of_window = [
        row
        for row in occurrences
        if row["token_class"] == "canonical"
        and row["existence"] not in {"owned_or_allowed", "canonical_unscoped", "not_applicable"}
        and row["existence"] != "unknown"
    ]
    # v2.1-small context is empty: unknown == out-of-window for well-formed absents
    unknown_well_formed = [
        row
        for row in occurrences
        if row["token_class"] == "canonical" and row["existence"] == "unknown"
    ]
    duplicates = [row for row in occurrences if row["duplicate_in_record"]]
    distinct_tokens = sorted({row["token"] for row in occurrences if row["token"]})
    distinct_canonical_owned = sorted(
        {
            row["token"]
            for row in occurrences
            if row["token_class"] == "canonical" and row["existence"] == "owned_or_allowed"
        }
    )
    extra_field_hits = walk_src_like_fields(payload) if isinstance(payload, Mapping) else []
    non_s_hits = [
        hit
        for hit in extra_field_hits
        if ".s[" not in hit["path"] and not hit["path"].endswith(".s")
    ]
    case_errors_all_fields = [
        hit
        for hit in extra_field_hits
        if classify_src_token(hit["token"]) == "wrong_case"
    ]
    only_src_case = (
        len(wrong_case) == 1
        and wrong_case[0]["token"] == A19_MALFORMED_SRC
        and len(case_errors_all_fields) == 1
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "canonical_pattern": SRC_CANONICAL_PATTERN,
        "normalized": False,
        "total_src_reference_occurrences": len(occurrences),
        "valid_canonical_owned_occurrences": len(canonical),
        "distinct_src_refs_raw": len(distinct_tokens),
        "distinct_canonical_owned_src_refs": len(distinct_canonical_owned),
        "malformed_lexical_refs": malformed,
        "wrong_case_refs": wrong_case,
        "unknown_well_formed_refs": unknown_well_formed,
        "out_of_window_refs": out_of_window,
        "duplicate_refs_within_records": duplicates,
        "empty_s_by_kind": {kind: list(indexes) for kind, indexes in empty_by_kind.items()},
        "empty_s_rules": per_kind_empty_s_rules(),
        "src_like_outside_s": non_s_hits,
        "wrong_case_all_structured_fields": case_errors_all_fields,
        "src000609_is_only_casing_error": only_src_case,
        "variant_search_normalized": False,
        "context_src_count": window.context_src_count,
        "owned_src_count": window.owned_src_count,
        "ownership_universe": "owned_only" if window.context_src_count == 0 else "owned_plus_context",
    }


__all__ = ["audit_source_refs"]
