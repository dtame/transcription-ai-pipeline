"""Fail-closed 4B.2.4 guards: one Terra call, no Sonnet, no publication."""

from __future__ import annotations

from pathlib import Path

from app.book_generation.writer import production_book_absent
from app.book_semantic_gate_4b24.constants import (
    AUTHORIZATION_SCOPE,
    PROJECT_NAME,
    PUBLICATION_AUTHORIZED,
)
from app.editorial_planner_canary_4a1.guard import OneShotCallGuard
from app.source_analysis.errors import MaxRealCallsExceededError


class BookSemanticGateCanaryError(RuntimeError):
    """Local failure before network, or mandatory stop after one attempt."""


def validate_authorization_scope(authorization_scope: str | None) -> str:
    scope = str(authorization_scope or "").strip()
    if scope != AUTHORIZATION_SCOPE:
        raise BookSemanticGateCanaryError(
            "Authorization scope must be exactly "
            f"{AUTHORIZATION_SCOPE}, received {scope!r}."
        )
    return scope


def assert_no_publication(path: Path) -> None:
    if path.is_file():
        raise BookSemanticGateCanaryError(
            f"Production book.json already present at {path}. "
            "4B.2.4 must not publish and must not overwrite."
        )
    if PUBLICATION_AUTHORIZED:
        raise BookSemanticGateCanaryError("publication is not authorized")
    if not production_book_absent(PROJECT_NAME):
        raise BookSemanticGateCanaryError("book.json must remain unpublished")


__all__ = [
    "BookSemanticGateCanaryError",
    "MaxRealCallsExceededError",
    "OneShotCallGuard",
    "assert_no_publication",
    "validate_authorization_scope",
]
