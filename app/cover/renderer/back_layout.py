"""Back-cover composition model. No PDF and no invented biography."""

from __future__ import annotations

from typing import Any

from app.cover.content.contract import back_layout_blocks, initial_content
from app.cover.renderer.geometry import CoverGeometry, cover_geometry


def back_cover_composition(
    content: dict[str, Any] | None = None,
    *,
    geometry: CoverGeometry | None = None,
) -> dict[str, Any]:
    state = initial_content(None) if content is None else dict(content)
    canvas = geometry or cover_geometry()
    blocks = back_layout_blocks(state)
    description_present = "book_description" in blocks
    biography_present = "author_biography" in blocks
    if description_present and biography_present:
        arrangement = "description_then_biography"
    elif description_present:
        arrangement = "description_uses_the_full_text_column"
    elif biography_present:
        arrangement = "biography_only_description_band_collapsed"
    else:
        arrangement = "color_field_only"
    return {
        "independent_of_front_cover": True,
        "pdf_generated": False,
        "background_mode": "solid_color",
        "background_color": None,
        "background_color_status": "PENDING_FRONT_COVER",
        "author_biography_status": state.get("author_biography_status"),
        "book_description_status": state.get("book_description_status"),
        "invented_biography": False,
        "blocks": blocks,
        "empty_biography_slot_reserved": False,
        "arrangement": arrangement,
        "text_column_px": {
            "x": canvas.full_width_px - canvas.trim_width_px,
            "y": canvas.full_height_px - canvas.trim_height_px,
            "width": canvas.safety_width_px,
            "height": canvas.safety_height_px,
            "note": "Type stays inside the trim safety inset. The band grows or collapses with the blocks.",
        },
        "public_facts": {
            "isbn": "NOT_APPROVED",
            "barcode": "NOT_APPROVED",
            "publisher": "NOT_APPROVED",
        },
        "reflow": [
            "MISSING biography removes its band and returns that space to the color field.",
            "A present description then occupies the text column alone.",
            "When both texts exist, the description stays above the biography with a gap.",
            "Neither text is invented or approved in this phase.",
        ],
    }


__all__ = ["back_cover_composition"]
