"""
Accounting-aware OpenAI Terra engine for 4B.2.6.

Local client construction is not a remote invocation.
The remote slot is recorded immediately before chat.completions.create.
"""

from __future__ import annotations

from typing import Any, Callable

from app.ai.contracts import AIRequest
from app.ai.providers.base import ProviderResult
from app.ai.providers.openai_engine import translate_sdk_error
from app.ai.retry import RetryPolicy
from app.book_semantic_gate_4b24.engine import (
    CountingOpenAIEngine,
    credential_available,
    describe_engine,
)
from app.book_semantic_gate_4b26.accounting import CallAccounting
from app.book_semantic_gate_4b26.constants import (
    CONNECT_TIMEOUT_SECONDS,
    CONSERVATIVE_MAX_OUTPUT_TOKENS,
    MAX_ENGINE_GENERATE,
    MAX_REMOTE_INVOCATIONS,
    MODEL,
    READ_TIMEOUT_SECONDS,
)
from app.book_semantic_gate_4b26.guard import BookSemanticGate26Error


class AccountingOpenAIEngine(CountingOpenAIEngine):
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

    def set_remote_boundary_hook(self, hook: Callable[[], None] | None) -> None:
        self._on_remote_boundary = hook

    def generate(self, request: AIRequest):
        self.accounting.execution_attempts += 1
        if self.accounting.execution_attempts > MAX_ENGINE_GENERATE:
            raise BookSemanticGate26Error("Second engine.generate refused.")
        return super().generate(request)

    def _invoke(self, request: AIRequest, model: str) -> ProviderResult:
        client = self.client()
        payload = self.build_payload(request, model)
        timeout = self.resolve_timeout(request)
        if timeout:
            payload["timeout"] = timeout

        if self.accounting.remote_invocations >= MAX_REMOTE_INVOCATIONS:
            raise BookSemanticGate26Error("Second remote invocation refused.")
        if self._on_remote_boundary is not None:
            self._on_remote_boundary()
        self.accounting.remote_invocations += 1
        self.accounting.boundary_crossed = True

        try:
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
        self.accounting.successful_payloads += 1
        return result


def build_real_canary_engine() -> AccountingOpenAIEngine:
    if not credential_available():
        raise BookSemanticGate26Error(
            "OpenAI credential unavailable — STOP WITHOUT PROVIDER CALL."
        )
    return AccountingOpenAIEngine()


def describe_accounting_engine(engine: Any) -> dict[str, Any]:
    payload = describe_engine(engine)
    accounting = getattr(engine, "accounting", None)
    if isinstance(accounting, CallAccounting):
        payload["accounting"] = accounting.to_dict()
    return payload


__all__ = [
    "AccountingOpenAIEngine",
    "build_real_canary_engine",
    "credential_available",
    "describe_accounting_engine",
]
