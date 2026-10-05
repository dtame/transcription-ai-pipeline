"""Canonical, accepted-chapter, BATCH-01 original, and lock hashes. Read-only."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.book_ch002_offline_recovery_4b224.constants import (
    BATCH01_CHAPTER_IDS,
    EXPECTED_ACCEPTED_JSON_SHA256,
    EXPECTED_ACCEPTED_MD_SHA256,
    EXPECTED_CH018_JSON_SHA256,
    EXPECTED_CH018_MD_SHA256,
    EXPECTED_EDITORIAL_PLAN,
    EXPECTED_LOCK_SHA256,
    EXPECTED_ORIGINAL_JSON_SHA256,
    EXPECTED_ORIGINAL_MD_SHA256,
    EXPECTED_SOURCE_MAP,
    EXPECTED_TRANSCRIPT,
    PHASE,
)
from app.book_ch002_offline_recovery_4b224.guard import BookCh002OfflineRecovery4224Error
from app.book_ch002_offline_recovery_4b224.paths import (
    accepted_chapter_json_path,
    accepted_chapter_md_path,
    accepted_editorial_manifest_path,
    batch01_lock_path,
    ch012_accepted_manifest_path,
    ch018_accepted_manifest_path,
    ch018_json_path,
    ch018_lock_path,
    ch018_md_path,
    historical_prompt_paths,
    original_candidate_json_path,
    original_candidate_md_path,
    original_chapter_json_path,
    original_chapter_md_path,
    original_lock_file,
    original_lock_path,
    original_raw_response_path,
    original_structural_path,
    production_book_path,
    production_cache_module_path,
    production_map_path,
    production_plan_path,
    production_transcript_path,
)
from app.book_editorial_acceptance_4b219.hashes import file_sha256


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
    original_ch012 = {
        "chapter_candidate_json": file_sha256(original_chapter_json_path()),
        "chapter_candidate_md": file_sha256(original_chapter_md_path()),
        "provider_lock": file_sha256(original_lock_path()),
    }
    accepted_ch012 = {
        "chapter_candidate_authorial_v2_json": file_sha256(accepted_chapter_json_path()),
        "chapter_candidate_authorial_v2_md": file_sha256(accepted_chapter_md_path()),
    }
    acceptance_ch012 = {
        "editorial_manifest": file_sha256(accepted_editorial_manifest_path()),
        "phase_manifest": file_sha256(ch012_accepted_manifest_path(root=root)),
    }
    accepted_ch018 = {
        "chapter_candidate_json": file_sha256(ch018_json_path()),
        "chapter_candidate_md": file_sha256(ch018_md_path()),
        "provider_lock": file_sha256(ch018_lock_path()),
        "editorial_manifest": file_sha256(ch018_accepted_manifest_path(root=root)),
    }
    batch01_originals = {
        chapter_id: {
            "chapter_candidate_json": file_sha256(
                original_candidate_json_path(chapter_id)
            ),
            "chapter_candidate_md": file_sha256(original_candidate_md_path(chapter_id)),
            "provider_response_raw": file_sha256(original_raw_response_path(chapter_id)),
            "structural_validation": file_sha256(original_structural_path(chapter_id)),
            "call_lock": file_sha256(original_lock_file(chapter_id)),
        }
        for chapter_id in BATCH01_CHAPTER_IDS
    }
    locks = {
        "batch_lock": file_sha256(batch01_lock_path()),
        "ch001": file_sha256(original_lock_file("CH001")),
        "ch002": file_sha256(original_lock_file("CH002")),
        "ch003": file_sha256(original_lock_file("CH003")),
        "ch004": file_sha256(original_lock_file("CH004")),
        "ch012": file_sha256(original_lock_path()),
        "ch018": file_sha256(ch018_lock_path()),
    }
    production_cache = {
        "module": file_sha256(production_cache_module_path(root=root)),
    }
    canonical_ok = (
        canonical["source_map"]["sha256"] == EXPECTED_SOURCE_MAP
        and canonical["editorial_plan"]["sha256"] == EXPECTED_EDITORIAL_PLAN
        and canonical["clean_transcript"]["sha256"] == EXPECTED_TRANSCRIPT
    )
    original_ok = (
        original_ch012["chapter_candidate_json"]["sha256"] == EXPECTED_ORIGINAL_JSON_SHA256
        and original_ch012["chapter_candidate_md"]["sha256"] == EXPECTED_ORIGINAL_MD_SHA256
        and original_ch012["provider_lock"]["sha256"] == EXPECTED_LOCK_SHA256
    )
    ch012_ok = (
        accepted_ch012["chapter_candidate_authorial_v2_json"]["sha256"]
        == EXPECTED_ACCEPTED_JSON_SHA256
        and accepted_ch012["chapter_candidate_authorial_v2_md"]["sha256"]
        == EXPECTED_ACCEPTED_MD_SHA256
    )
    ch018_ok = (
        accepted_ch018["chapter_candidate_json"]["sha256"] == EXPECTED_CH018_JSON_SHA256
        and accepted_ch018["chapter_candidate_md"]["sha256"] == EXPECTED_CH018_MD_SHA256
    )
    return {
        "phase": PHASE,
        "canonical": canonical,
        "historical_modules": historical,
        "original_chapter": original_ch012,
        "accepted_chapter": accepted_ch012,
        "acceptance_record": acceptance_ch012,
        "accepted_ch018": accepted_ch018,
        "batch01_originals": batch01_originals,
        "locks": locks,
        "production_cache": production_cache,
        "canonical_match_expected": canonical_ok,
        "original_match_expected": original_ok,
        "accepted_match_expected": ch012_ok,
        "ch018_match_expected": ch018_ok,
        "ch012_unchanged": original_ok and ch012_ok,
        "ch018_unchanged": ch018_ok,
        "book_json_published_by_this_phase": False,
        "production_cache_written_by_this_phase": False,
        "original_chapter_modified_by_this_phase": False,
        "accepted_chapter_modified_by_this_phase": False,
        "ch018_modified_by_this_phase": False,
        "provider_lock_modified_by_this_phase": False,
        "batch01_originals_modified_by_this_phase": False,
        "secrets_included": False,
    }


def snapshots_match(before: dict[str, Any], after: dict[str, Any]) -> bool:
    return (
        before.get("canonical") == after.get("canonical")
        and before.get("historical_modules") == after.get("historical_modules")
        and before.get("original_chapter") == after.get("original_chapter")
        and before.get("accepted_chapter") == after.get("accepted_chapter")
        and before.get("acceptance_record") == after.get("acceptance_record")
        and before.get("accepted_ch018") == after.get("accepted_ch018")
        and before.get("batch01_originals") == after.get("batch01_originals")
        and before.get("locks") == after.get("locks")
        and before.get("production_cache") == after.get("production_cache")
    )


def assert_canonical(snap: dict[str, Any]) -> None:
    if not snap.get("canonical_match_expected"):
        canonical = snap.get("canonical") or {}
        raise BookCh002OfflineRecovery4224Error(
            "Canonical hash mismatch: "
            f"source={((canonical.get('source_map') or {}).get('sha256'))} "
            f"plan={((canonical.get('editorial_plan') or {}).get('sha256'))} "
            f"transcript={((canonical.get('clean_transcript') or {}).get('sha256'))}"
        )


def assert_ch012_unchanged(snap: dict[str, Any]) -> None:
    if not snap.get("original_match_expected"):
        raise BookCh002OfflineRecovery4224Error(
            "Original 4B.2.17 CH012 artifacts or lock hash mismatch. STOP."
        )
    if not snap.get("accepted_match_expected"):
        raise BookCh002OfflineRecovery4224Error(
            "Accepted 4B.2.18 CH012 artifacts hash mismatch. STOP."
        )


def assert_ch018_unchanged(snap: dict[str, Any]) -> None:
    if not snap.get("ch018_match_expected"):
        raise BookCh002OfflineRecovery4224Error(
            "CH018 accepted artifacts hash mismatch. STOP."
        )


__all__ = [
    "assert_canonical",
    "assert_ch012_unchanged",
    "assert_ch018_unchanged",
    "file_sha256",
    "snapshot",
    "snapshots_match",
]
