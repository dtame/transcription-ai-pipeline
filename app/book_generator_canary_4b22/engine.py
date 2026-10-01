"""Reuse the 4B.2 one-shot Anthropic engine. 1 generate, 1 POST, retries=0."""

from app.book_generator_canary_4b2.engine import (
    CountingAnthropicEngine,
    build_real_canary_engine,
    credential_available,
    describe_engine,
)

__all__ = [
    "CountingAnthropicEngine",
    "build_real_canary_engine",
    "credential_available",
    "describe_engine",
]
