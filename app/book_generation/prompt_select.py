"""Resolve the active Book Generator prompt module by version."""

from __future__ import annotations

from types import ModuleType

from app.book_generation.constants import (
    BOOK_GENERATOR_PROMPT_VERSION,
    BOOK_GENERATOR_PROMPT_VERSION_V10,
)


def resolve_prompt_module(version: str | None = None) -> ModuleType:
    chosen = version or BOOK_GENERATOR_PROMPT_VERSION
    if chosen == BOOK_GENERATOR_PROMPT_VERSION_V10:
        from app.book_generation import prompt as module

        return module
    if chosen == "book-generator-1.0.1":
        from app.book_generation import prompt_v101 as module

        return module
    raise ValueError(f"unknown book-generator prompt version: {chosen}")


__all__ = ["resolve_prompt_module"]
