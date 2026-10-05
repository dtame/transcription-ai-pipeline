"""Independent cover record. It references a book; it does not store the manuscript."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.cover.constants import (
    COVER_MODE,
    COVER_STATUS_DRAFT,
    COVER_VERSION_DRAFT,
    DEFAULT_BLEED_MM,
    DEFAULT_DPI,
    DEFAULT_SAFETY_IN,
    SCHEMA_VERSION,
    SPINE_COMPUTED,
    TRIM_HEIGHT_IN,
    TRIM_WIDTH_IN,
    WRAPAROUND_COVER,
)


@dataclass
class CoverFormat:
    width_in: float = TRIM_WIDTH_IN
    height_in: float = TRIM_HEIGHT_IN
    bleed_mm: float = DEFAULT_BLEED_MM
    safety_in: float = DEFAULT_SAFETY_IN
    dpi: int = DEFAULT_DPI

    def to_dict(self) -> dict[str, Any]:
        return {
            "width_in": self.width_in,
            "height_in": self.height_in,
            "bleed_mm": self.bleed_mm,
            "safety_in": self.safety_in,
            "dpi": self.dpi,
            "printer_universal": False,
        }


@dataclass
class CoverRecord:
    cover_id: str
    project_id: str
    book_version: str
    source_document_version: str | None
    cover_version: str = COVER_VERSION_DRAFT
    status: str = COVER_STATUS_DRAFT
    cover_mode: str = COVER_MODE
    wraparound: bool = WRAPAROUND_COVER
    spine_computed: bool = SPINE_COMPUTED
    format: CoverFormat = field(default_factory=CoverFormat)
    front: dict[str, Any] = field(default_factory=dict)
    back: dict[str, Any] = field(default_factory=dict)
    author_id: str | None = None
    biography_snapshot: dict[str, Any] | None = None
    content: dict[str, Any] = field(default_factory=dict)
    export: dict[str, Any] = field(default_factory=dict)
    source_refs: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "schema_version": SCHEMA_VERSION,
            "cover_id": self.cover_id,
            "project_id": self.project_id,
            "book_version": self.book_version,
            "source_document_version": self.source_document_version,
            "cover_version": self.cover_version,
            "status": self.status,
            "cover_mode": self.cover_mode,
            "wraparound": self.wraparound,
            "spine_computed": self.spine_computed,
            "format": self.format.to_dict(),
            "front": dict(self.front),
            "back": dict(self.back),
            "author_id": self.author_id,
            "biography_snapshot": (
                dict(self.biography_snapshot) if self.biography_snapshot else None
            ),
            "content": dict(self.content),
            "export": dict(self.export),
            "source_refs": dict(self.source_refs),
        }
        forbidden = {"chapters", "paragraphs", "transcript", "editorial_plan", "source_map"}
        leaked = forbidden.intersection(payload)
        if leaked:
            raise ValueError(f"cover record must not store manuscript keys: {sorted(leaked)}")
        return payload


def empty_export() -> dict[str, Any]:
    return {
        "front_docx": None,
        "front_pdf": None,
        "back_docx": None,
        "back_pdf": None,
        "generated": False,
    }


def empty_front(*, title: str | None, subtitle: str | None) -> dict[str, Any]:
    return {
        "background_image_path": None,
        "image_generation_id": None,
        "title": title,
        "subtitle": subtitle,
        "author_display_name": None,
        "text_baked_into_image": False,
    }


def empty_back() -> dict[str, Any]:
    return {
        "background_mode": "SOLID_COLOR",
        "background_color": None,
        "book_description": None,
        "author_biography": None,
        "author_display_name": None,
        "barcode": None,
        "isbn": None,
        "testimonials": [],
    }


__all__ = [
    "CoverFormat",
    "CoverRecord",
    "empty_back",
    "empty_export",
    "empty_front",
]
