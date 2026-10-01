"""Anthropic engine: 1 generate, 1 POST, retries=0, A.2 timeouts and max_output."""

from __future__ import annotations

from typing import Any

from app.ai.contracts import AIRequest
from app.ai.providers.anthropic_engine import AnthropicEngine
from app.ai.providers.base import ProviderResult
from app.ai.retry import RetryPolicy
from app.editorial_planner_canary_4a3.constants import (
    CONNECT_TIMEOUT_SECONDS,
    MAX_ANTHROPIC_POST,
    MAX_ATTEMPTS,
    MODEL,
    PRODUCTION_MAX_OUTPUT_TOKENS,
    READ_TIMEOUT_SECONDS,
)
from app.editorial_planner_canary_4a3.guard import PlannerCanaryError
from app.source_analysis_hybrid_readiness.facts import anthropic_credential_available


class CountingAnthropicEngine(AnthropicEngine):
    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("model", MODEL)
        kwargs.setdefault("temperature", None)
        kwargs.setdefault("max_output_tokens", PRODUCTION_MAX_OUTPUT_TOKENS)
        kwargs.setdefault("timeout_seconds", READ_TIMEOUT_SECONDS)
        kwargs.setdefault("connect_timeout_seconds", CONNECT_TIMEOUT_SECONDS)
        kwargs.setdefault(
            "retry_policy",
            RetryPolicy(max_attempts=MAX_ATTEMPTS, base_delay_seconds=0.0),
        )
        super().__init__(**kwargs)
        self.generate_attempts = 0
        self.post_attempts = 0

    def generate(self, request: AIRequest):
        self.generate_attempts += 1
        if self.generate_attempts > MAX_ATTEMPTS:
            raise PlannerCanaryError("Second engine.generate refused.")
        return super().generate(request)

    def _invoke(self, request: AIRequest, model: str) -> ProviderResult:
        self.post_attempts += 1
        if self.post_attempts > MAX_ANTHROPIC_POST:
            raise PlannerCanaryError("Second Anthropic POST refused.")
        return super()._invoke(request, model)


def credential_available() -> bool:
    return bool(anthropic_credential_available())


def describe_engine(engine: Any) -> dict[str, Any]:
    policy = getattr(engine, "retry_policy", None) or getattr(
        engine, "_retry_policy", None
    )
    max_attempts = int(getattr(policy, "max_attempts", 0) or 0) if policy else 0
    return {
        "class_name": type(engine).__name__,
        "provider": getattr(engine, "provider_name", None),
        "retry_max_attempts": max_attempts,
        "is_anthropic": isinstance(engine, AnthropicEngine),
        "is_fake": type(engine).__name__ in {"FakeAIEngine", "WindowMappedFakeAI"},
        "generate_attempts": int(getattr(engine, "generate_attempts", 0) or 0),
        "post_attempts": int(getattr(engine, "post_attempts", 0) or 0),
        "connect_timeout_seconds": getattr(engine, "_connect_timeout_seconds", None),
        "read_timeout_seconds": getattr(engine, "_timeout_seconds", None),
        "engine_max_output_tokens": getattr(engine, "_max_output_tokens", None),
    }


def build_real_canary_engine() -> CountingAnthropicEngine:
    if not credential_available():
        raise PlannerCanaryError(
            "Anthropic credential unavailable — STOP WITHOUT PROVIDER CALL."
        )
    return CountingAnthropicEngine()


__all__ = [
    "CountingAnthropicEngine",
    "build_real_canary_engine",
    "credential_available",
    "describe_engine",
]
