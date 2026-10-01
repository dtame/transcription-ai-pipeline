"""Inventaire exact des 7 fenêtres READY + handles IDEA. 0 provider."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.file_utils import content_hash
from app.source_analysis_local_v3.source_refs import is_canonical_src
from app.source_analysis_v31_global_preflight.constants import MIXED_PROVENANCE
from app.source_analysis_v31_global_real_consolidation.input_contract import (
    assert_frozen_inventory,
    idea_records,
    load_normalized_bundle,
    local_src_by_input,
    serialize_twice,
)
from app.source_analysis_v31_global_v30_exact_preflight.constants import (
    EXPECTED_EXAMPLE,
    EXPECTED_IDEA,
    EXPECTED_REFERENCE,
    EXPECTED_RELATION,
    EXPECTED_TOPIC,
    EXPECTED_TOTAL_RECORDS,
    EXPECTED_UNCERTAINTY,
    LOCAL_EXTRACTION_FUNCTIONALLY_FROZEN,
    MIXED_PROVENANCE as FROZEN_PROVENANCE,
    PHASE,
    PROJECT_NAME,
    READY_LABEL,
    READY_WINDOWS,
    SCHEMA_VERSION,
)
from app.source_analysis_v31_global_v30_exact_preflight.offline import (
    GlobalExactPreflightError,
)


def load_exact_windows(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> dict[str, Any]:
    bundle = load_normalized_bundle(project_name, sortie_dir=sortie_dir)
    inventory_check = assert_frozen_inventory(
        bundle["normalized"], bundle["inventory"], bundle["boundary"]
    )
    determinism = serialize_twice(bundle["normalized"])
    return {
        **bundle,
        "inventory_check": inventory_check,
        "determinism": determinism,
    }


def idea_handle_identity(normalized: dict[str, Any]) -> dict[str, Any]:
    idea_ids = [str(item) for item in (normalized.get("idea_input_ids") or [])]
    if len(idea_ids) != EXPECTED_IDEA:
        raise GlobalExactPreflightError(
            f"BLOCKED: local IDEA count {len(idea_ids)} != {EXPECTED_IDEA}."
        )
    if len(set(idea_ids)) != len(idea_ids):
        raise GlobalExactPreflightError("BLOCKED: duplicate local IDEA handles.")
    ordered = list(idea_ids)
    payload = json.dumps(ordered, ensure_ascii=False, separators=(",", ":"))
    return {
        "count": len(ordered),
        "ordered_handles": ordered,
        "handle_set_sha256": content_hash(payload),
        "first": ordered[0] if ordered else None,
        "last": ordered[-1] if ordered else None,
    }


def verify_idea_source_refs(normalized: dict[str, Any]) -> dict[str, Any]:
    invalid: list[dict[str, Any]] = []
    empty: list[str] = []
    for item in idea_records(normalized):
        input_id = str(item.get("input_id") or "")
        refs = [str(ref) for ref in (item.get("source_refs") or []) if isinstance(ref, str)]
        if not refs:
            empty.append(input_id)
        bad = [ref for ref in refs if not is_canonical_src(ref)]
        if bad:
            invalid.append({"input_id": input_id, "invalid_src": bad})
    if invalid or empty:
        raise GlobalExactPreflightError(
            "BLOCKED: invalid or empty IDEA source_refs "
            f"invalid={len(invalid)} empty={len(empty)}."
        )
    mapping = local_src_by_input(normalized)
    return {
        "ok": True,
        "ideas_checked": EXPECTED_IDEA,
        "invalid_src": 0,
        "empty_src": 0,
        "derived_src_union_is_downstream": True,
        "src_by_input_count": len(mapping),
    }


def window_manifest(loaded: dict[str, Any], normalized: dict[str, Any]) -> dict[str, Any]:
    windows = normalized.get("windows") or {}
    loaded_windows = loaded.get("windows") or {}
    rows = []
    missing = [window_id for window_id in READY_WINDOWS if window_id not in windows]
    if missing:
        raise GlobalExactPreflightError(f"BLOCKED: missing READY windows {missing}.")
    hashes = []
    for window_id in READY_WINDOWS:
        row = windows[window_id]
        loaded_row = loaded_windows.get(window_id) or {}
        kinds = {}
        for item in row.get("records") or []:
            kind = str(item.get("kind") or "")
            kinds[kind] = int(kinds.get(kind) or 0) + 1
        sha = str(row.get("sha256") or "")
        hashes.append(sha)
        rows.append(
            {
                "window_id": window_id,
                "ready": True,
                "mixed_provenance": MIXED_PROVENANCE[window_id],
                "frozen_provenance": FROZEN_PROVENANCE[window_id],
                "candidate_path": row.get("candidate_path"),
                "request_id": row.get("request_id") or loaded_row.get("request_id"),
                "prompt_version": row.get("prompt_version"),
                "source_transport_version": row.get("source_transport_version"),
                "normalized_transport_version": row.get("normalized_transport_version"),
                "granularity_policy": row.get("granularity_policy"),
                "src_policy": row.get("src_policy"),
                "owned_src_range": row.get("owned_src_range"),
                "record_counts": kinds,
                "record_total": len(row.get("records") or []),
                "serialized_chars": row.get("serialized_chars"),
                "serialized_bytes": row.get("serialized_bytes"),
                "sha256": sha,
                "analysis_signature": row.get("analysis_signature"),
            }
        )
    combined = content_hash(json.dumps(hashes, ensure_ascii=False, separators=(",", ":")))
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "ready_windows": list(READY_WINDOWS),
        "ready_label": READY_LABEL,
        "ready_count": f"{len(rows)} / 7",
        "windows": rows,
        "window_hash_list": hashes,
        "window_set_sha256": combined,
        "local_extraction_functionally_frozen": LOCAL_EXTRACTION_FUNCTIONALLY_FROZEN,
        "regenerated": False,
        "provider_called": False,
    }


def exact_inventory_payload(
    *,
    inventory_check: dict[str, Any],
    idea_identity: dict[str, Any],
    src_audit: dict[str, Any],
    window_rows: dict[str, Any],
) -> dict[str, Any]:
    observed = inventory_check.get("observed") or {}
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "ready_windows": window_rows.get("ready_label"),
        "a34_expected": {
            "total_records": EXPECTED_TOTAL_RECORDS,
            "TOPIC": EXPECTED_TOPIC,
            "IDEA": EXPECTED_IDEA,
            "RELATION": EXPECTED_RELATION,
            "EXAMPLE": EXPECTED_EXAMPLE,
            "REFERENCE": EXPECTED_REFERENCE,
            "UNCERTAINTY": EXPECTED_UNCERTAINTY,
        },
        "observed": observed,
        "mismatch": {},
        "internally_consistent": True,
        "idea_accountability_input": {
            "count": idea_identity.get("count"),
            "handle_set_sha256": idea_identity.get("handle_set_sha256"),
            "ordered": True,
        },
        "source_refs": src_audit,
        "inventory_check": {
            key: value
            for key, value in inventory_check.items()
            if key != "idea_input_ids"
        },
        "window_set_sha256": window_rows.get("window_set_sha256"),
    }


__all__ = [
    "exact_inventory_payload",
    "idea_handle_identity",
    "load_exact_windows",
    "verify_idea_source_refs",
    "window_manifest",
]
