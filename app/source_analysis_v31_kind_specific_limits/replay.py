"""Replay offline de la réponse WIN003 A.28 sous la politique 1.2. 0 provider."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.source_analysis.errors import WindowGranularityLimitExceeded
from app.source_analysis_local_v2.granularity import (
    TEXT_HARD_LIMITS,
    V11_MINIMAL_TEXT_HARD_LIMITS,
    validate_v11_minimal_transport_granularity,
    validate_v2_transport_granularity,
)
from app.source_analysis_v31_kind_specific_limits.constants import (
    A28_VALIDATOR_ERROR,
    EXAMPLE_CHARS,
    EXAMPLE_INDEX,
    IDEA_CHARS,
    IDEA_INDEX,
    MODE,
    PHASE,
    PROJECT_NAME,
    SCHEMA_VERSION,
    THEME_CHARS,
    WIN003_SIGNATURE,
    WINDOW_ID,
)
from app.source_analysis_v31_kind_specific_limits.identity import (
    verify_saved_win003_identity,
)
from app.source_analysis_v31_length_ceiling.replay import (
    extract_win003_structured_text,
    offending_values,
)
from app.source_analysis_v31_real_win004.validate import interpret_local_lite_response
from app.source_analysis_v31_remaining_windows.canonical import reconstruct_mixed
from app.source_analysis_v31_remaining_windows.review import review_transport
from app.source_analysis_v31_remaining_windows.window import load_candidate_plan


def _status(ok: bool) -> str:
    return "PASS" if ok else "FAIL"


def replay_saved_win003(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> dict[str, Any]:
    identity = verify_saved_win003_identity(project_name, sortie_dir=sortie_dir)
    text, raw_json, raw = extract_win003_structured_text(
        project_name, sortie_dir=sortie_dir
    )
    bundle = load_candidate_plan(project_name, sortie_dir=sortie_dir)
    window = bundle["windows"][WINDOW_ID]
    validation = interpret_local_lite_response(None, window=window, raw_text=text)
    transport = validation.get("transport")
    historical_error = None
    live_error = None
    if isinstance(transport, dict):
        try:
            validate_v11_minimal_transport_granularity(transport)
        except WindowGranularityLimitExceeded as exc:
            historical_error = str(exc)
        try:
            validate_v2_transport_granularity(transport)
        except WindowGranularityLimitExceeded as exc:
            live_error = str(exc)
    offenders = offending_values(transport if isinstance(transport, dict) else None)
    offenders["theme"]["live_limit"] = TEXT_HARD_LIMITS["theme"]
    offenders["theme"]["historical_limit"] = V11_MINIMAL_TEXT_HARD_LIMITS["theme"]
    offenders["example"]["live_limit"] = TEXT_HARD_LIMITS["EXAMPLE.v"]
    offenders["example"]["historical_limit"] = V11_MINIMAL_TEXT_HARD_LIMITS["EXAMPLE.v"]
    offenders["idea"]["live_limit"] = TEXT_HARD_LIMITS["IDEA.v"]
    structured = validation.get("structured_parse")
    decoder = validation.get("v31_decoder")
    registry = validation.get("handle_registry")
    resolution = validation.get("handle_resolution")
    validator = validation.get("v31_validator")
    capacity = bool(validation.get("capacity_signal"))
    handles = validation.get("handles") or {}
    handle_gate = validation.get("handle_gate") or {}
    src_forensic = validation.get("src_forensic") or {}
    metadata = validation.get("metadata") or {}
    handle_ok = bool(handle_gate.get("handle_gate_pass"))
    numeric = handle_gate.get("numeric_link_regression") == "YES"
    src_ok = bool(src_forensic.get("src_success"))
    metadata_ok = bool(metadata.get("local_lite_metadata_pass"))
    technical_ok = (
        structured == "PASS"
        and decoder == "PASS"
        and registry == "PASS"
        and resolution == "PASS"
        and validator == "PASS"
        and live_error is None
        and src_ok
        and metadata_ok
        and handle_ok
        and not numeric
        and not capacity
    )
    review: dict[str, Any] = {"performed": False, "semantic_quality": None}
    canonical: dict[str, Any] = {}
    if isinstance(transport, dict):
        review = review_transport(
            transport,
            window=window,
            transcript=bundle["transcript"],
            capacity_signal=capacity,
            handle_gate_pass=handle_ok,
            technical_ok=technical_ok,
            src_audit=validation.get("src_audit"),
        )
    if technical_ok and isinstance(transport, dict):
        canonical = reconstruct_mixed(
            transport,
            window,
            signature=WIN003_SIGNATURE,
            project_name=project_name,
            sortie_dir=sortie_dir,
        )
    values_unchanged = (
        offenders["theme"]["chars"] == THEME_CHARS
        and offenders["example"]["chars"] == EXAMPLE_CHARS
        and offenders["idea"]["chars"] == IDEA_CHARS
        and offenders["example"]["kind"] == "EXAMPLE"
        and offenders["idea"]["kind"] == "IDEA"
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "window_id": WINDOW_ID,
        "analysis_signature": WIN003_SIGNATURE,
        "identity": identity,
        "raw_bytes": len(raw),
        "raw_json_top_level_keys": sorted(raw_json.keys())
        if isinstance(raw_json, dict)
        else [],
        "structured_parse": structured,
        "local_lite_metadata": _status(metadata_ok),
        "src": _status(src_ok),
        "handles": _status(handle_ok),
        "numeric_regression": "YES" if numeric else "NO",
        "decoder": decoder,
        "handle_registry": registry,
        "handle_resolution": resolution,
        "local_validator": _status(validator == "PASS" and live_error is None),
        "v31_validator": validator,
        "capacity": "present" if capacity else "absent",
        "historical_granularity_error": historical_error,
        "historical_a28_reproduced": historical_error == A28_VALIDATOR_ERROR,
        "live_granularity_error": live_error,
        "validation_errors": list(validation.get("errors") or []),
        "offenders": offenders,
        "values_unchanged": values_unchanged,
        "theme_length": offenders["theme"]["chars"],
        "example_length": offenders["example"]["chars"],
        "idea_length": offenders["idea"]["chars"],
        "example_index": EXAMPLE_INDEX,
        "idea_index": IDEA_INDEX,
        "technical_ok": technical_ok,
        "review": review,
        "semantic_quality": review.get("semantic_quality"),
        "unsupported_content": review.get("unsupported_content"),
        "material_omissions": review.get("material_omissions"),
        "relation_quality_summary": review.get("relation_quality_summary"),
        "canonical": canonical,
        "canonical_reconstruction": canonical.get("local", {}).get("idea_validation")
        if canonical
        else None,
        "mixed_compatibility": canonical.get("mixed_compatibility"),
        "importance_to_kind_contamination": (
            canonical.get("local") or {}
        ).get("importance_to_kind_contamination"),
        "local_idea_kind": (canonical.get("local") or {}).get("idea_kinds"),
        "all_kinds_empty": (canonical.get("local") or {}).get("all_kinds_empty"),
        "transport": transport,
        "window": window,
        "transcript": bundle["transcript"],
        "validation": validation,
        "response_repaired": False,
        "truncated": False,
        "provider_calls": 0,
    }


__all__ = ["replay_saved_win003"]
