"""Fail-closed 4B.2.2 guards: exact scope, one call, no publication."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from app.book_generator_canary_4b22.constants import AUTHORIZATION_SCOPE
from app.editorial_planner_canary_4a1.guard import OneShotCallGuard
from app.source_analysis.errors import MaxRealCallsExceededError


class BookGeneratorCanaryError(RuntimeError):
    """Local failure before network, or mandatory stop after one attempt."""


def validate_authorization_scope(authorization_scope: str | None) -> str:
    scope = str(authorization_scope or "").strip()
    if scope != AUTHORIZATION_SCOPE:
        raise BookGeneratorCanaryError(
            "Authorization scope must be exactly "
            f"{AUTHORIZATION_SCOPE}, received {scope!r}."
        )
    return scope


def assert_no_publication(path: Path) -> None:
    if path.is_file():
        raise BookGeneratorCanaryError(
            f"Production book.json already present at {path}. "
            "4B.2.2 must not publish and must not overwrite."
        )


def payload_max_tokens(payload: Mapping[str, Any]) -> Any:
    return payload.get("max_tokens")


__all__ = [
    "BookGeneratorCanaryError",
    "MaxRealCallsExceededError",
    "OneShotCallGuard",
    "assert_no_publication",
    "payload_max_tokens",
    "validate_authorization_scope",
]
