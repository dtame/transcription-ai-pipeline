"""Canonical, accepted, and historical hashes. Read-only. STOP on mismatch."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.book_editorial_acceptance_4b219.hashes import file_sha256
from app.book_full_generation_preparation_4b226.constants import (
    EXPECTED_ACCEPTED_JSON_SHA256,
    EXPECTED_ACCEPTED_MD_SHA256,
    EXPECTED_CH001_JSON_SHA256,
    EXPECTED_CH001_MD_SHA256,
    EXPECTED_CH002_ORIGINAL_JSON_SHA256,
    EXPECTED_CH002_ORIGINAL_MD_SHA256,
    EXPECTED_CH002_RECOVERED_JSON_SHA256,
    EXPECTED_CH002_RECOVERED_MD_SHA256,
    EXPECTED_CH003_JSON_SHA256,
    EXPECTED_CH003_MD_SHA256,
    EXPECTED_CH004_JSON_SHA256,
    EXPECTED_CH004_MD_SHA256,
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
from app.book_full_generation_preparation_4b226.guard import (
    BookFullGenerationPreparation4226Error,
)
from app.book_full_generation_preparation_4b226.paths import (
    accepted_chapter_json_path,
    accepted_chapter_md_path,
    ch001_approved_json_path,
    ch001_approved_md_path,
    ch002_approved_json_path,
    ch002_approved_md_path,
    ch002_original_json_path,
    ch002_original_md_path,
    ch003_approved_json_path,
    ch003_approved_md_path,
    ch004_approved_json_path,
    ch004_approved_md_path,
    ch018_json_path,
    ch018_md_path,
    historical_prompt_paths,
    production_book_path,
    production_cache_module_path,
    production_map_path,
    production_plan_path,
    production_transcript_path,
)
from app.book_generation_4b221.paths import (
    original_chapter_json_path,
    original_chapter_md_path,
    original_lock_path,
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
    accepted = {
        "CH001": {
            "json": file_sha256(ch001_approved_json_path()),
            "markdown": file_sha256(ch001_approved_md_path()),
        },
        "CH002": {
            "json": file_sha256(ch002_approved_json_path()),
            "markdown": file_sha256(ch002_approved_md_path()),
            "original_json": file_sha256(ch002_original_json_path()),
            "original_markdown": file_sha256(ch002_original_md_path()),
        },
        "CH003": {
            "json": file_sha256(ch003_approved_json_path()),
            "markdown": file_sha256(ch003_approved_md_path()),
        },
        "CH004": {
            "json": file_sha256(ch004_approved_json_path()),
            "markdown": file_sha256(ch004_approved_md_path()),
        },
        "CH012": {
            "json": file_sha256(accepted_chapter_json_path()),
            "markdown": file_sha256(accepted_chapter_md_path()),
            "original_json": file_sha256(original_chapter_json_path()),
            "original_markdown": file_sha256(original_chapter_md_path()),
            "provider_lock": file_sha256(original_lock_path()),
        },
        "CH018": {
            "json": file_sha256(ch018_json_path()),
            "markdown": file_sha256(ch018_md_path()),
        },
    }
    production_cache = {
        "module": file_sha256(production_cache_module_path(root=root)),
    }
    canonical_ok = (
        canonical["source_map"]["sha256"] == EXPECTED_SOURCE_MAP
        and canonical["editorial_plan"]["sha256"] == EXPECTED_EDITORIAL_PLAN
        and canonical["clean_transcript"]["sha256"] == EXPECTED_TRANSCRIPT
    )
    ch001_ok = (
        accepted["CH001"]["json"]["sha256"] == EXPECTED_CH001_JSON_SHA256
        and accepted["CH001"]["markdown"]["sha256"] == EXPECTED_CH001_MD_SHA256
    )
    ch002_ok = (
        accepted["CH002"]["json"]["sha256"] == EXPECTED_CH002_RECOVERED_JSON_SHA256
        and accepted["CH002"]["markdown"]["sha256"] == EXPECTED_CH002_RECOVERED_MD_SHA256
        and accepted["CH002"]["original_json"]["sha256"]
        == EXPECTED_CH002_ORIGINAL_JSON_SHA256
        and accepted["CH002"]["original_markdown"]["sha256"]
        == EXPECTED_CH002_ORIGINAL_MD_SHA256
    )
    ch003_ok = (
        accepted["CH003"]["json"]["sha256"] == EXPECTED_CH003_JSON_SHA256
        and accepted["CH003"]["markdown"]["sha256"] == EXPECTED_CH003_MD_SHA256
    )
    ch004_ok = (
        accepted["CH004"]["json"]["sha256"] == EXPECTED_CH004_JSON_SHA256
        and accepted["CH004"]["markdown"]["sha256"] == EXPECTED_CH004_MD_SHA256
    )
    ch012_ok = (
        accepted["CH012"]["json"]["sha256"] == EXPECTED_ACCEPTED_JSON_SHA256
        and accepted["CH012"]["markdown"]["sha256"] == EXPECTED_ACCEPTED_MD_SHA256
        and accepted["CH012"]["original_json"]["sha256"] == EXPECTED_ORIGINAL_JSON_SHA256
        and accepted["CH012"]["original_markdown"]["sha256"]
        == EXPECTED_ORIGINAL_MD_SHA256
        and accepted["CH012"]["provider_lock"]["sha256"] == EXPECTED_LOCK_SHA256
    )
    ch018_ok = (
        accepted["CH018"]["json"]["sha256"] == EXPECTED_CH018_JSON_SHA256
        and accepted["CH018"]["markdown"]["sha256"] == EXPECTED_CH018_MD_SHA256
    )
    return {
        "phase": PHASE,
        "canonical": canonical,
        "historical_modules": historical,
        "accepted_chapters": accepted,
        "production_cache": production_cache,
        "canonical_match_expected": canonical_ok,
        "ch001_unchanged": ch001_ok,
        "ch002_unchanged": ch002_ok,
        "ch003_unchanged": ch003_ok,
        "ch004_unchanged": ch004_ok,
        "ch012_unchanged": ch012_ok,
        "ch018_unchanged": ch018_ok,
        "six_accepted_immutable": all(
            (ch001_ok, ch002_ok, ch003_ok, ch004_ok, ch012_ok, ch018_ok)
        ),
        "book_json_published_by_this_phase": False,
        "production_cache_written_by_this_phase": False,
        "secrets_included": False,
    }


def snapshots_match(before: dict[str, Any], after: dict[str, Any]) -> bool:
    return (
        before.get("canonical") == after.get("canonical")
        and before.get("historical_modules") == after.get("historical_modules")
        and before.get("accepted_chapters") == after.get("accepted_chapters")
        and before.get("production_cache") == after.get("production_cache")
    )


def assert_canonical(snap: dict[str, Any]) -> None:
    if not snap.get("canonical_match_expected"):
        canonical = snap.get("canonical") or {}
        raise BookFullGenerationPreparation4226Error(
            "Canonical hash mismatch: "
            f"source={((canonical.get('source_map') or {}).get('sha256'))} "
            f"plan={((canonical.get('editorial_plan') or {}).get('sha256'))} "
            f"transcript={((canonical.get('clean_transcript') or {}).get('sha256'))}"
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
        raise BookFullGenerationPreparation4226Error(
            "Accepted chapter hash mismatch: " + ", ".join(failed) + ". STOP."
        )


__all__ = [
    "assert_accepted_unchanged",
    "assert_canonical",
    "file_sha256",
    "snapshot",
    "snapshots_match",
]
