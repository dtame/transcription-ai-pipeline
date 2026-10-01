"""OpenAI Terra engine: 1 generate, 1 POST, retries=0, temperature omitted."""

from __future__ import annotations

from typing import Any

from app.ai.contracts import AIRequest
from app.ai.providers.base import ProviderResult
from app.ai.providers.openai_engine import OpenAIEngine
from app.ai.retry import RetryPolicy
from app.ai.settings import ENV_OPENAI_API_KEY, get_api_key
from app.book_semantic_gate_4b24.constants import (
    CONNECT_TIMEOUT_SECONDS,
    CONSERVATIVE_MAX_OUTPUT_TOKENS,
    MAX_ENGINE_GENERATE,
    MAX_OPENAI_POST,
    MODEL,
    READ_TIMEOUT_SECONDS,
)
from app.book_semantic_gate_4b24.guard import BookSemanticGateCanaryError


class CountingOpenAIEngine(OpenAIEngine):
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
        self.generate_attempts = 0
        self.post_attempts = 0

    def config_temperature(self) -> float | None:
        # Terra temperature is omitted. Do not inherit OPENAI_TEMPERATURE.
        return None

    def build_payload(self, request: AIRequest, model: str) -> dict:
        payload = super().build_payload(request, model)
        payload.pop("temperature", None)
        payload.pop("x-api-key", None)
        payload.pop("api_key", None)
        payload.pop("authorization", None)
        return payload

    def generate(self, request: AIRequest):
        self.generate_attempts += 1
        if self.generate_attempts > MAX_ENGINE_GENERATE:
            raise BookSemanticGateCanaryError("Second engine.generate refused.")
        return super().generate(request)

    def _invoke(self, request: AIRequest, model: str) -> ProviderResult:
        self.post_attempts += 1
        if self.post_attempts > MAX_OPENAI_POST:
            raise BookSemanticGateCanaryError("Second OpenAI POST refused.")
        return super()._invoke(request, model)


def credential_available() -> bool:
    return bool(get_api_key(ENV_OPENAI_API_KEY, config_fallback="OPENAI_API_KEY"))


def describe_engine(engine: Any) -> dict[str, Any]:
    policy = getattr(engine, "retry_policy", None) or getattr(
        engine, "_retry_policy", None
    )
    max_attempts = int(getattr(policy, "max_attempts", 0) or 0) if policy else 0
    return {
        "class_name": type(engine).__name__,
        "provider": getattr(engine, "provider_name", None),
        "retry_max_attempts": max_attempts,
        "is_openai": isinstance(engine, OpenAIEngine),
        "is_anthropic": False,
        "is_fake": type(engine).__name__ in {"FakeAIEngine", "WindowMappedFakeAI"},
        "generate_attempts": int(getattr(engine, "generate_attempts", 0) or 0),
        "post_attempts": int(getattr(engine, "post_attempts", 0) or 0),
        "connect_timeout_seconds": getattr(engine, "_connect_timeout_seconds", None),
        "read_timeout_seconds": getattr(engine, "_timeout_seconds", None),
        "engine_max_output_tokens": getattr(engine, "_max_output_tokens", None),
        "temperature_omitted": True,
    }


def build_real_canary_engine() -> CountingOpenAIEngine:
    if not credential_available():
        raise BookSemanticGateCanaryError(
            "OpenAI credential unavailable — STOP WITHOUT PROVIDER CALL."
        )
    return CountingOpenAIEngine()


__all__ = [
    "CountingOpenAIEngine",
    "build_real_canary_engine",
    "credential_available",
    "describe_engine",
]
