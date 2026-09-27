"""
Reconstruction offline de la requête WIN001 et du payload Anthropic.

build_payload seulement. Jamais generate, jamais POST, jamais de clé API.
"""

from __future__ import annotations

import json
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from app.ai.capabilities import resolve_capabilities
from app.ai.estimation import (
    CHARS_PER_TOKEN,
    METHOD_HEURISTIC,
    estimate_request_tokens,
    estimate_tokens,
)
from app.ai.pricing import build_default_catalog
from app.ai.providers._anthropic_schema import prepare_anthropic_json_schema
from app.ai.providers.anthropic_engine import AnthropicEngine
from app.ai.settings import resolve_stage_settings
from app.source_analysis.ultra_compact_schema import (
    ALLOWED_RECORD_KINDS,
    build_ultra_compact_response_schema,
    ultra_compact_schema_fingerprint,
)
from app.source_analysis.window_analyzer import build_window_ai_request
from app.source_analysis.window_prompt import WINDOW_ANALYSIS_PROMPT_VERSION_V10
from app.source_analysis.window_models import STAGE_WINDOW
from app.source_analysis.window_prompt import window_prompt_sha256
from app.source_analysis_hybrid.planner import plan_windows_v2
from app.source_analysis_win001_failure_diagnosis.constants import (
    EXPECTED_MODEL,
    EXPECTED_PROVIDER,
    HARD_MAX_INPUT_TOKENS,
    INPUT_COST_PER_1M,
    LONG_CONTEXT_THRESHOLD_IN_REPO,
    LONG_CONTEXT_THRESHOLD_PROTOCOL,
    OBSERVED_COST_USD,
    OBSERVED_INPUT_COST_USD,
    OBSERVED_LOCAL_ESTIMATE,
    OBSERVED_OUTPUT_COST_USD,
    OBSERVED_PROVIDER_INPUT,
    OBSERVED_PROVIDER_OUTPUT,
    OUTPUT_COST_PER_1M,
    WINDOW_ID,
    WINDOW_MAX_OUTPUT_TOKENS,
)

VOCAB_HEADER = "IDENTIFIANTS CONTRÔLÉS — JETONS DE PROTOCOLE"
WINDOW_HEADER_PREFIX = "WINDOW — WIN001"
LANGUAGE_HEADER = "LANGUE DE SORTIE OBLIGATOIRE"
OWNED_HEADER = "OWNED SOURCES"
CONTEXT_HEADER = "CONTEXT-ONLY SOURCES"
ROLE_MARKER = "SOURCE WINDOW ANALYST"


def _count(haystack: str, needle: str) -> int:
    if not needle:
        return 0
    return haystack.count(needle)


def _utf8_bytes(text: str) -> int:
    return len(text.encode("utf-8"))


def _decimal_str(value: Decimal) -> str:
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def reconstruct_win001_request(transcript, *, window_id: str = WINDOW_ID) -> dict[str, Any]:
    """Reconstruit le AIRequest WIN001. N'appelle pas le provider."""
    plan = plan_windows_v2(transcript)
    matches = [window for window in plan.windows if window.window_id == window_id]
    if len(matches) != 1:
        raise RuntimeError(f"fenêtre {window_id} introuvable dans le plan.")
    window = matches[0]
    settings = resolve_stage_settings(STAGE_WINDOW)
    bundle = build_window_ai_request(
        window,
        transcript,
        settings=settings,
        prompt_version=WINDOW_ANALYSIS_PROMPT_VERSION_V10,
    )
    request = bundle.request
    engine = AnthropicEngine(model=EXPECTED_MODEL, api_key="offline-unused")
    payload = engine.build_payload(request, EXPECTED_MODEL)
    if "x-api-key" in payload or "Authorization" in payload:
        raise RuntimeError("le payload ne doit pas contenir de secret.")
    return {
        "window": window,
        "plan": plan,
        "bundle": bundle,
        "request": request,
        "payload": payload,
        "engine": engine,
    }


def payload_metrics(payload: dict[str, Any]) -> dict[str, Any]:
    redacted = {
        key: value
        for key, value in payload.items()
        if key not in {"system", "messages"}
    }
    serialized = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    pretty = json.dumps(payload, ensure_ascii=False)
    system = payload.get("system") or ""
    messages = payload.get("messages") or []
    user = ""
    if messages and isinstance(messages[0], dict):
        user = str(messages[0].get("content") or "")
    schema = ((payload.get("output_config") or {}).get("format") or {}).get("schema")
    schema_bytes = (
        _utf8_bytes(json.dumps(schema, ensure_ascii=False, separators=(",", ":")))
        if schema is not None
        else 0
    )
    return {
        "serialized_compact_bytes": _utf8_bytes(serialized),
        "serialized_pretty_bytes": _utf8_bytes(pretty),
        "system_bytes": _utf8_bytes(system) if isinstance(system, str) else 0,
        "messages_bytes": _utf8_bytes(json.dumps(messages, ensure_ascii=False)),
        "user_content_bytes": _utf8_bytes(user),
        "schema_bytes_in_payload": schema_bytes,
        "message_count": len(messages) if isinstance(messages, list) else 0,
        "system_block_count": 1 if system else 0,
        "user_content_block_count": 1 if user else 0,
        "has_api_key_field": any(
            key.lower() in {"x-api-key", "api_key", "authorization"}
            for key in payload
        ),
        "payload_keys": sorted(payload.keys()),
        "redacted_non_text_fields": {
            key: redacted[key]
            for key in redacted
            if key != "output_config"
        },
    }


def marker_counts(system: str, user: str, serialized: str, markers: dict[str, str]) -> dict[str, Any]:
    rows = []
    for name, needle in markers.items():
        system_n = _count(system, needle)
        user_n = _count(user, needle)
        payload_n = _count(serialized, needle)
        expected = {
            # SRC000001 appears once in the versioned system example
            # (TRACEABILITY_BLOCK) and once as the first owned segment.
            "first_src": 2 if name == "first_src" and needle.startswith("[SRC000001 |") else 1,
            "middle_src": 1,
            "last_src": 1,
            "window_header": 1,
            "vocabulary_header": 1,
            "owned_header": 2,
            "context_header": 2,
            "role_marker": 1,
            "language_directive": 2,
        }.get(name)
        rows.append(
            {
                "marker": name,
                "system_count": system_n,
                "user_count": user_n,
                "payload_count": payload_n,
                "expected_payload_count": expected,
                "matches_expected": payload_n == expected if expected is not None else None,
            }
        )
    unexpected = [
        row
        for row in rows
        if row["expected_payload_count"] is not None and not row["matches_expected"]
    ]
    return {
        "rows": rows,
        "unexpected_duplication": unexpected,
        "payload_duplication_of_src": any(
            row["user_count"] > 1
            for row in rows
            if row["marker"] in {"first_src", "middle_src", "last_src"}
        ),
        "src_user_counts_all_one": all(
            row["user_count"] == 1
            for row in rows
            if row["marker"] in {"first_src", "middle_src", "last_src"}
        ),
        "first_src_system_example_explained": (
            "TRACEABILITY_BLOCK of window-analysis-1.0 contains "
            "[SRC000001 | AUDIO001 | 0.000-11.420] as a format example. "
            "That is not a second insertion of WIN001 owned text."
        ),
    }


def diagnose_request(transcript, *, window_id: str = WINDOW_ID) -> dict[str, Any]:
    rebuilt = reconstruct_win001_request(transcript, window_id=window_id)
    window = rebuilt["window"]
    bundle = rebuilt["bundle"]
    request = rebuilt["request"]
    payload = rebuilt["payload"]
    system = request.system_prompt or ""
    user = request.prompt
    combined = "\n".join([system, user])
    estimate = estimate_request_tokens(request)
    system_est = estimate_tokens(system, model=request.model)
    user_est = estimate_tokens(user, model=request.model)
    schema = build_ultra_compact_response_schema()
    adapted = prepare_anthropic_json_schema(schema)
    raw_schema_text = json.dumps(schema, ensure_ascii=False, sort_keys=True)
    adapted_schema_text = json.dumps(adapted, ensure_ascii=False, sort_keys=True)
    schema_est = estimate_tokens(raw_schema_text, model=request.model)
    adapted_est = estimate_tokens(adapted_schema_text, model=request.model)
    payload_text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    payload_est = estimate_tokens(payload_text, model=request.model)
    owned = tuple(window.owned_src_refs)
    first_src = owned[0] if owned else ""
    last_src = owned[-1] if owned else ""
    middle_src = owned[len(owned) // 2] if owned else ""
    markers = marker_counts(
        system,
        user,
        payload_text,
        {
            "first_src": f"[{first_src} |" if first_src else "",
            "middle_src": f"[{middle_src} |" if middle_src else "",
            "last_src": f"[{last_src} |" if last_src else "",
            "window_header": WINDOW_HEADER_PREFIX,
            "vocabulary_header": VOCAB_HEADER,
            "owned_header": OWNED_HEADER,
            "context_header": CONTEXT_HEADER,
            "role_marker": ROLE_MARKER,
            "language_directive": LANGUAGE_HEADER,
        },
    )
    metrics = payload_metrics(payload)
    ratio = (
        Decimal(OBSERVED_PROVIDER_INPUT) / Decimal(OBSERVED_LOCAL_ESTIMATE)
    ).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
    gap = OBSERVED_PROVIDER_INPUT - OBSERVED_LOCAL_ESTIMATE
    schema_cannot_explain = adapted_est.tokens < gap
    capabilities = resolve_capabilities(EXPECTED_PROVIDER, EXPECTED_MODEL)
    settings = resolve_stage_settings(STAGE_WINDOW)
    usable_context = capabilities.usable_context(settings.context_safety_ratio)
    usable_input_model_max = capabilities.usable_input_context(
        settings.context_safety_ratio
    )
    actual_plus_configured_output = OBSERVED_PROVIDER_INPUT + OBSERVED_PROVIDER_OUTPUT
    catalog = build_default_catalog()
    pricing = catalog.get(EXPECTED_PROVIDER, EXPECTED_MODEL)
    computed = catalog.estimate_cost(
        EXPECTED_PROVIDER,
        EXPECTED_MODEL,
        OBSERVED_PROVIDER_INPUT,
        OBSERVED_PROVIDER_OUTPUT,
    )
    input_cost = (
        Decimal(OBSERVED_PROVIDER_INPUT) * Decimal(INPUT_COST_PER_1M) / Decimal(1_000_000)
    )
    output_cost = (
        Decimal(OBSERVED_PROVIDER_OUTPUT)
        * Decimal(OUTPUT_COST_PER_1M)
        / Decimal(1_000_000)
    )
    total_cost = input_cost + output_cost
    output_share = (
        (output_cost / total_cost).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
        if total_cost
        else Decimal(0)
    )
    tiktoken_available = False
    try:
        import tiktoken  # type: ignore

        tiktoken_available = True
        del tiktoken
    except ImportError:
        tiktoken_available = False

    return {
        "window_id": window.window_id,
        "owned_src_count": window.owned_src_count,
        "first_src": first_src,
        "middle_src": middle_src,
        "last_src": last_src,
        "word_count": window.word_count,
        "analysis_signature": bundle.signature,
        "prompt_version": bundle.signature_inputs.prompt_version,
        "prompt_sha256": window_prompt_sha256(system),
        "response_schema_sha256": ultra_compact_schema_fingerprint(schema),
        "model": request.model,
        "provider": EXPECTED_PROVIDER,
        "temperature": request.temperature,
        "max_output_tokens": request.max_output_tokens,
        "structured_output": {
            "wants_structured_output": request.wants_structured_output,
            "native_structured_output": True,
            "schema_injected_into_prompt": False,
            "schema_in_output_config": "output_config" in payload,
            "output_config_format_type": (
                (payload.get("output_config") or {}).get("format") or {}
            ).get("type"),
        },
        "character_counts": {
            "system_chars": len(system),
            "user_chars": len(user),
            "combined_chars": len(combined),
            "system_utf8_bytes": _utf8_bytes(system),
            "user_utf8_bytes": _utf8_bytes(user),
            "combined_utf8_bytes": _utf8_bytes(combined),
        },
        "local_estimate": {
            "algorithm": estimate.method,
            "chars_per_token_assumption": (
                CHARS_PER_TOKEN if estimate.method == METHOD_HEURISTIC else None
            ),
            "tiktoken_available_in_environment": tiktoken_available,
            "system_plus_user_tokens": estimate.tokens,
            "system_tokens": system_est.tokens,
            "user_tokens": user_est.tokens,
            "includes_system": True,
            "includes_user": True,
            "includes_response_schema": False,
            "includes_structured_output_grammar": False,
            "includes_json_escaping": False,
            "includes_anthropic_wrapper": False,
            "includes_tool_or_schema_transform": False,
            "matches_observed_49617": estimate.tokens == OBSERVED_LOCAL_ESTIMATE,
            "planner_hard_max_semantics": "LOCAL_ESTIMATED_TOKENS",
            "hard_max_input_tokens": HARD_MAX_INPUT_TOKENS,
            "observed_estimate": OBSERVED_LOCAL_ESTIMATE,
        },
        "schema_sizes": {
            "raw_schema_bytes": _utf8_bytes(raw_schema_text),
            "adapted_schema_bytes": _utf8_bytes(adapted_schema_text),
            "raw_schema_estimated_tokens": schema_est.tokens,
            "adapted_schema_estimated_tokens": adapted_est.tokens,
            "could_explain_57356_token_gap": False,
            "quantitative_reason": (
                f"adapted schema estimate={adapted_est.tokens} tokens / "
                f"{_utf8_bytes(adapted_schema_text)} bytes; gap="
                f"{gap} tokens. Schema size alone cannot explain the gap."
            ),
            "schema_cannot_explain_gap": schema_cannot_explain,
        },
        "payload": metrics,
        "payload_estimate_diagnostic_only": {
            "note": (
                "Diagnostic helper. Does not alter WindowPlannerV2. "
                "estimate_tokens(serialized compact payload) is still a local "
                "heuristic, not Anthropic billed input."
            ),
            "serialized_compact_estimated_tokens": payload_est.tokens,
            "alters_planning": False,
        },
        "duplication": markers,
        "provider_actual": {
            "input_tokens": OBSERVED_PROVIDER_INPUT,
            "output_tokens": OBSERVED_PROVIDER_OUTPUT,
            "ratio_exact": f"{OBSERVED_PROVIDER_INPUT}/{OBSERVED_LOCAL_ESTIMATE}",
            "ratio": str(ratio),
            "gap_tokens": gap,
            "estimate_represents": "human-readable system + user prompt text only",
            "actual_represents": (
                "Anthropic usage.input_tokens after the real call. "
                "Provider accounting semantics beyond that value are UNKNOWN."
            ),
        },
        "context": {
            "context_window": capabilities.context_window,
            "model_max_output_tokens": capabilities.max_output_tokens,
            "configured_request_max_output": WINDOW_MAX_OUTPUT_TOKENS,
            "safety_ratio": settings.context_safety_ratio,
            "usable_context": usable_context,
            "usable_input_subtracting_model_max_output": usable_input_model_max,
            "actual_input": OBSERVED_PROVIDER_INPUT,
            "actual_input_plus_configured_output": actual_plus_configured_output,
            "exceeded_usable_context": OBSERVED_PROVIDER_INPUT > usable_context,
            "exceeded_context_window": OBSERVED_PROVIDER_INPUT > capabilities.context_window,
            "margin_vs_usable_context": usable_context - actual_plus_configured_output,
            "margin_vs_context_window": (
                capabilities.context_window - actual_plus_configured_output
            ),
            "margin_vs_usable_input_model_max": (
                usable_input_model_max - OBSERVED_PROVIDER_INPUT
            ),
        },
        "long_context": {
            "threshold_encoded_in_repo": LONG_CONTEXT_THRESHOLD_IN_REPO,
            "protocol_cited_threshold": LONG_CONTEXT_THRESHOLD_PROTOCOL,
            "actual_input": OBSERVED_PROVIDER_INPUT,
            "crossed_protocol_threshold": (
                OBSERVED_PROVIDER_INPUT > LONG_CONTEXT_THRESHOLD_PROTOCOL
            ),
            "sonnet5_catalog_unmodeled_regimes": (
                pricing.unmodeled_regimes if pricing else None
            ),
            "base_pricing_applies_under_phase2b": True,
        },
        "cost": {
            "input_formula": f"{OBSERVED_PROVIDER_INPUT} × ${INPUT_COST_PER_1M} / 1M",
            "output_formula": f"{OBSERVED_PROVIDER_OUTPUT} × ${OUTPUT_COST_PER_1M} / 1M",
            "input_cost": _decimal_str(input_cost),
            "output_cost": _decimal_str(output_cost),
            "total_cost": _decimal_str(total_cost),
            "matches_observed_total": _decimal_str(total_cost) == OBSERVED_COST_USD,
            "matches_observed_input": _decimal_str(input_cost) == OBSERVED_INPUT_COST_USD,
            "matches_observed_output": _decimal_str(output_cost) == OBSERVED_OUTPUT_COST_USD,
            "catalog_total": str(computed.total_cost) if computed.total_cost is not None else None,
            "output_cost_share": str(output_share),
            "output_cost_share_percent": str(
                (output_share * Decimal(100)).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )
            ),
            "arithmetic_correct": _decimal_str(total_cost) == OBSERVED_COST_USD,
        },
        "record_bounds": {
            "schema_maxItems_on_records": None,
            "explicit_kind_caps": {kind: None for kind in ALLOWED_RECORD_KINDS},
            "prompt_numeric_caps": False,
            "unbounded_subject_to_max_output": True,
            "prompt_soft_guidance": "Reste sobre : un record par unité réellement distincte.",
        },
        "transcript_text_included": False,
        "secrets_included": False,
    }
