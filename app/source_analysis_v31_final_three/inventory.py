"""Inventaire offline des 7 candidats READY. Pas de consolidation. 0 provider."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.source_analysis_v31_local_lite.compatibility import load_a21_historical_transport
from app.source_analysis_v31_final_three.constants import (
    MODE,
    PHASE,
    PROJECT_NAME,
    SCHEMA_VERSION,
    WIN003_PROVENANCE,
    WINDOW_SPECS,
)
from app.source_analysis_v31_final_three.paths import (
    a27_candidate_window_dir,
    a28_candidate_window_dir,
    candidate_window_dir,
)


def _count_src(payload: dict[str, Any]) -> int:
    total = 0
    seen: set[str] = set()
    for item in payload.get("records") or []:
        if not isinstance(item, dict):
            continue
        for ref in item.get("s") or []:
            total += 1
            if isinstance(ref, str):
                seen.add(ref)
    return total


def _distinct_src(payload: dict[str, Any]) -> int:
    seen: set[str] = set()
    for item in payload.get("records") or []:
        if not isinstance(item, dict):
            continue
        for ref in item.get("s") or []:
            if isinstance(ref, str):
                seen.add(ref)
    return len(seen)


def _inspect_payload(path: Path | None, payload: dict[str, Any] | None) -> dict[str, Any]:
    if path is None or payload is None:
        return {
            "present": False,
            "path": None,
            "bytes": 0,
            "characters": 0,
            "token_estimate_chars_div_4": 0,
            "total_records": 0,
            "total_src_occurrences": 0,
            "distinct_src": 0,
        }
    text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    records = payload.get("records") if isinstance(payload.get("records"), list) else []
    size = path.stat().st_size if path.is_file() else len(text.encode("utf-8"))
    return {
        "present": True,
        "path": str(path),
        "bytes": size,
        "characters": len(text),
        "token_estimate_chars_div_4": (len(text) + 3) // 4,
        "total_records": len(records),
        "total_src_occurrences": _count_src(payload),
        "distinct_src": _distinct_src(payload),
    }


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else None


def build_global_inventory(
    project_name: str,
    result: Any,
    *,
    sortie_dir: Path | None = None,
) -> dict[str, Any]:
    win001 = load_a21_historical_transport(project_name, sortie_dir=sortie_dir)
    win004_path = a27_candidate_window_dir(project_name, sortie_dir=sortie_dir) / "transport.json"
    windows: dict[str, Any] = {}
    windows["WIN001"] = {
        "version": "semantic-transport-v3",
        "origin": "A.21",
        "ready": True,
        **_inspect_payload(
            Path(win001["path"]) if win001 else None,
            win001["payload"] if win001 else None,
        ),
    }
    for window_id, origin, version, extra in (
        ("WIN002", "A.28", "semantic-transport-v3.1-local-lite", {}),
        (
            "WIN003",
            "A.28 provider / A.30 revalidated",
            "semantic-transport-v3.1-local-lite",
            {"provenance": WIN003_PROVENANCE},
        ),
    ):
        path = (
            a28_candidate_window_dir(project_name, window_id, sortie_dir=sortie_dir)
            / "transport.json"
        )
        windows[window_id] = {
            "version": version,
            "origin": origin,
            "ready": True,
            "analysis_signature": WINDOW_SPECS[window_id]["analysis_signature"],
            **extra,
            **_inspect_payload(path, _load_json(path)),
        }
    windows["WIN004"] = {
        "version": "semantic-transport-v3.1-local-lite",
        "origin": "A.27",
        "ready": True,
        "analysis_signature": WINDOW_SPECS["WIN004"]["analysis_signature"],
        **_inspect_payload(win004_path, _load_json(win004_path)),
    }
    for window_id in ("WIN005", "WIN006", "WIN007"):
        item = (getattr(result, "windows", None) or {}).get(window_id) or {}
        execution = item.get("execution") or {}
        path = (
            candidate_window_dir(project_name, window_id, sortie_dir=sortie_dir)
            / "transport.json"
        )
        payload = item.get("transport")
        if not isinstance(payload, dict):
            payload = _load_json(path)
        windows[window_id] = {
            "version": "semantic-transport-v3.1-local-lite",
            "origin": "A.31",
            "ready": bool(execution.get("ready")),
            "analysis_signature": execution.get("analysis_signature")
            or WINDOW_SPECS[window_id]["analysis_signature"],
            **_inspect_payload(path if path.is_file() else None, payload),
        }
    totals = {
        "candidates": 7,
        "total_records": sum(int(row.get("total_records") or 0) for row in windows.values()),
        "total_src_occurrences": sum(
            int(row.get("total_src_occurrences") or 0) for row in windows.values()
        ),
        "total_bytes": sum(int(row.get("bytes") or 0) for row in windows.values()),
        "total_characters": sum(int(row.get("characters") or 0) for row in windows.values()),
        "token_estimate_chars_div_4": sum(
            int(row.get("token_estimate_chars_div_4") or 0) for row in windows.values()
        ),
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "project_name": project_name or PROJECT_NAME,
        "inventory_only": True,
        "semantic_merge": False,
        "provider_calls": 0,
        "global_consolidation_executed": False,
        "windows": windows,
        "totals": totals,
        "next": "OFFLINE GLOBAL CONSOLIDATION PREFLIGHT / DESIGN VALIDATION",
    }


__all__ = ["build_global_inventory"]
