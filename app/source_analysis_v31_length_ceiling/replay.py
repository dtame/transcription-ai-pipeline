"""Replay offline exact WIN003. Parse + valide. Ne répare pas. Ne promeut pas."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.ai.providers.anthropic_engine import extract_anthropic_text
from app.source_analysis.errors import WindowGranularityLimitExceeded
from app.source_analysis_local_v2.granularity import (
    V11_MINIMAL_TEXT_HARD_LIMITS,
    validate_v11_minimal_transport_granularity,
)
from app.source_analysis_v31_length_ceiling.constants import (
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
from app.source_analysis_v31_length_ceiling.evidence import read_win003_raw_bytes
from app.source_analysis_v31_remaining_windows.window import load_candidate_plan
from app.source_analysis_v31_real_win004.validate import interpret_local_lite_response


def extract_win003_structured_text(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> tuple[str, dict[str, Any], bytes]:
    raw = read_win003_raw_bytes(project_name, sortie_dir=sortie_dir)
    data = json.loads(raw.decode("utf-8"))
    text = extract_anthropic_text(data)
    return text, data, raw


def _char_len(value: Any) -> int:
    return len(str(value)) if value is not None else 0


def offending_values(transport: dict[str, Any] | None) -> dict[str, Any]:
    records = list((transport or {}).get("records") or [])
    theme = str((transport or {}).get("theme") or "")
    idea = records[IDEA_INDEX] if len(records) > IDEA_INDEX else {}
    example = records[EXAMPLE_INDEX] if len(records) > EXAMPLE_INDEX else {}
    idea_v = str(idea.get("v") or "")
    example_v = str(example.get("v") or "")
    return {
        "theme": {
            "field": "theme",
            "kind": None,
            "index": None,
            "value": theme,
            "chars": _char_len(theme),
            "python_len": len(theme),
            "utf8_bytes": len(theme.encode("utf-8")),
            "production_limit": V11_MINIMAL_TEXT_HARD_LIMITS["theme"],
            "a28_inventory_limit": 200,
            "exceeds_production": len(theme) > V11_MINIMAL_TEXT_HARD_LIMITS["theme"],
        },
        "idea": {
            "field": f"records[{IDEA_INDEX}].v",
            "kind": str(idea.get("k") or ""),
            "index": IDEA_INDEX,
            "value": idea_v,
            "chars": _char_len(idea_v),
            "python_len": len(idea_v),
            "utf8_bytes": len(idea_v.encode("utf-8")),
            "production_limit": V11_MINIMAL_TEXT_HARD_LIMITS["IDEA.v"],
            "a28_inventory_limit": 200,
            "exceeds_production": len(idea_v) > V11_MINIMAL_TEXT_HARD_LIMITS["IDEA.v"],
            "source_refs": list(idea.get("s") or []),
            "handle": idea.get("h"),
            "links": list(idea.get("l") or []),
            "metadata": list(idea.get("m") or []),
        },
        "example": {
            "field": f"records[{EXAMPLE_INDEX}].v",
            "kind": str(example.get("k") or ""),
            "index": EXAMPLE_INDEX,
            "value": example_v,
            "chars": _char_len(example_v),
            "python_len": len(example_v),
            "utf8_bytes": len(example_v.encode("utf-8")),
            "production_limit": V11_MINIMAL_TEXT_HARD_LIMITS["EXAMPLE.v"],
            "a28_inventory_limit": 200,
            "exceeds_production": len(example_v) > V11_MINIMAL_TEXT_HARD_LIMITS["EXAMPLE.v"],
            "source_refs": list(example.get("s") or []),
            "handle": example.get("h"),
            "links": list(example.get("l") or []),
            "metadata": list(example.get("m") or []),
        },
    }


def replay_win003_offline(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> dict[str, Any]:
    text, raw_json, raw = extract_win003_structured_text(
        project_name, sortie_dir=sortie_dir
    )
    bundle = load_candidate_plan(project_name, sortie_dir=sortie_dir)
    window = bundle["windows"][WINDOW_ID]
    validation = interpret_local_lite_response(
        None,
        window=window,
        raw_text=text,
    )
    transport = validation.get("transport")
    granularity_error = None
    if isinstance(transport, dict):
        try:
            validate_v11_minimal_transport_granularity(transport)
        except WindowGranularityLimitExceeded as exc:
            granularity_error = str(exc)
    if granularity_error:
        validation = dict(validation)
        validation["v31_validator"] = "FAIL"
        validation["v3_validator"] = "FAIL"
        errors = list(validation.get("errors") or [])
        if granularity_error not in errors:
            errors.append(granularity_error)
        validation["errors"] = errors
    offenders = offending_values(transport if isinstance(transport, dict) else None)
    reproduced = (
        validation.get("structured_parse") == "PASS"
        and validation.get("v31_decoder") == "PASS"
        and validation.get("v31_validator") == "FAIL"
        and granularity_error == A28_VALIDATOR_ERROR
        and offenders["theme"]["chars"] == THEME_CHARS
        and offenders["idea"]["chars"] == IDEA_CHARS
        and offenders["example"]["chars"] == EXAMPLE_CHARS
        and offenders["idea"]["kind"] == "IDEA"
        and offenders["example"]["kind"] == "EXAMPLE"
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "window_id": WINDOW_ID,
        "analysis_signature": WIN003_SIGNATURE,
        "raw_bytes": len(raw),
        "structured_text_chars": len(text),
        "raw_json_top_level_keys": sorted(raw_json.keys())
        if isinstance(raw_json, dict)
        else [],
        "structured_parse": validation.get("structured_parse"),
        "v31_decoder": validation.get("v31_decoder"),
        "handle_registry": validation.get("handle_registry"),
        "handle_resolution": validation.get("handle_resolution"),
        "v31_validator": validation.get("v31_validator"),
        "validation_errors": list(validation.get("errors") or []),
        "granularity_error": granularity_error,
        "matches_a28_validator_error": granularity_error == A28_VALIDATOR_ERROR,
        "offenders": offenders,
        "transport": transport,
        "window": window,
        "transcript": bundle["transcript"],
        "validation": validation,
        "evidence_modified": False,
        "response_repaired": False,
        "normalized": False,
        "promoted": False,
        "cached": False,
        "truncated": False,
        "reproduced": reproduced,
        "idea_exceeds_production_280": offenders["idea"]["exceeds_production"],
        "a28_inventory_treated_idea_as_200": True,
    }


__all__ = [
    "extract_win003_structured_text",
    "offending_values",
    "replay_win003_offline",
]
