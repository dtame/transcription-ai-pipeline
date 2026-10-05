"""Fail-closed 4B.2.21 guards: one Sonnet call, CH018 only, no publication."""

from __future__ import annotations

from pathlib import Path

from app.book_generation.writer import production_book_absent
from app.book_generation_4b221.constants import (
    ACCEPTED_CHAPTER_ID,
    AUTHORIZATION_SCOPE,
    FORBIDDEN_PROMPTS,
    PROJECT_NAME,
    PROMPT_VERSION,
    PUBLICATION_AUTHORIZED,
    TARGET_CHAPTER_ID,
)
from app.editorial_planner_canary_4a1.guard import OneShotCallGuard
from app.source_analysis.errors import MaxRealCallsExceededError


class BookGeneration4221Error(RuntimeError):
    """Local failure before network, or mandatory stop after one attempt."""


def validate_authorization_scope(authorization_scope: str | None) -> str:
    scope = str(authorization_scope or "").strip()
    if scope != AUTHORIZATION_SCOPE:
        raise BookGeneration4221Error(
            "Authorization scope must be exactly "
            f"{AUTHORIZATION_SCOPE}, received {scope!r}."
        )
    return scope


def assert_chapter_allowed(chapter_id: str) -> str:
    if chapter_id == ACCEPTED_CHAPTER_ID:
        raise BookGeneration4221Error(
            f"{ACCEPTED_CHAPTER_ID} is accepted and must not be regenerated."
        )
    if chapter_id != TARGET_CHAPTER_ID:
        raise BookGeneration4221Error(
            f"Chapter {chapter_id!r} is not authorized. Locked to {TARGET_CHAPTER_ID}."
        )
    return chapter_id


def assert_prompt_allowed(prompt_version: str) -> str:
    requested = str(prompt_version or "").strip()
    if requested in FORBIDDEN_PROMPTS:
        raise BookGeneration4221Error(
            f"Prompt {requested} is forbidden. Isolated 1.1 only."
        )
    if requested != PROMPT_VERSION:
        raise BookGeneration4221Error(
            f"Prompt {requested!r} is not authorized. Locked to {PROMPT_VERSION}."
        )
    return requested


def assert_no_publication(path: Path) -> None:
    if path.is_file():
        raise BookGeneration4221Error(
            f"Production book.json already present at {path}. "
            "4B.2.21 must not publish and must not overwrite."
        )
    if PUBLICATION_AUTHORIZED:
        raise BookGeneration4221Error("publication is not authorized")
    if not production_book_absent(PROJECT_NAME):
        raise BookGeneration4221Error("book.json must remain unpublished")


__all__ = [
    "BookGeneration4221Error",
    "MaxRealCallsExceededError",
    "OneShotCallGuard",
    "assert_chapter_allowed",
    "assert_no_publication",
    "assert_prompt_allowed",
    "validate_authorization_scope",
]
