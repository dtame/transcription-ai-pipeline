"""Replay offline A.13. Parse / decode / validate. Pas de repair. Pas d'écriture A.13."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.ai.providers.anthropic_engine import extract_anthropic_text
from app.ai.structured import parse_structured_output
from app.source_analysis_local_v2.decoder import decode_v2_transport
from app.source_analysis_local_v2.schema import build_semantic_transport_v2_schema
from app.source_analysis_local_v2.validator import validate_v2_links, validate_v2_transport
from app.source_analysis_v2_grammar_canary.fixture import build_synthetic_fixture
from app.source_analysis_v2_link_semantics.constants import (
    A13_CLASSIFICATION,
    A13_RECORDED_ERROR,
    A13_REQUEST_IDENTITY,
    PROJECT_NAME,
    SCHEMA_VERSION,
    PHASE,
    MODE,
)
from app.source_analysis_v2_link_semantics.evidence import read_a13_raw_bytes


def extract_a13_structured_text(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> tuple[str, dict[str, Any]]:
    raw = read_a13_raw_bytes(project_name, sortie_dir=sortie_dir)
    data = json.loads(raw.decode("utf-8"))
    text = extract_anthropic_text(data)
    return text, data


def record_link_failures(payload: dict[str, Any]) -> list[dict[str, Any]]:
    records = payload.get("records") or []
    failures: list[dict[str, Any]] = []
    bound = len(records) if isinstance(records, list) else 0
    if not isinstance(records, list):
        return failures
    for index, item in enumerate(records):
        if not isinstance(item, dict):
            continue
        kind = str(item.get("k") or "")
        links = item.get("l") or []
        if not isinstance(links, list):
            continue
        targets: list[dict[str, Any]] = []
        reasons: list[str] = []
        for link in links:
            if not isinstance(link, int) or isinstance(link, bool):
                reasons.append(f"non-integer link {link!r}")
                continue
            if link == index:
                reasons.append(
                    f"self-link: records[{index}] {kind}.l={link} points to itself"
                )
            if link < 0 or link >= bound:
                reasons.append(f"out-of-range index {link}")
                targets.append({"index": link, "kind": None, "in_range": False})
                continue
            target_kind = str(records[link].get("k") or "")
            targets.append({"index": link, "kind": target_kind, "in_range": True})
            if kind == "IDEA" and target_kind != "TOPIC":
                reasons.append(
                    f"IDEA.l={link} target kind {target_kind} ≠ TOPIC"
                )
            if kind == "EXAMPLE" and target_kind != "IDEA":
                reasons.append(
                    f"EXAMPLE.l={link} target kind {target_kind} ≠ IDEA"
                )
        if reasons:
            failures.append(
                {
                    "record_index": index,
                    "record_kind": kind,
                    "l": list(links),
                    "targets": targets,
                    "reasons": reasons,
                }
            )
    return failures


def replay_a13_offline(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> dict[str, Any]:
    text, raw_json = extract_a13_structured_text(project_name, sortie_dir=sortie_dir)
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

    fixture = build_synthetic_fixture()
    allowed = set(fixture.window.owned_src_refs) | set(fixture.window.context_src_refs)
    if payload is not None:
        try:
            decode_v2_transport(payload, allowed_source_refs=allowed)
            decoder = "PASS"
        except Exception as exc:
            errors.append(str(exc))
        try:
            validate_v2_links(payload)
            if decoder == "PASS":
                validate_v2_transport(payload, fixture.window)
            validator = "PASS"
        except Exception as exc:
            errors.append(str(exc))

    failures = record_link_failures(payload or {})
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "request_identity": A13_REQUEST_IDENTITY,
        "raw_json_top_level_keys": sorted(raw_json.keys()) if isinstance(raw_json, dict) else [],
        "structured_text": text,
        "structured_parse": structured,
        "v2_decoder": decoder,
        "v2_validator": validator,
        "classification": A13_CLASSIFICATION,
        "a13_recorded_error": A13_RECORDED_ERROR,
        "replay_errors": errors,
        "link_failures": failures,
        "transport": payload,
        "evidence_modified": False,
        "response_repaired": False,
        "reproduced": structured == "PASS" and decoder == "FAIL" and bool(failures),
    }


__all__ = [
    "extract_a13_structured_text",
    "record_link_failures",
    "replay_a13_offline",
]
