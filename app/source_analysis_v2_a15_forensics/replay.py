"""Replay offline exact A.15. Parse / decode / validate. Pas de repair."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.ai.providers.anthropic_engine import extract_anthropic_text
from app.ai.structured import parse_structured_output
from app.source_analysis_local_v2.decoder import decode_v2_transport
from app.source_analysis_local_v2.schema import build_semantic_transport_v2_schema
from app.source_analysis_local_v2.validator import validate_v2_links, validate_v2_transport
from app.source_analysis_v2_a15_forensics.constants import (
    A15_DECODER,
    A15_INVALID_LINKS,
    A15_RECORDS,
    A15_SIGNATURE,
    A15_STRUCTURED_PARSE,
    A15_VALIDATOR,
    MODE,
    PHASE,
    PROJECT_NAME,
    SCHEMA_VERSION,
    SEMANTIC_REVIEW_STATUS,
)
from app.source_analysis_v2_a15_forensics.evidence import read_a15_raw_bytes
from app.source_analysis_v2_real_win001.metrics import link_metrics, record_metrics
from app.source_analysis_v2_real_win001.window import load_candidate_win001


def extract_a15_structured_text(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> tuple[str, dict[str, Any], bytes]:
    raw = read_a15_raw_bytes(project_name, sortie_dir=sortie_dir)
    data = json.loads(raw.decode("utf-8"))
    text = extract_anthropic_text(data)
    return text, data, raw


def replay_a15_offline(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> dict[str, Any]:
    text, raw_json, raw = extract_a15_structured_text(
        project_name, sortie_dir=sortie_dir
    )
    schema = build_semantic_transport_v2_schema()
    structured = "FAIL"
    decoder = "FAIL"
    validator = "FAIL"
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

    bundle = load_candidate_win001(project_name, sortie_dir=sortie_dir)
    window = bundle["window"]
    allowed = set(window.owned_src_refs) | set(window.context_src_refs)
    if payload is not None:
        try:
            decode_v2_transport(payload, allowed_source_refs=allowed)
            decoder = "PASS"
        except Exception as exc:
            errors.append(str(exc))
        try:
            validate_v2_links(payload)
            if decoder == "PASS":
                validate_v2_transport(payload, window)
            validator = "PASS"
        except Exception as exc:
            errors.append(str(exc))

    records = payload.get("records") if isinstance(payload, dict) else []
    rec_count = len(records) if isinstance(records, list) else 0
    links = link_metrics(payload)
    reproduced = (
        structured == A15_STRUCTURED_PARSE
        and decoder == A15_DECODER
        and validator == A15_VALIDATOR
        and rec_count == A15_RECORDS
        and int(links.get("invalid_targets") or 0) == A15_INVALID_LINKS
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "analysis_signature": A15_SIGNATURE,
        "semantic_review_status": SEMANTIC_REVIEW_STATUS,
        "raw_json_top_level_keys": sorted(raw_json.keys())
        if isinstance(raw_json, dict)
        else [],
        "structured_text_chars": len(text),
        "structured_parse": structured,
        "v2_decoder": decoder,
        "v2_validator": validator,
        "replay_errors": errors,
        "record_count": rec_count,
        "record_metrics": record_metrics(payload),
        "link_metrics": links,
        "transport": payload,
        "window": window,
        "transcript": bundle["transcript"],
        "evidence_modified": False,
        "response_repaired": False,
        "promoted": False,
        "cached": False,
        "reproduced": reproduced,
    }


__all__ = ["extract_a15_structured_text", "replay_a15_offline"]
