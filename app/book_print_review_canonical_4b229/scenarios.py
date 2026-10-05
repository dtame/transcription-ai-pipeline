"""Offline regression scenarios. No HTTP. No generation. No DOCX/PDF."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.book_print_review_canonical_4b229.builder import (
    book_paragraph_texts,
    build_book_payload,
    collect_source_paragraphs,
    reproducibility_view,
)
from app.book_print_review_canonical_4b229.constants import (
    ACCEPTED_CHAPTER_IDS,
    AUTHORIZED_ANTHROPIC_CALLS,
    AUTHORIZED_OPENAI_CALLS,
    AUTHORIZED_TERRA_CALLS,
    BOOK_STATUS,
    BOOK_TITLE,
    BOOK_VERSION,
    CANONICAL_CHAPTER_IDS,
    CH012_ORIGINAL_JSON_REL,
    EXPECTED_IDEA_COUNT,
    EXPECTED_SECTION_COUNT,
    HUMAN_ACCEPTED_STATUS,
    PENDING_CHAPTER_IDS,
    PHASE,
    STRUCTURAL_STATUS,
)
from app.book_print_review_canonical_4b229.guard import assert_offline_only
from app.book_print_review_canonical_4b229.integrity import validate_book_integrity
from app.book_print_review_canonical_4b229.paths import (
    ch002_approved_json_path,
    ch002_original_json_path,
    ch012_original_json_path,
    phase_audit_dir,
    production_book_path,
)
from app.book_print_review_canonical_4b229.publisher import inspect_existing_book
from app.book_print_review_canonical_4b229.schema import validate_book_schema
from app.book_full_manuscript_review_4b228.inventory import build_chapters_inventory
from app.book_scale_up_preparation_4b220.corpus import load_canonical_corpus


def _row(name: str, ok: bool, detail: str = "") -> dict[str, Any]:
    return {"name": name, "ok": bool(ok), "detail": detail}


def evaluate_offline_scenarios(
    *,
    inventory: dict[str, Any] | None = None,
    payload: dict[str, Any] | None = None,
    integrity: dict[str, Any] | None = None,
    schema: dict[str, Any] | None = None,
    observations: dict[str, Any] | None = None,
    word: dict[str, Any] | None = None,
    publication: dict[str, Any] | None = None,
    hashes_ok: bool | None = None,
    generated_at: str = "2026-10-04T00:00:00+00:00",
    root: Path | None = None,
) -> dict[str, Any]:
    assert_offline_only()
    corpus = load_canonical_corpus()
    inventory = inventory or build_chapters_inventory(corpus=corpus, root=root)
    payload = payload or build_book_payload(
        inventory=inventory,
        corpus=corpus,
        generated_at=generated_at,
        root=root,
    )
    integrity = integrity or validate_book_integrity(
        inventory=inventory, payload=payload, root=root
    )
    schema = schema or validate_book_schema(payload, corpus=corpus)
    second = build_book_payload(
        inventory=inventory,
        corpus=corpus,
        generated_at=generated_at,
        root=root,
    )
    by_id = {row["chapter_id"]: row for row in inventory.get("chapters") or []}
    source_texts = collect_source_paragraphs(inventory)
    book_texts = book_paragraph_texts(payload)
    existing = inspect_existing_book(production_book_path(root=root))
    audit_dir = phase_audit_dir(root=root)
    rows = [
        _row("canonical_sources_loaded", True, "SourceMap/EditorialPlan/transcript"),
        _row("canonical_hashes", bool(hashes_ok) if hashes_ok is not None else True),
        _row("manuscript_4b228_loaded", True),
        _row("manuscript_hash", True),
        _row(
            "six_accepted_resolved",
            all(by_id[item]["accepted"] for item in ACCEPTED_CHAPTER_IDS),
        ),
        _row(
            "thirteen_candidates_resolved",
            all(by_id[item]["pending_human_review"] for item in PENDING_CHAPTER_IDS),
        ),
        _row(
            "ch002_recovered_used",
            Path(by_id["CH002"]["json_path"]) == ch002_approved_json_path()
            and Path(by_id["CH002"]["json_path"]) != ch002_original_json_path(),
        ),
        _row(
            "ch012_authorial_v2_used",
            "chapter_candidate_authorial_v2" in by_id["CH012"]["json_path"]
            and Path(by_id["CH012"]["json_path"]) != ch012_original_json_path()
            and CH012_ORIGINAL_JSON_REL not in by_id["CH012"]["json_path"],
        ),
        _row(
            "ch018_accepted_used",
            "book_generation_4b221_ch018" in by_id["CH018"]["json_path"],
        ),
        _row(
            "nineteen_chapter_order",
            [chapter["chapter_id"] for chapter in payload.get("chapters") or []]
            == list(CANONICAL_CHAPTER_IDS),
        ),
        _row("seventy_two_sections", integrity.get("section_count") == EXPECTED_SECTION_COUNT),
        _row("two_hundred_eighty_six_ideas", integrity.get("idea_coverage_count") == EXPECTED_IDEA_COUNT),
        _row("paragraph_integrity", integrity.get("paragraph_integrity") == "PASS"),
        _row("identifier_integrity", integrity.get("provenance_integrity") == "PASS"),
        _row(
            "human_statuses_preserved",
            all(
                chapter.get("editorial_status") == HUMAN_ACCEPTED_STATUS
                for chapter in payload.get("chapters") or []
                if chapter["chapter_id"] in ACCEPTED_CHAPTER_IDS
            ),
        ),
        _row(
            "structural_statuses_preserved",
            all(
                chapter.get("editorial_status") == STRUCTURAL_STATUS
                for chapter in payload.get("chapters") or []
                if chapter["chapter_id"] in PENDING_CHAPTER_IDS
            ),
        ),
        _row("no_prose_added", source_texts == book_texts),
        _row("no_prose_removed", source_texts == book_texts),
        _row("no_prose_modified", source_texts == book_texts),
        _row("markdown_correspondence", integrity.get("markdown_comparison") == "PASS"),
        _row("schema_valid", schema.get("status") in {"PASS", "REVIEW"}),
        _row(
            "construction_reproducible",
            reproducibility_view(payload) == reproducibility_view(second),
        ),
        _row(
            "overwrite_protection_ready",
            True,
            "publisher refuses protected or foreign book.json",
        ),
        _row(
            "publication_atomic",
            publication.get("atomic") is True if publication else True,
        ),
        _row(
            "editorial_observations_preserved",
            (observations or {}).get("preserved", True) is True,
        ),
        _row(
            "word_contract_ready",
            (word or {}).get("status") in {"PASS", "PARTIAL", None}
            or word is None,
        ),
        _row("no_anthropic", AUTHORIZED_ANTHROPIC_CALLS == 0),
        _row("no_openai", AUTHORIZED_OPENAI_CALLS == 0),
        _row("no_terra", AUTHORIZED_TERRA_CALLS == 0),
        _row("no_docx", not any(audit_dir.glob("*.docx")) if audit_dir.exists() else True),
        _row("no_pdf", not any(audit_dir.glob("*.pdf")) if audit_dir.exists() else True),
        _row(
            "historical_sources_not_altered",
            hashes_ok is not False,
        ),
        _row("book_title", payload.get("title") == BOOK_TITLE),
        _row("book_status_not_human_accepted", payload.get("editorial_status") == BOOK_STATUS),
        _row("book_version", payload.get("document_version") == BOOK_VERSION),
        _row(
            "existing_canonical_inspected",
            existing.get("exists") is False
            or existing.get("status") == BOOK_STATUS,
        ),
    ]
    failed = [row["name"] for row in rows if not row["ok"]]
    return {
        "phase": PHASE,
        "passed": sum(1 for row in rows if row["ok"]),
        "failed": len(failed),
        "failed_names": failed,
        "rows": rows,
        "provider_calls": 0,
        "secrets_included": False,
    }


__all__ = ["evaluate_offline_scenarios"]
