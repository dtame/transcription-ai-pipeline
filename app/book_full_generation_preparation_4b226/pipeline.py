"""
Narrow generation-pipeline hook.

Order: durable raw response already saved → normalize derived candidate →
existing production validator. The validator remains the authority.
Accepted chapters are never rewritten here.
"""

from __future__ import annotations

from typing import Any, Mapping

from app.book_ch002_offline_recovery_4b224.chapter_io import (
    candidate_from_dict,
    idea_handles,
)
from app.book_full_generation_preparation_4b226.constants import (
    ACCEPTED_CHAPTER_IDS,
    PHASE,
    VALIDATOR_VERSION,
)
from app.book_full_generation_preparation_4b226.normalize import (
    normalize_empty_paragraphs_idempotent,
)
from app.book_generation.validator import validate_chapter_candidate
from app.book_generation_4b223.inventory import ChapterSpec
from app.book_generation_4b223.validation import structural_validation
from app.editorial_planning.models import EditorialChapter, EditorialPlan
from app.source_analysis.models import SourceMap


def normalize_then_validate(
    chapter: Mapping[str, Any],
    *,
    plan: EditorialPlan,
    source_map: SourceMap,
    editorial_chapter: EditorialChapter,
    spec: ChapterSpec,
    allowed_handles: list[str],
    language: str,
    raw_response: Mapping[str, Any] | None = None,
    finish_reason: str | None = None,
    max_output_tokens: int | None = None,
    protect_accepted: bool = True,
) -> dict[str, Any]:
    chapter_id = str(chapter.get("chapter_id") or spec.chapter_id)
    protected = protect_accepted and chapter_id in ACCEPTED_CHAPTER_IDS
    normalization = normalize_empty_paragraphs_idempotent(
        chapter,
        raw_response=raw_response,
        protect_accepted=protect_accepted,
    )
    derived = normalization["derived"]
    candidate = candidate_from_dict(dict(derived))
    production = validate_chapter_candidate(
        candidate,
        plan,
        source_map,
        editorial_chapter,
        language=language,
        allowed_handles=allowed_handles,
    )
    interpreted = {
        "json_valid": True,
        "transport_ok": True,
        "candidate": candidate,
        "validation": production.to_dict(),
        "raw_idea_handles_in_paras_e": sorted(set(idea_handles(dict(derived)))),
    }
    structural = structural_validation(
        interpreted=interpreted,
        plan=plan,
        chapter=editorial_chapter,
        spec=spec,
        allowed_handles=allowed_handles,
        other_chapter_ids=[
            item.chapter_id for item in plan.chapters if item.chapter_id != chapter_id
        ],
        finish_reason=finish_reason,
        max_output_tokens=max_output_tokens,
    )
    validator_pass = (
        structural.get("status") == "PASS" and production.status != "FAIL"
    )
    if normalization["changed"] and not validator_pass:
        candidate_status = "REJECTED"
        note = (
            "Empty-paragraph normalization produced a derived object, but the "
            "existing validator rejected the candidate. The raw response is "
            "unchanged. A structural failure is not converted into a pass."
        )
    elif protected:
        candidate_status = "ACCEPTED_CHAPTER_UNCHANGED"
        note = "Accepted chapter was not rewritten."
    elif validator_pass:
        candidate_status = "STRUCTURALLY_VALID_DERIVED"
        note = "Derived candidate passed the existing production validator."
    else:
        candidate_status = "REJECTED"
        note = "Existing validator rejected the candidate."
    return {
        "phase": PHASE,
        "chapter_id": chapter_id,
        "integration_point": (
            "after_raw_response_save_before_structural_validation_of_derived_candidate"
        ),
        "production_validator_version": VALIDATOR_VERSION,
        "production_validator_modified": False,
        "validator_executed_after_normalization": True,
        "normalization": {
            "changed": normalization["changed"],
            "removed_paragraph_ids": normalization["removed_paragraph_ids"],
            "refused": normalization["refused"],
            "ids_renumbered": normalization["ids_renumbered"],
            "other_paragraphs_modified": normalization["other_paragraphs_modified"],
            "prose_rewritten": normalization["prose_rewritten"],
            "raw_response_unchanged": normalization["raw_response_unchanged"],
            "idea_coverage_unchanged": normalization["idea_coverage_unchanged"],
            "idempotent": normalization.get("idempotent"),
            "accepted_chapter_protected": normalization.get(
                "accepted_chapter_protected"
            ),
        },
        "derived": derived,
        "production_validator": production.to_dict(),
        "structural_validation": structural,
        "candidate_status": candidate_status,
        "validator_pass": validator_pass,
        "note": note,
        "secrets_included": False,
    }


__all__ = ["normalize_then_validate"]
