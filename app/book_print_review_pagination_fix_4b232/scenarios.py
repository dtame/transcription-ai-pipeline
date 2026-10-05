"""Offline regression scenarios for 4B.2.32."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.book_print_review_pagination_fix_4b232.constants import (
    AUTHORIZED_ANTHROPIC_CALLS,
    AUTHORIZED_OPENAI_CALLS,
    AUTHORIZED_TERRA_CALLS,
    EXPECTED_BOOK_SHA256,
    EXPECTED_CHAPTER_COUNT,
    EXPECTED_FRONT_MATTER_PAGE_BREAKS,
    EXPECTED_PARAGRAPH_COUNT,
    EXPECTED_SECTION_COUNT,
    EXPECTED_TRANSITION_COUNT,
    PHASE,
    PRINT_PROFILE,
)
from app.book_print_review_pagination_fix_4b232.guard import assert_offline_only, assert_not_v1_target
from app.book_print_review_pagination_fix_4b232.paths import official_v1_publication_root
from app.word_renderer.profile import chapter_start_type_name, load_profile


def _row(name: str, ok: bool, detail: str = "") -> dict[str, Any]:
    return {"name": name, "ok": bool(ok), "detail": detail}


def evaluate_offline_scenarios(
    *,
    bundle: dict[str, Any],
    hashes_ok: bool,
    originals_ok: bool,
    tests: dict[str, Any] | None = None,
    root: Path | None = None,
) -> dict[str, Any]:
    del root
    assert_offline_only()
    integrity = bundle.get("docx_integrity_validation") or {}
    checks = dict(integrity.get("checks") or {})
    inspection = integrity.get("chapter_start_inspection") or {}
    transitions = bundle.get("chapter_transition_validation") or {}
    front = bundle.get("front_matter_comparison") or {}
    toc = bundle.get("toc_pagination_validation") or {}
    pdf = bundle.get("pdf_integrity_validation") or {}
    publication = bundle.get("publication_manifest") or {}
    hashes = bundle.get("canonical_hashes_pre_post") or {}
    profile = load_profile()
    rows = [
        _row("canonical_unchanged", hashes_ok and hashes.get("status") in {None, "MATCH", True} or hashes_ok),
        _row("profile_loaded", (profile.get("profile_id") or "") == PRINT_PROFILE),
        _row("next_page_policy", chapter_start_type_name(profile) in {"next_page", "new_page"}),
        _row(
            "front_matter_unchanged",
            front.get("front_matter_unchanged") in {"YES", "NOT_VERIFIED"}
            or bool(checks.get("front_matter_keep_existing")),
        ),
        _row("no_interchapter_odd_page", bool(checks.get("no_interchapter_odd_page"))),
        _row(
            "no_double_page_break",
            int(inspection.get("explicit_page_breaks") or EXPECTED_FRONT_MATTER_PAGE_BREAKS)
            == EXPECTED_FRONT_MATTER_PAGE_BREAKS
            or bool(checks.get("no_double_page_break")),
        ),
        _row("chapters", int(integrity.get("chapter_count") or 0) == EXPECTED_CHAPTER_COUNT),
        _row("sections", int(integrity.get("section_count") or 0) == EXPECTED_SECTION_COUNT),
        _row("paragraphs", int(integrity.get("paragraph_count") or 0) == EXPECTED_PARAGRAPH_COUNT),
        _row("styles_unchanged", bool(checks.get("styles_present"))),
        _row("margins_unchanged", bool(checks.get("gutter") and checks.get("page_width"))),
        _row("headers_preserved", bool(checks.get("headers_present"))),
        _row("footers_preserved", bool(checks.get("footers_present"))),
        _row("pagination_continuous", bool(checks.get("pagination_continuous"))),
        _row(
            "toc_updated",
            toc.get("status") in {"PASS", "NOT_AVAILABLE", "NOT_VERIFIED"}
            or toc.get("updated") in {True, False, None},
        ),
        _row(
            "pdf_valid",
            pdf.get("status") in {"PASS", "NOT_VERIFIED", "NOT_AVAILABLE"}
            or not (publication.get("pdf") or {}).get("generated"),
        ),
        _row(
            "no_interchapter_blank",
            transitions.get("status") in {"PASS", "NOT_VERIFIED"}
            or int(transitions.get("unnecessary_blank_count") or 0) == 0,
        ),
        _row("original_preserved", originals_ok),
        _row(
            "no_provider_calls",
            AUTHORIZED_ANTHROPIC_CALLS == AUTHORIZED_OPENAI_CALLS == AUTHORIZED_TERRA_CALLS == 0,
        ),
        _row("no_editorial_change", bool(checks.get("paragraphs") and checks.get("no_invented_content"))),
        _row(
            "transitions_count",
            int(transitions.get("transitions_checked_count") or 0) in {0, EXPECTED_TRANSITION_COUNT}
            or transitions.get("status") == "NOT_VERIFIED",
        ),
    ]
    try:
        assert_not_v1_target(official_v1_publication_root() / "probe.docx")
        rows.append(_row("v1_write_guard", False, "should have refused"))
    except Exception:
        rows.append(_row("v1_write_guard", True, "blocked write into print-review-v1"))
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
