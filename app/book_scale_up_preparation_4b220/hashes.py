"""Canonical, historical, original, and accepted-CH012 hashes. Read-only."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.book_editorial_acceptance_4b219.hashes import file_sha256
from app.book_scale_up_preparation_4b220.constants import (
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
from app.book_scale_up_preparation_4b220.guard import BookScaleUpPreparation4220Error
from app.book_scale_up_preparation_4b220.paths import (
    accepted_chapter_json_path,
    accepted_chapter_md_path,
    accepted_editorial_manifest_path,
    historical_4b217_report_path,
    historical_4b218_report_path,
    historical_4b219_report_path,
    historical_prompt_paths,
    original_chapter_json_path,
    original_chapter_md_path,
    original_lock_path,
    production_book_path,
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
        "phase_report": file_sha256(historical_4b217_report_path()),
    }
    accepted = {
        "chapter_candidate_authorial_v2_json": file_sha256(accepted_chapter_json_path()),
        "chapter_candidate_authorial_v2_md": file_sha256(accepted_chapter_md_path()),
        "phase_report": file_sha256(historical_4b218_report_path()),
    }
    acceptance = {
        "editorial_manifest": file_sha256(accepted_editorial_manifest_path()),
        "phase_report": file_sha256(historical_4b219_report_path()),
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
        "acceptance_record": acceptance,
        "canonical_match_expected": canonical_ok,
        "original_match_expected": original_ok,
        "accepted_match_expected": accepted_ok,
        "book_json_published_by_this_phase": False,
        "production_cache_written_by_this_phase": False,
        "original_chapter_modified_by_this_phase": False,
        "accepted_chapter_modified_by_this_phase": False,
        "provider_lock_modified_by_this_phase": False,
        "historical_4b217_4b218_4b219_modified_by_this_phase": False,
        "secrets_included": False,
    }


def snapshots_match(before: dict[str, Any], after: dict[str, Any]) -> bool:
    return (
        before.get("canonical") == after.get("canonical")
        and before.get("historical_modules") == after.get("historical_modules")
        and before.get("original_chapter") == after.get("original_chapter")
        and before.get("accepted_chapter") == after.get("accepted_chapter")
        and before.get("acceptance_record") == after.get("acceptance_record")
    )


def assert_canonical(snap: dict[str, Any]) -> None:
    if not snap.get("canonical_match_expected"):
        canonical = snap.get("canonical") or {}
        raise BookScaleUpPreparation4220Error(
            "Canonical hash mismatch: "
            f"source={((canonical.get('source_map') or {}).get('sha256'))} "
            f"plan={((canonical.get('editorial_plan') or {}).get('sha256'))} "
            f"transcript={((canonical.get('clean_transcript') or {}).get('sha256'))}"
        )


def assert_historical_artifacts(snap: dict[str, Any]) -> None:
    if not snap.get("original_match_expected"):
        raise BookScaleUpPreparation4220Error(
            "Original 4B.2.17 CH012 artifacts or lock hash mismatch."
        )
    if not snap.get("accepted_match_expected"):
        raise BookScaleUpPreparation4220Error(
            "Accepted 4B.2.18 CH012 artifacts hash mismatch."
        )
    lock = ((snap.get("original_chapter") or {}).get("provider_lock") or {})
    if not lock.get("exists"):
        raise BookScaleUpPreparation4220Error("CH012 real-call lock is missing.")
    manifest = ((snap.get("acceptance_record") or {}).get("editorial_manifest") or {})
    if not manifest.get("exists"):
        raise BookScaleUpPreparation4220Error(
            "CH012 accepted editorial manifest is missing."
        )


__all__ = [
    "assert_canonical",
    "assert_historical_artifacts",
    "file_sha256",
    "snapshot",
    "snapshots_match",
]
