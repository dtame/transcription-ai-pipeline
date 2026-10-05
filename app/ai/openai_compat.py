"""
OpenAI request compatibility — model and endpoint aware.

AIRequest.max_output_tokens is a provider-neutral budget. It is NOT the
Responses API field `max_output_tokens` and must not be copied blindly
onto chat.completions as `max_tokens`.

Production OpenAIEngine uses chat.completions.create only. This module
does not assume max_completion_tokens applies to every model or to the
Responses API.

Server-only behavior stays UNKNOWN until a real provider response exists.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Mapping

from app.ai.capabilities import resolve_capabilities
from app.ai.contracts import AIRequest
from app.ai.errors import AIConfigurationError
from app.ai.thinking import (
    THINKING_MODE_PROVIDER_DEFAULT,
    normalize_thinking_mode,
)

ENDPOINT_CHAT_COMPLETIONS = "chat.completions"
ENDPOINT_RESPONSES = "responses"

PRODUCTION_OPENAI_ENDPOINT = ENDPOINT_CHAT_COMPLETIONS

TOKEN_PARAM_MAX_TOKENS = "max_tokens"
TOKEN_PARAM_MAX_COMPLETION_TOKENS = "max_completion_tokens"
TOKEN_PARAM_MAX_OUTPUT_TOKENS = "max_output_tokens"

CONFIDENCE_CONFIRMED = "CONFIRMED"
CONFIDENCE_LOCAL = "LOCALLY_VERIFIED"
CONFIDENCE_UNKNOWN = "UNKNOWN"

TERRA_MODEL = "gpt-5.6-terra"

CHAT_COMPLETIONS_TOKEN_FIELDS = (
    TOKEN_PARAM_MAX_TOKENS,
    TOKEN_PARAM_MAX_COMPLETION_TOKENS,
)

# Explicit per-model chat.completions contracts. Do not generalize.
# gpt-5.6-terra: 4B.2.5 HTTP 400 unsupported_parameter max_tokens;
# the server named max_completion_tokens as the replacement.
_CHAT_COMPLETIONS_TOKEN_CONTRACTS: dict[str, "TokenParameterContract"] = {}


@dataclass(frozen=True)
class TokenParameterContract:
    endpoint: str
    model: str
    parameter: str
    do_not_send: tuple[str, ...]
    confidence: str
    server_acceptance: str
    evidence: str
    source: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "endpoint": self.endpoint,
            "model": self.model,
            "parameter": self.parameter,
            "do_not_send": list(self.do_not_send),
            "confidence": self.confidence,
            "server_acceptance": self.server_acceptance,
            "evidence": self.evidence,
            "source": self.source,
        }


_CHAT_COMPLETIONS_TOKEN_CONTRACTS[TERRA_MODEL] = TokenParameterContract(
    endpoint=ENDPOINT_CHAT_COMPLETIONS,
    model=TERRA_MODEL,
    parameter=TOKEN_PARAM_MAX_COMPLETION_TOKENS,
    do_not_send=(TOKEN_PARAM_MAX_TOKENS, TOKEN_PARAM_MAX_OUTPUT_TOKENS),
    confidence=CONFIDENCE_CONFIRMED,
    server_acceptance=CONFIDENCE_UNKNOWN,
    evidence=(
        "4B.2.5 HTTP 400 invalid_request_error unsupported_parameter "
        "max_tokens. Server message: Use 'max_completion_tokens' instead. "
        "A successful Terra response with max_completion_tokens has not "
        "been observed; acceptance remains UNKNOWN."
    ),
    source="audit/real/book_semantic_gate_4b25/book_semantic_gate_4b25_provider_evidence.json",
)


def production_openai_endpoint() -> str:
    return PRODUCTION_OPENAI_ENDPOINT


def resolve_chat_completions_token_contract(model: str) -> TokenParameterContract:
    name = str(model or "").strip()
    known = _CHAT_COMPLETIONS_TOKEN_CONTRACTS.get(name)
    if known is not None:
        return known
    return TokenParameterContract(
        endpoint=ENDPOINT_CHAT_COMPLETIONS,
        model=name,
        parameter=TOKEN_PARAM_MAX_TOKENS,
        do_not_send=(TOKEN_PARAM_MAX_COMPLETION_TOKENS, TOKEN_PARAM_MAX_OUTPUT_TOKENS),
        confidence=CONFIDENCE_LOCAL,
        server_acceptance=CONFIDENCE_UNKNOWN,
        evidence=(
            "Unlisted OpenAI chat.completions model. Adapter keeps the "
            "legacy max_tokens field used by existing local OpenAI tests. "
            "This is not a claim that every future model accepts max_tokens."
        ),
        source="app/ai/openai_compat.py default chat.completions contract",
    )


def resolve_openai_token_contract(model: str, *, endpoint: str | None = None) -> TokenParameterContract:
    selected = str(endpoint or PRODUCTION_OPENAI_ENDPOINT).strip()
    if selected == ENDPOINT_CHAT_COMPLETIONS:
        return resolve_chat_completions_token_contract(model)
    if selected == ENDPOINT_RESPONSES:
        raise AIConfigurationError(
            f"OpenAI endpoint {selected!r} is not the production endpoint. "
            f"OpenAIEngine uses {PRODUCTION_OPENAI_ENDPOINT}. Do not map "
            "AIRequest.max_output_tokens onto Responses max_output_tokens "
            "from this adapter."
        )
    raise AIConfigurationError(
        f"Unknown OpenAI endpoint {selected!r}. Production endpoint is "
        f"{PRODUCTION_OPENAI_ENDPOINT}."
    )


def conflicting_token_fields(payload: Mapping[str, Any]) -> list[str]:
    return [name for name in CHAT_COMPLETIONS_TOKEN_FIELDS if name in payload]


def apply_chat_completions_output_tokens(
    payload: dict[str, Any],
    *,
    model: str,
    max_output_tokens: int | None,
    endpoint: str = PRODUCTION_OPENAI_ENDPOINT,
) -> TokenParameterContract:
    """
    Map the semantic output budget onto the endpoint-correct field.

    Never writes both max_tokens and max_completion_tokens.
    """
    contract = resolve_openai_token_contract(model, endpoint=endpoint)
    for name in CHAT_COMPLETIONS_TOKEN_FIELDS:
        payload.pop(name, None)
    payload.pop(TOKEN_PARAM_MAX_OUTPUT_TOKENS, None)

    if max_output_tokens is None:
        return contract

    budget = int(max_output_tokens)
    if budget <= 0:
        raise AIConfigurationError(
            f"OpenAI output token budget must be > 0, received {max_output_tokens}."
        )

    payload[contract.parameter] = budget
    present = conflicting_token_fields(payload)
    if len(present) != 1 or present[0] != contract.parameter:
        raise AIConfigurationError(
            "OpenAI chat.completions token fields are conflicting or missing "
            f"after mapping for {model}: {present}."
        )
    for forbidden in contract.do_not_send:
        if forbidden in payload:
            raise AIConfigurationError(
                f"OpenAI compatibility refused field {forbidden!r} for "
                f"{model} on {contract.endpoint}."
            )
    return contract


def apply_openai_chat_temperature(
    payload: dict[str, Any],
    *,
    request: AIRequest,
    temperature: float | None,
    model: str,
) -> dict[str, Any]:
    """
    Temperature is omitted for models that do not list it as a verified
    capability. An explicit request/engine temperature is a local error.
    An inherited OpenAI default is not applied.
    """
    payload.pop("temperature", None)
    caps = resolve_capabilities("openai", model)
    if temperature is None:
        return {"status": "OMITTED", "reason": "no_temperature_resolved"}
    if caps.supports_temperature:
        payload["temperature"] = float(temperature)
        return {"status": "INCLUDED", "confidence": CONFIDENCE_LOCAL}
    if request.temperature is not None:
        raise AIConfigurationError(
            f"temperature={request.temperature} is not a verified capability "
            f"for openai:{model}. Do not send it; fail locally."
        )
    return {
        "status": "OMITTED",
        "reason": "supports_temperature=false",
        "inherited_default_not_applied": True,
        "confidence": CONFIDENCE_LOCAL,
    }


def reject_unsupported_openai_optional_fields(request: AIRequest, model: str) -> None:
    mode = normalize_thinking_mode(request.thinking_mode)
    if mode != THINKING_MODE_PROVIDER_DEFAULT:
        raise AIConfigurationError(
            f"thinking_mode={mode!r} is not a verified OpenAI "
            f"chat.completions setting for {model}. "
            "Terra thinking remains provider_default / omitted."
        )
    if request.effort is not None:
        raise AIConfigurationError(
            f"effort={request.effort!r} is not a verified OpenAI "
            f"chat.completions setting for {model}."
        )
    if request.thinking_budget_tokens is not None:
        raise AIConfigurationError(
            f"thinking_budget_tokens={request.thinking_budget_tokens} is not "
            f"supported for openai:{model}. The field is not sent."
        )


def openai_endpoint_capability_matrix() -> dict[str, Any]:
    terra = resolve_chat_completions_token_contract(TERRA_MODEL)
    legacy = resolve_chat_completions_token_contract("gpt-4o-mini")
    return {
        "production_endpoint": PRODUCTION_OPENAI_ENDPOINT,
        "production_sdk_method": "client.chat.completions.create",
        "responses_api_used": False,
        "do_not_assume_max_completion_tokens_for_all_models": True,
        "do_not_map_provider_max_output_tokens_to_responses_field": True,
        "endpoints": {
            ENDPOINT_CHAT_COMPLETIONS: {
                "sdk_method": "client.chat.completions.create",
                "supported_token_parameters": [
                    TOKEN_PARAM_MAX_TOKENS,
                    TOKEN_PARAM_MAX_COMPLETION_TOKENS,
                ],
                "notes": (
                    "Parameter name is model-specific. o-series / Terra "
                    "reject max_tokens. Legacy chat models still use "
                    "max_tokens in this adapter."
                ),
            },
            ENDPOINT_RESPONSES: {
                "sdk_method": "client.responses.create",
                "supported_token_parameters": [TOKEN_PARAM_MAX_OUTPUT_TOKENS],
                "used_by_production_openai_engine": False,
                "notes": (
                    "Not the production endpoint. AIRequest.max_output_tokens "
                    "must not be forwarded here from OpenAIEngine."
                ),
            },
        },
        "models": {
            TERRA_MODEL: terra.to_dict(),
            "unlisted_openai_chat_completions_default": legacy.to_dict(),
        },
        "json_object": {
            "local_serialization": CONFIDENCE_LOCAL,
            "server_acceptance": CONFIDENCE_UNKNOWN,
            "note": (
                "4B.2.5 was rejected on max_tokens before json_object "
                "server acceptance could be observed."
            ),
        },
        "temperature": {
            TERRA_MODEL: {
                "policy": "omit",
                "supports_temperature": False,
                "server_acceptance": CONFIDENCE_UNKNOWN,
            }
        },
        "thinking": {
            TERRA_MODEL: {
                "policy": "provider_default_omitted",
                "server_behavior": CONFIDENCE_UNKNOWN,
            }
        },
    }


def capture_openai_sdk_chat_request(
    payload: Mapping[str, Any],
    *,
    api_key: str = "sk-offline-4b251-capture-unused",
) -> dict[str, Any]:
    """
    Construct the official OpenAI client and let the SDK prepare the
    chat.completions request. Serialization uses OpenAI._build_request.
    HTTP is never sent.
    """
    from openai import OpenAI
    from openai._models import FinalRequestOptions

    send_payload = dict(payload)
    send_payload.pop("timeout", None)
    client = OpenAI(api_key=api_key)
    options = FinalRequestOptions.construct(
        method="post",
        url="/chat/completions",
        json_data=send_payload,
    )
    request = client._build_request(options, retries_taken=0)
    body = json.loads(request.content.decode("utf-8")) if request.content else {}
    headers: dict[str, str] = {}
    for key, value in request.headers.items():
        lowered = str(key).lower()
        if lowered in {"authorization", "api-key", "x-api-key"}:
            headers[key] = "REDACTED"
        else:
            headers[key] = value
    return {
        "method": request.method,
        "url_path": request.url.path,
        "host": request.url.host,
        "body": body,
        "headers_redacted": headers,
        "intercepted": True,
        "prepared_without_send": True,
        "sdk_method": "client.chat.completions.create",
        "prepared_via": "OpenAI._build_request",
        "network_calls": 0,
        "http_requests": 0,
        "remote_invocations": 0,
        "provider_responses": 0,
        "local_error_class": None,
        "secrets_included": False,
    }


def assert_no_conflicting_token_fields(payload: Mapping[str, Any]) -> None:
    present = conflicting_token_fields(payload)
    if len(present) > 1:
        raise AIConfigurationError(
            "OpenAI request must not send both max_tokens and "
            f"max_completion_tokens. Present: {present}."
        )


__all__ = [
    "CHAT_COMPLETIONS_TOKEN_FIELDS",
    "CONFIDENCE_CONFIRMED",
    "CONFIDENCE_LOCAL",
    "CONFIDENCE_UNKNOWN",
    "ENDPOINT_CHAT_COMPLETIONS",
    "ENDPOINT_RESPONSES",
    "PRODUCTION_OPENAI_ENDPOINT",
    "TERRA_MODEL",
    "TOKEN_PARAM_MAX_COMPLETION_TOKENS",
    "TOKEN_PARAM_MAX_OUTPUT_TOKENS",
    "TOKEN_PARAM_MAX_TOKENS",
    "TokenParameterContract",
    "apply_chat_completions_output_tokens",
    "apply_openai_chat_temperature",
    "assert_no_conflicting_token_fields",
    "capture_openai_sdk_chat_request",
    "conflicting_token_fields",
    "openai_endpoint_capability_matrix",
    "production_openai_endpoint",
    "reject_unsupported_openai_optional_fields",
    "resolve_chat_completions_token_contract",
    "resolve_openai_token_contract",
]
