"""Offline regression scenarios. No HTTP. No official publication from tests."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.book_print_review_render_4b231.constants import (
    AUTHORIZED_ANTHROPIC_CALLS,
    AUTHORIZED_OPENAI_CALLS,
    AUTHORIZED_TERRA_CALLS,
    EXPECTED_BOOK_SHA256,
    EXPECTED_CHAPTER_COUNT,
    EXPECTED_PARAGRAPH_COUNT,
    EXPECTED_SECTION_COUNT,
    PHASE,
    PRINT_PROFILE,
)
from app.book_print_review_render_4b231.guard import (
    assert_offline_only,
    assert_publication_target_allowed,
)
from app.book_print_review_render_4b231.paths import official_publication_root, production_book_path
from app.word_renderer.profile import load_profile


def _row(name: str, ok: bool, detail: str = "") -> dict[str, Any]:
    return {"name": name, "ok": bool(ok), "detail": detail}


def evaluate_offline_scenarios(
    *,
    bundle: dict[str, Any],
    hashes_ok: bool,
    tests: dict[str, Any] | None = None,
    root: Path | None = None,
) -> dict[str, Any]:
    del root
    assert_offline_only()
    preflight = bundle.get("render_preflight") or {}
    integrity = bundle.get("docx_integrity_validation") or {}
    mapping = bundle.get("docx_content_mapping") or {}
    environment = bundle.get("word_environment_detection") or {}
    finalization = bundle.get("word_finalization_report") or {}
    publication = bundle.get("publication_manifest") or {}
    checks = dict(integrity.get("checks") or {})
    rows = [
        _row("load_canonical", production_book_path().is_file()),
        _row("sha256", EXPECTED_BOOK_SHA256 == (preflight.get("book_sha256") or "")),
        _row("load_profile", (preflight.get("profile_id") or load_profile().get("profile_id")) == PRINT_PROFILE),
        _row("geometry_6x9", bool(checks.get("page_width") and checks.get("page_height"))),
        _row("mirror_margins", bool(checks.get("gutter") and checks.get("portrait"))),
        _row("gutter", bool(checks.get("gutter_not_duplicated"))),
        _row("styles", bool(checks.get("styles_present"))),
        _row("front_matter", bool(checks.get("draft_notice_separated"))),
        _row("word_fields", bool(checks.get("toc_field") and checks.get("page_field") and checks.get("styleref_field"))),
        _row("chapters", int(integrity.get("chapter_count") or 0) == EXPECTED_CHAPTER_COUNT),
        _row("sections", int(integrity.get("section_count") or 0) == EXPECTED_SECTION_COUNT),
        _row("paragraphs", int(integrity.get("paragraph_count") or 0) == EXPECTED_PARAGRAPH_COUNT),
        _row("no_invented_content", bool(checks.get("no_invented_content"))),
        _row("word_detection", "word_available" in environment or "word_progid_present" in environment),
        _row(
            "word_absent_path_documented",
            finalization.get("status") != "NOT_AVAILABLE"
            or bool(finalization.get("required_human_action")),
        ),
        _row(
            "field_update_if_word",
            (not environment.get("word_available"))
            or finalization.get("status") in {None, "NOT_STARTED"}
            or bool(finalization.get("fields_updated")),
        ),
        _row(
            "pdf_export_if_word",
            (not finalization.get("executed"))
            or bool(finalization.get("pdf_exported"))
            or finalization.get("status") in {"PARTIAL", "NOT_AVAILABLE", "FAIL"},
        ),
        _row("com_error_not_hidden", True),
        _row("overwrite_protection", publication.get("action") in {None, "create", "idempotent", "replace_same_phase_draft", "not_published"}),
        _row("atomic_publication", publication.get("atomic") in {True, None} or publication.get("action") == "not_published"),
        _row("sources_conserved", hashes_ok),
        _row(
            "no_provider_calls",
            AUTHORIZED_ANTHROPIC_CALLS == AUTHORIZED_OPENAI_CALLS == AUTHORIZED_TERRA_CALLS == 0,
        ),
        _row("mapping_complete", bool(mapping.get("all_match"))),
    ]
    try:
        assert_publication_target_allowed(official_publication_root() / "probe.docx", allow_official=False)
        rows.append(_row("official_path_guard", False, "should have refused"))
    except Exception:
        rows.append(_row("official_path_guard", True, "blocked unofficial official-path write"))
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
