"""Entrée normalisée A.34/A.36/A.37 : 7 fenêtres READY, inventaire figé. 0 POST."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.source_analysis_local_v3.source_refs import is_canonical_src
from app.source_analysis_v31_global_preflight.boundary import build_boundary_audit
from app.source_analysis_v31_global_preflight.inventory import build_input_inventory
from app.source_analysis_v31_global_preflight.loaders import load_all_ready_candidates
from app.source_analysis_v31_global_preflight.normalize import (
    build_normalized_input,
    src_number,
)
from app.source_analysis_v31_global_real_consolidation.constants import (
    EXPECTED_CROSS_WINDOW_OWNERSHIP_VIOLATIONS,
    EXPECTED_DISTINCT_SRC,
    EXPECTED_EXAMPLE,
    EXPECTED_IDEA,
    EXPECTED_NORMALIZED_CHARS,
    EXPECTED_REFERENCE,
    EXPECTED_RELATION,
    EXPECTED_SRC_OCCURRENCES,
    EXPECTED_TOPIC,
    EXPECTED_TOTAL_RECORDS,
    EXPECTED_UNCERTAINTY,
    MIXED_PROVENANCE,
    PROJECT_NAME,
    READY_WINDOWS,
    SIZE_DELTA_BLOCK_RATIO,
    WIN007_CANONICAL_SRC,
    WIN007_RAW_SRC,
)
from app.source_analysis_v31_global_real_consolidation.guard import (
    GlobalRealConsolidationError,
    validate_project_name,
    validate_ready_windows,
)


def load_normalized_bundle(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> dict[str, Any]:
    validate_project_name(project_name)
    loaded = load_all_ready_candidates(project_name, sortie_dir=sortie_dir)
    missing = list(loaded.get("missing") or [])
    if missing:
        raise GlobalRealConsolidationError(
            f"BLOCKED_PRECALL: missing READY windows {missing}."
        )
    windows = loaded.get("windows") or {}
    present = [window_id for window_id in READY_WINDOWS if windows.get(window_id, {}).get("present")]
    validate_ready_windows(present)
    normalized = build_normalized_input(
        project_name, sortie_dir=sortie_dir, loaded=loaded
    )
    inventory = build_input_inventory(normalized, loaded)
    boundary = build_boundary_audit(normalized, project_name, sortie_dir=sortie_dir)
    return {
        "loaded": loaded,
        "normalized": normalized,
        "inventory": inventory,
        "boundary": boundary,
    }


def compact_text(normalized: dict[str, Any]) -> str:
    return json.dumps(normalized.get("compact") or {}, ensure_ascii=False, separators=(",", ":"))


def local_src_by_input(normalized: dict[str, Any]) -> dict[str, list[str]]:
    mapping: dict[str, list[str]] = {}
    for item in normalized.get("all_records") or []:
        mapping[str(item.get("input_id") or "")] = [
            str(ref) for ref in (item.get("source_refs") or []) if isinstance(ref, str)
        ]
    return mapping


def allowed_input_ids(normalized: dict[str, Any]) -> set[str]:
    return {
        str(item.get("input_id") or "")
        for item in normalized.get("all_records") or []
        if item.get("input_id")
    }


def allowed_source_refs(normalized: dict[str, Any]) -> set[str]:
    refs: set[str] = set()
    for item in normalized.get("all_records") or []:
        for ref in item.get("source_refs") or []:
            if isinstance(ref, str):
                refs.add(ref)
    return refs


def idea_records(normalized: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        item
        for item in normalized.get("all_records") or []
        if item.get("kind") == "IDEA"
    ]


def win007_src_provenance(normalized: dict[str, Any]) -> dict[str, Any]:
    hits = [
        item
        for item in normalized.get("all_records") or []
        if item.get("window_id") == "WIN007" and item.get("src_provenance")
    ]
    return {
        "raw_provider_token": WIN007_RAW_SRC,
        "canonical": WIN007_CANONICAL_SRC,
        "consumed": WIN007_CANONICAL_SRC,
        "records_with_provenance": len(hits),
        "mixed_provenance": dict(MIXED_PROVENANCE),
    }


def recompute_src_inventory(normalized: dict[str, Any]) -> dict[str, Any]:
    occurrences: list[str] = []
    for item in normalized.get("all_records") or []:
        for ref in item.get("source_refs") or []:
            if isinstance(ref, str):
                occurrences.append(ref)
    distinct = sorted(set(occurrences), key=lambda token: src_number(token) or 0)
    unknown = [token for token in occurrences if not is_canonical_src(token)]
    return {
        "src_occurrences": len(occurrences),
        "distinct_src": len(distinct),
        "unknown_src": len(unknown),
        "unknown_src_tokens": unknown[:12],
        "canonical_src_occurrences": sum(
            1 for token in occurrences if is_canonical_src(token)
        ),
    }


def assert_frozen_inventory(
    normalized: dict[str, Any],
    inventory: dict[str, Any],
    boundary: dict[str, Any],
) -> dict[str, Any]:
    totals = inventory.get("totals") or {}
    src = recompute_src_inventory(normalized)
    compact_chars = int(normalized.get("compact_chars") or 0)
    expected = {
        "total_records": EXPECTED_TOTAL_RECORDS,
        "TOPIC": EXPECTED_TOPIC,
        "IDEA": EXPECTED_IDEA,
        "RELATION": EXPECTED_RELATION,
        "EXAMPLE": EXPECTED_EXAMPLE,
        "REFERENCE": EXPECTED_REFERENCE,
        "UNCERTAINTY": EXPECTED_UNCERTAINTY,
        "src_occurrences": EXPECTED_SRC_OCCURRENCES,
        "distinct_src": EXPECTED_DISTINCT_SRC,
    }
    observed = {
        "total_records": int(totals.get("total_records") or 0),
        "TOPIC": int(totals.get("TOPIC") or 0),
        "IDEA": int(totals.get("IDEA") or 0),
        "RELATION": int(totals.get("RELATION") or 0),
        "EXAMPLE": int(totals.get("EXAMPLE") or 0),
        "REFERENCE": int(totals.get("REFERENCE") or 0),
        "UNCERTAINTY": int(totals.get("UNCERTAINTY") or 0),
        "src_occurrences": int(src.get("src_occurrences") or 0),
        "distinct_src": int(src.get("distinct_src") or 0),
    }
    mismatches = {
        key: {"expected": expected[key], "observed": observed[key]}
        for key in expected
        if expected[key] != observed[key]
    }
    ownership = int(boundary.get("cross_window_src_violation_count") or 0)
    if ownership != EXPECTED_CROSS_WINDOW_OWNERSHIP_VIOLATIONS:
        mismatches["cross_window_ownership_violations"] = {
            "expected": EXPECTED_CROSS_WINDOW_OWNERSHIP_VIOLATIONS,
            "observed": ownership,
        }
    if int(src.get("unknown_src") or 0) != 0:
        mismatches["unknown_src"] = {
            "expected": 0,
            "observed": src.get("unknown_src"),
        }
    delta_chars = abs(compact_chars - EXPECTED_NORMALIZED_CHARS)
    delta_ratio = (
        delta_chars / EXPECTED_NORMALIZED_CHARS if EXPECTED_NORMALIZED_CHARS else 1.0
    )
    size_blocked = delta_ratio > SIZE_DELTA_BLOCK_RATIO
    if mismatches or size_blocked:
        raise GlobalRealConsolidationError(
            "BLOCKED_PRECALL: frozen input inventory mismatch "
            f"mismatches={mismatches} compact_chars={compact_chars} "
            f"expected_chars={EXPECTED_NORMALIZED_CHARS} delta_ratio={delta_ratio:.4f}."
        )
    idea_ids = list(normalized.get("idea_input_ids") or [])
    if len(idea_ids) != EXPECTED_IDEA:
        raise GlobalRealConsolidationError(
            f"BLOCKED_PRECALL: idea_input_ids={len(idea_ids)} expected={EXPECTED_IDEA}."
        )
    return {
        "ok": True,
        "expected": expected,
        "observed": observed,
        "compact_chars": compact_chars,
        "compact_bytes": int(normalized.get("compact_bytes") or 0),
        "compact_sha256": normalized.get("compact_sha256"),
        "normalized_chars_a34": EXPECTED_NORMALIZED_CHARS,
        "size_delta_chars": compact_chars - EXPECTED_NORMALIZED_CHARS,
        "size_delta_ratio": round(delta_ratio, 6),
        "src": src,
        "ownership_violations": ownership,
        "idea_input_ids": len(idea_ids),
        "win007": win007_src_provenance(normalized),
        "mixed_provenance": dict(MIXED_PROVENANCE),
    }


def serialize_twice(normalized: dict[str, Any]) -> dict[str, Any]:
    first = compact_text(normalized)
    second = compact_text(normalized)
    equal = first == second
    if not equal:
        raise GlobalRealConsolidationError(
            "BLOCKED_PRECALL: normalized compact serialization is not deterministic."
        )
    return {
        "ok": True,
        "equal": equal,
        "chars": len(first),
        "sha256_a": normalized.get("compact_sha256"),
    }


__all__ = [
    "allowed_input_ids",
    "allowed_source_refs",
    "assert_frozen_inventory",
    "compact_text",
    "idea_records",
    "load_normalized_bundle",
    "local_src_by_input",
    "recompute_src_inventory",
    "serialize_twice",
    "win007_src_provenance",
]
