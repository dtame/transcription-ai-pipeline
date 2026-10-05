"""Canonical, accepted, and remaining-13 hashes. Read-only. STOP on mismatch."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.book_editorial_acceptance_4b219.hashes import file_sha256
from app.book_full_generation_preparation_4b226.hashes import snapshot as accepted_snapshot
from app.book_full_manuscript_review_4b228.constants import (
    EXPECTED_EDITORIAL_PLAN,
    EXPECTED_SOURCE_MAP,
    EXPECTED_TRANSCRIPT,
    PENDING_CHAPTER_IDS,
    PHASE,
)
from app.book_full_manuscript_review_4b228.guard import BookFullManuscriptReview4228Error
from app.book_full_manuscript_review_4b228.paths import (
    remaining13_json_path,
    remaining13_md_path,
)


def snapshot(*, root: Path | None = None) -> dict[str, Any]:
    snap = accepted_snapshot(root=root)
    remaining: dict[str, Any] = {}
    for chapter_id in PENDING_CHAPTER_IDS:
        remaining[chapter_id] = {
            "json": file_sha256(remaining13_json_path(chapter_id, root=root)),
            "markdown": file_sha256(remaining13_md_path(chapter_id, root=root)),
        }
    remaining_ok = all(
        row["json"].get("exists") and row["markdown"].get("exists")
        for row in remaining.values()
    )
    snap["phase"] = PHASE
    snap["remaining_chapters"] = remaining
    snap["thirteen_candidates_present"] = remaining_ok
    snap["canonical_match_expected"] = bool(
        snap.get("canonical_match_expected")
        and (snap.get("canonical") or {}).get("source_map", {}).get("sha256")
        == EXPECTED_SOURCE_MAP
        and (snap.get("canonical") or {}).get("editorial_plan", {}).get("sha256")
        == EXPECTED_EDITORIAL_PLAN
        and (snap.get("canonical") or {}).get("clean_transcript", {}).get("sha256")
        == EXPECTED_TRANSCRIPT
    )
    return snap


def snapshots_match(before: dict[str, Any], after: dict[str, Any]) -> bool:
    return (
        before.get("canonical") == after.get("canonical")
        and before.get("historical_modules") == after.get("historical_modules")
        and before.get("accepted_chapters") == after.get("accepted_chapters")
        and before.get("remaining_chapters") == after.get("remaining_chapters")
        and before.get("production_cache") == after.get("production_cache")
    )


def assert_canonical(snap: dict[str, Any]) -> None:
    if not snap.get("canonical_match_expected"):
        canonical = snap.get("canonical") or {}
        raise BookFullManuscriptReview4228Error(
            "Canonical hash mismatch: "
            f"source={((canonical.get('source_map') or {}).get('sha256'))} "
            f"plan={((canonical.get('editorial_plan') or {}).get('sha256'))} "
            f"transcript={((canonical.get('clean_transcript') or {}).get('sha256'))}. STOP."
        )


def assert_accepted_unchanged(snap: dict[str, Any]) -> None:
    labels = {
        "ch001_unchanged": "CH001",
        "ch002_unchanged": "CH002",
        "ch003_unchanged": "CH003",
        "ch004_unchanged": "CH004",
        "ch012_unchanged": "CH012",
        "ch018_unchanged": "CH018",
    }
    failed = [label for key, label in labels.items() if not snap.get(key)]
    if failed:
        raise BookFullManuscriptReview4228Error(
            "Accepted chapter hash mismatch: " + ", ".join(failed) + ". STOP."
        )


def assert_candidates_present(snap: dict[str, Any]) -> None:
    if not snap.get("thirteen_candidates_present"):
        raise BookFullManuscriptReview4228Error(
            "One or more of the thirteen remaining chapter candidates is missing. STOP."
        )


__all__ = [
    "assert_accepted_unchanged",
    "assert_candidates_present",
    "assert_canonical",
    "file_sha256",
    "snapshot",
    "snapshots_match",
]
