"""Canonical and historical-file hashes. Read-only."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from app.book_editorial_alignment_4b216.constants import (
    EXPECTED_EDITORIAL_PLAN,
    EXPECTED_SOURCE_MAP,
    EXPECTED_TRANSCRIPT,
    PHASE,
)
from app.book_editorial_alignment_4b216.paths import (
    historical_prompt_paths,
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
        name: file_sha256(path) for name, path in historical_prompt_paths(root=root).items()
    }
    canonical_ok = (
        canonical["source_map"]["sha256"] == EXPECTED_SOURCE_MAP
        and canonical["editorial_plan"]["sha256"] == EXPECTED_EDITORIAL_PLAN
        and canonical["clean_transcript"]["sha256"] == EXPECTED_TRANSCRIPT
    )
    return {
        "phase": PHASE,
        "canonical": canonical,
        "historical_modules": historical,
        "canonical_match_expected": canonical_ok,
        "book_json_published_by_this_phase": False,
        "secrets_included": False,
    }


def snapshots_match(before: dict[str, Any], after: dict[str, Any]) -> bool:
    return before.get("canonical") == after.get("canonical") and before.get(
        "historical_modules"
    ) == after.get("historical_modules")


__all__ = ["file_sha256", "snapshot", "snapshots_match"]
