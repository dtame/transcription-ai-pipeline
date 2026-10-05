"""Assemble a draft cover record from resolved book fields."""

from __future__ import annotations

from typing import Any, Mapping

from app.cover.constants import COVER_VERSION_DRAFT
from app.cover.content.contract import initial_content
from app.cover.models.author import AuthorProfile
from app.cover.models.cover import CoverFormat, CoverRecord, empty_back, empty_export, empty_front
from app.cover.renderer.geometry import cover_geometry
from app.cover.resolution import resolve_author_display_name, resolve_canonical_text


class CoverValidationError(ValueError):
    """Draft cover failed a structural check."""


def build_draft_cover(
    book: Mapping[str, Any],
    *,
    project_id: str,
    book_version: str,
    profile: AuthorProfile | None = None,
    biography_snapshot: dict[str, Any] | None = None,
    bleed_mm: float = 3.0,
    safety_in: float = 0.25,
    background_color: str | None = None,
) -> dict[str, Any]:
    resolved = resolve_canonical_text(book)
    content = initial_content(profile)
    if biography_snapshot is not None:
        content["author_biography"] = biography_snapshot.get("text")
        content["author_biography_status"] = biography_snapshot.get("status")
    front = empty_front(title=resolved["title"], subtitle=resolved["subtitle"])
    front["author_display_name"] = resolve_author_display_name(profile)
    back = empty_back()
    back["background_color"] = background_color
    back["book_description"] = content["book_description"]
    back["author_biography"] = content["author_biography"]
    back["author_display_name"] = front["author_display_name"]
    record = CoverRecord(
        cover_id=f"cover_{project_id}_{COVER_VERSION_DRAFT.replace('-', '_')}",
        project_id=project_id,
        book_version=book_version,
        source_document_version=resolved["source_document_version"],
        format=CoverFormat(bleed_mm=bleed_mm, safety_in=safety_in),
        front=front,
        back=back,
        author_id=None if profile is None else profile.author_id,
        biography_snapshot=biography_snapshot,
        content=content,
        export=empty_export(),
        source_refs={
            "book_json": "read_only",
            "interior_independent": True,
            "title_source": "book.title",
            "subtitle_source": "book.subtitle",
        },
    )
    payload = record.to_dict()
    validate_draft(payload)
    return payload


def validate_draft(cover: Mapping[str, Any]) -> None:
    if cover.get("cover_mode") != "TWO_SEPARATE_PAGES":
        raise CoverValidationError("cover mode must be two separate pages")
    if cover.get("wraparound") or cover.get("spine_computed"):
        raise CoverValidationError("wraparound and spine are out of scope")
    fmt = cover.get("format") or {}
    if float(fmt.get("width_in")) != 6.0 or float(fmt.get("height_in")) != 9.0:
        raise CoverValidationError("finished format must be 6 × 9 inches")
    geometry = cover_geometry(
        bleed_mm=float(fmt.get("bleed_mm")),
        safety_in=float(fmt.get("safety_in")),
        dpi=int(fmt.get("dpi") or 300),
    )
    if geometry.safety_width_px <= 0 or geometry.safety_height_px <= 0:
        raise CoverValidationError("safety zone must sit inside the trim")
    front = cover.get("front") or {}
    if front.get("text_baked_into_image"):
        raise CoverValidationError("generated art must not contain cover text")
    if cover.get("status") == "DRAFT" and front.get("background_image_path") is None:
        pass
    elif cover.get("status") != "DRAFT" and not front.get("background_image_path"):
        raise CoverValidationError("a non-draft front cover needs a background image")
    back = cover.get("back") or {}
    if back.get("background_mode") != "SOLID_COLOR":
        raise CoverValidationError("the back cover uses a solid color")
    if back.get("barcode") or back.get("isbn") or back.get("testimonials"):
        raise CoverValidationError("barcode, ISBN, and testimonials are excluded")
    export = cover.get("export") or {}
    if any(export.get(key) for key in ("front_docx", "front_pdf", "back_docx", "back_pdf")):
        raise CoverValidationError("this phase does not publish cover DOCX or PDF files")
    for key in ("chapters", "paragraphs", "transcript"):
        if key in cover:
            raise CoverValidationError(f"cover record contains manuscript key {key}")


def draft_has_no_published_files(cover: Mapping[str, Any]) -> bool:
    export = cover.get("export") or {}
    return all(export.get(key) is None for key in ("front_docx", "front_pdf", "back_docx", "back_pdf"))


__all__ = ["CoverValidationError", "build_draft_cover", "draft_has_no_published_files", "validate_draft"]
