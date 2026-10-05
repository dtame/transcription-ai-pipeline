"""Fail-closed 4B.2.7.3 guards: one Terra remote invocation, no Sonnet, no publication."""

from __future__ import annotations

from pathlib import Path

from app.book_generation.writer import production_book_absent
from app.book_semantic_gate_4b273.constants import (
    AUTHORIZATION_SCOPE,
    PROJECT_NAME,
    PUBLICATION_AUTHORIZED,
)
from app.editorial_planner_canary_4a1.guard import OneShotCallGuard
from app.source_analysis.errors import MaxRealCallsExceededError


class BookSemanticGate273Error(RuntimeError):
    """Local failure before network, or mandatory stop after one attempt."""


def validate_authorization_scope(authorization_scope: str | None) -> str:
    scope = str(authorization_scope or "").strip()
    if scope != AUTHORIZATION_SCOPE:
        raise BookSemanticGate273Error(
            "Authorization scope must be exactly "
            f"{AUTHORIZATION_SCOPE}, received {scope!r}."
        )
    return scope


def assert_no_publication(path: Path) -> None:
    if path.is_file():
        raise BookSemanticGate273Error(
            f"Production book.json already present at {path}. "
            "4B.2.7.3 must not publish and must not overwrite."
        )
    if PUBLICATION_AUTHORIZED:
        raise BookSemanticGate273Error("publication is not authorized")
    if not production_book_absent(PROJECT_NAME):
        raise BookSemanticGate273Error("book.json must remain unpublished")


def consume_remote_lock(*, path: Path, phase: str, scope: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise BookSemanticGate273Error(
            "Canary remote-invocation lock already present — authorization "
            "consumed. NO RETRY."
        )
    path.write_text(
        f"{phase}\n{scope}\nconsumed=1\nboundary=remote_invocation\n",
        encoding="utf-8",
    )


__all__ = [
    "BookSemanticGate273Error",
    "MaxRealCallsExceededError",
    "OneShotCallGuard",
    "assert_no_publication",
    "consume_remote_lock",
    "validate_authorization_scope",
]
