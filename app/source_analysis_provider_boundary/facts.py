"""Faits déterministes 3B.7.7A.5. Aucun appel provider."""

from __future__ import annotations

import inspect
import json
from pathlib import Path
from typing import Any

from app.ai.errors import AIResponseError
from app.ai.provider_forensics import (
    CLASS_HTTP_ERROR,
    CLASS_HTTP_TRANSPORT_FAILURE,
    CLASS_INVALID_CONTENT_TYPE,
    CLASS_INVALID_RESPONSE_JSON,
    CLASS_INVALID_RESPONSE_TOP_LEVEL,
    CLASS_INVALID_TEXT_BLOCK,
    CLASS_MISSING_CONTENT,
    CLASS_NO_TEXT_BLOCK,
    CLASS_STRUCTURED_JSON_DECODE,
    CLASS_STRUCTURED_SCHEMA_VALIDATION,
    FORENSICS_DIR_NAME,
    SAFE_RESPONSE_HEADERS,
)
from app.ai.providers import anthropic_engine
from app.ai.providers import openai_engine
from app.ai.providers import ollama as ollama_engine
from app.ai.providers import lmstudio as lmstudio_engine
from app.ai.providers import _http as http_module
from app.ai.providers.base import BaseAIEngine
from app.language_cleanup.transcript_source import audit_dir
from app.source_analysis.window_models import WINDOW_MAX_OUTPUT_TOKENS
from app.source_analysis.window_prompt import WINDOW_ANALYSIS_PROMPT_VERSION
from app.source_analysis.window_writer import result_path, transport_path, windows_root
from app.source_analysis_execution_strategy.review import inspect_project_state
from app.source_analysis_hybrid.constants import HARD_MAX_INPUT_TOKENS, TARGET_INPUT_TOKENS
from app.source_analysis_provider_boundary.constants import (
    CALL1_SIGNATURE,
    CALL2_SIGNATURE,
    CLEAN_SHA,
    GENERATION_C_ANTHROPIC_SHA,
    GENERATION_C_RAW_SHA,
    MODE,
    NEXT_ACTION,
    NEXT_PHASE,
    NEXT_PHASE_LABEL,
    PHASE,
    PRIMARY_FINDING,
    PROJECT_NAME,
    PROMPT_10_SHA,
    PROMPT_11_SHA,
    REAL_PROVIDER_CALLS_THIS_PHASE,
    RESULT,
    SCHEMA_VERSION,
    SECONDARY_FINDING,
    THIRD_WIN001_CALL,
    THIRD_WIN001_CALL_AUTHORIZED,
    WINDOW_ANALYSIS_11_REAL_STATUS,
    WINDOW_ANALYSIS_11_STATUS_DETAIL,
    WINDOW_ID,
)
from app.source_analysis_bounded_win001_retry_readiness.integrity import (
    clean_integrity,
    generation_c_integrity,
    prompt_integrity,
)
from app.source_analysis_win001_failure_diagnosis.integrity import protected_hashes


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else None


def _lineno(func) -> int | None:
    try:
        return int(inspect.getsourcelines(func)[1])
    except (OSError, TypeError):
        return None


def airesponseerror_inventory() -> list[dict[str, Any]]:
    return [
        {
            "module": "app.ai.providers._http",
            "function": "decode_json_from_envelope / execute_provider_post",
            "line": _lineno(http_module.execute_provider_post),
            "condition": "HTTP body is not valid JSON",
            "classification": CLASS_INVALID_RESPONSE_JSON,
            "message": "Réponse {provider} illisible (JSON attendu).",
            "http_response_exists": True,
            "raw_body_exists": True,
            "parsed_json_exists": False,
            "usage_exists": False,
            "headers_exist": True,
            "status_exists": True,
        },
        {
            "module": "app.ai.providers._http",
            "function": "decode_json_from_envelope / execute_provider_post",
            "line": _lineno(http_module.execute_provider_post),
            "condition": "JSON decoded but top-level is not an object",
            "classification": CLASS_INVALID_RESPONSE_TOP_LEVEL,
            "message": "objet JSON attendu, {type} reçu",
            "http_response_exists": True,
            "raw_body_exists": True,
            "parsed_json_exists": True,
            "usage_exists": False,
            "headers_exist": True,
            "status_exists": True,
        },
        {
            "module": "app.ai.providers.anthropic_engine",
            "function": "extract_anthropic_text",
            "line": _lineno(anthropic_engine.extract_anthropic_text),
            "condition": "object JSON, key content missing",
            "classification": CLASS_MISSING_CONTENT,
            "message": "champ 'content' absent",
            "http_response_exists": True,
            "raw_body_exists": True,
            "parsed_json_exists": True,
            "usage_exists": "best_effort",
            "headers_exist": True,
            "status_exists": True,
        },
        {
            "module": "app.ai.providers.anthropic_engine",
            "function": "extract_anthropic_text",
            "line": _lineno(anthropic_engine.extract_anthropic_text),
            "condition": "content present but not a list",
            "classification": CLASS_INVALID_CONTENT_TYPE,
            "message": "champ 'content' absent ou non listé",
            "http_response_exists": True,
            "raw_body_exists": True,
            "parsed_json_exists": True,
            "usage_exists": "best_effort",
            "headers_exist": True,
            "status_exists": True,
        },
        {
            "module": "app.ai.providers.anthropic_engine",
            "function": "extract_anthropic_text",
            "line": _lineno(anthropic_engine.extract_anthropic_text),
            "condition": "content list has no type=text block",
            "classification": CLASS_NO_TEXT_BLOCK,
            "message": "sans bloc de texte exploitable",
            "http_response_exists": True,
            "raw_body_exists": True,
            "parsed_json_exists": True,
            "usage_exists": "best_effort",
            "headers_exist": True,
            "status_exists": True,
        },
        {
            "module": "app.ai.providers.anthropic_engine",
            "function": "extract_anthropic_text",
            "line": _lineno(anthropic_engine.extract_anthropic_text),
            "condition": "type=text block missing text or text is not a str",
            "classification": CLASS_INVALID_TEXT_BLOCK,
            "message": "bloc de texte malformé",
            "http_response_exists": True,
            "raw_body_exists": True,
            "parsed_json_exists": True,
            "usage_exists": "best_effort",
            "headers_exist": True,
            "status_exists": True,
        },
        {
            "module": "app.ai.providers.ollama",
            "function": "OllamaEngine._invoke",
            "line": _lineno(ollama_engine.OllamaEngine._invoke),
            "condition": "field response absent",
            "classification": "MISSING_PROVIDER_FIELD",
            "message": "champ 'response' absent",
            "http_response_exists": True,
            "raw_body_exists": True,
            "parsed_json_exists": True,
            "usage_exists": False,
            "headers_exist": True,
            "status_exists": True,
        },
        {
            "module": "app.ai.providers.lmstudio",
            "function": "LMStudioEngine._invoke",
            "line": _lineno(lmstudio_engine.LMStudioEngine._invoke),
            "condition": "choices/message/content missing or wrong shape",
            "classification": "MISSING_PROVIDER_FIELD",
            "message": "structure de réponse invalide",
            "http_response_exists": True,
            "raw_body_exists": True,
            "parsed_json_exists": True,
            "usage_exists": False,
            "headers_exist": True,
            "status_exists": True,
        },
        {
            "module": "app.ai.providers.openai_engine",
            "function": "OpenAIEngine._normalize",
            "line": _lineno(openai_engine.OpenAIEngine._normalize),
            "condition": "no exploitable message",
            "classification": "MISSING_PROVIDER_FIELD",
            "message": "aucun message exploitable",
            "http_response_exists": "sdk_object_not_raw_http",
            "raw_body_exists": False,
            "parsed_json_exists": False,
            "usage_exists": False,
            "headers_exist": False,
            "status_exists": False,
        },
        {
            "module": "app.ai.providers.openai_engine",
            "function": "OpenAIEngine._normalize",
            "line": _lineno(openai_engine.OpenAIEngine._normalize),
            "condition": "message.content is None",
            "classification": CLASS_NO_TEXT_BLOCK,
            "message": "Réponse OpenAI vide",
            "http_response_exists": "sdk_object_not_raw_http",
            "raw_body_exists": False,
            "parsed_json_exists": False,
            "usage_exists": False,
            "headers_exist": False,
            "status_exists": False,
        },
        {
            "module": "app.ai.providers.openai_engine",
            "function": "translate_sdk_error",
            "line": _lineno(openai_engine.translate_sdk_error),
            "condition": "unrecognized SDK exception",
            "classification": "SDK_UNEXPECTED",
            "message": "erreur inattendue",
            "http_response_exists": False,
            "raw_body_exists": False,
            "parsed_json_exists": False,
            "usage_exists": False,
            "headers_exist": False,
            "status_exists": "maybe_on_exception",
        },
    ]


def call2_narrowing() -> dict[str, Any]:
    return {
        "error_type": "AIResponseError",
        "exact_sub_condition": "UNKNOWN",
        "exact_sub_condition_confidence": "UNKNOWN",
        "possible_branches": [
            CLASS_INVALID_RESPONSE_JSON,
            CLASS_INVALID_RESPONSE_TOP_LEVEL,
            CLASS_MISSING_CONTENT,
            CLASS_NO_TEXT_BLOCK,
        ],
        "not_selected_without_evidence": True,
        "http_response_received": {
            "value": True,
            "confidence": "PROVEN",
            "basis": (
                "AIResponseError is raised only after requests.post returns. "
                "AITimeoutError / AIConnectionError would have been used if no "
                "complete HTTP response existed."
            ),
        },
        "http_status_known": False,
        "http_status_lt_400": {
            "value": True,
            "confidence": "PROVEN",
            "basis": (
                "_raise_for_status raises AIAuthenticationError / AIRateLimitError / "
                "AIServerError / AIRequestError when status >= 400. Call #2 was "
                "AIResponseError."
            ),
        },
        "http_2xx": {
            "value": None,
            "confidence": "STRONGLY_SUPPORTED",
            "basis": (
                "status < 400 is proven. 2xx is the expected production status. "
                "3xx is theoretically possible because requests may expose it "
                "without raising. Not claimed as proven 200."
            ),
        },
        "raw_body_available_historically": "NO",
        "raw_body_persisted": False,
        "usage_persisted": False,
        "stop_reason_persisted": False,
        "request_id_persisted": False,
        "forensics_unavailable": True,
        "do_not_fabricate": True,
        "traceback_in_logs": False,
        "log_fields_only": [
            "event",
            "stage",
            "provider",
            "model",
            "latency_ms",
            "attempts",
            "error_type",
            "timestamp",
        ],
        "exception_message_persisted": False,
    }


def forensic_matrix() -> list[dict[str, Any]]:
    def row(
        failure: str,
        *,
        http: bool | str,
        raw_bytes: bool | str,
        raw_text: bool | str,
        headers: bool | str,
        status: bool | str,
        parsed_json: bool | str,
        usage: bool | str,
        stop: bool | str,
        request_id: bool | str,
        persisted_before: bool,
        persisted_now: bool,
        logged: str,
        secret_risk: str,
        recoverable: bool | str,
    ) -> dict[str, Any]:
        return {
            "FAILURE_CLASS": failure,
            "HTTP_RESPONSE_AVAILABLE": http,
            "RAW_BYTES_AVAILABLE": raw_bytes,
            "RAW_TEXT_AVAILABLE": raw_text,
            "HEADERS_AVAILABLE": headers,
            "STATUS_AVAILABLE": status,
            "JSON_AVAILABLE": parsed_json,
            "USAGE_AVAILABLE": usage,
            "STOP_REASON_AVAILABLE": stop,
            "REQUEST_ID_AVAILABLE": request_id,
            "PREVIOUSLY_PERSISTED": persisted_before,
            "CURRENTLY_PERSISTED": persisted_now,
            "CURRENTLY_LOGGED": logged,
            "SECRET_RISK": secret_risk,
            "RECOVERABLE_OFFLINE": recoverable,
        }

    meta = "metadata_only"
    return [
        row(
            CLASS_HTTP_TRANSPORT_FAILURE,
            http=False,
            raw_bytes=False,
            raw_text=False,
            headers=False,
            status=False,
            parsed_json=False,
            usage=False,
            stop=False,
            request_id=False,
            persisted_before=False,
            persisted_now=False,
            logged=meta,
            secret_risk="none",
            recoverable=False,
        ),
        row(
            CLASS_HTTP_ERROR,
            http=True,
            raw_bytes=True,
            raw_text="if_utf8",
            headers="whitelist",
            status=True,
            parsed_json="if_object",
            usage="best_effort",
            stop="best_effort",
            request_id="header_or_body",
            persisted_before=False,
            persisted_now=True,
            logged=meta,
            secret_risk="body_may_echo_provider_error",
            recoverable=True,
        ),
        row(
            CLASS_INVALID_RESPONSE_JSON,
            http=True,
            raw_bytes=True,
            raw_text="if_utf8",
            headers="whitelist",
            status=True,
            parsed_json=False,
            usage=False,
            stop=False,
            request_id="header_only",
            persisted_before=False,
            persisted_now=True,
            logged=meta,
            secret_risk="none_if_whitelist",
            recoverable=True,
        ),
        row(
            CLASS_INVALID_RESPONSE_TOP_LEVEL,
            http=True,
            raw_bytes=True,
            raw_text=True,
            headers="whitelist",
            status=True,
            parsed_json=True,
            usage=False,
            stop=False,
            request_id="header_only",
            persisted_before=False,
            persisted_now=True,
            logged=meta,
            secret_risk="none_if_whitelist",
            recoverable=True,
        ),
        row(
            CLASS_MISSING_CONTENT,
            http=True,
            raw_bytes=True,
            raw_text=True,
            headers="whitelist",
            status=True,
            parsed_json=True,
            usage="best_effort",
            stop="best_effort",
            request_id="header_or_body",
            persisted_before=False,
            persisted_now=True,
            logged=meta,
            secret_risk="none_if_whitelist",
            recoverable=True,
        ),
        row(
            CLASS_INVALID_CONTENT_TYPE,
            http=True,
            raw_bytes=True,
            raw_text=True,
            headers="whitelist",
            status=True,
            parsed_json=True,
            usage="best_effort",
            stop="best_effort",
            request_id="header_or_body",
            persisted_before=False,
            persisted_now=True,
            logged=meta,
            secret_risk="none_if_whitelist",
            recoverable=True,
        ),
        row(
            CLASS_NO_TEXT_BLOCK,
            http=True,
            raw_bytes=True,
            raw_text=True,
            headers="whitelist",
            status=True,
            parsed_json=True,
            usage="best_effort",
            stop="best_effort",
            request_id="header_or_body",
            persisted_before=False,
            persisted_now=True,
            logged=meta,
            secret_risk="none_if_whitelist",
            recoverable=True,
        ),
        row(
            CLASS_INVALID_TEXT_BLOCK,
            http=True,
            raw_bytes=True,
            raw_text=True,
            headers="whitelist",
            status=True,
            parsed_json=True,
            usage="best_effort",
            stop="best_effort",
            request_id="header_or_body",
            persisted_before=False,
            persisted_now=True,
            logged=meta,
            secret_risk="none_if_whitelist",
            recoverable=True,
        ),
        row(
            CLASS_STRUCTURED_JSON_DECODE,
            http=True,
            raw_bytes=True,
            raw_text=True,
            headers="whitelist",
            status=True,
            parsed_json=True,
            usage=True,
            stop=True,
            request_id=True,
            persisted_before=True,
            persisted_now=True,
            logged=meta,
            secret_risk="raw_text_file_not_logs",
            recoverable=True,
        ),
        row(
            CLASS_STRUCTURED_SCHEMA_VALIDATION,
            http=True,
            raw_bytes=True,
            raw_text=True,
            headers="whitelist",
            status=True,
            parsed_json=True,
            usage=True,
            stop=True,
            request_id=True,
            persisted_before=True,
            persisted_now=True,
            logged=meta,
            secret_risk="raw_text_file_not_logs",
            recoverable=True,
        ),
    ]


def two_call_review(project_name: str, *, sortie_dir: Path | None = None) -> dict[str, Any]:
    audit = audit_dir(project_name, sortie_dir=sortie_dir)
    call1 = _load_json(audit / "source_analysis_real_win001_canary_execution.json") or {}
    call2 = _load_json(audit / "source_analysis_real_bounded_win001_execution.json") or {}
    usage1 = call1.get("usage") or {}
    elapsed1 = call1.get("elapsed") or {}
    elapsed2 = call2.get("elapsed") or {}
    outcome1 = call1.get("provider_outcome") or {}
    outcome2 = call2.get("http_provider_outcome") or {}
    cost1 = call1.get("cost") or {}
    cost2 = call2.get("cost") or {}
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "real_provider_calls_this_phase": REAL_PROVIDER_CALLS_THIS_PHASE,
        "third_win001_call_authorized": THIRD_WIN001_CALL_AUTHORIZED,
        "invented_missing_values": False,
        "comparison": [
            {"dimension": "prompt", "call_1_0": call1.get("prompt_version"), "call_1_1": call2.get("prompt_version")},
            {
                "dimension": "signature",
                "call_1_0": (call1.get("window_identity") or {}).get("analysis_signature") or CALL1_SIGNATURE,
                "call_1_1": call2.get("analysis_signature") or CALL2_SIGNATURE,
            },
            {"dimension": "provider", "call_1_0": call1.get("provider"), "call_1_1": call2.get("provider")},
            {"dimension": "model", "call_1_0": call1.get("model"), "call_1_1": call2.get("model")},
            {
                "dimension": "elapsed_provider_ms",
                "call_1_0": elapsed1.get("provider_latency_ms"),
                "call_1_1": elapsed2.get("provider_latency_ms"),
            },
            {
                "dimension": "http_body_availability",
                "call_1_0": "received_in_memory_then_discarded",
                "call_1_1": "unknown_not_persisted",
            },
            {
                "dimension": "usage",
                "call_1_0": {
                    "input_tokens": usage1.get("input_tokens"),
                    "output_tokens": usage1.get("output_tokens"),
                },
                "call_1_1": "unavailable",
            },
            {
                "dimension": "finish_reason",
                "call_1_0": call1.get("finish_reason"),
                "call_1_1": call2.get("finish_reason"),
            },
            {
                "dimension": "parse_reached",
                "call_1_0": True,
                "call_1_1": False,
            },
            {
                "dimension": "failure_class",
                "call_1_0": outcome1.get("error_type"),
                "call_1_1": outcome2.get("error_type"),
            },
            {
                "dimension": "forensics",
                "call_1_0": "absent_not_yet_implemented",
                "call_1_1": call2.get("forensic_status"),
            },
            {
                "dimension": "transport",
                "call_1_0": call1.get("transport_status"),
                "call_1_1": call2.get("transport_status"),
            },
            {
                "dimension": "result",
                "call_1_0": call1.get("result_status"),
                "call_1_1": call2.get("result_status"),
            },
            {
                "dimension": "cost",
                "call_1_0": cost1.get("total_cost"),
                "call_1_1": cost2.get("total_cost"),
            },
        ],
        "call_1": {
            "prompt": "window-analysis-1.0",
            "result": "FAIL CONTROLLED",
            "error": "AIStructuredOutputError",
            "engine_generate_attempts": call1.get("engine_generate_attempts"),
            "anthropic_post_attempts": call1.get("http_post_attempts_observable"),
            "input_tokens": usage1.get("input_tokens"),
            "output_tokens": usage1.get("output_tokens"),
            "cost_usd": cost1.get("total_cost"),
            "provider_elapsed_ms": elapsed1.get("provider_latency_ms"),
            "http_body": "received",
            "structured_parse": "attempted_and_failed",
            "transport": "absent",
            "result": "absent",
        },
        "call_2": {
            "prompt": "window-analysis-1.1",
            "result": "FAIL CONTROLLED",
            "error": "AIResponseError",
            "engine_generate_attempts": call2.get("engine_generate_attempts"),
            "anthropic_post_attempts": call2.get("anthropic_post_attempts"),
            "input_tokens": call2.get("actual_input_tokens"),
            "output_tokens": call2.get("actual_output_tokens"),
            "cost_usd": cost2.get("total_cost"),
            "provider_elapsed_ms": elapsed2.get("provider_latency_ms"),
            "wall_elapsed_ms": elapsed2.get("wall_clock_ms"),
            "structured_parse": "NOT_REACHED",
            "transport": "absent",
            "forensics": "absent",
            "result": "absent",
            "finish_reason": call2.get("finish_reason"),
            "request_id": call2.get("request_id"),
        },
        "window_analysis_1_1_real_status": WINDOW_ANALYSIS_11_STATUS_DETAIL,
        "do_not_blame_bounding": True,
        "secrets_included": False,
    }


def architecture() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "principle": {
            "statement": (
                "HTTP RESPONSE FORENSICS MUST BE CAPTURED BEFORE PROVIDER "
                "RESPONSE INTERPRETATION."
            ),
            "adopted": True,
        },
        "current_lifecycle_before": [
            "WindowAnalyzer.analyze_window",
            "engine.generate",
            "AnthropicEngine._invoke",
            "build_payload / build_headers",
            "requests.post",
            "HTTP response",
            "_raise_for_status",
            "response.json()",
            "top-level object check",
            "_extract_text",
            "ProviderResult",
            "AIResponse",
            "parse_structured_output",
        ],
        "new_lifecycle": [
            "WindowAnalyzer.analyze_window + provider_forensic_scope",
            "engine.generate",
            "AnthropicEngine._invoke",
            "build_payload / build_headers",
            "requests.post",
            "HTTP response received",
            "capture_http_response (bytes, status, header whitelist)",
            "optional persist on subsequent failure",
            "status classification",
            "JSON decode from captured bytes",
            "top-level object check",
            "best-effort usage / stop_reason",
            "extract_anthropic_text",
            "ProviderResult + envelope",
            "AIResponse",
            "parse_structured_output",
            "semantic transport / decoder / validator",
        ],
        "loss_points_before": [
            "requests exception — no body, now classified HTTP_TRANSPORT_FAILURE",
            "HTTP non-success — body discarded after 200-char excerpt in exception",
            "response.json() failure — body discarded",
            "non-object JSON — parsed value discarded",
            "missing/invalid content — JSON discarded",
            "no text / malformed text — JSON discarded",
            "usage parse coupled to ProviderResult",
            "AIResponseError before ProviderResult — no forensic persist",
            "KeyboardInterrupt after HTTP — no persist",
        ],
        "forensic_envelope": {
            "fields": [
                "provider",
                "model",
                "http_status",
                "headers_subset",
                "request_id",
                "raw_body_bytes",
                "raw_sha256",
                "raw_size",
                "json_decode_status",
                "parsed_top_level_type",
                "usage_if_extractable",
                "finish_reason_if_extractable",
                "content_metadata",
                "elapsed_ms",
            ],
            "secrets_excluded": True,
        },
        "persistence_order": [
            "requests.post",
            "HTTP response received",
            "capture safe forensic envelope in memory",
            "on interpretation failure: persist raw + envelope",
            "provider JSON interpretation",
            "content extraction",
            "AIResponse",
            "structured parsing",
            "semantic transport",
        ],
        "success_policy": "in-memory compact metadata; no durable raw body",
        "failure_policy": "persist raw bytes + envelope; no console dump; no repair; no retry",
        "raw_storage": {
            "root": f"analysis/{FORENSICS_DIR_NAME}/<window_id>/<analysis_signature>/",
            "files": ["provider_http_envelope.json", "provider_raw_response.bin"],
            "signature_aware": True,
            "collision": "fail / refuse overwrite",
            "atomic": ".partial + replace",
        },
        "header_whitelist": sorted(SAFE_RESPONSE_HEADERS),
        "error_taxonomy": [
            CLASS_HTTP_TRANSPORT_FAILURE,
            CLASS_HTTP_ERROR,
            CLASS_INVALID_RESPONSE_JSON,
            CLASS_INVALID_RESPONSE_TOP_LEVEL,
            CLASS_MISSING_CONTENT,
            CLASS_INVALID_CONTENT_TYPE,
            CLASS_NO_TEXT_BLOCK,
            CLASS_INVALID_TEXT_BLOCK,
            CLASS_STRUCTURED_JSON_DECODE,
            CLASS_STRUCTURED_SCHEMA_VALIDATION,
            "SEMANTIC_CAPACITY_EXCEEDED",
            "SEMANTIC_GRANULARITY_LIMIT",
            "WINDOW_VALIDATION_FAILURE",
        ],
        "offline_replay": {
            "status": "READY",
            "strict": True,
            "repairs_json": False,
            "publishes_transport": False,
            "uses_production_parsers": True,
        },
        "generic_responsibility": [
            "HTTP capture",
            "status classification",
            "JSON decode from bytes",
            "top-level type check",
            "header whitelist",
            "atomic persist",
            "collision safety",
            "replay shell",
        ],
        "anthropic_specific_responsibility": [
            "content list / text block extraction",
            "usage.input_tokens / output_tokens",
            "stop_reason",
            "content metadata",
        ],
        "other_providers": {
            "openai": "SDK path; no Anthropic envelope assumptions",
            "ollama": "generic HTTP envelope + local field response",
            "lmstudio": "generic HTTP envelope + OpenAI-shaped choices",
        },
        "interruption": {
            "after_http_before_parse": "KeyboardInterrupt persist attempted if envelope exists",
            "before_http": "response_received=false, no fabricated body",
        },
        "alternatives_reviewed_not_selected": [
            {
                "id": "A",
                "label": "keep synchronous non-streaming with stronger forensic boundary",
                "status": "IMPLEMENTED_THIS_PHASE",
            },
            {
                "id": "B",
                "label": "provider streaming support",
                "status": "NOT_SELECTED",
                "reason": "architecture review only; no local verified streaming contract",
            },
            {
                "id": "C",
                "label": "provider batch/async",
                "status": "NOT_SELECTED",
                "reason": "external verification marked future work",
            },
            {
                "id": "D",
                "label": "smaller semantic windows",
                "status": "DEFER_TO_3B77A6",
            },
            {
                "id": "E",
                "label": "hierarchical/local-first extraction",
                "status": "DEFER_TO_3B77A6",
            },
        ],
        "secrets_included": False,
    }


def build_diagnosis(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> dict[str, Any]:
    audit = audit_dir(project_name, sortie_dir=sortie_dir)
    call2 = _load_json(audit / "source_analysis_real_bounded_win001_execution.json") or {}
    state = inspect_project_state(project_name, sortie_dir=sortie_dir)
    root = windows_root(project_name, sortie_dir=sortie_dir)
    source_map = Path(root).parent / "source_map.json"
    prompts = prompt_integrity()
    generation_c = generation_c_integrity()
    clean = clean_integrity(project_name, sortie_dir=sortie_dir)
    state_status = (
        state.get("status")
        if isinstance(state, dict)
        else getattr(state, "status", None)
    )
    state_error = (
        state.get("error")
        if isinstance(state, dict)
        else getattr(state, "error", None)
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "result": RESULT,
        "project_name": project_name,
        "window_id": WINDOW_ID,
        "real_provider_calls_this_phase": REAL_PROVIDER_CALLS_THIS_PHASE,
        "third_win001_call_authorized": THIRD_WIN001_CALL_AUTHORIZED,
        "third_win001_call": THIRD_WIN001_CALL,
        "call_1": "AIStructuredOutputError",
        "call_2": "AIResponseError",
        "call_2_exact_sub_condition": "UNKNOWN",
        "http_response_received": "PROVEN",
        "http_status_known": False,
        "raw_body_available_historically": "NO",
        "raw_body_persisted": False,
        "usage_persisted": False,
        "stop_reason_persisted": False,
        "request_id_persisted": False,
        "current_forensic_coverage": "AIStructuredOutputError plus all HTTP-received provider-boundary failures",
        "new_forensic_boundary": "capture_http_response before JSON/content interpretation",
        "offline_replay": "READY",
        "window_analysis_1_1_real_status": WINDOW_ANALYSIS_11_REAL_STATUS,
        "primary_architectural_finding": PRIMARY_FINDING,
        "secondary_finding": SECONDARY_FINDING,
        "source_map": "NOT PUBLISHED",
        "source_map_present": source_map.is_file(),
        "phase_3b": "INCOMPLETE",
        "project_state": {
            "status": state_status,
            "error": state_error,
            "not_success": state_status != "SUCCESS",
        },
        "inventory": airesponseerror_inventory(),
        "call_2_narrowing": call2_narrowing(),
        "anthropic_lifecycle": {
            "WindowAnalyzer": "analyze_window",
            "engine.generate": "BaseAIEngine.generate",
            "AnthropicEngine": "AnthropicEngine._invoke",
            "payload": "AnthropicEngine.build_payload",
            "post": "execute_provider_post / requests.post",
            "capture": "capture_http_response",
            "status": "_raise_for_status",
            "json": "decode_json_from_envelope",
            "content": "extract_anthropic_text",
            "provider_result": "ProviderResult",
            "airesponse": "AIResponse",
            "structured": "parse_structured_output",
            "generate_line": _lineno(BaseAIEngine.generate),
            "extract_line": _lineno(anthropic_engine.extract_anthropic_text),
            "post_line": _lineno(http_module.execute_provider_post),
        },
        "airesponseerror_is_class": inspect.isclass(AIResponseError),
        "historical_call_2_forensics_unavailable": True,
        "historical_call_2_error_type": (call2.get("http_provider_outcome") or {}).get("error_type"),
        "integrity": {
            "prompt_1_0_sha": prompts.get("historical_sha256"),
            "prompt_1_0_expected": PROMPT_10_SHA,
            "prompt_1_0_unchanged": prompts.get("historical_sha256") == PROMPT_10_SHA,
            "prompt_1_1_sha": prompts.get("successor_sha256"),
            "prompt_1_1_expected": PROMPT_11_SHA,
            "prompt_1_1_unchanged": prompts.get("successor_sha256") == PROMPT_11_SHA,
            "prompt_1_1_version": WINDOW_ANALYSIS_PROMPT_VERSION,
            "generation_c_raw_sha": generation_c.get("raw_sha256"),
            "generation_c_raw_expected": GENERATION_C_RAW_SHA,
            "generation_c_raw_unchanged": generation_c.get("raw_sha256") == GENERATION_C_RAW_SHA,
            "generation_c_anthropic_sha": generation_c.get("anthropic_sha256"),
            "generation_c_anthropic_expected": GENERATION_C_ANTHROPIC_SHA,
            "generation_c_anthropic_unchanged": generation_c.get("anthropic_sha256")
            == GENERATION_C_ANTHROPIC_SHA,
            "max_output": WINDOW_MAX_OUTPUT_TOKENS,
            "max_output_unchanged": WINDOW_MAX_OUTPUT_TOKENS == 32000,
            "windows": 3,
            "target_input_tokens": TARGET_INPUT_TOKENS,
            "hard_max_input_tokens": HARD_MAX_INPUT_TOKENS,
            "clean_sha": clean.get("sha256"),
            "clean_expected": CLEAN_SHA,
            "clean_unchanged": clean.get("sha256") == CLEAN_SHA,
            "transport_exists": transport_path(project_name, WINDOW_ID, root=root).exists(),
            "result_exists": result_path(project_name, WINDOW_ID, root=root).exists(),
        },
        "protected_hashes": protected_hashes(project_name, sortie_dir=sortie_dir),
        "next_phase": NEXT_PHASE,
        "next_phase_label": NEXT_PHASE_LABEL,
        "next_action": NEXT_ACTION,
        "secrets_included": False,
    }


def build_all(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> dict[str, Any]:
    diagnosis = build_diagnosis(project_name, sortie_dir=sortie_dir)
    return {
        "diagnosis": diagnosis,
        "matrix": {
            "schema_version": SCHEMA_VERSION,
            "phase": PHASE,
            "mode": MODE,
            "real_provider_calls_this_phase": REAL_PROVIDER_CALLS_THIS_PHASE,
            "rows": forensic_matrix(),
            "secrets_included": False,
        },
        "architecture": architecture(),
        "two_call": two_call_review(project_name, sortie_dir=sortie_dir),
    }
