"""Explicit status sets for authors, facts, and cover copy."""

from __future__ import annotations

from app.cover.constants import (
    CONTENT_STATUSES,
    PUBLICATION_FACT_STATUSES,
    VERIFICATION_STATUSES,
)


class CoverModelError(ValueError):
    """A cover or author value is outside the contract."""


def require_status(value: str, allowed: tuple[str, ...], *, field: str) -> str:
    text = str(value or "").strip()
    if text not in allowed:
        raise CoverModelError(f"{field} must be one of {allowed}, got {text!r}")
    return text


def require_content_status(value: str) -> str:
    return require_status(value, CONTENT_STATUSES, field="content_status")


def require_verification_status(value: str) -> str:
    return require_status(value, VERIFICATION_STATUSES, field="verification_status")


def require_publication_status(value: str) -> str:
    return require_status(value, PUBLICATION_FACT_STATUSES, field="publication_status")


__all__ = [
    "CoverModelError",
    "require_content_status",
    "require_publication_status",
    "require_verification_status",
]
