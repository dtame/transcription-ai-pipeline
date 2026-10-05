"""4B.2.4.1 fail-closed guards. Offline only. No Terra authorization."""

from __future__ import annotations

from pathlib import Path

from app.book_generation.writer import production_book_absent
from app.book_semantic_gate_4b241.constants import (
    AUTHORIZATION_SCOPE,
    AUTHORIZED_TERRA_CALLS,
    PROJECT_NAME,
    PUBLICATION_AUTHORIZED,
    TERRA_EXECUTION_AUTHORIZED,
)


class BookSemanticGate241Error(RuntimeError):
    pass


def validate_authorization_scope(authorization_scope: str | None) -> str:
    scope = str(authorization_scope or "").strip()
    if scope != AUTHORIZATION_SCOPE:
        raise BookSemanticGate241Error(
            "Authorization scope must be exactly "
            f"{AUTHORIZATION_SCOPE}, received {scope!r}."
        )
    return scope


def assert_offline_only() -> None:
    if TERRA_EXECUTION_AUTHORIZED:
        raise BookSemanticGate241Error("Terra execution is not authorized in 4B.2.4.1.")
    if AUTHORIZED_TERRA_CALLS != 0:
        raise BookSemanticGate241Error("AUTHORIZED_TERRA_CALLS must remain 0.")
    if PUBLICATION_AUTHORIZED:
        raise BookSemanticGate241Error("publication is not authorized")
    if not production_book_absent(PROJECT_NAME):
        raise BookSemanticGate241Error("book.json must remain unpublished")


def assert_no_publication(path: Path) -> None:
    if path.is_file():
        raise BookSemanticGate241Error(
            f"Production book.json already present at {path}."
        )
    assert_offline_only()


__all__ = [
    "BookSemanticGate241Error",
    "assert_no_publication",
    "assert_offline_only",
    "validate_authorization_scope",
]
