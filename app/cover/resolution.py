"""Resolve cover text from a book payload without copying the manuscript."""

from __future__ import annotations

from typing import Any, Mapping

from app.cover.models.author import AuthorProfile


class CoverResolutionError(ValueError):
    """Canonical cover fields could not be resolved."""


def resolve_canonical_text(book: Mapping[str, Any]) -> dict[str, Any]:
    title = str(book.get("title") or "").strip()
    if not title:
        raise CoverResolutionError("the book title is missing")
    subtitle = str(book.get("subtitle") or "").strip() or None
    project = book.get("project")
    project_id = None
    if isinstance(project, Mapping):
        project_id = str(project.get("name") or "").strip() or None
    return {
        "title": title,
        "subtitle": subtitle,
        "project_id": project_id,
        "source_document_version": str(book.get("document_version") or "").strip() or None,
        "editorial_status": str(book.get("editorial_status") or "").strip() or None,
        "language": str(book.get("language") or "").strip() or None,
        "author_in_book": _absent_author(book),
    }


def resolve_author_display_name(profile: AuthorProfile | None) -> str | None:
    if profile is None or not profile.name_publication_authorized:
        return None
    return profile.display_name


def manuscript_keys_excluded() -> tuple[str, ...]:
    return (
        "chapters",
        "paragraphs",
        "transcript",
        "editorial_plan",
        "source_map",
        "back_matter",
        "front_matter",
    )


def _absent_author(book: Mapping[str, Any]) -> None:
    absent = book.get("absent_editorial_fields")
    if isinstance(absent, Mapping) and "author" in absent:
        return None
    author = book.get("author")
    if author in (None, "", []):
        return None
    return None


__all__ = [
    "CoverResolutionError",
    "manuscript_keys_excluded",
    "resolve_author_display_name",
    "resolve_canonical_text",
]
