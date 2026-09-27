"""Replay offline exact A.22. Parse structured. Ne répare pas. Ne promeut pas."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.ai.providers.anthropic_engine import extract_anthropic_text
from app.ai.structured import parse_structured_output
from app.source_analysis_local_v3.decoder import decode_v3_transport
from app.source_analysis_local_v3.schema import build_semantic_transport_v3_schema
from app.source_analysis_v3_a22_forensics.constants import (
    A22_RECORDS,
    A22_SIGNATURE,
    A22_STRUCTURED_PARSE,
    MODE,
    PHASE,
    PROJECT_NAME,
    SCHEMA_VERSION,
    SEMANTIC_REVIEW_STATUS,
)
from app.source_analysis_v3_a22_forensics.evidence import read_a22_raw_bytes
from app.source_analysis_v3_real_win001.metrics import record_metrics
from app.source_analysis_v3_second_window.window import load_selected_window

A22_DECODER = "FAIL"


def extract_a22_structured_text(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> tuple[str, dict[str, Any], bytes]:
    raw = read_a22_raw_bytes(project_name, sortie_dir=sortie_dir)
    data = json.loads(raw.decode("utf-8"))
    text = extract_anthropic_text(data)
    return text, data, raw


def replay_a22_offline(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> dict[str, Any]:
    text, raw_json, raw = extract_a22_structured_text(
        project_name, sortie_dir=sortie_dir
    )
    schema = build_semantic_transport_v3_schema()
    structured = "FAIL"
    decoder = "FAIL"
    errors: list[str] = []
    payload: dict[str, Any] | None = None
    try:
        parsed = parse_structured_output(text, schema)
        if isinstance(parsed, dict):
            payload = parsed
            structured = "PASS"
        else:
            errors.append("structured parse did not return an object")
    except Exception as exc:
        errors.append(str(exc))

    bundle = load_selected_window(project_name, sortie_dir=sortie_dir)
    window = bundle["window"]
    allowed = set(window.owned_src_refs) | set(window.context_src_refs)
    if payload is not None:
        try:
            decode_v3_transport(payload, allowed_source_refs=allowed)
            decoder = "PASS"
        except Exception as exc:
            errors.append(str(exc))

    records = payload.get("records") if isinstance(payload, dict) else []
    rec_count = len(records) if isinstance(records, list) else 0
    reproduced = (
        structured == A22_STRUCTURED_PARSE
        and decoder == A22_DECODER
        and rec_count == A22_RECORDS
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "analysis_signature": A22_SIGNATURE,
        "semantic_review_status": SEMANTIC_REVIEW_STATUS,
        "raw_json_top_level_keys": sorted(raw_json.keys())
        if isinstance(raw_json, dict)
        else [],
        "structured_text_chars": len(text),
        "structured_parse": structured,
        "v3_decoder": decoder,
        "official_pipeline": "FAIL",
        "replay_errors": errors,
        "record_count": rec_count,
        "record_metrics": record_metrics(payload),
        "transport": payload,
        "window": window,
        "transcript": bundle["transcript"],
        "identity": bundle["identity"],
        "allowed_source_refs": sorted(allowed),
        "owned_source_refs": list(window.owned_src_refs),
        "context_source_refs": list(window.context_src_refs),
        "evidence_modified": False,
        "response_repaired": False,
        "normalized": False,
        "promoted": False,
        "cached": False,
        "reproduced": reproduced,
        "raw_bytes": len(raw),
    }


__all__ = ["extract_a22_structured_text", "replay_a22_offline"]
