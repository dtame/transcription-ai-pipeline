"""Load CH003 and CH004 specs from the 4B.2.22 inventory and EditorialPlan."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.book_generation_4b223.inventory import (
    ChapterSpec,
    chapter_from_plan,
    chapter_spec,
    load_preparation,
)
from app.book_generation_4b225.constants import (
    AUTHORIZED_CHAPTER_IDS,
    BATCH_ID,
    FORBIDDEN_CHAPTER_IDS,
    LOCK_CONSUMED_STATES,
    PHASE,
)
from app.book_generation_4b225.guard import BookGeneration4225Error
from app.book_generation_4b225.paths import (
    ch003_historical_lock_path,
    ch004_historical_lock_path,
    resume_plan_path,
)
from app.book_scale_up_preparation_4b220.corpus import CanonicalCorpus, load_canonical_corpus


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise BookGeneration4225Error(f"Required resume artifact missing: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise BookGeneration4225Error(f"Resume artifact is not an object: {path}")
    return payload


def load_resume_plan() -> dict[str, Any]:
    plan = _load_json(resume_plan_path())
    resume = tuple(plan.get("resume_chapters") or ())
    if resume != AUTHORIZED_CHAPTER_IDS:
        raise BookGeneration4225Error(
            f"Resume plan chapters {resume} ≠ {AUTHORIZED_CHAPTER_IDS}."
        )
    if plan.get("previous_authorization_reusable") is True:
        raise BookGeneration4225Error("4B.2.23 authorization is not reusable.")
    return plan


def inspect_historical_resume_locks() -> dict[str, Any]:
    rows = {}
    for chapter_id, path in (
        ("CH003", ch003_historical_lock_path()),
        ("CH004", ch004_historical_lock_path()),
    ):
        payload = _load_json(path)
        state = str(payload.get("state") or "")
        consumed = bool(payload.get("consumed")) or state in LOCK_CONSUMED_STATES
        if consumed or state in LOCK_CONSUMED_STATES:
            raise BookGeneration4225Error(
                f"{chapter_id} historical lock is {state} / consumed={consumed}. "
                "STOP. Do not bypass the lock."
            )
        if state != "PREFLIGHT_VALIDATED":
            raise BookGeneration4225Error(
                f"{chapter_id} historical lock is {state!r}, expected "
                "PREFLIGHT_VALIDATED. STOP."
            )
        rows[chapter_id] = {
            "path": str(path).replace("\\", "/"),
            "state": state,
            "consumed": False,
            "call_consumed": False,
        }
    return rows


def load_resume_specs(
    *,
    corpus: CanonicalCorpus | None = None,
    root: Path | None = None,
) -> dict[str, Any]:
    del root
    corpus = corpus or load_canonical_corpus()
    preparation = load_preparation()
    resume_plan = load_resume_plan()
    historical_locks = inspect_historical_resume_locks()
    specs = [
        chapter_spec(chapter_id, corpus=corpus, preparation=preparation)
        for chapter_id in AUTHORIZED_CHAPTER_IDS
    ]
    if any(spec.chapter_id in FORBIDDEN_CHAPTER_IDS for spec in specs):
        raise BookGeneration4225Error("Accepted chapters leaked into the resume lot.")
    if [spec.chapter_id for spec in specs] != list(AUTHORIZED_CHAPTER_IDS):
        raise BookGeneration4225Error("Resume spec order is not CH003, CH004.")
    return {
        "phase": PHASE,
        "batch_id": BATCH_ID,
        "chapter_ids": list(AUTHORIZED_CHAPTER_IDS),
        "specs": {spec.chapter_id: spec for spec in specs},
        "resume_plan": {
            "resume_chapters": resume_plan.get("resume_chapters"),
            "exclude_from_resume_calls": resume_plan.get("exclude_from_resume_calls"),
            "previous_authorization_reusable": resume_plan.get(
                "previous_authorization_reusable"
            ),
            "historical_remaining_budget_is_authorization": resume_plan.get(
                "remaining_4b223_budget_is_not_authorization"
            ),
        },
        "historical_locks": historical_locks,
        "expected_from_plan": {
            spec.chapter_id: {
                "title": spec.title,
                "section_ids": list(spec.section_ids),
                "section_count": spec.section_count,
                "idea_ids": list(spec.idea_ids),
                "idea_count": spec.idea_count,
                "example_ids": list(spec.example_ids),
                "example_count": spec.example_count,
                "reference_ids": list(spec.reference_ids),
                "reference_count": spec.reference_count,
                "uncertainty_ids": list(spec.uncertainty_ids),
                "uncertainty_count": spec.uncertainty_count,
                "src_ids": list(spec.src_ids),
                "src_count": spec.src_count,
            }
            for spec in specs
        },
        "secrets_included": False,
    }


__all__ = [
    "ChapterSpec",
    "chapter_from_plan",
    "inspect_historical_resume_locks",
    "load_resume_plan",
    "load_resume_specs",
]
