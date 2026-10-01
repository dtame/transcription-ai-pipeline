"""Charge et vérifie les 7 candidats READY. Lecture seule. 0 provider."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from app.language_cleanup.transcript_source import audit_dir
from app.source_analysis_v31_final_three.paths import (
    a27_candidate_window_dir,
    candidate_window_dir as a31_candidate_window_dir,
)
from app.source_analysis_v31_global_preflight.constants import (
    EXECUTION_ARTIFACTS,
    MIXED_PROVENANCE,
    PROJECT_NAME,
    READY_WINDOWS,
    WIN007_CANONICAL_SRC,
    WIN007_PROMOTION_LABEL,
    WIN007_RAW_SRC,
    WIN007_REQUEST_ID,
    WINDOW_SPECS,
)
from app.source_analysis_v31_local_lite.compatibility import load_a21_historical_transport
from app.source_analysis_v31_remaining_windows.paths import (
    candidate_window_dir as a28_candidate_window_dir,
)


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else None


def window_short(window_id: str) -> str:
    return "W" + str(window_id).removeprefix("WIN")


def owned_src_range(window_id: str) -> tuple[int, int]:
    spec = WINDOW_SPECS[window_id]
    first = int(str(spec["first_owned_src"]).removeprefix("SRC"))
    last = int(str(spec["last_owned_src"]).removeprefix("SRC"))
    return first, last


def candidate_path_for(
    window_id: str,
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> Path | None:
    if window_id == "WIN001":
        historical = load_a21_historical_transport(project_name, sortie_dir=sortie_dir)
        return Path(historical["path"]) if historical else None
    if window_id in {"WIN002", "WIN003"}:
        return (
            a28_candidate_window_dir(project_name, window_id, sortie_dir=sortie_dir)
            / "transport.json"
        )
    if window_id == "WIN004":
        return a27_candidate_window_dir(project_name, sortie_dir=sortie_dir) / "transport.json"
    return (
        a31_candidate_window_dir(project_name, window_id, sortie_dir=sortie_dir)
        / "transport.json"
    )


def _execution_row(
    window_id: str,
    project_name: str,
    *,
    sortie_dir: Path | None,
) -> dict[str, Any]:
    name = EXECUTION_ARTIFACTS.get(window_id)
    path = audit_dir(project_name, sortie_dir=sortie_dir) / name if name else None
    payload = _load_json(path) if path else None
    execution = (payload or {}).get("execution") or payload or {}
    http = execution.get("http") if isinstance(execution, Mapping) else {}
    http = http if isinstance(http, Mapping) else {}
    cost = execution.get("cost") if isinstance(execution, Mapping) else None
    return {
        "path": str(path) if path and path.is_file() else None,
        "request_id": http.get("request_id") or execution.get("request_id"),
        "input_tokens": http.get("input_tokens"),
        "output_tokens": http.get("output_tokens"),
        "elapsed_ms": http.get("elapsed_ms"),
        "http_status": http.get("http_status") or execution.get("http_status"),
        "finish_reason": http.get("finish_reason"),
        "thinking_tokens": ((http.get("usage") or {}).get("output_tokens_details") or {}).get(
            "thinking_tokens"
        )
        if isinstance(http.get("usage"), Mapping)
        else None,
        "cost": dict(cost) if isinstance(cost, Mapping) else None,
    }


def load_ready_candidate(
    window_id: str,
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> dict[str, Any]:
    path = candidate_path_for(window_id, project_name, sortie_dir=sortie_dir)
    payload = _load_json(path) if path else None
    metadata_path = path.with_name("metadata.json") if path else None
    metadata = _load_json(metadata_path) if metadata_path else None
    execution = _execution_row(window_id, project_name, sortie_dir=sortie_dir)
    spec = WINDOW_SPECS[window_id]
    present = bool(path and path.is_file() and isinstance(payload, dict))
    text = json.dumps(payload, ensure_ascii=False, separators=(",", ":")) if payload else ""
    encoded = text.encode("utf-8")
    return {
        "window_id": window_id,
        "ready": present,
        "present": present,
        "path": str(path) if path else None,
        "metadata_path": str(metadata_path) if metadata_path and metadata_path.is_file() else None,
        "payload": payload,
        "metadata": metadata or {},
        "mixed_provenance": MIXED_PROVENANCE[window_id],
        "first_owned_src": spec["first_owned_src"],
        "last_owned_src": spec["last_owned_src"],
        "owned_src_count": spec["owned_src_count"],
        "owned_src_range": owned_src_range(window_id),
        "analysis_signature": spec["analysis_signature"],
        "word_count": spec["word_count"],
        "local_input_estimate": spec["local_input_estimate"],
        "serialized_chars": len(text),
        "serialized_bytes": path.stat().st_size if path and path.is_file() else len(encoded),
        "execution": execution,
        "request_id": execution.get("request_id")
        or ((metadata or {}).get("provenance") or {}).get("provider_request_id"),
    }


def load_all_ready_candidates(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> dict[str, Any]:
    windows: dict[str, Any] = {}
    missing: list[str] = []
    for window_id in READY_WINDOWS:
        row = load_ready_candidate(window_id, project_name, sortie_dir=sortie_dir)
        windows[window_id] = row
        if not row["present"]:
            missing.append(window_id)
    win007 = windows["WIN007"]
    win007_meta = win007.get("metadata") or {}
    win007_prov = win007_meta.get("provenance") or {}
    return {
        "windows": windows,
        "missing": missing,
        "ready_count": sum(1 for row in windows.values() if row["present"]),
        "ready_label": f"{sum(1 for row in windows.values() if row['present'])} / {len(READY_WINDOWS)}",
        "all_ready": not missing,
        "win007_raw_src": WIN007_RAW_SRC,
        "win007_canonical_src": WIN007_CANONICAL_SRC,
        "win007_request_id": win007.get("request_id") or WIN007_REQUEST_ID,
        "win007_label": win007_prov.get("label") or WIN007_PROMOTION_LABEL,
        "win003_provenance": (windows["WIN003"].get("metadata") or {}).get("provenance") or {},
    }


__all__ = [
    "candidate_path_for",
    "load_all_ready_candidates",
    "load_ready_candidate",
    "owned_src_range",
    "window_short",
]
