"""Assemble one front cover and one back cover. No spine and no wraparound."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PIL import Image

from app.cover.renderer.geometry import cover_geometry
from app.cover_print_ready_4b235.constants import (
    ART_DIRECTION,
    AUTHOR_STATUS_MISSING,
    BACK_DOCX_NAME,
    BACK_FIELD_NAME,
    BACK_PDF_NAME,
    BACK_PREVIEW_NAME,
    BIOGRAPHY_STATUS_MISSING,
    CONTACT_SHEET_NAME,
    COVER_MODE,
    COVER_RECORD_NAME,
    COVER_VERSION,
    FRONT_DOCX_NAME,
    FRONT_PDF_NAME,
    FRONT_PREVIEW_NAME,
    HUMAN_IMAGE_STATUS,
    INTERIOR_PDF_PAGES,
    INTERIOR_VERSION,
    ISBN_STATUS_MISSING,
    OFF_WHITE,
    PREPARED_IMAGE_NAME,
    PROJECT_NAME,
)
from app.cover_print_ready_4b235.export_docx import render_back_docx, render_front_docx
from app.cover_print_ready_4b235.export_pdf import render_back_pdf, render_front_pdf
from app.cover_print_ready_4b235.fonts import font_set
from app.cover_print_ready_4b235.guard import assert_no_provider_calls, assert_output_allowed
from app.cover_print_ready_4b235.image_prep import prepare_cover_image
from app.cover_print_ready_4b235.layout import layout_back, layout_front, page_inches
from app.cover_print_ready_4b235.palette import contrast_ratio, select_back_color
from app.cover_print_ready_4b235.preview import render_contact_sheet, render_preview


@dataclass(frozen=True)
class CoverJob:
    title: str
    subtitle: str | None
    subtitle_status: str
    author_name: str | None
    author_status: str
    description: str | None
    description_status: str
    description_canonical: bool
    biography: str | None
    biography_status: str
    source_image: Path
    expected_sha256: str
    art_direction: str = ART_DIRECTION
    human_image_status: str = HUMAN_IMAGE_STATUS
    book_sha256: str = ""
    interior_version: str = INTERIOR_VERSION
    interior_pages: int = INTERIOR_PDF_PAGES
    project_id: str = PROJECT_NAME
    cover_version: str = COVER_VERSION
    background_rgb: tuple[int, int, int] | None = None


def assemble(job: CoverJob, directory: Path) -> dict[str, Any]:
    assert_no_provider_calls()
    assert_output_allowed(directory)
    geometry = cover_geometry()
    directory.mkdir(parents=True, exist_ok=True)
    prepared = directory / PREPARED_IMAGE_NAME
    preparation = prepare_cover_image(
        job.source_image,
        prepared,
        geometry,
        expected_sha256=job.expected_sha256,
    )
    if job.background_rgb is None:
        color = select_back_color(job.source_image)
        rgb = tuple(color["rgb"])
    else:
        rgb = job.background_rgb
        color = {
            "rgb": list(rgb),
            "hex": "#{:02X}{:02X}{:02X}".format(*rgb),
            "method": "supplied_for_this_render",
            "second_generated_image": False,
        }
    field = directory / BACK_FIELD_NAME
    _write_field(field, geometry.full_width_px, geometry.full_height_px, rgb, geometry.dpi)
    front = layout_front(
        title=job.title,
        subtitle=job.subtitle,
        author=job.author_name,
        geometry=geometry,
    )
    back = layout_back(
        title=job.title,
        subtitle=job.subtitle,
        author=job.author_name,
        description=job.description,
        description_status=job.description_status,
        biography=job.biography,
        geometry=geometry,
    )
    front_pdf = directory / FRONT_PDF_NAME
    back_pdf = directory / BACK_PDF_NAME
    front_docx = directory / FRONT_DOCX_NAME
    back_docx = directory / BACK_DOCX_NAME
    front_preview = directory / FRONT_PREVIEW_NAME
    back_preview = directory / BACK_PREVIEW_NAME
    contact = directory / CONTACT_SHEET_NAME
    render_front_pdf(front_pdf, front, prepared)
    render_back_pdf(back_pdf, back, rgb)
    render_front_docx(front_docx, front, prepared, f"{job.title} - front cover")
    render_back_docx(back_docx, back, field, f"{job.title} - back cover")
    render_preview(front_preview, front, image_path=prepared, fill=None, geometry=geometry)
    render_preview(back_preview, back, image_path=None, fill=rgb, geometry=geometry)
    render_contact_sheet(contact, front_preview, back_preview, geometry=geometry)
    page_w, page_h = page_inches(geometry)
    fonts = font_set()
    record = {
        "schema_version": "cover-print-review-v1",
        "phase": "4B.2.35",
        "project_id": job.project_id,
        "book_title": job.title,
        "canonical_book_sha256": job.book_sha256,
        "interior_version": job.interior_version,
        "interior_pages": job.interior_pages,
        "cover_version": job.cover_version,
        "cover_mode": COVER_MODE,
        "wraparound": False,
        "spine_computed": False,
        "spine_file": None,
        "art_direction": job.art_direction,
        "human_approval_status": job.human_image_status,
        "front_image_source": str(job.source_image).replace("\\", "/"),
        "original_image_sha256": preparation["source_sha256"],
        "prepared_image": _rel(prepared),
        "prepared_image_sha256": preparation["prepared_sha256"],
        "prepared_resolution_px": preparation["canvas_px"],
        "image_preparation": preparation,
        "trim_size_in": {"width": geometry.width_in, "height": geometry.height_in},
        "bleed_mm": geometry.bleed_mm,
        "document_size_in": {"width": round(page_w, 6), "height": round(page_h, 6)},
        "safe_area_in": geometry.safety_in,
        "applied_text_inset_inside_trim_in": {
            "front_side": round(front.left_in - (geometry.bleed_mm / 25.4), 4),
            "back_side": round(back.left_in - (geometry.bleed_mm / 25.4), 4),
        },
        "dpi": geometry.dpi,
        "placement": "cover",
        "background_color": color,
        "text_color_rgb": list(OFF_WHITE),
        "text_contrast_ratio": round(contrast_ratio(OFF_WHITE, rgb), 2),
        "font_family": fonts["family"],
        "pdf_fonts_embedded": True,
        "title": job.title,
        "front_title_lines": [line.text for line in front.lines if line.kind == "bold"],
        "subtitle": job.subtitle,
        "subtitle_status": job.subtitle_status,
        "author": job.author_name,
        "author_status": job.author_status,
        "book_description": job.description,
        "book_description_status": job.description_status,
        "book_description_canonical": job.description_canonical,
        "author_biography": job.biography,
        "author_biography_status": job.biography_status,
        "isbn": None,
        "isbn_status": ISBN_STATUS_MISSING,
        "barcode": None,
        "barcode_status": "NOT_GENERATED",
        "testimonials": [],
        "front_docx": _rel(front_docx),
        "front_pdf": _rel(front_pdf),
        "back_docx": _rel(back_docx),
        "back_pdf": _rel(back_pdf),
        "front_preview_png": _rel(front_preview),
        "back_preview_png": _rel(back_preview),
        "contact_sheet": _rel(contact),
        "contact_sheet_printable": False,
        "inspection_png_source": "same_layout_as_pdf",
        "pdf_rasterizer": "unavailable",
        "color_mode": "RGB",
        "pdfx": False,
        "printer_profile_applied": False,
        "ai_generation_calls": 0,
        "openai_calls": 0,
        "black_forest_labs_calls": 0,
        "generation_timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "print_status": (
            "PRINT_REVIEW"
            if job.description_canonical
            else "PRINT_REVIEW_DRAFT"
        ),
    }
    if job.author_status == AUTHOR_STATUS_MISSING:
        record["author"] = None
    if job.biography_status == BIOGRAPHY_STATUS_MISSING:
        record["author_biography"] = None
    _reject_manuscript_keys(record)
    record_path = directory / COVER_RECORD_NAME
    _write_json(record_path, record)
    return {
        "record": record,
        "record_path": record_path,
        "geometry": geometry,
        "front_layout": front,
        "back_layout": back,
        "directory": directory,
        "provider_calls": 0,
    }


def _write_field(path: Path, width: int, height: int, rgb: tuple[int, int, int], dpi: int) -> None:
    assert_output_allowed(path)
    image = Image.new("RGB", (width, height), rgb)
    image.save(path, format="PNG", dpi=(dpi, dpi))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    import json

    assert_output_allowed(path)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")


def _rel(path: Path) -> str:
    return str(path).replace("\\", "/")


def _reject_manuscript_keys(record: dict[str, Any]) -> None:
    forbidden = {"chapters", "paragraphs", "transcript", "editorial_plan", "source_map"}
    leaked = forbidden.intersection(record)
    if leaked:
        from app.cover_print_ready_4b235.guard import CoverPrintReady4235Error

        raise CoverPrintReady4235Error(f"cover record must not store manuscript keys: {sorted(leaked)}")


__all__ = ["CoverJob", "assemble"]
