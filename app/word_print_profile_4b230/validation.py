"""Offline validations. In-memory Word objects only. No published DOCX/PDF."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.word_print_profile_4b230.constants import (
    ACCEPTED_CHAPTER_IDS,
    BOOK_STATUS,
    BOOK_TITLE,
    BOOK_VERSION,
    EXPECTED_BOOK_SHA256,
    EXPECTED_CHAPTER_COUNT,
    EXPECTED_HUMAN_ACCEPTED,
    EXPECTED_IDEA_COUNT,
    EXPECTED_SECTION_COUNT,
    EXPECTED_STRUCTURAL,
    PENDING_CHAPTER_IDS,
    PHASE,
    PRINT_PROFILE,
)
from app.word_print_profile_4b230.guard import WordPrintProfile4230Error
from app.word_print_profile_4b230.paths import production_book_path
from app.word_renderer.constants import (
    ABSENT_EDITORIAL_FIELDS,
    DRAFT_NOTICE,
    STYLE_BODY,
    STYLE_BODY_FIRST,
    STYLE_CHAPTER_TITLE,
    STYLE_SECTION_TITLE,
)
from app.word_renderer.cover import cover_contract
from app.word_renderer.document import (
    WordPublishForbidden,
    assert_not_published,
    build_print_document,
    configure_document,
    inspect_document,
)
from app.word_renderer.finalizer import finalizer_readiness
from app.word_renderer.geometry import inspect_geometry
from app.word_renderer.headers import inspect_headers
from app.word_renderer.inventory import renderer_inventory
from app.word_renderer.mapping import (
    find_technical_leaks,
    map_book,
    printed_strings,
    source_paragraph_texts,
    visible_metadata,
)
from app.word_renderer.oxml import field_instructions, iter_paragraph_texts
from app.word_renderer.profile import load_profile
from app.word_renderer.styles import inspect_style


def load_canonical_book(*, root: Path | None = None) -> dict[str, Any]:
    path = production_book_path(root=root)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise WordPrintProfile4230Error("book.json must be an object")
    return payload


def synthetic_book_payload() -> dict[str, Any]:
    return {
        "title": "A Different Synthetic Book",
        "subtitle": "",
        "language": "en",
        "document_version": "synthetic-v1",
        "editorial_status": "DRAFT_FOR_PRINT_REVIEW",
        "absent_editorial_fields": {field: None for field in ABSENT_EDITORIAL_FIELDS},
        "chapters": [
            {
                "order": 1,
                "title": "Opening the Door",
                "sections": [
                    {
                        "order": 1,
                        "title": "A Quiet Threshold",
                        "paragraphs": [
                            {"text": "The first paragraph has no indent."},
                            {"text": "The second paragraph keeps the indent."},
                        ],
                    }
                ],
            },
            {
                "order": 2,
                "title": "Crossing the Room",
                "sections": [
                    {
                        "order": 1,
                        "title": "Another Turning",
                        "paragraphs": [{"text": "A later chapter still uses the same profile."}],
                    }
                ],
            },
        ],
    }


def validate_styles(doc, profile: dict[str, Any]) -> dict[str, Any]:
    snapshots = {
        name: inspect_style(doc, name)
        for name in (STYLE_BODY, STYLE_BODY_FIRST, STYLE_CHAPTER_TITLE, STYLE_SECTION_TITLE)
    }
    body = snapshots[STYLE_BODY]
    first = snapshots[STYLE_BODY_FIRST]
    chapter = snapshots[STYLE_CHAPTER_TITLE]
    section = snapshots[STYLE_SECTION_TITLE]
    checks = {
        "book_body_font": body["font_name"] == "Georgia" and body["font_size_pt"] == 11,
        "book_body_indent": body["first_line_indent_inches"] > 0,
        "book_body_first_no_indent": first["first_line_indent_inches"] == 0,
        "same_body_metrics": (
            first["font_name"] == body["font_name"]
            and first["font_size_pt"] == body["font_size_pt"]
            and first["line_spacing"] == body["line_spacing"]
        ),
        "chapter_keep_with_next": chapter["keep_with_next"] is True,
        "section_keep_with_next": section["keep_with_next"] is True,
        "chapter_outline": chapter["outline_level"] == 0,
        "section_outline": section["outline_level"] == 1,
        "widow_control": all(item["widow_control"] for item in snapshots.values()),
        "body_not_keep_with_next": body["keep_with_next"] is False,
    }
    return {
        "phase": PHASE,
        "status": "PASS" if all(checks.values()) else "FAIL",
        "styles": snapshots,
        "checks": checks,
        "profile_id": profile.get("profile_id"),
        "secrets_included": False,
    }


def validate_geometry(doc, profile: dict[str, Any]) -> dict[str, Any]:
    geometry = inspect_geometry(doc.sections[0], profile)
    settings = field_instructions(doc.settings.element)
    del settings
    mirror = doc.settings.element.find(
        "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}mirrorMargins"
    )
    checks = {
        "page_width": geometry["page_width_matches"],
        "page_height": geometry["page_height_matches"],
        "portrait": geometry["portrait"] and geometry["portrait_enum"],
        "mirror_margins": mirror is not None,
        "gutter_matches": geometry["gutter_matches_profile"],
        "gutter_not_duplicated": geometry["gutter_not_added_to_left_margin"],
    }
    return {
        "phase": PHASE,
        "status": "PASS" if all(checks.values()) else "FAIL",
        "geometry": geometry,
        "gutter_convention": profile.get("gutter_convention"),
        "checks": checks,
        "secrets_included": False,
    }


def validate_toc(doc) -> dict[str, Any]:
    fields = field_instructions(doc.element)
    toc = [item for item in fields if item.startswith("TOC")]
    chapter = inspect_style(doc, STYLE_CHAPTER_TITLE)
    section = inspect_style(doc, STYLE_SECTION_TITLE)
    checks = {
        "toc_field_present": any('TOC \\o "1-1"' in item or 'TOC \\o "1-2"' in item for item in toc),
        "no_estimated_page_numbers": all("PAGEREF" not in item for item in toc),
        "chapter_style_toc_compatible": chapter["outline_level"] == 0,
        "section_style_toc_compatible": section["outline_level"] == 1,
    }
    return {
        "phase": PHASE,
        "status": "PASS" if all(checks.values()) else "FAIL",
        "fields": toc,
        "default_levels": "1-1",
        "include_sections_option": True,
        "requires_word_refresh": True,
        "checks": checks,
        "secrets_included": False,
    }


def validate_headers(doc, book_title: str) -> dict[str, Any]:
    if len(doc.sections) < 2:
        raise WordPrintProfile4230Error("body section missing")
    body = inspect_headers(doc.sections[1])
    front = inspect_headers(doc.sections[0])
    checks = {
        "even_header_has_title": book_title in body["even_header_texts"],
        "odd_header_has_styleref": any("STYLEREF" in item for item in body["odd_header_fields"]),
        "body_page_field": any("PAGE" in item for item in body["footer_fields"]),
        "first_page_header_empty": body["first_page_header_empty"],
        "title_page_has_no_page_field_on_first": not any(
            "PAGE" in item for item in front["first_footer_fields"]
        ),
    }
    return {
        "phase": PHASE,
        "status": "PASS" if all(checks.values()) else "FAIL",
        "body": body,
        "front_matter": front,
        "checks": checks,
        "limitation": (
            "python-docx writes first-page header suppression and STYLEREF. "
            "Rendered even/odd pages are confirmed only after Microsoft Word refreshes fields."
        ),
        "secrets_included": False,
    }


def validate_mapping(payload: dict[str, Any], book) -> dict[str, Any]:
    source_texts = source_paragraph_texts(payload)
    mapped_texts = book.paragraph_texts
    accepted = [
        chapter.get("chapter_id")
        for chapter in payload.get("chapters") or []
        if chapter.get("editorial_status") == "HUMAN_EDITORIALLY_ACCEPTED"
    ]
    structural = [
        chapter.get("chapter_id")
        for chapter in payload.get("chapters") or []
        if chapter.get("editorial_status") == "GENERATED_STRUCTURALLY_VALID"
    ]
    leaks = find_technical_leaks(printed_strings(book))
    metadata = visible_metadata(book)
    checks = {
        "title": book.title == BOOK_TITLE == payload.get("title"),
        "version": book.version == BOOK_VERSION,
        "status": book.status == BOOK_STATUS,
        "chapters": book.chapter_count == EXPECTED_CHAPTER_COUNT,
        "sections": book.section_count == EXPECTED_SECTION_COUNT,
        "paragraphs_unmodified": source_texts == mapped_texts,
        "human_accepted": accepted == list(ACCEPTED_CHAPTER_IDS),
        "structural": structural == list(PENDING_CHAPTER_IDS),
        "no_technical_ids": not leaks,
        "no_invented_author": metadata["author"] is None,
        "no_invented_isbn": metadata["isbn"] is None,
        "idea_coverage": int(payload.get("idea_coverage_count") or 0) == EXPECTED_IDEA_COUNT,
        "orders_used": [chapter.order for chapter in book.chapters]
        == list(range(1, EXPECTED_CHAPTER_COUNT + 1)),
        "titles_not_prefixed": all(
            not chapter.title.startswith(f"{chapter.order}")
            and not chapter.title.lower().startswith("chapter ")
            for chapter in book.chapters
        ),
    }
    return {
        "phase": PHASE,
        "status": "PASS" if all(checks.values()) else "FAIL",
        "title": book.title,
        "chapter_count": book.chapter_count,
        "section_count": book.section_count,
        "paragraph_count": len(mapped_texts),
        "human_accepted_chapters": accepted,
        "structural_chapters": structural,
        "technical_leaks": list(leaks),
        "visible_metadata": metadata,
        "checks": checks,
        "secrets_included": False,
    }


def validate_rendered_texts(doc, book) -> dict[str, Any]:
    texts = iter_paragraph_texts(doc.element)
    joined = "\n".join(texts)
    leaks = find_technical_leaks(texts)
    invented_author = "TranscriptionAI" in joined or "PublishForge" in joined
    checks = {
        "no_technical_ids": not leaks,
        "no_invented_author": not invented_author and "ISBN" not in joined,
        "draft_notice_present": DRAFT_NOTICE in texts,
        "draft_notice_not_in_body_styles": all(
            paragraph.text != DRAFT_NOTICE
            for paragraph in doc.paragraphs
            if paragraph.style.name in {STYLE_BODY, STYLE_BODY_FIRST}
        ),
        "chapter_titles_present": all(
            chapter.title in texts for chapter in book.chapters
        ),
        "section_titles_present": all(
            section.title in texts
            for chapter in book.chapters
            for section in chapter.sections
        ),
        "paragraphs_present": all(text in joined for text in book.paragraph_texts),
    }
    return {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "technical_leaks": list(leaks),
        "checks": checks,
    }


def build_validations(*, root: Path | None = None) -> dict[str, Any]:
    payload = load_canonical_book(root=root)
    profile = load_profile()
    book = map_book(payload)
    configured = configure_document(profile)
    synthetic = map_book(synthetic_book_payload())
    preview = build_print_document(synthetic, profile, include_sections=False)
    reused = build_print_document(synthetic, profile, include_sections=True)
    styles = validate_styles(configured, profile)
    geometry = validate_geometry(configured, profile)
    toc = validate_toc(preview)
    headers = validate_headers(preview, synthetic.title)
    mapping = validate_mapping(payload, book)
    rendered = validate_rendered_texts(preview, synthetic)
    reused_ok = reused.core_properties.title == synthetic.title
    cover = cover_contract(profile)
    finalizer = finalizer_readiness()
    inventory = renderer_inventory()
    body_starts = inspect_document(preview, profile)
    publish_blocked = False
    try:
        assert_not_published(Path("audit/word_print_profile_4b230/book.docx"))
    except WordPublishForbidden:
        publish_blocked = True
    policy = str(
        ((profile.get("pagination") or {}).get("body") or {}).get("chapter_start")
        or (profile.get("chapter") or {}).get("start")
        or ""
    )
    if policy in {"next_page", "new_page"}:
        limitation = (
            "NEW_PAGE/next_page section breaks are written for chapter starts. "
            "Front-matter sections keep their existing start type. This phase "
            "does not insert empty paragraphs to fake page breaks."
        )
    else:
        limitation = (
            "ODD_PAGE section breaks are written. Word, not python-docx, "
            "materializes any intervening blank verso. This phase does not "
            "insert empty paragraphs to fake page breaks."
        )
    page_breaks = {
        "status": "PASS" if body_starts.get("odd_or_new_page_starts") else "FAIL",
        "start_types": body_starts.get("body_start_types"),
        "policy": policy,
        "limitation": limitation,
    }
    ready = all(
        (
            styles["status"] == "PASS",
            geometry["status"] == "PASS",
            toc["status"] == "PASS",
            headers["status"] == "PASS",
            mapping["status"] == "PASS",
            rendered["status"] == "PASS",
            reused_ok,
            publish_blocked,
            cover["status"] == "OPTIONAL",
            finalizer["executed"] is False,
        )
    )
    return {
        "payload": payload,
        "profile": profile,
        "book": book,
        "inventory": inventory,
        "styles": styles,
        "geometry": geometry,
        "toc": toc,
        "headers": headers,
        "mapping": mapping,
        "rendered": rendered,
        "cover": cover,
        "finalizer": finalizer,
        "page_breaks": page_breaks,
        "profile_reused_on_synthetic_book": reused_ok,
        "publish_blocked": publish_blocked,
        "ready": ready,
        "book_sha256_expected": EXPECTED_BOOK_SHA256,
        "print_profile": PRINT_PROFILE,
    }


__all__ = [
    "build_validations",
    "load_canonical_book",
    "synthetic_book_payload",
]
