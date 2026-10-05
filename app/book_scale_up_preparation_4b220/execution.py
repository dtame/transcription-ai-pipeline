"""Three-level execution plan. This phase prepares, it does not execute."""

from __future__ import annotations

from typing import Any, Mapping

from app.book_scale_up_preparation_4b220.constants import (
    ACCEPTED_CHAPTER,
    EXPECTED_FIRST_CHAPTER_ID,
    FAITHFUL_PROMPT_1_1,
    MODEL,
    PHASE,
    PROVIDER,
    TOTAL_CHAPTER_COUNT,
)


def _batch(name: str, chapter_ids: list[str], note: str) -> dict[str, Any]:
    return {
        "batch_id": name,
        "chapter_ids": chapter_ids,
        "authorized": False,
        "executable_in_this_phase": False,
        "interruptible": True,
        "resume_without_rerunning_completed": True,
        "note": note,
    }


def scale_up_execution_plan(
    *,
    selection: Mapping[str, Any],
    inventory: Mapping[str, Any],
    cost: Mapping[str, Any],
) -> dict[str, Any]:
    first_id = str(selection.get("selected_chapter_id") or EXPECTED_FIRST_CHAPTER_ID)
    remaining = [
        row["chapter_id"]
        for row in inventory.get("chapters") or []
        if row["chapter_id"] != first_id
    ]
    first = dict(cost.get("first_chapter") or {})
    return {
        "phase": PHASE,
        "this_phase_executes": False,
        "levels": {
            "1_first_real_chapter": {
                "chapter_id": first_id,
                "authorized": False,
                "executable_in_this_phase": False,
                "provider": PROVIDER,
                "model": MODEL,
                "prompt_version": FAITHFUL_PROMPT_1_1,
                "post_generation_checks": [
                    "JSON valid",
                    "transport contract respected",
                    "all expected sections present in plan order",
                    "valid identifiers",
                    "SRC provenance",
                    "IDEA provenance in paras[].e when justified",
                    "no invented evidence fields",
                    "metadata consistency",
                    "no truncation",
                    "budget respected",
                    "output stored in an isolated audit space",
                ],
                "blocking_failure": "STOP. No automatic additional call.",
                "calculable_maximum_usd": first.get("calculable_maximum_usd"),
                "central_estimate_is_not_the_cap": True,
            },
            "2_small_batches": {
                "authorized": False,
                "executable_in_this_phase": False,
                "requires_first_chapter_acceptance": True,
                "batches": [
                    _batch(
                        "LOT-A",
                        [item for item in ("CH011", "CH008") if item in remaining],
                        "Similar mid-size chapters with EX and REF after CH018 acceptance.",
                    ),
                    _batch(
                        "LOT-B",
                        [item for item in ("CH007", "CH019") if item in remaining],
                        "Smaller remaining chapters. Still one authorization per chapter.",
                    ),
                    _batch(
                        "LOT-C",
                        [item for item in ("CH001", "CH002", "CH003") if item in remaining],
                        "Opening theological sequence. Do not collapse into one call.",
                    ),
                    _batch(
                        "LOT-D",
                        [item for item in ("CH009", "CH010", "CH014") if item in remaining],
                        "Mid-book practice and anthropology chapters.",
                    ),
                    _batch(
                        "LOT-E",
                        [item for item in ("CH004", "CH005", "CH015", "CH017") if item in remaining],
                        "Larger remaining mid-complexity chapters.",
                    ),
                    _batch(
                        "LOT-F",
                        [item for item in ("CH013", "CH016", "CH006") if item in remaining],
                        "Hardest remaining chapters last. CH006 is 38 ideas / 8 sections.",
                    ),
                ],
            },
            "3_book_assembly": {
                "authorized": False,
                "executable_in_this_phase": False,
                "book_json_created": False,
                "docx_created": False,
                "pdf_created": False,
                "required_chapter_count": TOTAL_CHAPTER_COUNT,
                "must_include": [
                    f"{ACCEPTED_CHAPTER} by reference to the 4B.2.19 accepted editorial manifest",
                    "the 18 remaining chapters only after generation and human acceptance",
                ],
                "must_not_duplicate_ch012_content": True,
            },
        },
        "publication": "not_granted",
        "secrets_included": False,
    }


__all__ = ["scale_up_execution_plan"]
