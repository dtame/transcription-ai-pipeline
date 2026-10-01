"""Inventaire exact des 7 fenêtres READY normalisées. 0 consolidation."""

from __future__ import annotations

from collections import Counter
from typing import Any, Mapping

from app.source_analysis_local_v3.source_refs import is_canonical_src
from app.source_analysis_v31_global_preflight.constants import (
    FROZEN_GRANULARITY,
    FROZEN_PLANNER,
    FROZEN_PROMPT,
    FROZEN_SRC_POLICY,
    FROZEN_TRANSPORT,
    MIXED_PROVENANCE,
    MODE,
    PHASE,
    SCHEMA_VERSION,
    WIN007_CANONICAL_SRC,
    WIN007_RAW_SRC,
)
from app.source_analysis_v31_global_preflight.normalize import src_number


_KINDS = ("TOPIC", "IDEA", "RELATION", "EXAMPLE", "REFERENCE", "UNCERTAINTY")


def _kind_counts(records: list[Mapping[str, Any]]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for item in records:
        kind = str(item.get("kind") or "")
        if kind:
            counts[kind] += 1
    return {kind: int(counts.get(kind) or 0) for kind in _KINDS} | {
        "total_records": len(records)
    }


def _src_stats(records: list[Mapping[str, Any]]) -> dict[str, Any]:
    occurrences: list[str] = []
    for item in records:
        for ref in item.get("source_refs") or []:
            if isinstance(ref, str):
                occurrences.append(ref)
    distinct = sorted(set(occurrences), key=lambda token: src_number(token) or 0)
    return {
        "src_occurrences": len(occurrences),
        "distinct_src_refs": len(distinct),
        "canonical_src_occurrences": sum(1 for token in occurrences if is_canonical_src(token)),
        "noncanonical_src_occurrences": sum(
            1 for token in occurrences if not is_canonical_src(token)
        ),
        "distinct_src_list_head": distinct[:12],
    }


def _window_inventory(normalized: Mapping[str, Any], loaded: Mapping[str, Any]) -> dict[str, Any]:
    records = list(normalized.get("records") or [])
    execution = loaded.get("execution") or {}
    kinds = _kind_counts(records)
    src = _src_stats(records)
    return {
        "window_id": normalized["window_id"],
        "ready": True,
        "candidate_path": normalized.get("candidate_path"),
        "source_response_provenance": MIXED_PROVENANCE[normalized["window_id"]],
        "request_id": loaded.get("request_id") or normalized.get("request_id"),
        "prompt_version": normalized.get("prompt_version"),
        "transport_version": normalized.get("source_transport_version"),
        "normalized_transport_version": normalized.get("normalized_transport_version"),
        "granularity_policy": normalized.get("granularity_policy"),
        "src_policy": normalized.get("src_policy"),
        "src_ownership_range": {
            "first": normalized.get("first_owned_src"),
            "last": normalized.get("last_owned_src"),
            "numeric": normalized.get("owned_src_range"),
        },
        "record_counts": kinds,
        "serialized_size": {
            "candidate_chars": loaded.get("serialized_chars"),
            "candidate_bytes": loaded.get("serialized_bytes"),
            "normalized_chars": normalized.get("serialized_chars"),
            "normalized_bytes": normalized.get("serialized_bytes"),
        },
        "token_estimate_chars_div_4": (int(loaded.get("serialized_chars") or 0) + 3) // 4,
        **src,
        **kinds,
        "analysis_signature": normalized.get("analysis_signature"),
        "provider_input_tokens": execution.get("input_tokens"),
        "provider_output_tokens": execution.get("output_tokens"),
        "elapsed_ms": execution.get("elapsed_ms"),
        "cost": execution.get("cost"),
        "local_input_estimate": loaded.get("local_input_estimate"),
        "win007_src_provenance": (
            {
                "raw_provider_src": WIN007_RAW_SRC,
                "derived_canonical_src": WIN007_CANONICAL_SRC,
                "policy": FROZEN_SRC_POLICY,
            }
            if normalized["window_id"] == "WIN007"
            else None
        ),
        "dropped_local_idea_subtypes": len(normalized.get("dropped_local_idea_subtypes") or []),
    }


def build_input_inventory(
    normalized: Mapping[str, Any],
    loaded: Mapping[str, Any],
) -> dict[str, Any]:
    windows: dict[str, Any] = {}
    all_records = list(normalized.get("all_records") or [])
    for window_id, row in (normalized.get("windows") or {}).items():
        windows[window_id] = _window_inventory(
            row, (loaded.get("windows") or {}).get(window_id) or {}
        )
    totals_kinds = _kind_counts(all_records)
    totals_src = _src_stats(all_records)
    candidate_chars = sum(
        int(row.get("serialized_size", {}).get("candidate_chars") or 0)
        for row in windows.values()
    )
    candidate_bytes = sum(
        int(row.get("serialized_size", {}).get("candidate_bytes") or 0)
        for row in windows.values()
    )
    provider_in = [
        int(row["provider_input_tokens"])
        for row in windows.values()
        if row.get("provider_input_tokens") is not None
    ]
    local_est = [
        int(row["local_input_estimate"])
        for row in windows.values()
        if row.get("local_input_estimate")
    ]
    ratios = [
        provider / local
        for provider, local in zip(provider_in, local_est)
        if local
    ]
    mean_ratio = sum(ratios) / len(ratios) if ratios else None
    compact_chars = int(normalized.get("compact_chars") or 0)
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "frozen_local_extraction": {
            "planner": FROZEN_PLANNER,
            "prompt": FROZEN_PROMPT,
            "transport": FROZEN_TRANSPORT,
            "granularity": FROZEN_GRANULARITY,
            "src_policy": FROZEN_SRC_POLICY,
        },
        "mixed_provenance": dict(MIXED_PROVENANCE),
        "windows": windows,
        "totals": {
            **totals_kinds,
            **totals_src,
            "serialized_characters": candidate_chars,
            "serialized_bytes": candidate_bytes,
            "normalized_compact_chars": compact_chars,
            "normalized_compact_bytes": int(normalized.get("compact_bytes") or 0),
            "estimated_provider_tokens_chars_div_4": (compact_chars + 3) // 4,
            "observed_window_provider_input_over_local_mean": mean_ratio,
            "idea_input_ids": len(normalized.get("idea_input_ids") or []),
        },
        "win007_src_provenance": {
            "raw_provider_src": WIN007_RAW_SRC,
            "derived_canonical_src": WIN007_CANONICAL_SRC,
            "policy": FROZEN_SRC_POLICY,
            "consolidator_consumes": WIN007_CANONICAL_SRC,
        },
        "win003_provenance": normalized.get("win003_provenance"),
        "semantic_merge": False,
        "provider_calls": 0,
        "global_consolidation_executed": False,
        "source_map_created": False,
    }


__all__ = ["build_input_inventory"]
