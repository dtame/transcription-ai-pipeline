"""Deterministic offline replay from the saved Terra h11 response. No provider calls."""

from __future__ import annotations

import json
from typing import Any, Mapping, Sequence

from app.ai.errors import AIStructuredOutputError
from app.ai.structured import parse_json_payload
from app.book_semantic_gate_4b275.coverage import validate_compact_payload_113
from app.book_semantic_gate_4b277.constants import PHASE, PROMPT_VERSION, SELECTED_CASE_HANDLE
from app.file_utils import content_hash


def parse_saved_response(raw_text: str | None) -> dict[str, Any]:
    if raw_text is None or not str(raw_text).strip():
        return {
            "json_parse": "FAIL",
            "parsed": None,
            "error": "empty_or_missing",
            "repaired": False,
        }
    try:
        parsed = parse_json_payload(str(raw_text))
    except AIStructuredOutputError as exc:
        return {
            "json_parse": "FAIL",
            "parsed": None,
            "error": str(exc),
            "kind": getattr(exc, "parse_failure_kind", None),
            "repaired": False,
        }
    if not isinstance(parsed, dict):
        return {
            "json_parse": "FAIL",
            "parsed": parsed,
            "error": "not_object",
            "repaired": False,
        }
    return {"json_parse": "PASS", "parsed": parsed, "error": None, "repaired": False}


def _canonical(payload: Mapping[str, Any]) -> str:
    return content_hash(json.dumps(dict(payload), ensure_ascii=False, sort_keys=True))


def replay_saved_response(
    raw_text: str | None,
    *,
    paragraph_texts: Mapping[str, str],
    required_handles: Sequence[str] | None = None,
    paragraph_kinds: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    handles = list(required_handles or [SELECTED_CASE_HANDLE])
    first_parse = parse_saved_response(raw_text)
    second_parse = parse_saved_response(raw_text)
    first = validate_compact_payload_113(
        first_parse.get("parsed") if isinstance(first_parse.get("parsed"), dict) else None,
        paragraph_texts=paragraph_texts,
        required_handles=handles,
        paragraph_kinds=paragraph_kinds,
    )
    second = validate_compact_payload_113(
        second_parse.get("parsed") if isinstance(second_parse.get("parsed"), dict) else None,
        paragraph_texts=paragraph_texts,
        required_handles=handles,
        paragraph_kinds=paragraph_kinds,
    )
    first_hash = _canonical(first)
    second_hash = _canonical(second)
    identical = first_hash == second_hash and first_parse.get("json_parse") == second_parse.get(
        "json_parse"
    )
    return {
        "phase": PHASE,
        "provider_calls": 0,
        "first_parse": first_parse.get("json_parse"),
        "second_parse": second_parse.get("json_parse"),
        "first_status": first.get("status"),
        "second_status": second.get("status"),
        "first_sha256": first_hash,
        "second_sha256": second_hash,
        "identical": identical,
        "pass": identical,
        "repaired": False,
        "contract_candidate": PROMPT_VERSION,
        "first": {
            "json_parse": first_parse.get("json_parse"),
            "status": first.get("status"),
            "errors": first.get("errors"),
            "missing_handles": first.get("missing_handles"),
            "coverage_errors": first.get("coverage_errors"),
        },
        "second": {
            "json_parse": second_parse.get("json_parse"),
            "status": second.get("status"),
            "errors": second.get("errors"),
            "missing_handles": second.get("missing_handles"),
            "coverage_errors": second.get("coverage_errors"),
        },
        "secrets_included": False,
    }


__all__ = ["parse_saved_response", "replay_saved_response"]
