"""Validate book.json against the existing 1.0 Book contract plus 4B.2.29 fields."""

from __future__ import annotations

from typing import Any

from app.book_generation.models import Book, scan_forbidden_book_structure
from app.book_generation.validator import validate_book_precheck
from app.book_print_review_canonical_4b229.constants import (
    ABSENT_EDITORIAL_FIELDS,
    BOOK_LANGUAGE,
    BOOK_STATUS,
    BOOK_TITLE,
    BOOK_VERSION,
    CANONICAL_CHAPTER_IDS,
    EXPECTED_IDEA_COUNT,
    EXPECTED_SECTION_COUNT,
    HUMAN_ACCEPTED_STATUS,
    PHASE,
    PROJECT_NAME,
    SCHEMA_VERSION,
    STRUCTURAL_STATUS,
    TITLE_STATUS,
)
from app.book_scale_up_preparation_4b220.corpus import CanonicalCorpus


def validate_book_schema(
    payload: dict[str, Any],
    *,
    corpus: CanonicalCorpus,
) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    leaked = scan_forbidden_book_structure(payload)
    if leaked:
        errors.extend(f"forbidden layout/technical field: {name}" for name in leaked)
    if payload.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version {payload.get('schema_version')!r} ≠ {SCHEMA_VERSION}")
    if (payload.get("project") or {}).get("name") != PROJECT_NAME:
        errors.append("project name mismatch")
    if payload.get("language") != BOOK_LANGUAGE:
        errors.append(f"language {payload.get('language')!r} ≠ {BOOK_LANGUAGE}")
    if payload.get("title") != BOOK_TITLE:
        errors.append(f"title {payload.get('title')!r} ≠ {BOOK_TITLE}")
    if payload.get("title_status") != TITLE_STATUS:
        errors.append("title_status must remain working")
    if payload.get("editorial_status") != BOOK_STATUS:
        errors.append(f"editorial_status {payload.get('editorial_status')!r} ≠ {BOOK_STATUS}")
    if payload.get("document_version") != BOOK_VERSION:
        errors.append(f"document_version {payload.get('document_version')!r} ≠ {BOOK_VERSION}")
    if payload.get("phase") != PHASE:
        errors.append("phase identifier mismatch")
    if payload.get("front_matter"):
        errors.append("front_matter must remain empty")
    if payload.get("back_matter"):
        errors.append("back_matter must remain empty")
    absent = payload.get("absent_editorial_fields") or {}
    for field in ABSENT_EDITORIAL_FIELDS:
        if field in payload and payload.get(field) not in (None, "", [], {}):
            errors.append(f"invented editorial field {field}")
        if field in absent and absent.get(field) not in (None, ""):
            errors.append(f"absent field {field} is not empty")
    book = Book.from_dict(payload)
    precheck = validate_book_precheck(
        book,
        corpus.plan,
        corpus.source_map,
        language=corpus.language,
    )
    errors.extend(precheck.errors)
    warnings.extend(precheck.warnings)
    chapters = list(payload.get("chapters") or [])
    ids = [str(chapter.get("chapter_id") or "") for chapter in chapters]
    if ids != list(CANONICAL_CHAPTER_IDS):
        errors.append(f"chapter order {ids} ≠ {list(CANONICAL_CHAPTER_IDS)}")
    orders = [int(chapter.get("order") or 0) for chapter in chapters]
    if orders != list(range(1, 20)):
        errors.append(f"chapter order numbers {orders} are not 1..19")
    section_count = sum(len(chapter.get("sections") or []) for chapter in chapters)
    if section_count != EXPECTED_SECTION_COUNT:
        errors.append(f"section count {section_count} ≠ {EXPECTED_SECTION_COUNT}")
    if int(payload.get("chapter_count") or 0) != 19:
        errors.append("chapter_count metadata mismatch")
    if int(payload.get("section_count") or 0) != EXPECTED_SECTION_COUNT:
        errors.append("section_count metadata mismatch")
    if int(payload.get("idea_coverage_count") or 0) != EXPECTED_IDEA_COUNT:
        errors.append("idea_coverage_count metadata mismatch")
    statuses = {HUMAN_ACCEPTED_STATUS, STRUCTURAL_STATUS}
    for chapter in chapters:
        if chapter.get("editorial_status") not in statuses:
            errors.append(
                f"{chapter.get('chapter_id')} editorial_status "
                f"{chapter.get('editorial_status')!r} is invalid"
            )
        if chapter.get("editorial_status") == BOOK_STATUS:
            errors.append(
                f"{chapter.get('chapter_id')} chapter status was overwritten by the book status"
            )
    status = "PASS" if not errors else "FAIL"
    if status == "PASS" and (warnings or precheck.status == "REVIEW"):
        status = "REVIEW"
    return {
        "status": status,
        "errors": errors,
        "warnings": list(warnings),
        "book_from_dict_ok": True,
        "precheck_status": precheck.status,
        "schema_version": SCHEMA_VERSION,
        "compatible_with_book_1_0": not errors,
        "secrets_included": False,
    }


__all__ = ["validate_book_schema"]
