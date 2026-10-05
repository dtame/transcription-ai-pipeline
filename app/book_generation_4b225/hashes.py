"""Canonical, accepted, and historical-lock hashes. Read-only. STOP on mismatch."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.book_editorial_acceptance_4b219.hashes import file_sha256
from app.book_generation_4b225.constants import (
    EXPECTED_ACCEPTED_JSON_SHA256,
    EXPECTED_ACCEPTED_MD_SHA256,
    EXPECTED_CH001_JSON_SHA256,
    EXPECTED_CH001_LOCK_SHA256,
    EXPECTED_CH001_MD_SHA256,
    EXPECTED_CH002_LOCK_SHA256,
    EXPECTED_CH002_ORIGINAL_JSON_SHA256,
    EXPECTED_CH002_ORIGINAL_MD_SHA256,
    EXPECTED_CH002_RECOVERED_JSON_INMEMORY_4B224_SHA256,
    EXPECTED_CH002_RECOVERED_JSON_SHA256,
    EXPECTED_CH002_RECOVERED_MD_SHA256,
    EXPECTED_CH003_HISTORICAL_LOCK_SHA256,
    EXPECTED_CH004_HISTORICAL_LOCK_SHA256,
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
from app.book_generation_4b225.guard import BookGeneration4225Error
from app.book_generation_4b221.paths import (
    original_chapter_json_path,
    original_chapter_md_path,
    original_lock_path,
)
from app.book_generation_4b225.paths import (
    accepted_chapter_json_path,
    accepted_chapter_md_path,
    accepted_editorial_manifest_path,
    ch001_approved_json_path,
    ch001_approved_md_path,
    ch001_historical_lock_path,
    ch002_approved_json_path,
    ch002_approved_md_path,
    ch002_historical_lock_path,
    ch002_original_json_path,
    ch002_original_md_path,
    ch003_historical_lock_path,
    ch004_historical_lock_path,
    ch012_accepted_manifest_path,
    ch018_accepted_manifest_path,
    ch018_json_path,
    ch018_lock_path,
    ch018_md_path,
    historical_prompt_paths,
    production_book_path,
    production_cache_module_path,
    production_map_path,
    production_plan_path,
    production_transcript_path,
)


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
    accepted_ch001 = {
        "chapter_candidate_json": file_sha256(ch001_approved_json_path()),
        "chapter_candidate_md": file_sha256(ch001_approved_md_path()),
        "provider_lock": file_sha256(ch001_historical_lock_path()),
    }
    accepted_ch002 = {
        "recovered_json": file_sha256(ch002_approved_json_path()),
        "recovered_md": file_sha256(ch002_approved_md_path()),
        "original_json": file_sha256(ch002_original_json_path()),
        "original_md": file_sha256(ch002_original_md_path()),
        "provider_lock": file_sha256(ch002_historical_lock_path()),
    }
    historical_resume_locks = {
        "ch003": file_sha256(ch003_historical_lock_path()),
        "ch004": file_sha256(ch004_historical_lock_path()),
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
        original["chapter_candidate_json"]["sha256"] == EXPECTED_ORIGINAL_JSON_SHA256
        and original["chapter_candidate_md"]["sha256"] == EXPECTED_ORIGINAL_MD_SHA256
        and original["provider_lock"]["sha256"] == EXPECTED_LOCK_SHA256
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
    ch001_ok = (
        accepted_ch001["chapter_candidate_json"]["sha256"] == EXPECTED_CH001_JSON_SHA256
        and accepted_ch001["chapter_candidate_md"]["sha256"] == EXPECTED_CH001_MD_SHA256
        and accepted_ch001["provider_lock"]["sha256"] == EXPECTED_CH001_LOCK_SHA256
    )
    ch002_ok = (
        accepted_ch002["recovered_json"]["sha256"]
        == EXPECTED_CH002_RECOVERED_JSON_SHA256
        and accepted_ch002["recovered_md"]["sha256"]
        == EXPECTED_CH002_RECOVERED_MD_SHA256
        and accepted_ch002["original_json"]["sha256"]
        == EXPECTED_CH002_ORIGINAL_JSON_SHA256
        and accepted_ch002["original_md"]["sha256"] == EXPECTED_CH002_ORIGINAL_MD_SHA256
        and accepted_ch002["provider_lock"]["sha256"] == EXPECTED_CH002_LOCK_SHA256
    )
    historical_locks_ok = (
        historical_resume_locks["ch003"]["sha256"]
        == EXPECTED_CH003_HISTORICAL_LOCK_SHA256
        and historical_resume_locks["ch004"]["sha256"]
        == EXPECTED_CH004_HISTORICAL_LOCK_SHA256
    )
    return {
        "phase": PHASE,
        "canonical": canonical,
        "historical_modules": historical,
        "original_chapter": original,
        "accepted_chapter": accepted_ch012,
        "acceptance_record": acceptance_ch012,
        "accepted_ch018": accepted_ch018,
        "accepted_ch001": accepted_ch001,
        "accepted_ch002": accepted_ch002,
        "historical_resume_locks": historical_resume_locks,
        "production_cache": production_cache,
        "canonical_match_expected": canonical_ok,
        "original_match_expected": original_ok,
        "accepted_match_expected": ch012_ok,
        "ch018_match_expected": ch018_ok,
        "ch001_match_expected": ch001_ok,
        "ch002_match_expected": ch002_ok,
        "historical_resume_locks_match_expected": historical_locks_ok,
        "ch012_unchanged": original_ok and ch012_ok,
        "ch018_unchanged": ch018_ok,
        "ch001_unchanged": ch001_ok,
        "ch002_unchanged": ch002_ok,
        "ch001_ch002_immutable": ch001_ok and ch002_ok,
        "book_json_published_by_this_phase": False,
        "production_cache_written_by_this_phase": False,
        "original_chapter_modified_by_this_phase": False,
        "accepted_chapter_modified_by_this_phase": False,
        "ch018_modified_by_this_phase": False,
        "provider_lock_modified_by_this_phase": False,
        "ch002_4b224_inmemory_dump_sha256": (
            EXPECTED_CH002_RECOVERED_JSON_INMEMORY_4B224_SHA256
        ),
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
        and before.get("accepted_ch001") == after.get("accepted_ch001")
        and before.get("accepted_ch002") == after.get("accepted_ch002")
        and before.get("historical_resume_locks") == after.get("historical_resume_locks")
        and before.get("production_cache") == after.get("production_cache")
    )


def assert_canonical(snap: dict[str, Any]) -> None:
    if not snap.get("canonical_match_expected"):
        canonical = snap.get("canonical") or {}
        raise BookGeneration4225Error(
            "Canonical hash mismatch: "
            f"source={((canonical.get('source_map') or {}).get('sha256'))} "
            f"plan={((canonical.get('editorial_plan') or {}).get('sha256'))} "
            f"transcript={((canonical.get('clean_transcript') or {}).get('sha256'))}"
        )


def assert_ch012_unchanged(snap: dict[str, Any]) -> None:
    if not snap.get("original_match_expected"):
        raise BookGeneration4225Error(
            "Original 4B.2.17 CH012 artifacts or lock hash mismatch. STOP."
        )
    if not snap.get("accepted_match_expected"):
        raise BookGeneration4225Error(
            "Accepted 4B.2.18 CH012 artifacts hash mismatch. STOP."
        )
    lock = ((snap.get("original_chapter") or {}).get("provider_lock") or {})
    if not lock.get("exists"):
        raise BookGeneration4225Error("CH012 real-call lock is missing. STOP.")
    manifest = ((snap.get("acceptance_record") or {}).get("editorial_manifest") or {})
    if not manifest.get("exists"):
        raise BookGeneration4225Error(
            "CH012 accepted editorial manifest is missing. STOP."
        )


def assert_ch018_unchanged(snap: dict[str, Any]) -> None:
    if not snap.get("ch018_match_expected"):
        raise BookGeneration4225Error(
            "CH018 accepted artifacts hash mismatch. STOP."
        )
    json_file = ((snap.get("accepted_ch018") or {}).get("chapter_candidate_json") or {})
    md_file = ((snap.get("accepted_ch018") or {}).get("chapter_candidate_md") or {})
    if not json_file.get("exists") or not md_file.get("exists"):
        raise BookGeneration4225Error("CH018 accepted artifacts are missing. STOP.")


def assert_accepted_batch01_unchanged(snap: dict[str, Any]) -> None:
    if not snap.get("ch001_match_expected"):
        raise BookGeneration4225Error(
            "Approved CH001 artifacts or consumed lock hash mismatch. STOP."
        )
    if not snap.get("ch002_match_expected"):
        raise BookGeneration4225Error(
            "Approved recovered CH002 artifacts or consumed lock hash mismatch. STOP."
        )
    if not snap.get("historical_resume_locks_match_expected"):
        raise BookGeneration4225Error(
            "Historical CH003/CH004 4B.2.23 locks were altered. STOP."
        )


__all__ = [
    "assert_accepted_batch01_unchanged",
    "assert_canonical",
    "assert_ch012_unchanged",
    "assert_ch018_unchanged",
    "file_sha256",
    "snapshot",
    "snapshots_match",
]
