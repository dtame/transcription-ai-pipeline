"""Fail-closed 4B.2.25 guards: two Sonnet calls, CH003–CH004 only."""

from __future__ import annotations

from pathlib import Path

from app.book_generation.writer import production_book_absent
from app.book_generation_4b225.constants import (
    AUTHORIZATION_SCOPE,
    AUTHORIZED_CHAPTER_IDS,
    FORBIDDEN_CHAPTER_IDS,
    FORBIDDEN_PROMPTS,
    PROJECT_NAME,
    PROMPT_VERSION,
    PUBLICATION_AUTHORIZED,
)
from app.editorial_planner_canary_4a1.guard import OneShotCallGuard
from app.source_analysis.errors import MaxRealCallsExceededError


class BookGeneration4225Error(RuntimeError):
    """Local failure before network, or mandatory stop after a reserved attempt."""


def validate_authorization_scope(authorization_scope: str | None) -> str:
    scope = str(authorization_scope or "").strip()
    if scope != AUTHORIZATION_SCOPE:
        raise BookGeneration4225Error(
            "Authorization scope must be exactly "
            f"{AUTHORIZATION_SCOPE}, received {scope!r}."
        )
    return scope


def assert_chapter_allowed(chapter_id: str) -> str:
    if chapter_id in FORBIDDEN_CHAPTER_IDS:
        raise BookGeneration4225Error(
            f"{chapter_id} is accepted or forbidden and must not be regenerated."
        )
    if chapter_id not in AUTHORIZED_CHAPTER_IDS:
        raise BookGeneration4225Error(
            f"Chapter {chapter_id!r} is not authorized. "
            f"Locked to {AUTHORIZED_CHAPTER_IDS}."
        )
    return chapter_id


def chapter_lock_id(chapter_id: str) -> str:
    assert_chapter_allowed(chapter_id)
    return f"BATCH-01-RESUME / {chapter_id}"


def assert_prompt_allowed(prompt_version: str) -> str:
    requested = str(prompt_version or "").strip()
    if requested in FORBIDDEN_PROMPTS:
        raise BookGeneration4225Error(
            f"Prompt {requested} is forbidden. Isolated 1.1 only."
        )
    if requested != PROMPT_VERSION:
        raise BookGeneration4225Error(
            f"Prompt {requested!r} is not authorized. Locked to {PROMPT_VERSION}."
        )
    return requested


def assert_no_publication(path: Path) -> None:
    if path.is_file():
        raise BookGeneration4225Error(
            f"Production book.json already present at {path}. "
            "4B.2.25 must not publish and must not overwrite."
        )
    if PUBLICATION_AUTHORIZED:
        raise BookGeneration4225Error("publication is not authorized")
    if not production_book_absent(PROJECT_NAME):
        raise BookGeneration4225Error("book.json must remain unpublished")


class BatchCallGuard:
    """Resume-lot generate counter. A third attempt is refused."""

    def __init__(self, max_calls: int = 2) -> None:
        self.max_calls = int(max_calls)
        self.generate_attempts = 0

    def register(self) -> int:
        if self.generate_attempts >= self.max_calls:
            raise MaxRealCallsExceededError(
                f"CH003–CH004 resume authorizes at most {self.max_calls} "
                f"engine.generate attempt(s); a {self.generate_attempts + 1}th "
                "was refused."
            )
        self.generate_attempts += 1
        return self.generate_attempts


__all__ = [
    "BatchCallGuard",
    "BookGeneration4225Error",
    "MaxRealCallsExceededError",
    "OneShotCallGuard",
    "assert_chapter_allowed",
    "assert_no_publication",
    "assert_prompt_allowed",
    "chapter_lock_id",
    "validate_authorization_scope",
]
