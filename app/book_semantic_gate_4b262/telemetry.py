"""Offline reasoning-token telemetry cases. No network."""

from __future__ import annotations

from typing import Any

from app.ai.providers.openai_engine import _usage_as_dict
from app.ai.structured import parse_json_payload
from app.ai.thinking import (
    UNKNOWN_TOKEN_COUNT,
    extract_openai_usage_telemetry,
    extract_thinking_tokens_from_usage,
)
from app.book_semantic_gate_4b24.validate import validate_semantic_response
from app.book_semantic_gate_4b262.constants import PHASE


class _DetailObject:
    def __init__(self, **kwargs: Any) -> None:
        for key, value in kwargs.items():
            setattr(self, key, value)


class _UsageObject:
    def __init__(self, **kwargs: Any) -> None:
        for key, value in kwargs.items():
            setattr(self, key, value)


def _case(name: str, usage: Any, *, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    telemetry = extract_openai_usage_telemetry(usage if isinstance(usage, dict) else _usage_as_dict(usage))
    extracted = extract_thinking_tokens_from_usage(
        usage if isinstance(usage, dict) else _usage_as_dict(usage)
    )
    row = {
        "name": name,
        "telemetry": telemetry,
        "extracted_thinking_or_reasoning": extracted,
        "persisted_usage": usage if isinstance(usage, dict) else _usage_as_dict(usage),
    }
    if extra:
        row.update(extra)
    return row


def run_telemetry_cases() -> dict[str, Any]:
    present = _case(
        "reasoning_tokens_present",
        {
            "prompt_tokens": 1200,
            "completion_tokens": 400,
            "total_tokens": 1600,
            "completion_tokens_details": {"reasoning_tokens": 320},
        },
    )
    absent = _case(
        "reasoning_tokens_absent",
        {"prompt_tokens": 1200, "completion_tokens": 400, "total_tokens": 1600},
    )
    explicit_zero = _case(
        "reasoning_tokens_explicit_zero",
        {
            "prompt_tokens": 10,
            "completion_tokens": 8,
            "completion_tokens_details": {"reasoning_tokens": 0},
        },
    )
    no_details = _case(
        "completion_tokens_details_absent",
        {"prompt_tokens": 10, "completion_tokens": 8, "total_tokens": 18},
    )
    historical_thinking = _case(
        "historical_thinking_tokens_still_read",
        {
            "input_tokens": 10,
            "output_tokens": 20,
            "output_tokens_details": {"thinking_tokens": 7},
        },
    )
    sdk_object = _case(
        "sdk_object_with_completion_details",
        _UsageObject(
            prompt_tokens=40,
            completion_tokens=90,
            total_tokens=130,
            completion_tokens_details=_DetailObject(reasoning_tokens=55),
        ),
    )
    empty_content = {
        "name": "empty_content",
        "content": "",
        "parse": None,
    }
    try:
        parse_json_payload("")
        empty_content["parse"] = "unexpected_pass"
    except Exception as exc:
        empty_content["parse"] = type(exc).__name__
        empty_content["kind"] = getattr(exc, "parse_failure_kind", None) or "empty"
    length = {
        "name": "finish_reason_length",
        "finish_reason": "length",
        "does_not_classify_missing_cases": True,
        "does_not_prove_reasoning_cause": True,
        "validation": validate_semantic_response(
            None,
            required_handles=["h01"],
            paragraph_texts={"h01": "x"},
        ),
    }
    valid_json = {
        "name": "valid_json",
        "parsed": parse_json_payload('{"ch":"CH016","v":"PASS","pr":[],"sc":{},"uh":[],"rr":false}'),
    }
    truncated = {"name": "truncated_json", "parse": None}
    try:
        parse_json_payload('{"ch":"CH016","v":"PASS","pr":[')
        truncated["parse"] = "unexpected_pass"
    except Exception as exc:
        truncated["parse"] = type(exc).__name__
        truncated["kind"] = getattr(exc, "parse_failure_kind", None) or "invalid"

    assertions = {
        "present_is_320": present["telemetry"]["reasoning_tokens"] == 320,
        "absent_is_unknown": absent["telemetry"]["reasoning_tokens"] == UNKNOWN_TOKEN_COUNT,
        "absent_is_not_zero": absent["extracted_thinking_or_reasoning"] is None,
        "explicit_zero_is_zero": explicit_zero["telemetry"]["reasoning_tokens"] == 0,
        "details_absent_unknown": no_details["telemetry"]["reasoning_tokens"]
        == UNKNOWN_TOKEN_COUNT,
        "historical_thinking_preserved": historical_thinking["extracted_thinking_or_reasoning"]
        == 7,
        "sdk_object_reasoning_persisted": sdk_object["extracted_thinking_or_reasoning"] == 55,
        "visible_not_inferred_by_subtraction": present["telemetry"]["visible_output_tokens"]
        == UNKNOWN_TOKEN_COUNT,
        "empty_content_not_accepted": empty_content["parse"] != "unexpected_pass",
        "length_missing_h01": (length["validation"] or {}).get("missing_cases") == ["h01"],
        "valid_json_parses": isinstance(valid_json["parsed"], dict),
        "truncated_json_fails": truncated["parse"] != "unexpected_pass",
        "did_not_infer_from_max_completion_tokens": present["telemetry"][
            "did_not_infer_from_max_completion_tokens"
        ],
        "did_not_infer_cause_from_finish_reason": present["telemetry"][
            "did_not_infer_cause_from_finish_reason"
        ],
    }
    return {
        "phase": PHASE,
        "cases": [
            present,
            absent,
            explicit_zero,
            no_details,
            historical_thinking,
            sdk_object,
            empty_content,
            length,
            valid_json,
            truncated,
        ],
        "assertions": assertions,
        "passed": all(assertions.values()),
        "failed": [name for name, ok in assertions.items() if not ok],
        "network_calls": 0,
        "secrets_included": False,
    }


__all__ = ["run_telemetry_cases"]
