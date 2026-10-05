"""Checks for a finished front/back cover package."""

from __future__ import annotations

import re
import zipfile
from pathlib import Path
from typing import Any

from PIL import Image

from app.cover.renderer.geometry import CoverGeometry, cover_geometry
from app.cover_print_ready_4b235.constants import (
    BACK_DOCX_NAME,
    BACK_PDF_NAME,
    DESCRIPTION_STATUS_PROPOSED,
    FRONT_DOCX_NAME,
    FRONT_PDF_NAME,
)
from app.cover_print_ready_4b235.fonts import font_metrics
from app.cover_print_ready_4b235.layout import FaceLayout, page_inches


def validate_package(
    directory: Path,
    record: dict[str, Any],
    *,
    front_layout: FaceLayout,
    back_layout: FaceLayout,
    geometry: CoverGeometry | None = None,
    canonical_match: bool = True,
    source_unchanged: bool = True,
    imports_ok: bool = True,
) -> dict[str, Any]:
    canvas = geometry or cover_geometry()
    checks = [
        _check("original_image_present", Path(record["front_image_source"]).is_file()),
        _check(
            "original_image_hash",
            record.get("original_image_sha256")
            == record.get("image_preparation", {}).get("source_sha256"),
        ),
        _check("prepared_image_decodable", _decodable(directory, record)),
        _check("prepared_ratio", _ratio_ok(record)),
        _check("prepared_resolution", _resolution_ok(record, canvas)),
        _check("front_docx", (directory / FRONT_DOCX_NAME).is_file()),
        _check("front_pdf", (directory / FRONT_PDF_NAME).is_file()),
        _check("front_pdf_pages", _pdf_pages(directory / FRONT_PDF_NAME) == 1),
        _check("back_docx", (directory / BACK_DOCX_NAME).is_file()),
        _check("back_pdf", (directory / BACK_PDF_NAME).is_file()),
        _check("back_pdf_pages", _pdf_pages(directory / BACK_PDF_NAME) == 1),
        _check("physical_dimensions", _dimensions_ok(directory, canvas)),
        _check("interior_unchanged", canonical_match and source_unchanged),
        _check("canonical_hash", canonical_match),
        _check("openai_calls", record.get("openai_calls") == 0),
        _check("black_forest_labs_calls", record.get("black_forest_labs_calls") == 0),
        _check("description_not_falsely_canonical", _description_ok(record)),
        _check("no_fake_isbn", record.get("isbn") is None and not _contains_isbn(directory)),
        _check("no_fake_barcode", record.get("barcode") is None and not _jpeg(directory)),
        _check("no_invented_author", _author_ok(record, directory)),
        _check("no_spine", record.get("spine_computed") is False and record.get("spine_file") is None),
        _check("no_wraparound", record.get("wraparound") is False),
        _check("safe_area", _safe(front_layout, canvas) and _safe(back_layout, canvas)),
        _check("bleed", canvas.full_width_px > canvas.trim_width_px and canvas.bleed_mm == 3),
        _check("provider_imports", imports_ok),
    ]
    return {
        "passed": sum(1 for item in checks if item["passed"]),
        "failed": sum(1 for item in checks if not item["passed"]),
        "checks": checks,
        "ok": all(item["passed"] for item in checks),
    }


def pdf_page_count(path: Path) -> int:
    if not path.is_file():
        return 0
    data = path.read_bytes()
    return len(re.findall(rb"/Type\s*/Page(?!s)", data))


def pdf_media_box(path: Path) -> tuple[float, float] | None:
    if not path.is_file():
        return None
    match = re.search(rb"/MediaBox\s*\[\s*0\s+0\s+([0-9.]+)\s+([0-9.]+)\s*\]", path.read_bytes())
    if not match:
        return None
    return float(match.group(1)), float(match.group(2))


def docx_document_xml(path: Path) -> str:
    with zipfile.ZipFile(path) as archive:
        return archive.read("word/document.xml").decode("utf-8")


def _pdf_pages(path: Path) -> int:
    return pdf_page_count(path)


def _decodable(directory: Path, record: dict[str, Any]) -> bool:
    path = directory / Path(str(record["prepared_image"])).name
    try:
        with Image.open(path) as image:
            image.load()
            return image.size[0] > 0 and image.size[1] > 0
    except OSError:
        return False


def _ratio_ok(record: dict[str, Any]) -> bool:
    source = record.get("image_preparation", {}).get("source_px") or [0, 0]
    if source[1] == 0:
        return False
    return abs((source[0] / source[1]) - (2 / 3)) < 1e-6


def _resolution_ok(record: dict[str, Any], geometry: CoverGeometry) -> bool:
    canvas = record.get("prepared_resolution_px") or [0, 0]
    return canvas[0] >= geometry.full_width_px and canvas[1] >= geometry.full_height_px


def _dimensions_ok(directory: Path, geometry: CoverGeometry) -> bool:
    expected = page_inches(geometry)
    expected_pt = (expected[0] * 72, expected[1] * 72)
    for name in (FRONT_PDF_NAME, BACK_PDF_NAME):
        box = pdf_media_box(directory / name)
        if box is None:
            return False
        if abs(box[0] - expected_pt[0]) > 0.6 or abs(box[1] - expected_pt[1]) > 0.6:
            return False
    return True


def _description_ok(record: dict[str, Any]) -> bool:
    status = record.get("book_description_status")
    canonical = bool(record.get("book_description_canonical"))
    if status == DESCRIPTION_STATUS_PROPOSED:
        return canonical is False and bool(record.get("book_description"))
    if status == "APPROVED":
        return canonical is True
    if status == "MISSING":
        return record.get("book_description") in (None, "") and canonical is False
    return False


def _author_ok(record: dict[str, Any], directory: Path) -> bool:
    if record.get("author_status") != "MISSING_OPTIONAL":
        return bool(record.get("author"))
    if record.get("author"):
        return False
    front = docx_document_xml(directory / FRONT_DOCX_NAME)
    return "MISSING_OPTIONAL" not in front


def _contains_isbn(directory: Path) -> bool:
    for name in (FRONT_DOCX_NAME, BACK_DOCX_NAME):
        if "ISBN" in docx_document_xml(directory / name).upper():
            return True
    return False


def _jpeg(directory: Path) -> bool:
    for name in (FRONT_PDF_NAME, BACK_PDF_NAME):
        if b"/DCTDecode" in (directory / name).read_bytes():
            return True
    return False


def _safe(layout: FaceLayout, geometry: CoverGeometry) -> bool:
    bleed_in = geometry.bleed_mm / 25.4
    minimum = bleed_in + geometry.safety_in - 0.02
    if layout.left_in < minimum:
        return False
    page_h_pt = layout.page_height_in * 72
    for line in layout.lines:
        ascent, descent = font_metrics(line.kind, line.size_pt)
        top_in = (line.baseline_from_top_pt - ascent) / 72
        bottom_in = (page_h_pt - (line.baseline_from_top_pt + descent)) / 72
        if top_in < minimum or bottom_in < minimum:
            return False
    return True


def _check(name: str, passed: bool) -> dict[str, Any]:
    return {"name": name, "passed": bool(passed)}


__all__ = [
    "docx_document_xml",
    "pdf_media_box",
    "pdf_page_count",
    "validate_package",
]
