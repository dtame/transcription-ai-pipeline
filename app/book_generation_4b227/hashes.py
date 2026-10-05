"""Canonical and accepted hashes. Read-only. STOP on mismatch."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.book_full_generation_preparation_4b226.guard import (
    BookFullGenerationPreparation4226Error,
)
from app.book_full_generation_preparation_4b226.hashes import (
    assert_accepted_unchanged as _assert_accepted,
    assert_canonical as _assert_canonical,
    file_sha256,
    snapshot as _snapshot,
    snapshots_match,
)
from app.book_generation_4b227.constants import PHASE
from app.book_generation_4b227.guard import BookGeneration4227Error


def snapshot(*, root: Path | None = None) -> dict[str, Any]:
    snap = _snapshot(root=root)
    snap["phase"] = PHASE
    return snap


def assert_canonical(snap: dict[str, Any]) -> None:
    try:
        _assert_canonical(snap)
    except BookFullGenerationPreparation4226Error as exc:
        raise BookGeneration4227Error(str(exc)) from exc


def assert_accepted_unchanged(snap: dict[str, Any]) -> None:
    try:
        _assert_accepted(snap)
    except BookFullGenerationPreparation4226Error as exc:
        raise BookGeneration4227Error(str(exc)) from exc


__all__ = [
    "assert_accepted_unchanged",
    "assert_canonical",
    "file_sha256",
    "snapshot",
    "snapshots_match",
]
