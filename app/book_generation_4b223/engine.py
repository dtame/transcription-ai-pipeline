"""Anthropic engine: 1 generate and 1 POST per chapter, 4 posts for the batch."""

from __future__ import annotations

from typing import Any

from app.ai.contracts import AIRequest
from app.ai.providers.anthropic_engine import AnthropicEngine
from app.ai.providers.base import ProviderResult
from app.ai.retry import RetryPolicy
from app.book_generation_4b223.constants import (
    CONNECT_TIMEOUT_SECONDS,
    MAX_ANTHROPIC_POST,
    MAX_EXECUTION_ATTEMPTS,
    MODEL,
    READ_TIMEOUT_SECONDS,
)
from app.book_generation_4b223.guard import BookGeneration4223Error
from app.source_analysis_hybrid_readiness.facts import anthropic_credential_available


class CountingAnthropicEngine(AnthropicEngine):
    def __init__(self, **kwargs: Any) -> None:
        self.max_posts = int(kwargs.pop("max_posts", 1) or 1)
        kwargs.setdefault("model", MODEL)
        kwargs.setdefault("temperature", None)
        kwargs.setdefault("timeout_seconds", READ_TIMEOUT_SECONDS)
        kwargs.setdefault("connect_timeout_seconds", CONNECT_TIMEOUT_SECONDS)
        kwargs.setdefault(
            "retry_policy",
            RetryPolicy(max_attempts=MAX_EXECUTION_ATTEMPTS, base_delay_seconds=0.0),
        )
        super().__init__(**kwargs)
        self.generate_attempts = 0
        self.post_attempts = 0

    def generate(self, request: AIRequest):
        self.generate_attempts += 1
        if self.generate_attempts > MAX_EXECUTION_ATTEMPTS:
            raise BookGeneration4223Error("Second engine.generate refused for this chapter.")
        return super().generate(request)

    def _invoke(self, request: AIRequest, model: str) -> ProviderResult:
        self.post_attempts += 1
        if self.post_attempts > self.max_posts:
            raise BookGeneration4223Error("Second Anthropic POST refused for this chapter.")
        if self.post_attempts > MAX_ANTHROPIC_POST:
            raise BookGeneration4223Error("BATCH-01 Anthropic POST ceiling exceeded.")
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
        "is_openai": type(engine).__name__
        in {"OpenAIEngine", "NoRetryAccountingOpenAIEngine"},
        "is_fake": type(engine).__name__ in {"FakeAIEngine", "WindowMappedFakeAI"},
        "generate_attempts": int(getattr(engine, "generate_attempts", 0) or 0),
        "post_attempts": int(getattr(engine, "post_attempts", 0) or 0),
        "connect_timeout_seconds": getattr(engine, "_connect_timeout_seconds", None),
        "read_timeout_seconds": getattr(engine, "_timeout_seconds", None),
    }


def build_real_engine() -> CountingAnthropicEngine:
    if not credential_available():
        raise BookGeneration4223Error(
            "Anthropic credential unavailable — STOP WITHOUT PROVIDER CALL."
        )
    return CountingAnthropicEngine(max_posts=1)


__all__ = [
    "CountingAnthropicEngine",
    "build_real_engine",
    "credential_available",
    "describe_engine",
]
