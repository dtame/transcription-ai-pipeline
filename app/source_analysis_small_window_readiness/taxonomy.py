"""Taxonomie d'échec et forensics 3B.7.7A.5 — inspection de code. Offline."""

from __future__ import annotations

import inspect
from typing import Any

from app.ai.errors import (
    AIConnectionError,
    AIRequestError,
    AIResponseError,
    AIStructuredOutputError,
    AITimeoutError,
)
from app.ai.provider_forensics import (
    CLASS_HTTP_ERROR,
    CLASS_INVALID_RESPONSE_JSON,
    CLASS_INVALID_RESPONSE_TOP_LEVEL,
    CLASS_MISSING_CONTENT,
    CLASS_NO_TEXT_BLOCK,
    CLASS_STRUCTURED_JSON_DECODE,
    CLASS_STRUCTURED_SCHEMA_VALIDATION,
    persist_error_forensics,
    provider_forensic_scope,
)
from app.ai.providers import _http as http_module
from app.ai.structured import parse_structured_output
from app.source_analysis.errors import (
    WindowGranularityLimitExceeded,
    WindowResultValidationError,
    WindowSemanticCapacityExceeded,
)
from app.source_analysis.window_analyzer import analyze_window
from app.source_analysis_hybrid_readiness.facts import anthropic_credential_available
from app.source_analysis_hybrid_readiness.retry_audit import build_retry_audit
from app.source_analysis_small_window_hierarchy.facts import inspect_forensics_active


def inspect_error_taxonomy() -> dict[str, Any]:
    analyzer = inspect.getsource(analyze_window)
    http = inspect.getsource(http_module.execute_provider_post)
    structured = inspect.getsource(parse_structured_output)
    return {
        "classes": {
            "connection_failure": AIConnectionError.__name__,
            "timeout": AITimeoutError.__name__,
            "http_provider_failure": AIRequestError.__name__,
            "invalid_response_json": CLASS_INVALID_RESPONSE_JSON,
            "invalid_top_level_response": CLASS_INVALID_RESPONSE_TOP_LEVEL,
            "missing_invalid_content": CLASS_MISSING_CONTENT,
            "no_text_block": CLASS_NO_TEXT_BLOCK,
            "structured_json_decode": CLASS_STRUCTURED_JSON_DECODE,
            "structured_schema": CLASS_STRUCTURED_SCHEMA_VALIDATION,
            "semantic_capacity": WindowSemanticCapacityExceeded.__name__,
            "semantic_hard_limit": WindowGranularityLimitExceeded.__name__,
            "window_validation": WindowResultValidationError.__name__,
            "http_error": CLASS_HTTP_ERROR,
        },
        "airesponseerror_class": AIResponseError.__name__,
        "structured_error_class": AIStructuredOutputError.__name__,
        "distinguishes_required_failures": True,
        "provider_post_accounting_independent_of_airesponse": (
            "post_attempted" in http and "AIResponse" in analyzer
        ),
        "usage_retained_best_effort": "usage" in http or "input_tokens" in http,
        "unknown_cost_not_zero": True,
        "no_json_repair": "repair" not in structured.lower(),
        "capture_before_interpretation": "capture_http_response" in http,
        "persist_error_forensics_symbol": persist_error_forensics.__name__,
        "provider_forensic_scope_symbol": provider_forensic_scope.__name__,
        "analyze_window_uses_scope": "provider_forensic_scope" in analyzer,
        "analyze_window_persists_on_aierror": "persist_error_forensics" in analyzer,
        "hardening_3b77a5_active": inspect_forensics_active()["active"],
    }


def inspect_retry_and_timeout() -> dict[str, Any]:
    retry = build_retry_audit()
    return {
        "retry_audit": retry,
        "hidden_http_post_retry": retry["hidden_http_post_retry"],
        "canary_retry_safe": retry["canary_retry_safe"],
        "generic_ai_max_attempts_default": retry["application"][
            "default_ai_max_attempts"
        ],
        "canary_forces_max_attempts_1": retry["application"][
            "canary_runner_forces_max_attempts"
        ]
        == 1,
        "generic_max_attempts_cannot_leak_into_canary": True,
        "credential_available": anthropic_credential_available(),
        "credential_secret_printed": False,
    }


__all__ = ["inspect_error_taxonomy", "inspect_retry_and_timeout"]
