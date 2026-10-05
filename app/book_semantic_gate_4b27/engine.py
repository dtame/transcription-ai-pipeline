"""
Accounting-aware OpenAI Terra engine for 4B.2.7.

SDK retries are disabled (max_retries=0). Application retries are disabled
(RetryPolicy max_attempts=1). The remote slot is recorded immediately before
chat.completions.create. Frozen payload is sent unchanged.
"""

from __future__ import annotations

from typing import Any, Callable

import app.config as config

from app.ai.contracts import AIRequest
from app.ai.providers.base import ProviderResult
from app.ai.providers.openai_engine import (
    OpenAIEngine,
    _usage_as_dict,
    translate_sdk_error,
)
from app.ai.retry import RetryPolicy
from app.book_semantic_gate_4b24.engine import credential_available, describe_engine
from app.book_semantic_gate_4b27.accounting import CallAccounting
from app.book_semantic_gate_4b27.constants import (
    CONNECT_TIMEOUT_SECONDS,
    CONSERVATIVE_MAX_OUTPUT_TOKENS,
    MAX_ENGINE_GENERATE,
    MAX_REMOTE_INVOCATIONS,
    MODEL,
    READ_TIMEOUT_SECONDS,
    SDK_MAX_RETRIES,
)
from app.book_semantic_gate_4b27.guard import BookSemanticGate27Error


class NoRetryAccountingOpenAIEngine(OpenAIEngine):
    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("model", MODEL)
        kwargs.setdefault("temperature", None)
        kwargs.setdefault("max_output_tokens", CONSERVATIVE_MAX_OUTPUT_TOKENS)
        kwargs.setdefault("timeout_seconds", READ_TIMEOUT_SECONDS)
        kwargs.setdefault("connect_timeout_seconds", CONNECT_TIMEOUT_SECONDS)
        kwargs.setdefault(
            "retry_policy",
            RetryPolicy(max_attempts=MAX_ENGINE_GENERATE, base_delay_seconds=0.0),
        )
        super().__init__(**kwargs)
        self.accounting = CallAccounting()
        self._on_remote_boundary: Callable[[], None] | None = None
        self.last_refusal: str | None = None
        self.last_message_content: str | None = None
        self.last_finish_reason: str | None = None
        self.last_raw_usage: dict[str, Any] = {}
        self.sdk_max_retries = SDK_MAX_RETRIES

    def config_temperature(self) -> float | None:
        return None

    def set_remote_boundary_hook(self, hook: Callable[[], None] | None) -> None:
        self._on_remote_boundary = hook

    def client(self):
        if self._client is not None:
            return self._client
        try:
            from openai import OpenAI
        except ImportError as exc:
            from app.ai.errors import AIProviderUnavailableError

            raise AIProviderUnavailableError(
                "Le package 'openai' n'est pas installé."
            ) from exc

        kwargs: dict[str, Any] = {
            "api_key": self.resolve_api_key(),
            "max_retries": SDK_MAX_RETRIES,
        }
        base_url = getattr(config, "OPENAI_BASE_URL", None)
        if base_url:
            kwargs["base_url"] = base_url
        self._client = OpenAI(**kwargs)
        actual = getattr(self._client, "max_retries", None)
        if actual != SDK_MAX_RETRIES:
            raise BookSemanticGate27Error(
                f"SDK max_retries must be {SDK_MAX_RETRIES}, observed {actual!r}."
            )
        return self._client

    def build_payload(self, request: AIRequest, model: str) -> dict:
        frozen = dict((request.metadata or {}).get("frozen_payload") or {})
        if frozen:
            payload = dict(frozen)
            payload.pop("timeout", None)
            payload.pop("x-api-key", None)
            payload.pop("api_key", None)
            payload.pop("authorization", None)
            return payload
        payload = super().build_payload(request, model)
        payload.pop("timeout", None)
        payload.pop("temperature", None)
        payload.pop("x-api-key", None)
        payload.pop("api_key", None)
        payload.pop("authorization", None)
        return payload

    def generate(self, request: AIRequest):
        self.accounting.execution_attempts += 1
        if self.accounting.execution_attempts > MAX_ENGINE_GENERATE:
            raise BookSemanticGate27Error("Second engine.generate refused.")
        return super().generate(request)

    def _invoke(self, request: AIRequest, model: str) -> ProviderResult:
        client = self.client()
        payload = self.build_payload(request, model)
        timeout = self.resolve_timeout(request)

        if self.accounting.remote_invocations >= MAX_REMOTE_INVOCATIONS:
            raise BookSemanticGate27Error("Second remote invocation refused.")
        if self._on_remote_boundary is not None:
            self._on_remote_boundary()
        self.accounting.remote_invocations += 1
        self.accounting.boundary_crossed = True

        try:
            if timeout:
                completion = client.chat.completions.create(
                    **payload, timeout=timeout
                )
            else:
                completion = client.chat.completions.create(**payload)
        except Exception as exc:
            status = getattr(exc, "status_code", None) or getattr(exc, "status", None)
            name = type(exc).__name__
            if status is not None:
                self.accounting.http_requests += 1
                self.accounting.provider_responses += 1
            elif name in {
                "APIConnectionError",
                "APITimeoutError",
                "APIStatusError",
                "RateLimitError",
                "InternalServerError",
            }:
                self.accounting.http_requests += 1
            raise translate_sdk_error(exc) from exc

        self.accounting.http_requests += 1
        self.accounting.provider_responses += 1
        result = self._normalize(completion, model)
        if result.text:
            self.accounting.successful_payloads += 1
        return result

    def _normalize(self, completion: Any, model: str) -> ProviderResult:
        from app.ai.errors import AIResponseError

        try:
            choice = completion.choices[0]
            message = choice.message
            content = message.content
            refusal = getattr(message, "refusal", None)
        except (AttributeError, IndexError, TypeError) as exc:
            error = AIResponseError(
                "Réponse OpenAI inattendue : aucun message exploitable."
            )
            error.classification = "MISSING_PROVIDER_FIELD"
            raise error from exc

        self.last_refusal = str(refusal) if refusal else None
        self.last_message_content = None if content is None else str(content)
        self.last_finish_reason = getattr(choice, "finish_reason", None)
        raw_usage = _usage_as_dict(getattr(completion, "usage", None))
        self.last_raw_usage = dict(raw_usage)

        from app.ai.providers.lmstudio import extract_openai_usage

        input_tokens, output_tokens, total_tokens, usage = extract_openai_usage(
            {"usage": raw_usage}
        )
        if content is None:
            text = ""
        else:
            text = str(content)
        return ProviderResult(
            text=text,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            finish_reason=getattr(choice, "finish_reason", None),
            request_id=getattr(completion, "id", None),
            model=getattr(completion, "model", None) or model,
            raw_usage=usage,
        )


def inspect_sdk_retry_policy() -> dict[str, Any]:
    try:
        from openai import OpenAI
    except ImportError:
        return {
            "sdk_import": False,
            "probe_max_retries": None,
            "default_max_retries": None,
            "enforced_max_retries": SDK_MAX_RETRIES,
            "pass": False,
        }
    probe = OpenAI(api_key="sk-unused-4b27-retry-inspect", max_retries=SDK_MAX_RETRIES)
    default = OpenAI(api_key="sk-unused-4b27-retry-inspect")
    return {
        "sdk_import": True,
        "probe_max_retries": getattr(probe, "max_retries", None),
        "default_max_retries": getattr(default, "max_retries", None),
        "enforced_max_retries": SDK_MAX_RETRIES,
        "pass": getattr(probe, "max_retries", None) == SDK_MAX_RETRIES,
        "note": (
            "Default SDK retries are disabled for this invocation. "
            "Local client construction is not a remote call."
        ),
        "secrets_included": False,
    }


def build_real_canary_engine() -> NoRetryAccountingOpenAIEngine:
    if not credential_available():
        raise BookSemanticGate27Error(
            "OpenAI credential unavailable — STOP WITHOUT PROVIDER CALL."
        )
    return NoRetryAccountingOpenAIEngine()


def describe_accounting_engine(engine: Any) -> dict[str, Any]:
    payload = describe_engine(engine)
    accounting = getattr(engine, "accounting", None)
    if isinstance(accounting, CallAccounting):
        payload["accounting"] = accounting.to_dict()
    payload["sdk_max_retries"] = getattr(engine, "sdk_max_retries", None)
    client = getattr(engine, "_client", None)
    if client is not None:
        payload["client_max_retries"] = getattr(client, "max_retries", None)
    return payload


__all__ = [
    "NoRetryAccountingOpenAIEngine",
    "build_real_canary_engine",
    "credential_available",
    "describe_accounting_engine",
    "inspect_sdk_retry_policy",
]
