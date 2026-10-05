"""Canonical, historical, original, and accepted-CH012 hashes. Read-only."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from app.book_editorial_acceptance_4b219.constants import (
    EXPECTED_ACCEPTED_JSON_SHA256,
    EXPECTED_ACCEPTED_MD_SHA256,
    EXPECTED_EDITORIAL_PLAN,
    EXPECTED_LOCK_SHA256,
    EXPECTED_ORIGINAL_JSON_SHA256,
    EXPECTED_ORIGINAL_MD_SHA256,
    EXPECTED_SOURCE_MAP,
    EXPECTED_TRANSCRIPT,
    PHASE,
)
from app.book_editorial_acceptance_4b219.paths import (
    accepted_chapter_json_path,
    accepted_chapter_md_path,
    historical_prompt_paths,
    original_chapter_json_path,
    original_chapter_md_path,
    original_lock_path,
    production_book_path,
    production_map_path,
    production_plan_path,
    production_transcript_path,
)


def file_sha256(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {
            "path": str(path).replace("\\", "/"),
            "exists": False,
            "sha256": "",
            "bytes": 0,
        }
    raw = path.read_bytes()
    return {
        "path": str(path).replace("\\", "/"),
        "exists": True,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


def snapshot(*, root: Path | None = None) -> dict[str, Any]:
    canonical = {
        "source_map": file_sha256(production_map_path()),
        "editorial_plan": file_sha256(production_plan_path()),
        "clean_transcript": file_sha256(production_transcript_path()),
        "book_json": file_sha256(production_book_path()),
    }
    historical = {
        name: file_sha256(path)
        for name, path in historical_prompt_paths(root=root).items()
    }
    original = {
        "chapter_candidate_json": file_sha256(original_chapter_json_path()),
        "chapter_candidate_md": file_sha256(original_chapter_md_path()),
        "provider_lock": file_sha256(original_lock_path()),
    }
    accepted = {
        "chapter_candidate_authorial_v2_json": file_sha256(accepted_chapter_json_path()),
        "chapter_candidate_authorial_v2_md": file_sha256(accepted_chapter_md_path()),
    }
    canonical_ok = (
        canonical["source_map"]["sha256"] == EXPECTED_SOURCE_MAP
        and canonical["editorial_plan"]["sha256"] == EXPECTED_EDITORIAL_PLAN
        and canonical["clean_transcript"]["sha256"] == EXPECTED_TRANSCRIPT
    )
    original_ok = (
        original["chapter_candidate_json"]["sha256"] == EXPECTED_ORIGINAL_JSON_SHA256
        and original["chapter_candidate_md"]["sha256"] == EXPECTED_ORIGINAL_MD_SHA256
        and original["provider_lock"]["sha256"] == EXPECTED_LOCK_SHA256
    )
    accepted_ok = (
        accepted["chapter_candidate_authorial_v2_json"]["sha256"]
        == EXPECTED_ACCEPTED_JSON_SHA256
        and accepted["chapter_candidate_authorial_v2_md"]["sha256"]
        == EXPECTED_ACCEPTED_MD_SHA256
    )
    return {
        "phase": PHASE,
        "canonical": canonical,
        "historical_modules": historical,
        "original_chapter": original,
        "accepted_chapter": accepted,
        "canonical_match_expected": canonical_ok,
        "original_match_expected": original_ok,
        "accepted_match_expected": accepted_ok,
        "book_json_published_by_this_phase": False,
        "production_cache_written_by_this_phase": False,
        "original_chapter_modified_by_this_phase": False,
        "accepted_chapter_modified_by_this_phase": False,
        "provider_lock_modified_by_this_phase": False,
        "secrets_included": False,
    }


def snapshots_match(before: dict[str, Any], after: dict[str, Any]) -> bool:
    return (
        before.get("canonical") == after.get("canonical")
        and before.get("historical_modules") == after.get("historical_modules")
        and before.get("original_chapter") == after.get("original_chapter")
        and before.get("accepted_chapter") == after.get("accepted_chapter")
    )


def assert_canonical(snap: dict[str, Any]) -> None:
    if not snap.get("canonical_match_expected"):
        canonical = snap.get("canonical") or {}
        raise RuntimeError(
            "Canonical hash mismatch: "
            f"source={((canonical.get('source_map') or {}).get('sha256'))} "
            f"plan={((canonical.get('editorial_plan') or {}).get('sha256'))} "
            f"transcript={((canonical.get('clean_transcript') or {}).get('sha256'))}"
        )


def assert_historical_artifacts(snap: dict[str, Any]) -> None:
    if not snap.get("original_match_expected"):
        raise RuntimeError("Original 4B.2.17 CH012 artifacts or lock hash mismatch.")
    if not snap.get("accepted_match_expected"):
        raise RuntimeError("Accepted 4B.2.18 CH012 artifacts hash mismatch.")


__all__ = [
    "assert_canonical",
    "assert_historical_artifacts",
    "file_sha256",
    "snapshot",
    "snapshots_match",
]
