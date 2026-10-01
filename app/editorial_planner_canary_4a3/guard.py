"""Fail-closed A.3 guards: exact scope, one call, no publication, no book."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from app.editorial_planner_canary_4a1.guard import OneShotCallGuard
from app.editorial_planner_canary_4a3.constants import AUTHORIZATION_SCOPE
from app.editorial_planning.guard import (
    assert_analyzer_untouched,
    assert_no_book_generator as _assert_no_book_generator_planner,
)
from app.source_analysis.errors import MaxRealCallsExceededError

_PACKAGE_DIR = Path(__file__).resolve().parent


class PlannerCanaryError(RuntimeError):
    """Local failure before network, or mandatory stop after one attempt."""


def validate_authorization_scope(authorization_scope: str | None) -> str:
    scope = str(authorization_scope or "").strip()
    if scope != AUTHORIZATION_SCOPE:
        raise PlannerCanaryError(
            "Authorization scope must be exactly "
            f"{AUTHORIZATION_SCOPE}, received {scope!r}."
        )
    return scope


def assert_no_book_generator() -> None:
    _assert_no_book_generator_planner(_PACKAGE_DIR)
    _assert_no_book_generator_planner()


def assert_phase3b_untouched() -> None:
    assert_analyzer_untouched()


def assert_no_publication(path: Path) -> None:
    if path.is_file():
        raise PlannerCanaryError(
            f"Production editorial_plan.json already present at {path}. "
            "A.3 must not publish and must not overwrite."
        )


def payload_max_tokens(payload: Mapping[str, Any]) -> Any:
    return payload.get("max_tokens")


__all__ = [
    "MaxRealCallsExceededError",
    "OneShotCallGuard",
    "PlannerCanaryError",
    "assert_no_book_generator",
    "assert_no_publication",
    "assert_phase3b_untouched",
    "payload_max_tokens",
    "validate_authorization_scope",
]
