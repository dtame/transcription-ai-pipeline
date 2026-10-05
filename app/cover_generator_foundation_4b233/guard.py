"""Fail-closed 4B.2.33 guards. Offline foundation only."""

from __future__ import annotations

from pathlib import Path

from app.book_print_review_canonical_4b229.constants import (
    AUTHORIZATION_SCOPE as CONSUMED_4B229_SCOPE,
)
from app.book_print_review_pagination_fix_4b232.constants import (
    AUTHORIZATION_SCOPE as CONSUMED_4B232_SCOPE,
)
from app.book_print_review_render_4b231.constants import (
    AUTHORIZATION_SCOPE as CONSUMED_4B231_SCOPE,
)
from app.cover_generator_foundation_4b233.constants import (
    AUTHORIZATION_SCOPE,
    AUTHORIZED_ANTHROPIC_CALLS,
    AUTHORIZED_OPENAI_CALLS,
    AUTHORIZED_SONNET_CALLS,
    AUTHORIZED_TERRA_CALLS,
    BOOK_JSON_MUTATION_AUTHORIZED,
    COVER_GENERATION_AUTHORIZED,
    DOCX_GENERATION_AUTHORIZED,
    IMAGE_GENERATION_AUTHORIZED,
    MODEL_DOWNLOAD_AUTHORIZED,
    PDF_GENERATION_AUTHORIZED,
)
from app.cover_generator_foundation_4b233.paths import is_protected_publication_path
from app.word_print_profile_4b230.constants import (
    AUTHORIZATION_SCOPE as CONSUMED_4B230_SCOPE,
)


class CoverGeneratorFoundation4233Error(RuntimeError):
    """Cover-generator foundation rejected."""


def validate_authorization_scope(scope: str | None) -> str:
    text = str(scope or "").strip()
    consumed = {
        CONSUMED_4B229_SCOPE: "4B.2.29 book constitution",
        CONSUMED_4B230_SCOPE: "4B.2.30 print profile",
        CONSUMED_4B231_SCOPE: "4B.2.31 interior render",
        CONSUMED_4B232_SCOPE: "4B.2.32 pagination fix",
    }
    if text in consumed:
        raise CoverGeneratorFoundation4233Error(
            f"The {consumed[text]} authorization cannot prepare the cover generator."
        )
    if text != AUTHORIZATION_SCOPE:
        raise CoverGeneratorFoundation4233Error(
            "authorization scope does not match the 4B.2.33 cover foundation"
        )
    return text


def assert_offline_only() -> None:
    if AUTHORIZED_TERRA_CALLS or AUTHORIZED_OPENAI_CALLS or AUTHORIZED_ANTHROPIC_CALLS:
        raise CoverGeneratorFoundation4233Error("provider calls are not authorized")
    if AUTHORIZED_SONNET_CALLS:
        raise CoverGeneratorFoundation4233Error("Sonnet calls are not authorized")
    if IMAGE_GENERATION_AUTHORIZED or COVER_GENERATION_AUTHORIZED:
        raise CoverGeneratorFoundation4233Error("cover image generation is not authorized")
    if DOCX_GENERATION_AUTHORIZED or PDF_GENERATION_AUTHORIZED:
        raise CoverGeneratorFoundation4233Error("cover DOCX/PDF export is not authorized")
    if MODEL_DOWNLOAD_AUTHORIZED:
        raise CoverGeneratorFoundation4233Error("model download is not authorized")
    if BOOK_JSON_MUTATION_AUTHORIZED:
        raise CoverGeneratorFoundation4233Error("book.json mutation is not authorized")


def assert_write_target_allowed(path: Path) -> None:
    if is_protected_publication_path(path):
        raise CoverGeneratorFoundation4233Error(
            f"refusing to write into the interior publication: {path}. STOP."
        )
    suffix = path.suffix.lower()
    if suffix in {".docx", ".pdf", ".png", ".jpg", ".jpeg", ".webp"}:
        raise CoverGeneratorFoundation4233Error(
            f"refusing to write a cover binary: {path}. STOP."
        )


def reject_real_execution(token: str) -> None:
    raise CoverGeneratorFoundation4233Error(
        f"{token} is rejected. This phase is an offline cover foundation."
    )


__all__ = [
    "CoverGeneratorFoundation4233Error",
    "assert_offline_only",
    "assert_write_target_allowed",
    "reject_real_execution",
    "validate_authorization_scope",
]
