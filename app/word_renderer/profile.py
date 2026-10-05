"""Load and validate reusable Word print profiles."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from app.word_renderer.constants import (
    GUTTER_INCHES,
    INSIDE_MARGIN_INCHES,
    OUTSIDE_MARGIN_INCHES,
    PAGE_HEIGHT_INCHES,
    PAGE_WIDTH_INCHES,
    PROFILE_FILENAME,
    PROFILE_NAME,
    STYLE_BODY,
    STYLE_BODY_FIRST,
    STYLE_CHAPTER_TITLE,
    STYLE_SECTION_TITLE,
)

_PROFILES_DIR = Path(__file__).resolve().parent / "profiles"


class WordPrintProfileError(ValueError):
    """Print profile is missing or inconsistent."""


def profiles_dir() -> Path:
    return _PROFILES_DIR


def default_profile_path() -> Path:
    return _PROFILES_DIR / PROFILE_FILENAME


def load_profile(path: Path | None = None) -> dict[str, Any]:
    target = Path(path) if path is not None else default_profile_path()
    payload = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise WordPrintProfileError("print profile must be a JSON object")
    validate_profile(payload)
    return payload


def validate_profile(profile: Mapping[str, Any]) -> dict[str, Any]:
    if profile.get("profile_id") != PROFILE_NAME:
        raise WordPrintProfileError(
            f"unsupported profile_id {profile.get('profile_id')!r}"
        )
    if profile.get("book_agnostic") is not True:
        raise WordPrintProfileError("print profile must be book-agnostic")
    page = _mapping(profile, "page")
    if float(page.get("width_inches")) != PAGE_WIDTH_INCHES:
        raise WordPrintProfileError("page width must be 6.0 inches")
    if float(page.get("height_inches")) != PAGE_HEIGHT_INCHES:
        raise WordPrintProfileError("page height must be 9.0 inches")
    if str(page.get("orientation")) != "portrait":
        raise WordPrintProfileError("orientation must be portrait")
    if str(page.get("apply_on")) != "word_section":
        raise WordPrintProfileError("page geometry must apply on Word sections")
    margins = _mapping(profile, "margins")
    if float(margins.get("inside_inches")) != INSIDE_MARGIN_INCHES:
        raise WordPrintProfileError("inside margin must be 0.85 inch")
    if float(margins.get("outside_inches")) != OUTSIDE_MARGIN_INCHES:
        raise WordPrintProfileError("outside margin must be 0.65 inch")
    if float(margins.get("gutter_inches")) != GUTTER_INCHES:
        raise WordPrintProfileError("gutter must be 0.15 inch")
    if margins.get("mirror") is not True:
        raise WordPrintProfileError("mirror margins are required")
    gutter = _mapping(profile, "gutter_convention")
    if gutter.get("gutter_included_in_inside_margin_value") is True:
        raise WordPrintProfileError("gutter must not be folded into inside margin")
    if gutter.get("double_compensation_risk") is True:
        raise WordPrintProfileError("profile would double-count the gutter")
    styles = _mapping(profile, "styles")
    for name in (STYLE_BODY, STYLE_BODY_FIRST, STYLE_CHAPTER_TITLE, STYLE_SECTION_TITLE):
        if name not in styles:
            raise WordPrintProfileError(f"missing style {name}")
    body = _mapping(styles, STYLE_BODY)
    first = _mapping(styles, STYLE_BODY_FIRST)
    if float(first.get("first_line_indent_inches") or 0) != 0.0:
        raise WordPrintProfileError("BookBodyFirst must have no first-line indent")
    if float(body.get("first_line_indent_inches") or 0) <= 0:
        raise WordPrintProfileError("BookBody must keep a first-line indent")
    chapter = _mapping(profile, "chapter")
    numbering = _mapping(chapter, "numbering")
    if numbering.get("include_in_title_text") is True:
        raise WordPrintProfileError("chapter numbers must not be merged into titles")
    if numbering.get("source") != "chapter.order":
        raise WordPrintProfileError("chapter numbers must come from chapter.order")
    start = str(chapter.get("start") or "next_page")
    if start not in {"next_page", "new_page", "odd_page"}:
        raise WordPrintProfileError(f"unsupported chapter.start {start!r}")
    pagination = _mapping(profile, "pagination")
    front_pagination = _mapping(pagination, "front_matter")
    body_pagination = _mapping(pagination, "body")
    front_start = str(front_pagination.get("section_start") or "keep_existing")
    if front_start not in {"keep_existing", "new_page", "next_page", "continuous"}:
        raise WordPrintProfileError(
            f"unsupported pagination.front_matter.section_start {front_start!r}"
        )
    body_start = str(body_pagination.get("chapter_start") or start)
    if body_start not in {"next_page", "new_page", "odd_page"}:
        raise WordPrintProfileError(
            f"unsupported pagination.body.chapter_start {body_start!r}"
        )
    cover = _mapping(profile, "cover")
    if cover.get("required") is True:
        raise WordPrintProfileError("cover must remain optional")
    if cover.get("spine_width_computed") is True:
        raise WordPrintProfileError("spine width must not be computed yet")
    dumped = json.dumps(profile, ensure_ascii=True)
    if "The Life You Already Inherited" in dumped:
        raise WordPrintProfileError("generic profile must not contain a book title")
    return dict(profile)


def style_spec(profile: Mapping[str, Any], name: str) -> dict[str, Any]:
    return dict(_mapping(_mapping(profile, "styles"), name))


def include_sections_in_toc(profile: Mapping[str, Any], *, include_sections: bool | None) -> bool:
    toc = _mapping(profile, "toc")
    if include_sections is not None:
        return bool(include_sections)
    return bool(toc.get("include_sections_default"))


def front_matter_section_start_name(profile: Mapping[str, Any]) -> str:
    pagination = profile.get("pagination")
    if isinstance(pagination, Mapping):
        front = pagination.get("front_matter")
        if isinstance(front, Mapping) and front.get("section_start"):
            return str(front.get("section_start"))
    return "keep_existing"


def chapter_start_type_name(profile: Mapping[str, Any]) -> str:
    pagination = profile.get("pagination")
    if isinstance(pagination, Mapping):
        body = pagination.get("body")
        if isinstance(body, Mapping) and body.get("chapter_start"):
            return str(body.get("chapter_start"))
    chapter = profile.get("chapter")
    if isinstance(chapter, Mapping) and chapter.get("start"):
        return str(chapter.get("start"))
    return "next_page"


def first_chapter_start_type_name(profile: Mapping[str, Any]) -> str:
    pagination = profile.get("pagination")
    if isinstance(pagination, Mapping):
        body = pagination.get("body")
        if isinstance(body, Mapping) and body.get("first_chapter_start"):
            return str(body.get("first_chapter_start"))
    chapter = profile.get("chapter")
    if isinstance(chapter, Mapping) and chapter.get("first_start"):
        return str(chapter.get("first_start"))
    return chapter_start_type_name(profile)


def _mapping(payload: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = payload.get(key)
    if not isinstance(value, Mapping):
        raise WordPrintProfileError(f"profile field {key!r} must be an object")
    return value


__all__ = [
    "WordPrintProfileError",
    "chapter_start_type_name",
    "default_profile_path",
    "first_chapter_start_type_name",
    "front_matter_section_start_name",
    "include_sections_in_toc",
    "load_profile",
    "profiles_dir",
    "style_spec",
    "validate_profile",
]
