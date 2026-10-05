"""Apply 6x9 portrait geometry and mirror margins to Word sections."""

from __future__ import annotations

from typing import Any, Mapping

from docx.enum.section import WD_ORIENT, WD_SECTION
from docx.shared import Inches

from app.word_renderer.oxml import (
    disable_hyphenation,
    enable_even_odd_headers,
    enable_mirror_margins,
    enable_update_fields_on_open,
    gutter_emu,
    set_gutter,
    set_page_number_format,
)
from app.word_renderer.profile import (
    chapter_start_type_name,
    first_chapter_start_type_name,
    front_matter_section_start_name,
)

_START_TYPES = {
    "odd_page": WD_SECTION.ODD_PAGE,
    "new_page": WD_SECTION.NEW_PAGE,
    "next_page": WD_SECTION.NEW_PAGE,
    "even_page": WD_SECTION.EVEN_PAGE,
    "continuous": WD_SECTION.CONTINUOUS,
}


def apply_document_settings(doc, profile: Mapping[str, Any]) -> None:
    enable_mirror_margins(doc)
    enable_even_odd_headers(doc)
    enable_update_fields_on_open(doc)
    if str(profile.get("typography", {}).get("hyphenation") or "disabled") == "disabled":
        disable_hyphenation(doc)


def apply_section_geometry(section, profile: Mapping[str, Any]) -> None:
    page = profile["page"]
    margins = profile["margins"]
    section.page_width = Inches(float(page["width_inches"]))
    section.page_height = Inches(float(page["height_inches"]))
    section.left_margin = Inches(float(margins["inside_inches"]))
    section.right_margin = Inches(float(margins["outside_inches"]))
    section.top_margin = Inches(float(margins["top_inches"]))
    section.bottom_margin = Inches(float(margins["bottom_inches"]))
    set_gutter(section, float(margins["gutter_inches"]))


def apply_front_matter_section(section, profile: Mapping[str, Any]) -> None:
    apply_section_geometry(section, profile)
    section.different_first_page_header_footer = True
    set_page_number_format(section, fmt="none")
    start_name = front_matter_section_start_name(profile)
    if start_name != "keep_existing" and start_name in _START_TYPES:
        section.start_type = _START_TYPES[start_name]


def apply_body_section(section, profile: Mapping[str, Any], *, start: bool = False) -> None:
    apply_section_geometry(section, profile)
    section.different_first_page_header_footer = True
    section.start_type = chapter_start_type(profile, first=start)
    pagination = profile["pagination"]["body"]
    set_page_number_format(
        section,
        fmt=str(pagination.get("format") or "decimal"),
        start=int(pagination.get("restart_at") or 1) if start else None,
    )


def chapter_start_type(profile: Mapping[str, Any], *, first: bool = False):
    name = (
        first_chapter_start_type_name(profile)
        if first
        else chapter_start_type_name(profile)
    )
    return _START_TYPES.get(name, WD_SECTION.NEW_PAGE)


def inspect_geometry(section, profile: Mapping[str, Any]) -> dict[str, Any]:
    page = profile["page"]
    margins = profile["margins"]
    expected_gutter = int(Inches(float(margins["gutter_inches"])))
    actual_gutter = gutter_emu(section)
    portrait = int(section.page_width) < int(section.page_height)
    return {
        "page_width_inches": float(section.page_width.inches),
        "page_height_inches": float(section.page_height.inches),
        "orientation": "portrait" if portrait else "landscape",
        "word_orientation": str(section.orientation),
        "left_margin_inches": float(section.left_margin.inches),
        "right_margin_inches": float(section.right_margin.inches),
        "top_margin_inches": float(section.top_margin.inches),
        "bottom_margin_inches": float(section.bottom_margin.inches),
        "gutter_emu": actual_gutter,
        "expected_gutter_emu": expected_gutter,
        "gutter_matches_profile": actual_gutter == expected_gutter,
        "gutter_not_added_to_left_margin": abs(
            float(section.left_margin.inches) - float(margins["inside_inches"])
        )
        < 0.0001,
        "inside_is_left_margin": True,
        "outside_is_right_margin": True,
        "mirror_convention": (
            "left_margin=inside, right_margin=outside, gutter additional, "
            "w:mirrorMargins swaps the pair on even pages"
        ),
        "page_width_matches": abs(
            float(section.page_width.inches) - float(page["width_inches"])
        )
        < 0.0001,
        "page_height_matches": abs(
            float(section.page_height.inches) - float(page["height_inches"])
        )
        < 0.0001,
        "portrait": portrait,
        "portrait_enum": section.orientation == WD_ORIENT.PORTRAIT,
    }


__all__ = [
    "apply_body_section",
    "apply_document_settings",
    "apply_front_matter_section",
    "apply_section_geometry",
    "chapter_start_type",
    "inspect_geometry",
]
