"""Candidate single-chapter mode. Disabled for real providers in this phase."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from app.book_generation_bridge_4b214.constants import (
    PHASE,
    REAL_PROVIDERS_ENABLED,
    SINGLE_CHAPTER_MODE_DEFAULT,
    SINGLE_CHAPTER_MODE_VERSION,
)
from app.book_generation_bridge_4b214.guard import BookGenerationBridge214Error


@dataclass(frozen=True)
class SingleChapterMode:
    enabled: bool
    chapter_id: str
    allow_real_providers: bool = False
    allow_book_assembly: bool = False
    allow_phase5: bool = False
    allow_word_pdf: bool = False
    allow_fallback: bool = False
    allow_automatic_retry: bool = False
    allow_other_chapters: bool = False

    def assert_allowed(self, requested_chapter_id: str) -> None:
        if not self.enabled:
            raise BookGenerationBridge214Error("single_chapter_only is not enabled.")
        if not requested_chapter_id:
            raise BookGenerationBridge214Error("single_chapter_only requires an explicit chapter_id.")
        if requested_chapter_id != self.chapter_id:
            raise BookGenerationBridge214Error(
                "single_chapter_only refuses "
                f"{requested_chapter_id!r}; locked to {self.chapter_id!r}."
            )
        if self.allow_real_providers or REAL_PROVIDERS_ENABLED:
            raise BookGenerationBridge214Error(
                "single_chapter_only real providers are disabled in 4B.2.14."
            )
        if self.allow_other_chapters:
            raise BookGenerationBridge214Error("single_chapter_only must not walk other chapters.")
        if self.allow_book_assembly:
            raise BookGenerationBridge214Error("single_chapter_only must not assemble the book.")
        if self.allow_phase5:
            raise BookGenerationBridge214Error("single_chapter_only must not run Phase 5.")
        if self.allow_word_pdf:
            raise BookGenerationBridge214Error("single_chapter_only must not emit Word/PDF.")
        if self.allow_fallback:
            raise BookGenerationBridge214Error("single_chapter_only must not fallback.")
        if self.allow_automatic_retry:
            raise BookGenerationBridge214Error(
                "single_chapter_only must not retry providers automatically."
            )


def default_single_chapter_mode() -> SingleChapterMode:
    return SingleChapterMode(enabled=SINGLE_CHAPTER_MODE_DEFAULT, chapter_id="")


def assert_no_other_chapters(chapter_id: str, seen: Sequence[str]) -> None:
    extra = [item for item in seen if item and item != chapter_id]
    if extra:
        raise BookGenerationBridge214Error(
            "single_chapter_only extra chapters requested: " + ",".join(extra)
        )


def single_chapter_mode_document() -> dict[str, Any]:
    return {
        "phase": PHASE,
        "version": SINGLE_CHAPTER_MODE_VERSION,
        "enabled_by_default": SINGLE_CHAPTER_MODE_DEFAULT,
        "real_providers_enabled": False,
        "requires_explicit_chapter_id": True,
        "does_not_walk_other_chapters": True,
        "does_not_trigger_global_generation": True,
        "does_not_assemble_book": True,
        "does_not_run_phase5": True,
        "does_not_emit_word_pdf": True,
        "does_not_fallback": True,
        "does_not_retry_provider_automatically": True,
        "tested_with_fakeai_only": True,
        "secrets_included": False,
    }


__all__ = [
    "SingleChapterMode",
    "assert_no_other_chapters",
    "default_single_chapter_mode",
    "single_chapter_mode_document",
]
