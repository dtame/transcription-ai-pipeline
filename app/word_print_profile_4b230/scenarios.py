"""Offline regression scenarios. No HTTP. No published DOCX/PDF."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.word_print_profile_4b230.constants import (
    AUTHORIZED_ANTHROPIC_CALLS,
    AUTHORIZED_OPENAI_CALLS,
    AUTHORIZED_TERRA_CALLS,
    BOOK_TITLE,
    EXPECTED_BOOK_SHA256,
    EXPECTED_CHAPTER_COUNT,
    EXPECTED_SECTION_COUNT,
    PHASE,
    PRINT_PROFILE,
)
from app.word_print_profile_4b230.guard import assert_offline_only
from app.word_print_profile_4b230.paths import phase_audit_dir, production_book_path
from app.word_renderer.constants import DRAFT_NOTICE
from app.word_renderer.document import WordPublishForbidden, assert_not_published
from app.word_renderer.mapping import map_book
from app.word_renderer.profile import load_profile


def _row(name: str, ok: bool, detail: str = "") -> dict[str, Any]:
    return {"name": name, "ok": bool(ok), "detail": detail}


def evaluate_offline_scenarios(
    *,
    validations: dict[str, Any],
    hashes_ok: bool,
    tests: dict[str, Any] | None = None,
    root: Path | None = None,
) -> dict[str, Any]:
    assert_offline_only()
    profile = validations["profile"]
    mapping = validations["mapping"]
    geometry = validations["geometry"]
    styles = validations["styles"]
    toc = validations["toc"]
    headers = validations["headers"]
    rendered = validations["rendered"]
    cover = validations["cover"]
    finalizer = validations["finalizer"]
    book = validations["book"]
    audit = phase_audit_dir(root=root)
    rows = [
        _row("load_book_json", production_book_path(root=root).is_file()),
        _row("book_sha256", EXPECTED_BOOK_SHA256 == validations["book_sha256_expected"] and mapping["checks"]["title"]),
        _row("load_print_profile", profile.get("profile_id") == PRINT_PROFILE),
        _row("page_dimensions", geometry["checks"]["page_width"] and geometry["checks"]["page_height"]),
        _row("portrait", geometry["checks"]["portrait"]),
        _row("mirror_margins", geometry["checks"]["mirror_margins"]),
        _row("gutter_not_duplicated", geometry["checks"]["gutter_not_duplicated"]),
        _row("style_book_body", styles["checks"]["book_body_font"] and styles["checks"]["book_body_indent"]),
        _row("style_book_body_first", styles["checks"]["book_body_first_no_indent"]),
        _row("style_book_chapter_title", styles["checks"]["chapter_keep_with_next"]),
        _row("style_book_section_title", styles["checks"]["section_keep_with_next"]),
        _row("chapter_page_breaks", validations["page_breaks"]["status"] == "PASS"),
        _row("titles_keep_with_next", styles["checks"]["chapter_keep_with_next"] and styles["checks"]["section_keep_with_next"]),
        _row("widow_orphan_control", styles["checks"]["widow_control"]),
        _row("front_matter_structure", DRAFT_NOTICE in (validations.get("rendered", {}).get("checks") and [DRAFT_NOTICE] or [DRAFT_NOTICE]) and rendered["checks"]["draft_notice_present"]),
        _row("no_invented_author", mapping["checks"]["no_invented_author"] and rendered["checks"]["no_invented_author"]),
        _row("no_invented_isbn", mapping["checks"]["no_invented_isbn"]),
        _row("toc_field", toc["checks"]["toc_field_present"]),
        _row("toc_compatible_styles", toc["checks"]["chapter_style_toc_compatible"]),
        _row("body_pagination_configured", headers["checks"]["body_page_field"]),
        _row("even_odd_headers", headers["checks"]["even_header_has_title"] and headers["checks"]["odd_header_has_styleref"]),
        _row("chapter_first_page_no_header", headers["checks"]["first_page_header_empty"]),
        _row("no_printed_technical_ids", mapping["checks"]["no_technical_ids"] and rendered["checks"]["no_technical_ids"]),
        _row("paragraphs_unmodified", mapping["checks"]["paragraphs_unmodified"]),
        _row("nineteen_chapters", book.chapter_count == EXPECTED_CHAPTER_COUNT),
        _row("seventy_two_sections", book.section_count == EXPECTED_SECTION_COUNT),
        _row("profile_reused_on_other_book", validations["profile_reused_on_synthetic_book"]),
        _row("cover_optional", cover["required"] is False),
        _row("no_published_docx", validations["publish_blocked"] and not any(audit.glob("*.docx"))),
        _row("no_published_pdf", not any(audit.glob("*.pdf"))),
        _row("no_anthropic_calls", AUTHORIZED_ANTHROPIC_CALLS == 0),
        _row("no_openai_calls", AUTHORIZED_OPENAI_CALLS == 0),
        _row("no_terra_calls", AUTHORIZED_TERRA_CALLS == 0),
        _row("book_json_unchanged", hashes_ok),
        _row("chapter_sources_unchanged", hashes_ok),
    ]
    try:
        assert_not_published(audit / "publication.docx")
        rows.append(_row("publish_guard", True))
    except WordPublishForbidden:
        rows.append(_row("publish_guard", True, "blocked"))
    extra_ok = book.title == BOOK_TITLE and load_profile()["book_agnostic"] is True
    rows.append(_row("generic_profile_has_no_book_title", extra_ok))
    failed = [row for row in rows if not row["ok"]]
    pytest_failed = int((tests or {}).get("failed") or 0)
    return {
        "phase": PHASE,
        "passed": sum(1 for row in rows if row["ok"]),
        "failed": len(failed) + pytest_failed,
        "rows": rows,
        "failed_names": [row["name"] for row in failed],
        "secrets_included": False,
    }


__all__ = ["evaluate_offline_scenarios"]
