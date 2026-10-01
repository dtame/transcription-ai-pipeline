"""Canonical input and historical artifact identities. No mutation."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from app.book_semantic_gate_4b23.constants import (
    EXPECTED_CLEAN_TRANSCRIPT,
    EXPECTED_EDITORIAL_PLAN,
    EXPECTED_SOURCE_MAP,
    HISTORICAL_4B22_CANDIDATE_CANONICAL_SHA256,
    HISTORICAL_4B2_CANDIDATE_FILE_SHA256,
    HISTORICAL_4B2_CANDIDATE_SHA256,
    HISTORICAL_4B2_RAW_SHA256,
    PROJECT_NAME,
)
from app.book_semantic_gate_4b23.paths import (
    historical_4b21_dir,
    historical_4b22_dir,
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
        }
    raw = path.read_bytes()
    return {
        "path": str(path).replace("\\", "/"),
        "exists": True,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def canonical_json_sha256(payload: Any) -> str:
    return content_hash(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def _candidate_identities(path: Path) -> dict[str, Any]:
    file_meta = file_identity(path)
    payload = load_json(path) if file_meta["exists"] else {}
    return {
        "file": file_meta,
        "canonical_sha256": canonical_json_sha256(payload) if payload else "",
        "payload": payload,
    }


def verify_canonical_inputs(*, root: Path | None = None) -> dict[str, Any]:
    source_map = file_identity(production_map_path())
    plan = file_identity(production_plan_path())
    transcript = file_identity(production_transcript_path())
    historical = historical_4b2_dir(root=root)
    hardened = historical_4b22_dir(root=root)
    forensics = historical_4b21_dir(root=root)
    raw = file_identity(historical / "book_generator_4b2_raw_structured_response.json")
    raw_text = file_identity(historical / "book_generator_4b2_raw_provider_text.txt")
    candidate_4b2 = _candidate_identities(historical / "chapter_CH016_candidate.json")
    raw_payload = (
        load_json(historical / "book_generator_4b2_raw_structured_response.json")
        if raw["exists"]
        else {}
    )
    raw_inner = str(raw_payload.get("sha256") or "")
    candidate_4b22 = _candidate_identities(hardened / "chapter_CH016_candidate.json")
    raw_4b22 = file_identity(hardened / "book_generator_4b22_raw_structured_response.json")
    forensics_files = sorted(
        path.name for path in forensics.glob("*.json") if path.is_file()
    )
    return {
        "project_name": PROJECT_NAME,
        "source_map": source_map,
        "editorial_plan": plan,
        "clean_transcript": transcript,
        "historical_4b2_raw_response_file": raw,
        "historical_4b2_raw_provider_text": raw_text,
        "historical_4b2_candidate_file": candidate_4b2["file"],
        "historical_4b22_raw_response_file": raw_4b22,
        "historical_4b22_candidate_file": candidate_4b22["file"],
        "source_map_unchanged": source_map["sha256"] == EXPECTED_SOURCE_MAP,
        "editorial_plan_unchanged": plan["sha256"] == EXPECTED_EDITORIAL_PLAN,
        "clean_transcript_unchanged": transcript["sha256"] == EXPECTED_CLEAN_TRANSCRIPT,
        "raw_4b2_unchanged": raw_inner == HISTORICAL_4B2_RAW_SHA256,
        "candidate_4b2_unchanged": (
            candidate_4b2["canonical_sha256"] == HISTORICAL_4B2_CANDIDATE_SHA256
            and candidate_4b2["file"]["sha256"] == HISTORICAL_4B2_CANDIDATE_FILE_SHA256
        ),
        "candidate_4b22_unchanged": (
            candidate_4b22["canonical_sha256"]
            == HISTORICAL_4B22_CANDIDATE_CANONICAL_SHA256
        ),
        "historical_4b21_audits_present": bool(forensics_files),
        "candidate_4b2_canonical_sha256": candidate_4b2["canonical_sha256"],
        "candidate_4b2_file_sha256": candidate_4b2["file"]["sha256"],
        "candidate_4b22_canonical_sha256": candidate_4b22["canonical_sha256"],
        "candidate_4b22_file_sha256": candidate_4b22["file"]["sha256"],
        "raw_4b2_inner_sha256": raw_inner,
        "expected": {
            "source_map": EXPECTED_SOURCE_MAP,
            "editorial_plan": EXPECTED_EDITORIAL_PLAN,
            "clean_transcript": EXPECTED_CLEAN_TRANSCRIPT,
            "raw_4b2": HISTORICAL_4B2_RAW_SHA256,
            "candidate_4b2": HISTORICAL_4B2_CANDIDATE_SHA256,
            "candidate_4b22": HISTORICAL_4B22_CANDIDATE_CANONICAL_SHA256,
        },
    }


def snapshot_identities(identities: dict[str, Any]) -> dict[str, str]:
    return {
        "source_map": str((identities.get("source_map") or {}).get("sha256") or ""),
        "editorial_plan": str((identities.get("editorial_plan") or {}).get("sha256") or ""),
        "clean_transcript": str(
            (identities.get("clean_transcript") or {}).get("sha256") or ""
        ),
        "candidate_4b2": str(identities.get("candidate_4b2_canonical_sha256") or ""),
        "candidate_4b22": str(identities.get("candidate_4b22_canonical_sha256") or ""),
        "raw_4b2": str(identities.get("raw_4b2_inner_sha256") or ""),
    }


__all__ = [
    "canonical_json_sha256",
    "file_identity",
    "load_json",
    "snapshot_identities",
    "verify_canonical_inputs",
]
