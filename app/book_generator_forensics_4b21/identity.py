"""Canonical input and historical artifact identities. No mutation."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from app.book_generator_forensics_4b21.constants import (
    EXPECTED_CLEAN_TRANSCRIPT,
    EXPECTED_EDITORIAL_PLAN,
    EXPECTED_SOURCE_MAP,
    HISTORICAL_CANDIDATE_SHA256,
    HISTORICAL_RAW_RESPONSE_SHA256,
    PROJECT_NAME,
)
from app.book_generator_forensics_4b21.paths import (
    historical_4b2_dir,
    production_map_path,
    production_plan_path,
    production_transcript_path,
)
from app.file_utils import content_hash


def file_identity(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {
            "path": str(path).replace("\\", "/"),
            "exists": False,
            "sha256": "",
            "bytes": 0,
            "chars": 0,
        }
    raw = path.read_bytes()
    try:
        chars = len(raw.decode("utf-8"))
    except UnicodeDecodeError:
        chars = 0
    return {
        "path": str(path).replace("\\", "/"),
        "exists": True,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "bytes": len(raw),
        "chars": chars,
    }


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def verify_canonical_inputs(*, root: Path | None = None) -> dict[str, Any]:
    source_map = file_identity(production_map_path())
    plan = file_identity(production_plan_path())
    transcript = file_identity(production_transcript_path())
    historical = historical_4b2_dir(root=root)
    raw = file_identity(historical / "book_generator_4b2_raw_structured_response.json")
    raw_text = file_identity(historical / "book_generator_4b2_raw_provider_text.txt")
    candidate = file_identity(historical / "chapter_CH016_candidate.json")
    candidate_payload = (
        load_json(historical / "chapter_CH016_candidate.json") if candidate["exists"] else {}
    )
    candidate_canonical = (
        content_hash(json.dumps(candidate_payload, ensure_ascii=False, sort_keys=True))
        if candidate_payload
        else ""
    )
    raw_payload = (
        load_json(historical / "book_generator_4b2_raw_structured_response.json")
        if raw["exists"]
        else {}
    )
    raw_inner = str(raw_payload.get("sha256") or "")
    return {
        "project_name": PROJECT_NAME,
        "source_map": source_map,
        "editorial_plan": plan,
        "clean_transcript": transcript,
        "historical_raw_response_file": raw,
        "historical_raw_provider_text": raw_text,
        "historical_candidate_file": candidate,
        "source_map_unchanged": source_map["sha256"] == EXPECTED_SOURCE_MAP,
        "editorial_plan_unchanged": plan["sha256"] == EXPECTED_EDITORIAL_PLAN,
        "clean_transcript_unchanged": transcript["sha256"] == EXPECTED_CLEAN_TRANSCRIPT,
        "raw_response_unchanged": raw_inner == HISTORICAL_RAW_RESPONSE_SHA256,
        "candidate_unchanged": candidate_canonical == HISTORICAL_CANDIDATE_SHA256,
        "candidate_file_sha256": candidate["sha256"],
        "candidate_canonical_sha256": candidate_canonical,
        "raw_inner_sha256": raw_inner,
        "expected": {
            "source_map": EXPECTED_SOURCE_MAP,
            "editorial_plan": EXPECTED_EDITORIAL_PLAN,
            "clean_transcript": EXPECTED_CLEAN_TRANSCRIPT,
            "raw_response": HISTORICAL_RAW_RESPONSE_SHA256,
            "candidate": HISTORICAL_CANDIDATE_SHA256,
        },
    }


__all__ = ["file_identity", "load_json", "verify_canonical_inputs"]
