"""Replay offline CALL C — diagnostic V2 only. Aucune réparation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.source_analysis.errors import WindowTransportValidationError
from app.source_analysis_local_v2.decoder import decode_v2_transport, looks_like_truncated_json
from app.source_analysis_local_v2.subdivision import LocalV2SubdivisionNotTriggered
from app.source_analysis_output_ceiling_review.facts import forensic_paths
from app.source_analysis_output_ceiling_review.raw_analyzer import analyze_structured_raw_text
from app.source_analysis_output_ceiling_review.constants import PROJECT_NAME, SMALL_SIGNATURE


def replay_call_c_against_v2(
    *,
    project_name: str = PROJECT_NAME,
    sortie_dir: Path | None = None,
) -> dict[str, Any]:
    paths = forensic_paths(project_name, sortie_dir=sortie_dir)
    raw_path = paths["structured_raw"]
    text = raw_path.read_text(encoding="utf-8") if raw_path.is_file() else ""
    truncated = looks_like_truncated_json(text)
    metrics = analyze_structured_raw_text(text) if text else {}
    decoded_ok = False
    error = None
    subdivision_attempted = False
    subdivision_triggered = False
    try:
        import json

        payload = json.loads(text)
        decode_v2_transport(payload)
        decoded_ok = True
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        if not isinstance(exc, WindowTransportValidationError) and "JSON" not in type(exc).__name__:
            pass
    return {
        "signature": SMALL_SIGNATURE,
        "truncated_or_invalid_json": truncated,
        "json_valid": bool(metrics.get("json_valid")) if metrics else False,
        "treated_as_transport": bool(metrics.get("treated_as_transport")) if metrics else False,
        "v2_decode_ok": decoded_ok,
        "became_valid_v2_result": False,
        "repaired": False,
        "prefix_salvaged": False,
        "subdivision_attempted": subdivision_attempted,
        "subdivision_triggered": subdivision_triggered,
        "error": error,
        "forensics_only": True,
    }


def assert_no_subdivision_on_failure() -> None:
    raise LocalV2SubdivisionNotTriggered("parse/provider failure — no subdivision")
