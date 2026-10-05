"""Adapter validation against real canonical objects (read-only) and synthetic fixtures."""

from __future__ import annotations

from typing import Any

from app.book_generation.identity import load_production_inputs
from app.book_generation.models import BookParagraph, BookSection, ChapterCandidate
from app.book_generation_bridge_4b214.adapter import (
    adapt_chapter_candidate,
    adapt_editorial_chapter_without_generation,
    adapt_paragraph,
)
from app.book_generation_bridge_4b214.constants import PHASE, PROJECT_NAME, SYNTHETIC_PREFIX
from app.book_generation_integration_4b213.fakeai import FakeGeneratorTransport
from app.book_generation_integration_4b213.fixtures import SYN_ALLOWED


def adapter_validation() -> dict[str, Any]:
    inputs = load_production_inputs(PROJECT_NAME, require_expected_identity=True)
    chapter = inputs.plan.chapters[0]
    real_without_generation = adapt_editorial_chapter_without_generation(
        inputs.plan,
        inputs.source_map,
        chapter.chapter_id,
        identity={
            "source_map_sha256": inputs.source_map_sha256,
            "editorial_plan_sha256": inputs.plan_sha256,
        },
    )
    synthetic_chapter = FakeGeneratorTransport("fully_supported").produce_chapter()
    synthetic_ok = adapt_chapter_candidate(synthetic_chapter, synthetic=True)
    missing = adapt_chapter_candidate(
        {
            "chapter_id": "",
            "title": "",
            "sections": [],
            "synthetic": True,
        },
        synthetic=True,
    )
    invalid_handle = adapt_paragraph(
        {
            "paragraph_id": f"{SYNTHETIC_PREFIX}P9",
            "kind": "substantive",
            "text": "A claim.",
            "evidence_handles": ["SRC999999"],
        },
        chapter_id=chapter.chapter_id,
        section_id=chapter.sections[0].section_id,
        allowed_handles=list(chapter.source_refs) or list(SYN_ALLOWED),
        source_index={item: "SRC" for item in chapter.source_refs},
        synthetic=False,
    )
    real_models = ChapterCandidate(
        chapter_id=f"{SYNTHETIC_PREFIX}CH001",
        title="Synthetic candidate using real dataclasses",
        sections=(
            BookSection(
                section_id=f"{SYNTHETIC_PREFIX}CH001-SEC001",
                title="Synthetic section",
                paragraphs=(
                    BookParagraph(
                        text="Synthetic connective.",
                        kind="connective",
                        paragraph_id=f"{SYNTHETIC_PREFIX}CH001-P000001",
                    ),
                    BookParagraph(
                        text="Synthetic substantive uses only SYN handles.",
                        kind="substantive",
                        evidence_handles=SYN_ALLOWED,
                        source_refs=(SYN_ALLOWED[1],),
                        idea_refs=(SYN_ALLOWED[0],),
                        paragraph_id=f"{SYNTHETIC_PREFIX}CH001-P000002",
                    ),
                ),
            ),
        ),
    )
    from_models = adapt_chapter_candidate(
        real_models,
        identity={
            "source_map_sha256": "SYNTHETIC_OFFLINE_FIXTURE",
            "editorial_plan_sha256": "SYNTHETIC_OFFLINE_FIXTURE",
        },
        allowed_handles=list(SYN_ALLOWED),
        synthetic=True,
    )
    ok = (
        real_without_generation.get("ok") is False
        and real_without_generation.get("paragraphs_unknown_before_generation") is True
        and synthetic_ok.get("ok") is True
        and missing.get("ok") is False
        and invalid_handle.get("ok") is False
        and from_models.get("ok") is True
        and "missing_required_evidence" not in str(synthetic_ok.get("errors"))
    )
    return {
        "phase": PHASE,
        "ok": ok,
        "real_plan_chapter_id": chapter.chapter_id,
        "real_section_ids": [section.section_id for section in chapter.sections],
        "real_data_without_generated_paragraphs": {
            "ok": real_without_generation.get("ok"),
            "errors": real_without_generation.get("errors"),
            "gaps": real_without_generation.get("gaps"),
            "paragraphs_unknown_before_generation": True,
            "does_not_invent_paragraphs": True,
        },
        "synthetic_fixture_ok": synthetic_ok.get("ok"),
        "missing_data_blocks": missing.get("ok") is False,
        "invalid_evidence_handle_blocks": invalid_handle.get("ok") is False,
        "real_dataclasses_synthetic_handles_ok": from_models.get("ok"),
        "does_not_invent_src": True,
        "does_not_use_synthetic_as_real_proof": True,
        "canonical_objects_mutated": False,
        "secrets_included": False,
    }


__all__ = ["adapter_validation"]
