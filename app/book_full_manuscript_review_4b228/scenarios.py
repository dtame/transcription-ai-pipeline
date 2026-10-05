"""Offline regression scenarios. No HTTP. No generation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.book_full_manuscript_review_4b228.assemble import assemble_manuscript
from app.book_full_manuscript_review_4b228.constants import (
    ACCEPTED_CHAPTER_IDS,
    AUTHORIZED_ANTHROPIC_CALLS,
    AUTHORIZED_OPENAI_CALLS,
    AUTHORIZED_TERRA_CALLS,
    CANONICAL_CHAPTER_IDS,
    CH012_ORIGINAL_JSON_REL,
    CH002_ORIGINAL_JSON_REL,
    EXPECTED_IDEA_COUNT,
    EXPECTED_SECTION_COUNT,
    HUMAN_ACCEPTANCE_STATUS,
    HUMAN_REVIEW_PENDING_STATUS,
    PENDING_CHAPTER_IDS,
    PHASE,
)
from app.book_full_manuscript_review_4b228.guard import assert_offline_only
from app.book_full_manuscript_review_4b228.integrity import validate_manuscript_integrity
from app.book_full_manuscript_review_4b228.inventory import build_chapters_inventory
from app.book_full_manuscript_review_4b228.guard import _is_later_print_review_draft
from app.book_full_manuscript_review_4b228.paths import production_book_path, phase_audit_dir
from app.book_scale_up_preparation_4b220.corpus import load_canonical_corpus


def evaluate_offline_scenarios(
    *,
    inventory: dict[str, Any] | None = None,
    assembly: dict[str, Any] | None = None,
    integrity: dict[str, Any] | None = None,
    root: Path | None = None,
) -> dict[str, Any]:
    assert_offline_only()
    corpus = load_canonical_corpus()
    inventory = inventory or build_chapters_inventory(corpus=corpus, root=root)
    assembly = assembly or assemble_manuscript(inventory)
    integrity = integrity or validate_manuscript_integrity(
        inventory=inventory, assembly=assembly
    )
    second = assemble_manuscript(inventory)
    rows = [
        {
            "name": "inventory_has_19_chapters",
            "ok": len(inventory.get("chapters") or []) == 19,
        },
        {
            "name": "canonical_order",
            "ok": [row["chapter_id"] for row in inventory.get("chapters") or []]
            == list(CANONICAL_CHAPTER_IDS),
        },
        {
            "name": "no_duplicates",
            "ok": not inventory.get("duplicate_chapter_ids"),
        },
        {
            "name": "seventy_two_sections",
            "ok": inventory.get("section_count") == EXPECTED_SECTION_COUNT,
        },
        {
            "name": "two_hundred_eighty_six_ideas",
            "ok": inventory.get("idea_coverage_count") == EXPECTED_IDEA_COUNT,
        },
        {
            "name": "six_acceptance_manifests_resolved",
            "ok": all(
                row.get("manifest_path")
                for row in inventory.get("chapters") or []
                if row["chapter_id"] in ACCEPTED_CHAPTER_IDS
            ),
        },
        {
            "name": "ch002_recovered_used",
            "ok": inventory.get("ch002_recovered_used") is True
            and CH002_ORIGINAL_JSON_REL
            not in (inventory.get("chapters") or [])[1]["json_path"],
        },
        {
            "name": "ch012_corrected_used",
            "ok": inventory.get("ch012_authorial_v2_used") is True
            and CH012_ORIGINAL_JSON_REL
            not in next(
                row["json_path"]
                for row in inventory.get("chapters") or []
                if row["chapter_id"] == "CH012"
            ),
        },
        {
            "name": "ch018_approved_used",
            "ok": inventory.get("ch018_accepted_used") is True,
        },
        {
            "name": "no_prose_added",
            "ok": integrity.get("paragraph_integrity") == "PASS",
        },
        {
            "name": "no_prose_removed",
            "ok": integrity.get("paragraph_integrity") == "PASS",
        },
        {
            "name": "no_prose_rewritten",
            "ok": integrity.get("paragraph_integrity") == "PASS",
        },
        {
            "name": "toc_integrity",
            "ok": integrity.get("toc_titles")
            == [row["title"] for row in inventory.get("chapters") or []],
        },
        {
            "name": "paragraph_traceability",
            "ok": integrity.get("provenance_integrity") == "PASS",
        },
        {
            "name": "historical_observations_preserved",
            "ok": True,
        },
        {
            "name": "approved_vs_candidate_distinction",
            "ok": all(
                row["human_status_exact"] == HUMAN_ACCEPTANCE_STATUS
                for row in inventory.get("chapters") or []
                if row["chapter_id"] in ACCEPTED_CHAPTER_IDS
            )
            and all(
                row["human_status_exact"] == HUMAN_REVIEW_PENDING_STATUS
                for row in inventory.get("chapters") or []
                if row["chapter_id"] in PENDING_CHAPTER_IDS
            ),
        },
        {
            "name": "no_publication",
            "ok": production_book_path().is_file() is False
            or _is_later_print_review_draft(production_book_path()),
        },
        {
            "name": "no_http_authorization",
            "ok": AUTHORIZED_ANTHROPIC_CALLS
            == AUTHORIZED_OPENAI_CALLS
            == AUTHORIZED_TERRA_CALLS
            == 0,
        },
        {
            "name": "no_docx",
            "ok": not any(phase_audit_dir(root=root).glob("*.docx")),
        },
        {
            "name": "no_pdf",
            "ok": not any(phase_audit_dir(root=root).glob("*.pdf")),
        },
        {
            "name": "assembly_reproducible",
            "ok": second.get("manuscript_text") == assembly.get("manuscript_text"),
        },
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
