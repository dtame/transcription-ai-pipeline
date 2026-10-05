"""Raw 4B.2.6 response and token-usage forensics. No inference of reasoning counts."""

from __future__ import annotations

import inspect
from pathlib import Path
from typing import Any

from app.ai.openai_compat import (
    PRODUCTION_OPENAI_ENDPOINT,
    capture_openai_sdk_chat_request,
)
from app.ai.providers.openai_engine import OpenAIEngine, _usage_as_dict
from app.ai.structured import parse_json_payload
from app.ai.thinking import extract_thinking_tokens_from_usage
from app.book_semantic_gate_4b261.constants import (
    CONFIDENCE_CONFIRMED,
    CONFIDENCE_HYPOTHESIS,
    CONFIDENCE_LOCAL,
    CONFIDENCE_UNKNOWN,
    EXPECTED_REQUEST_SHA256_4B26,
    HISTORICAL_4B26_STATUS,
    MODEL,
    OBSERVED_4B26_COST_USD,
    OBSERVED_4B26_ELAPSED_MS,
    OBSERVED_4B26_FINISH_REASON,
    OBSERVED_4B26_INPUT_TOKENS,
    OBSERVED_4B26_OUTPUT_TOKENS,
    OBSERVED_4B26_REQUEST_ID,
    PHASE,
    PRODUCTION_ENDPOINT,
)
from app.book_semantic_gate_4b261.evidence import load_4b26_bundle, usage_field_inventory


def _first_value(hits: list[dict[str, Any]]) -> Any:
    for hit in hits:
        value = hit.get("value")
        if value not in (None, {}, []):
            return value
    return None


def raw_response_forensics(bundle: dict[str, Any] | None = None) -> dict[str, Any]:
    collected = bundle or load_4b26_bundle()
    loaded = dict(collected.get("loaded") or {})
    provider = dict(loaded.get("provider") or {})
    structured = dict(loaded.get("raw_structured") or {})
    forensics = dict(loaded.get("forensics") or {})
    raw_text = loaded.get("raw_text")
    if raw_text is None:
        raw_text = ""
    inventory = usage_field_inventory(collected)
    refusal_hits = inventory.get("refusal") or []
    content_hits = [
        hit
        for hit in (inventory.get("content") or [])
        if str(hit.get("path") or "").endswith(".content")
        or str(hit.get("path") or "").endswith("raw_content")
    ]
    persisted = str(provider.get("raw_response") if provider.get("raw_response") is not None else raw_text or structured.get("text") or "")
    visible = persisted.strip()
    return {
        "phase": PHASE,
        "historical_4b26": HISTORICAL_4B26_STATUS,
        "request_sha256": collected.get("request_sha256") or EXPECTED_REQUEST_SHA256_4B26,
        "request_id": provider.get("request_id") or OBSERVED_4B26_REQUEST_ID,
        "model": MODEL,
        "endpoint": PRODUCTION_ENDPOINT,
        "http_status": {
            "value": provider.get("http_status"),
            "available": provider.get("http_status") is not None,
            "forensics_http_status_available": forensics.get("http_status_available"),
            "confidence": CONFIDENCE_CONFIRMED,
            "note": "SDK completion was persisted; raw HTTP status was not.",
        },
        "finish_reason": {
            "value": provider.get("finish_reason") or forensics.get("finish_reason"),
            "expected": OBSERVED_4B26_FINISH_REASON,
            "confidence": CONFIDENCE_CONFIRMED,
        },
        "elapsed_ms": {
            "value": provider.get("elapsed_ms") or OBSERVED_4B26_ELAPSED_MS,
            "confidence": CONFIDENCE_CONFIRMED,
        },
        "message_content": {
            "visible_text": visible,
            "visible_chars": len(visible),
            "visible_bytes": len(visible.encode("utf-8")),
            "persisted_file_bytes": len(persisted.encode("utf-8")),
            "persisted_is_whitespace_only": bool(persisted) and not visible,
            "raw_text_present": bool(visible),
            "structured_text": structured.get("text"),
            "structured_parsed": structured.get("parsed"),
            "structured_truncated": structured.get("truncated"),
            "forensics_raw_text_present": (forensics.get("raw_content") or {}).get(
                "raw_text_present"
            ),
            "confidence": CONFIDENCE_CONFIRMED,
        },
        "message_refusal": {
            "value": _first_value(refusal_hits),
            "hits": refusal_hits,
            "persisted": bool(refusal_hits),
            "status": "UNKNOWN" if not refusal_hits else "PRESENT",
            "confidence": CONFIDENCE_UNKNOWN if not refusal_hits else CONFIDENCE_CONFIRMED,
            "note": (
                "No message.refusal field was persisted in the 4B.2.6 audits. "
                "Absence from artifacts is not proof the server omitted it."
            ),
        },
        "other_output_fields": {
            "provider_metadata": provider.get("provider_metadata"),
            "content_hits": content_hits,
            "parse_error": forensics.get("parse_error") or provider.get("error"),
        },
        "request_metadata": {
            "max_completion_tokens": (collected.get("payload") or {}).get(
                "max_completion_tokens"
            ),
            "max_tokens_absent": "max_tokens" not in (collected.get("payload") or {}),
            "temperature_present": "temperature" in (collected.get("payload") or {}),
            "thinking_present": "thinking" in (collected.get("payload") or {}),
            "response_format": (collected.get("payload") or {}).get("response_format"),
        },
        "json_usable": False,
        "cases_classified": 0,
        "missing_decisions_are_not_misclassifications": True,
        "secrets_included": False,
    }


def token_usage_analysis(bundle: dict[str, Any] | None = None) -> dict[str, Any]:
    collected = bundle or load_4b26_bundle()
    loaded = dict(collected.get("loaded") or {})
    provider = dict(loaded.get("provider") or {})
    cost = dict(loaded.get("cost") or {})
    forensics = dict(loaded.get("forensics") or {})
    inventory = usage_field_inventory(collected)
    details_hits = inventory.get("completion_tokens_details") or []
    reasoning_hits = inventory.get("reasoning_tokens") or []
    thinking_hits = [
        hit
        for hit in (inventory.get("thinking_tokens") or [])
        if hit.get("value") not in (None, "unknown")
    ]
    extracted = extract_thinking_tokens_from_usage(
        forensics.get("usage") if isinstance(forensics.get("usage"), dict) else {}
    )
    if extracted is None:
        extracted = extract_thinking_tokens_from_usage(
            {
                "prompt_tokens": provider.get("input_tokens"),
                "completion_tokens": provider.get("output_tokens"),
                "total_tokens": None,
            }
        )
    usage_source = (forensics.get("usage") or {}).get("source")
    return {
        "phase": PHASE,
        "usage_fields_available": {
            "prompt_tokens_or_input_tokens": OBSERVED_4B26_INPUT_TOKENS,
            "completion_tokens_or_output_tokens": OBSERVED_4B26_OUTPUT_TOKENS,
            "total_tokens": OBSERVED_4B26_INPUT_TOKENS + OBSERVED_4B26_OUTPUT_TOKENS,
            "completion_tokens_details": None,
            "reasoning_tokens": "UNKNOWN",
            "thinking_tokens": "UNKNOWN",
            "finish_reason": OBSERVED_4B26_FINISH_REASON,
        },
        "provider_reported": {
            "input_tokens": provider.get("input_tokens"),
            "output_tokens": provider.get("output_tokens"),
            "thinking_tokens": provider.get("thinking_tokens"),
            "usage_source": usage_source,
            "forensics_usage": forensics.get("usage"),
            "cost_thinking_tokens_status": cost.get("thinking_tokens_status"),
        },
        "reasoning_tokens": "UNKNOWN",
        "visible_output_tokens": "UNKNOWN",
        "do_not_infer_reasoning_from_completion_tokens": True,
        "why_reasoning_is_unknown": [
            "Preserved 4B.2.6 artifacts do not contain completion_tokens_details.",
            "Preserved artifacts do not contain reasoning_tokens.",
            "thinking_tokens is null / unknown, not zero.",
            "Visible message.content is empty, so visible output tokens cannot be counted from text.",
            "completion_tokens=8192 must not be treated as a reasoning count.",
        ],
        "local_extraction_gap": {
            "confidence": CONFIDENCE_LOCAL,
            "extract_thinking_tokens_from_usage_reads": [
                "output_tokens_details.thinking_tokens",
                "usage.thinking_tokens",
            ],
            "does_not_read": ["completion_tokens_details.reasoning_tokens"],
            "usage_as_dict_fallback_keys": [
                "prompt_tokens",
                "completion_tokens",
                "total_tokens",
            ],
            "note": (
                "Even if the server sent OpenAI completion_tokens_details, "
                "the persisted 4B.2.6 audits do not contain that object. "
                "Missing persistence is not proof the server omitted it."
            ),
        },
        "inventory": {
            "completion_tokens_details_hits": details_hits,
            "reasoning_tokens_hits": reasoning_hits,
            "non_null_thinking_token_hits": thinking_hits,
            "extracted_thinking_tokens": extracted,
        },
        "observed_cost_usd": OBSERVED_4B26_COST_USD,
        "budget_exhausted": True,
        "visible_json_bytes": 0,
        "confidence": {
            "input_tokens": CONFIDENCE_CONFIRMED,
            "completion_tokens": CONFIDENCE_CONFIRMED,
            "finish_reason_length": CONFIDENCE_CONFIRMED,
            "reasoning_tokens": CONFIDENCE_UNKNOWN,
            "hidden_reasoning_consumed_budget": CONFIDENCE_HYPOTHESIS,
        },
        "secrets_included": False,
    }


def inspect_usage_as_dict_source() -> dict[str, Any]:
    source = inspect.getsource(_usage_as_dict)
    normalize = inspect.getsource(OpenAIEngine._normalize)
    return {
        "usage_as_dict_source_mentions_details": "completion_tokens_details" in source,
        "normalize_errors_on_none_content": "NO_TEXT_BLOCK" in normalize
        or "aucun contenu" in normalize,
        "normalize_strips_empty_string": "str(content).strip()" in normalize,
    }


def sdk_capture_historical_payload(payload: dict[str, Any]) -> dict[str, Any]:
    captured = capture_openai_sdk_chat_request(payload)
    body = dict(captured.get("body") or {})
    return {
        **captured,
        "endpoint": PRODUCTION_OPENAI_ENDPOINT,
        "max_completion_tokens": body.get("max_completion_tokens"),
        "max_tokens_absent": "max_tokens" not in body,
        "json_object": body.get("response_format") == {"type": "json_object"},
        "network_calls": 0,
    }


def parse_recorded_empty_response(text: str) -> dict[str, Any]:
    try:
        parse_json_payload(text)
        return {"empty": False, "error": None}
    except Exception as exc:
        return {
            "empty": True,
            "error_type": type(exc).__name__,
            "message": str(exc),
            "parse_failure_kind": getattr(exc, "parse_failure_kind", None),
        }


def collect_forensics(*, root: Path | None = None) -> dict[str, Any]:
    bundle = load_4b26_bundle(root=root)
    return {
        "bundle": bundle,
        "raw": raw_response_forensics(bundle),
        "usage": token_usage_analysis(bundle),
        "adapter": inspect_usage_as_dict_source(),
    }


__all__ = [
    "collect_forensics",
    "inspect_usage_as_dict_source",
    "parse_recorded_empty_response",
    "raw_response_forensics",
    "sdk_capture_historical_payload",
    "token_usage_analysis",
]
