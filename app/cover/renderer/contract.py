"""Cover renderer contract. Export methods refuse to write files in this phase."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.cover.constants import COVER_EXPORT_AUTHORIZED, COVER_MODE, SPINE_COMPUTED, WRAPAROUND_COVER
from app.cover.content.contract import back_layout_blocks
from app.cover.renderer.geometry import cover_geometry


class CoverRenderNotAuthorized(RuntimeError):
    """DOCX or PDF cover export is not authorized."""


class CoverRenderer:
    """Two independent faces. No wraparound and no spine."""

    def compose(self, cover: dict[str, Any]) -> dict[str, Any]:
        geometry = cover_geometry(
            width_in=float(cover["format"]["width_in"]),
            height_in=float(cover["format"]["height_in"]),
            bleed_mm=float(cover["format"]["bleed_mm"]),
            safety_in=float(cover["format"]["safety_in"]),
            dpi=int(cover["format"]["dpi"]),
        )
        content = cover.get("content") or {}
        return {
            "cover_mode": COVER_MODE,
            "wraparound": WRAPAROUND_COVER,
            "spine_computed": SPINE_COMPUTED,
            "faces": ["front", "back"],
            "independent_exports": True,
            "geometry": geometry.to_dict(),
            "front": {
                "background_image_path": cover["front"].get("background_image_path"),
                "image_optional_while_draft": cover.get("status") == "DRAFT",
                "text_baked_into_image": False,
                "text_layers": _front_text_layers(cover["front"]),
                "title_zone": "composition_engine",
                "safety_zone": "inside_trim",
            },
            "back": {
                "background_mode": cover["back"].get("background_mode"),
                "background_color": cover["back"].get("background_color"),
                "blocks": back_layout_blocks(content),
                "empty_biography_slot": False,
                "barcode": None,
                "isbn": None,
                "testimonials": [],
            },
            "text_style": {
                "font_family": "Georgia",
                "font_embedded": False,
                "title_size_pt": None,
                "body_size_pt": None,
                "color": None,
                "alignment": None,
                "line_spacing": None,
                "contrast": "NOT_EVALUATED",
                "overflow_detection": "REQUIRED_BEFORE_EXPORT",
            },
            "pdf_checks_before_delivery": [
                "dimensions",
                "bleed",
                "selectable_text",
                "embedded_images",
                "fonts",
                "safety_zone",
                "clipped_text",
            ],
            "printer_conformance_claimed": False,
            "export_executed": False,
        }

    def render_front_docx(self, cover: dict[str, Any], destination: Path) -> None:
        self._refuse("front_docx", destination, cover)

    def render_front_pdf(self, cover: dict[str, Any], destination: Path) -> None:
        self._refuse("front_pdf", destination, cover)

    def render_back_docx(self, cover: dict[str, Any], destination: Path) -> None:
        self._refuse("back_docx", destination, cover)

    def render_back_pdf(self, cover: dict[str, Any], destination: Path) -> None:
        self._refuse("back_pdf", destination, cover)

    def _refuse(self, kind: str, destination: Path, cover: dict[str, Any]) -> None:
        del cover
        if COVER_EXPORT_AUTHORIZED:
            raise CoverRenderNotAuthorized("export authorization flag is inconsistent")
        raise CoverRenderNotAuthorized(
            f"{kind} export is not authorized. Refusing to write {destination}."
        )


def renderer_contract_document() -> dict[str, Any]:
    return {
        "component": "CoverRenderer",
        "mode": COVER_MODE,
        "wraparound": False,
        "spine": False,
        "outputs": ["front_cover.docx", "front_cover.pdf", "back_cover.docx", "back_cover.pdf"],
        "independent_of_interior": True,
        "export_authorized": COVER_EXPORT_AUTHORIZED,
        "image_text": "added_by_composition_engine",
        "back_background": "SOLID_COLOR",
        "missing_biography": "reflow_without_reserved_empty_slot",
        "forbidden_back_elements": ["testimonial", "award", "barcode", "isbn"],
        "print_pixels_at_300dpi_trim": [1800, 2700],
        "print_pixels_at_300dpi_3mm_bleed_rounded": [1871, 2771],
        "pixel_values_are_calculated": True,
        "declared_resolution_is_not_observed_quality": True,
        "printer_universal_conformance": False,
    }


def _front_text_layers(front: dict[str, Any]) -> list[str]:
    layers = ["title"]
    if front.get("subtitle"):
        layers.append("subtitle")
    if front.get("author_display_name"):
        layers.append("author_display_name")
    return layers


__all__ = ["CoverRenderNotAuthorized", "CoverRenderer", "renderer_contract_document"]
