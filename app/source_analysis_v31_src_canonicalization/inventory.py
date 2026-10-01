"""Inventaire offline des 7 candidats READY. Pas de consolidation. 0 provider."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

from app.source_analysis_v31_final_three.constants import WIN003_PROVENANCE
from app.source_analysis_v31_final_three.paths import (
    a27_candidate_window_dir,
    candidate_window_dir as a31_candidate_window_dir,
)
from app.source_analysis_v31_local_lite.compatibility import load_a21_historical_transport
from app.source_analysis_v31_remaining_windows.paths import (
    candidate_window_dir as a28_candidate_window_dir,
)
from app.source_analysis_v31_src_canonicalization.constants import (
    GRANULARITY_POLICY,
    MODE,
    PHASE,
    PROJECT_NAME,
    SCHEMA_VERSION,
    SRC_POLICY_NEW,
    SRC_POLICY_OLD,
    TRANSPORT_VERSION,
    WIN007_PROMOTION_LABEL,
    WIN007_REQUEST_ID,
    WIN007_SIGNATURE,
    WINDOW_SPECS,
)


def _count_kinds(payload: Mapping[str, Any]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    records = payload.get("records") if isinstance(payload.get("records"), list) else []
    for item in records:
        if isinstance(item, dict):
            kind = str(item.get("k") or "")
            if kind:
                counts[kind] += 1
    return {
        "TOPIC": int(counts.get("TOPIC") or 0),
        "IDEA": int(counts.get("IDEA") or 0),
        "RELATION": int(counts.get("RELATION") or 0),
        "EXAMPLE": int(counts.get("EXAMPLE") or 0),
        "REFERENCE": int(counts.get("REFERENCE") or 0),
        "UNCERTAINTY": int(counts.get("UNCERTAINTY") or 0),
        "total_records": len(records) if isinstance(records, list) else 0,
    }


def _distinct_src(payload: Mapping[str, Any]) -> int:
    seen: set[str] = set()
    for item in payload.get("records") or []:
        if not isinstance(item, dict):
            continue
        for ref in item.get("s") or []:
            if isinstance(ref, str):
                seen.add(ref)
    return len(seen)


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else None


def _inspect(
    path: Path | None,
    payload: dict[str, Any] | None,
    *,
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if path is None or payload is None:
        row = {
            "present": False,
            "path": None,
            "bytes": 0,
            "characters": 0,
            "token_estimate_chars_div_4": 0,
            "distinct_src_refs": 0,
        }
        row.update(_count_kinds({}))
        if extra:
            row.update(dict(extra))
        return row
    text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    size = path.stat().st_size if path.is_file() else len(text.encode("utf-8"))
    kinds = _count_kinds(payload)
    metadata_path = path.with_name("metadata.json")
    metadata = _load_json(metadata_path) if metadata_path.is_file() else None
    row = {
        "present": True,
        "path": str(path),
        "bytes": size,
        "characters": len(text),
        "serialized_bytes": size,
        "serialized_chars": len(text),
        "token_estimate_chars_div_4": (len(text) + 3) // 4,
        "estimated_consolidation_tokens": (len(text) + 3) // 4,
        "distinct_src_refs": _distinct_src(payload),
        "metadata_path": str(metadata_path) if metadata_path.is_file() else None,
        "candidate_metadata": metadata,
        **kinds,
    }
    if extra:
        row.update(dict(extra))
    return row


def build_consolidation_inventory(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
    win007_promoted: bool,
) -> dict[str, Any]:
    win001 = load_a21_historical_transport(project_name, sortie_dir=sortie_dir)
    windows: dict[str, Any] = {}
    windows["WIN001"] = {
        "window_id": "WIN001",
        "ready": True,
        "generation": "historical V3",
        "transport_generation": "semantic-transport-v3",
        "origin": "A.21",
        "mixed_version": "WIN001 historical V3",
        "prompt": "window-analysis-1.3.1",
        "src_reference_policy": SRC_POLICY_OLD,
        **_inspect(
            Path(win001["path"]) if win001 else None,
            win001["payload"] if win001 else None,
        ),
    }
    for window_id, extra in (
        (
            "WIN002",
            {
                "generation": "A.28",
                "origin": "A.28",
                "mixed_version": "WIN002 V3.1/local-lite",
            },
        ),
        (
            "WIN003",
            {
                "generation": "A.28 provider / A.30 revalidated",
                "origin": "A.28 provider / A.30 revalidated",
                "mixed_version": "WIN003 revalidated A.30",
                "provenance": WIN003_PROVENANCE,
            },
        ),
    ):
        path = (
            a28_candidate_window_dir(project_name, window_id, sortie_dir=sortie_dir)
            / "transport.json"
        )
        windows[window_id] = {
            "window_id": window_id,
            "ready": True,
            "transport_generation": TRANSPORT_VERSION,
            "prompt": "window-analysis-1.4.0",
            "granularity": GRANULARITY_POLICY,
            "src_reference_policy": SRC_POLICY_OLD,
            "analysis_signature": WINDOW_SPECS[window_id]["analysis_signature"],
            **extra,
            **_inspect(path, _load_json(path)),
        }
    win004_path = (
        a27_candidate_window_dir(project_name, sortie_dir=sortie_dir) / "transport.json"
    )
    windows["WIN004"] = {
        "window_id": "WIN004",
        "ready": True,
        "generation": "A.27",
        "origin": "A.27",
        "mixed_version": "WIN004 V3.1/local-lite",
        "transport_generation": TRANSPORT_VERSION,
        "prompt": "window-analysis-1.4.0",
        "granularity": GRANULARITY_POLICY,
        "src_reference_policy": SRC_POLICY_OLD,
        "analysis_signature": WINDOW_SPECS["WIN004"]["analysis_signature"],
        **_inspect(win004_path, _load_json(win004_path)),
    }
    for window_id in ("WIN005", "WIN006"):
        path = (
            a31_candidate_window_dir(project_name, window_id, sortie_dir=sortie_dir)
            / "transport.json"
        )
        windows[window_id] = {
            "window_id": window_id,
            "ready": True,
            "generation": "A.31",
            "origin": "A.31",
            "mixed_version": f"{window_id} V3.1/local-lite",
            "transport_generation": TRANSPORT_VERSION,
            "prompt": "window-analysis-1.4.0",
            "granularity": GRANULARITY_POLICY,
            "src_reference_policy": SRC_POLICY_OLD,
            "analysis_signature": WINDOW_SPECS[window_id]["analysis_signature"],
            **_inspect(path, _load_json(path)),
        }
    win007_path = (
        a31_candidate_window_dir(project_name, "WIN007", sortie_dir=sortie_dir)
        / "transport.json"
    )
    windows["WIN007"] = {
        "window_id": "WIN007",
        "ready": win007_promoted,
        "generation": "A.31 provider / A.33 derived SRC-canonicalized",
        "origin": "A.31 provider / A.33 derived SRC-canonicalized",
        "mixed_version": "WIN007 derived SRC-canonicalized A.33",
        "transport_generation": TRANSPORT_VERSION,
        "prompt": "window-analysis-1.4.0",
        "granularity": GRANULARITY_POLICY,
        "src_reference_policy": SRC_POLICY_NEW if win007_promoted else SRC_POLICY_OLD,
        "analysis_signature": WIN007_SIGNATURE,
        "provider_request_id": WIN007_REQUEST_ID,
        "label": WIN007_PROMOTION_LABEL if win007_promoted else None,
        "derived_representation": True,
        **_inspect(win007_path if win007_promoted else None, _load_json(win007_path) if win007_promoted else None),
    }
    totals = {
        "candidates": 7,
        "ready_candidates": 7 if win007_promoted else 6,
        "total_records": sum(int(row.get("total_records") or 0) for row in windows.values()),
        "TOPIC": sum(int(row.get("TOPIC") or 0) for row in windows.values()),
        "IDEA": sum(int(row.get("IDEA") or 0) for row in windows.values()),
        "RELATION": sum(int(row.get("RELATION") or 0) for row in windows.values()),
        "EXAMPLE": sum(int(row.get("EXAMPLE") or 0) for row in windows.values()),
        "REFERENCE": sum(int(row.get("REFERENCE") or 0) for row in windows.values()),
        "UNCERTAINTY": sum(int(row.get("UNCERTAINTY") or 0) for row in windows.values()),
        "distinct_src_refs_sum": sum(
            int(row.get("distinct_src_refs") or 0) for row in windows.values()
        ),
        "total_bytes": sum(int(row.get("bytes") or 0) for row in windows.values()),
        "total_characters": sum(int(row.get("characters") or 0) for row in windows.values()),
        "estimated_consolidation_tokens": sum(
            int(row.get("estimated_consolidation_tokens") or 0) for row in windows.values()
        ),
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "project_name": project_name or PROJECT_NAME,
        "inventory_only": True,
        "semantic_merge": False,
        "deduplicate_ideas": False,
        "merge_topics": False,
        "reclassify_relations": False,
        "assign_global_idea_subtypes": False,
        "create_global_themes": False,
        "source_map_created": False,
        "provider_calls": 0,
        "global_consolidation_executed": False,
        "mixed_version_inventory": {
            "WIN001": "historical V3",
            "WIN002": "V3.1/local-lite",
            "WIN003": "revalidated A.30",
            "WIN004": "V3.1/local-lite",
            "WIN005": "V3.1/local-lite A.31",
            "WIN006": "V3.1/local-lite A.31",
            "WIN007": "derived SRC-canonicalized A.33" if win007_promoted else "NOT READY",
        },
        "windows": windows,
        "totals": totals,
        "next": "OFFLINE GLOBAL CONSOLIDATION PREFLIGHT / DESIGN VALIDATION",
    }


__all__ = ["build_consolidation_inventory"]
