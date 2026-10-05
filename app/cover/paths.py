"""Repository paths owned by the cover package."""

from __future__ import annotations

from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def default_library_root(*, root: Path | None = None) -> Path:
    return (root or repo_root()) / "data" / "author_library"


__all__ = ["default_library_root", "repo_root"]
