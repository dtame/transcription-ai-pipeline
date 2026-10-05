"""Canonical, manuscript, and chapter hashes. STOP on source mismatch."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.book_full_manuscript_review_4b228.hashes import (
    assert_accepted_unchanged,
    assert_candidates_present,
    file_sha256,
    snapshot as manuscript_snapshot,
)
from app.book_print_review_canonical_4b229.constants import (
    EXPECTED_EDITORIAL_PLAN_SHA256,
    EXPECTED_MANUSCRIPT_SHA256,
    EXPECTED_SOURCE_MAP_SHA256,
    EXPECTED_TRANSCRIPT_SHA256,
    PHASE,
)
from app.book_print_review_canonical_4b229.guard import BookPrintReviewCanonical4229Error
from app.book_print_review_canonical_4b229.paths import manuscript_path


def snapshot(*, root: Path | None = None) -> dict[str, Any]:
    snap = manuscript_snapshot(root=root)
    manuscript = file_sha256(manuscript_path(root=root))
    snap["phase"] = PHASE
    snap["manuscript"] = manuscript
    snap["manuscript_match_expected"] = (
        bool(manuscript.get("exists"))
        and manuscript.get("sha256") == EXPECTED_MANUSCRIPT_SHA256
    )
    snap["canonical_match_expected"] = bool(
        snap.get("canonical_match_expected")
        and (snap.get("canonical") or {}).get("source_map", {}).get("sha256")
        == EXPECTED_SOURCE_MAP_SHA256
        and (snap.get("canonical") or {}).get("editorial_plan", {}).get("sha256")
        == EXPECTED_EDITORIAL_PLAN_SHA256
        and (snap.get("canonical") or {}).get("clean_transcript", {}).get("sha256")
        == EXPECTED_TRANSCRIPT_SHA256
        and snap["manuscript_match_expected"]
    )
    return snap


def source_snapshots_match(before: dict[str, Any], after: dict[str, Any]) -> bool:
    return (
        before.get("canonical", {}).get("source_map")
        == after.get("canonical", {}).get("source_map")
        and before.get("canonical", {}).get("editorial_plan")
        == after.get("canonical", {}).get("editorial_plan")
        and before.get("canonical", {}).get("clean_transcript")
        == after.get("canonical", {}).get("clean_transcript")
        and before.get("historical_modules") == after.get("historical_modules")
        and before.get("accepted_chapters") == after.get("accepted_chapters")
        and before.get("remaining_chapters") == after.get("remaining_chapters")
        and before.get("production_cache") == after.get("production_cache")
        and before.get("manuscript") == after.get("manuscript")
    )


def assert_canonical(snap: dict[str, Any]) -> None:
    if not snap.get("canonical_match_expected"):
        canonical = snap.get("canonical") or {}
        raise BookPrintReviewCanonical4229Error(
            "Canonical hash mismatch: "
            f"source={((canonical.get('source_map') or {}).get('sha256'))} "
            f"plan={((canonical.get('editorial_plan') or {}).get('sha256'))} "
            f"transcript={((canonical.get('clean_transcript') or {}).get('sha256'))} "
            f"manuscript={((snap.get('manuscript') or {}).get('sha256'))}. STOP."
        )


def assert_sources_unchanged(before: dict[str, Any], after: dict[str, Any]) -> None:
    if not source_snapshots_match(before, after):
        raise BookPrintReviewCanonical4229Error(
            "A historical canonical or chapter source changed during 4B.2.29. STOP."
        )


__all__ = [
    "assert_accepted_unchanged",
    "assert_candidates_present",
    "assert_canonical",
    "assert_sources_unchanged",
    "file_sha256",
    "snapshot",
    "source_snapshots_match",
]
