"""Préflight offline WIN005/WIN006/WIN007. 0 appel. 0 exécution."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.source_analysis_local_v3.decoder import decode_v31_local_lite_transport
from app.source_analysis_v31_kind_specific_limits.constants import (
    EXPECTED_SCHEMA_HASH,
    MAX_OUTPUT_TOKENS,
    MODE,
    PHASE,
    PROJECT_NAME,
    PROMPT_VERSION,
    SCHEMA_VERSION,
    THINKING_MODE,
    TRANSPORT_VERSION,
    WINDOW_SPECS,
)
from app.source_analysis_v31_real_win004.canonical import normalized_src_refs
from app.source_analysis_v31_remaining_windows.payload import (
    assert_schema_identity,
    build_audited_request,
    dry_run_twice,
)
from app.source_analysis_v31_remaining_windows.paths import candidate_cache_dir
from app.source_analysis_v31_remaining_windows.window import load_candidate_plan
from app.source_analysis_v31_length_ceiling.evidence import read_json


def inspect_win002_compatibility(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> dict[str, Any]:
    spec = WINDOW_SPECS["WIN002"]
    path = (
        candidate_cache_dir(
            project_name, spec["analysis_signature"], "WIN002", sortie_dir=sortie_dir
        )
        / "transport.json"
    )
    if not path.is_file():
        return {"present": False, "readable_as_local_lite": False, "path": str(path)}
    payload = read_json(path)
    try:
        decode_v31_local_lite_transport(
            payload, allowed_source_refs=set(normalized_src_refs(payload))
        )
        readable = True
        error = None
    except Exception as exc:  # noqa: BLE001
        readable = False
        error = str(exc)
    return {
        "present": True,
        "path": str(path),
        "readable_as_local_lite": readable,
        "error": error,
        "analysis_signature": spec["analysis_signature"],
    }


def future_windows_preflight(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> dict[str, Any]:
    schema = assert_schema_identity()
    bundle = load_candidate_plan(project_name, sortie_dir=sortie_dir)
    windows: dict[str, Any] = {}
    compatible = True
    for window_id in ("WIN005", "WIN006", "WIN007"):
        window = bundle["windows"][window_id]
        built = build_audited_request(window, bundle["transcript"])
        twice = dry_run_twice(window, bundle["transcript"])
        audit = built.get("audit") or {}
        thinking_ok = audit.get("thinking_type") == THINKING_MODE
        prompt_ok = PROMPT_VERSION == "window-analysis-1.4.0"
        transport_ok = TRANSPORT_VERSION == "semantic-transport-v3.1-local-lite"
        max_ok = MAX_OUTPUT_TOKENS == 32000
        schema_ok = schema.get("raw_hash") == EXPECTED_SCHEMA_HASH
        row_ok = (
            thinking_ok
            and prompt_ok
            and transport_ok
            and max_ok
            and schema_ok
            and twice.get("deterministic") is True
        )
        if not row_ok:
            compatible = False
        windows[window_id] = {
            "window_id": window_id,
            "executed": False,
            "authorized": False,
            "prompt": PROMPT_VERSION,
            "transport": TRANSPORT_VERSION,
            "thinking_mode": THINKING_MODE,
            "max_output_tokens": MAX_OUTPUT_TOKENS,
            "schema_hash": schema.get("raw_hash"),
            "local_input_estimate": WINDOW_SPECS[window_id]["local_input_estimate"],
            "analysis_signature": WINDOW_SPECS[window_id]["analysis_signature"],
            "dry_run_deterministic": twice.get("deterministic"),
            "thinking_type": audit.get("thinking_type"),
            "compatible": row_ok,
        }
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "executed": False,
        "provider_calls": 0,
        "prompt": PROMPT_VERSION,
        "transport": TRANSPORT_VERSION,
        "thinking_mode": THINKING_MODE,
        "max_output_tokens": MAX_OUTPUT_TOKENS,
        "schema_raw": schema.get("raw_bytes"),
        "schema_adapted": schema.get("adapted_bytes"),
        "schema_hash": schema.get("raw_hash"),
        "schema_identity": "UNCHANGED" if schema.get("matches_expected") else "CHANGED",
        "windows": windows,
        "compatible": compatible,
        "ready_for_future_execution": compatible,
        "authorized_now": False,
    }


__all__ = ["future_windows_preflight", "inspect_win002_compatibility"]
