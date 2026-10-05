"""Optional cover integration contract. No image generation."""

from __future__ import annotations

from typing import Any, Mapping


def cover_contract(profile: Mapping[str, Any] | None = None) -> dict[str, Any]:
    cover = dict((profile or {}).get("cover") or {})
    trim = dict(cover.get("trim") or {"width_inches": 6.0, "height_inches": 9.0})
    return {
        "required": False,
        "status": "OPTIONAL",
        "front_cover": {
            "optional": True,
            "role": "first_of_cover_or_interior_optional_image",
            "trim_width_inches": trim.get("width_inches"),
            "trim_height_inches": trim.get("height_inches"),
            "accepted_when_absent": True,
        },
        "back_cover": {
            "optional": True,
            "role": "fourth_cover_optional_image",
            "trim_width_inches": trim.get("width_inches"),
            "trim_height_inches": trim.get("height_inches"),
            "accepted_when_absent": True,
        },
        "spine": {
            "computed": False,
            "reason": (
                "Full wraparound cover width depends on the printed page count "
                "and the printer's spine formula. Those values are unknown "
                "until Phase 4B.2.31 renders the interior."
            ),
        },
        "interior_docx_requires_cover": False,
        "image_generation": False,
        "fictitious_cover_forbidden": True,
        "existing_cover_hooks": {
            "publication_docx_engine_cover_png": "optional_workshop_cover",
            "docx_export_service_image_cover": "optional_publication_cover",
        },
        "notes": (
            "The illustrated wraparound cover is out of scope for this phase. "
            "The interior renderer must proceed without a cover image."
        ),
    }


__all__ = ["cover_contract"]
