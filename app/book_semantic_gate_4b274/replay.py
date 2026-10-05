"""Deterministic offline replays of saved h01/h02 responses. No provider calls."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from app.ai.errors import AIStructuredOutputError
from app.ai.structured import parse_json_payload
from app.book_semantic_gate_4b262.contract import validate_compact_payload
from app.book_semantic_gate_4b271.coverage import validate_compact_payload_111
from app.book_semantic_gate_4b271.evidence import load_saved_terra_payload as load_h01_payload
from app.book_semantic_gate_4b27.request import paragraph_context
from app.book_semantic_gate_4b272.identity import load_p3_gate_paragraph
from app.book_semantic_gate_4b274.claims import load_saved_h02_payload
from app.book_semantic_gate_4b274.constants import (
    H01_CASE_HANDLE,
    H02_CASE_HANDLE,
    PHASE,
    PROMPT_VERSION_111,
    PROMPT_VERSION_112,
)
from app.book_semantic_gate_4b274.coverage import validate_compact_payload_112
from app.book_semantic_gate_4b274.paths import historical_h01_dir, historical_h02_dir
from app.book_semantic_gate_4b274.reasons import inspect_payload_reason_codes
from app.file_utils import content_hash


def _parse(raw_text: str | None) -> dict[str, Any]:
    if raw_text is None or not str(raw_text).strip():
        return {"json_parse": "FAIL", "parsed": None, "error": "empty_or_missing"}
    try:
        parsed = parse_json_payload(str(raw_text))
    except AIStructuredOutputError as exc:
        return {
            "json_parse": "FAIL",
            "parsed": None,
            "error": str(exc),
            "kind": getattr(exc, "parse_failure_kind", None),
        }
    if not isinstance(parsed, dict):
        return {"json_parse": "FAIL", "parsed": parsed, "error": "not_object"}
    return {"json_parse": "PASS", "parsed": parsed, "error": None}


def _canonical(payload: Mapping[str, Any]) -> str:
    return content_hash(json.dumps(dict(payload), ensure_ascii=False, sort_keys=True))


def _load_raw_text(path: Path) -> str | None:
    if not path.is_file():
        return None
    return path.read_text(encoding="utf-8")


def replay_payload(
    parsed: Mapping[str, Any] | None,
    *,
    handle: str,
    text: str,
    kind: str = "substantive",
) -> dict[str, Any]:
    texts = {handle: text}
    handles = [handle]
    kinds = {handle: kind}
    frozen = validate_compact_payload(
        parsed,
        paragraph_texts=texts,
        required_handles=handles,
        paragraph_kinds=kinds,
    )
    v111 = validate_compact_payload_111(
        parsed,
        paragraph_texts=texts,
        required_handles=handles,
        paragraph_kinds=kinds,
    )
    v112 = validate_compact_payload_112(
        parsed,
        paragraph_texts=texts,
        required_handles=handles,
        paragraph_kinds=kinds,
    )
    reasons = inspect_payload_reason_codes(parsed)
    historical_verdict = None
    if isinstance(parsed, Mapping):
        historical_verdict = parsed.get("v")
        for para in parsed.get("pr") or []:
            if str(para.get("h") or "") == handle:
                historical_verdict = {
                    "chapter": parsed.get("v"),
                    "paragraph": para.get("v"),
                }
                break
    return {
        "json_object": isinstance(parsed, Mapping),
        "frozen_1_1_schema": {
            "status": frozen.get("status"),
            "errors": frozen.get("errors"),
            "coverage_errors": frozen.get("coverage_errors"),
            "span_errors": frozen.get("span_errors"),
        },
        "validator_1_1_1": {
            "status": v111.get("status"),
            "errors": v111.get("errors"),
            "coverage_errors": v111.get("coverage_errors"),
            "reason_code_warnings": v111.get("reason_code_warnings"),
        },
        "validator_1_1_2": {
            "status": v112.get("status"),
            "errors": v112.get("errors"),
            "coverage_errors": v112.get("coverage_errors"),
            "reason_code_errors": v112.get("reason_code_errors"),
        },
        "reason_codes": reasons,
        "historical_semantic_verdict": historical_verdict,
        "historical_verdict_not_rewritten": True,
        "raw_response_not_corrected": True,
        "missing_reason_codes_not_injected": True,
        "new_validator_does_not_prove_future_terra": True,
    }


def replay_case(
    *,
    handle: str,
    text: str,
    parsed: Mapping[str, Any] | None,
    raw_text: str | None,
) -> dict[str, Any]:
    first_parse = _parse(raw_text)
    second_parse = _parse(raw_text)
    first = replay_payload(parsed, handle=handle, text=text)
    second = replay_payload(parsed, handle=handle, text=text)
    identical = _canonical(first) == _canonical(second) and first_parse.get(
        "json_parse"
    ) == second_parse.get("json_parse")
    return {
        "handle": handle,
        "json_parse": first_parse.get("json_parse"),
        "parse_error": first_parse.get("error"),
        "deterministic": identical,
        "first": first,
        "second_status_1_1_2": second["validator_1_1_2"]["status"],
        "repaired": False,
        "provider_calls": 0,
    }


def historical_response_replays(*, root: Path | None = None) -> dict[str, Any]:
    h01_text = str(
        (paragraph_context(root=root).get("paragraph_texts") or {}).get(H01_CASE_HANDLE) or ""
    )
    h02_text = str(load_p3_gate_paragraph(root=root).get("text") or "")
    h01_parsed = load_h01_payload(root=root)
    h02_parsed = load_saved_h02_payload(root=root)
    h01_raw = _load_raw_text(
        historical_h01_dir(root=root) / "book_semantic_gate_4b27_raw_provider_text.txt"
    )
    h02_raw = _load_raw_text(historical_h02_dir(root=root) / "p3_real_raw_provider_text.txt")
    h01 = replay_case(
        handle=H01_CASE_HANDLE,
        text=h01_text,
        parsed=h01_parsed,
        raw_text=h01_raw,
    )
    h02 = replay_case(
        handle=H02_CASE_HANDLE,
        text=h02_text if "pr" in h02_parsed else "",
        parsed=h02_parsed if "pr" in h02_parsed else None,
        raw_text=h02_raw,
    )
    return {
        "phase": PHASE,
        "provider_calls": 0,
        "h01": h01,
        "h02": h02,
        "notes": {
            "h01_1_1_1": h01["first"]["validator_1_1_1"]["status"],
            "h01_1_1_2": h01["first"]["validator_1_1_2"]["status"],
            "h02_1_1_1": h02["first"]["validator_1_1_1"]["status"],
            "h02_1_1_2": h02["first"]["validator_1_1_2"]["status"],
            "h01_historical_verdict": h01["first"]["historical_semantic_verdict"],
            "h02_historical_verdict": h02["first"]["historical_semantic_verdict"],
            "coverage_1_1_2_may_differ_from_1_1_1": True,
            "difference_is_not_proof_terra_would_conform": True,
        },
        "candidate_versions_compared": [PROMPT_VERSION_111, PROMPT_VERSION_112],
        "secrets_included": False,
    }


__all__ = ["historical_response_replays", "replay_case", "replay_payload"]
