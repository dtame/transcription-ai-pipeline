"""Record CH001 and recovered-CH002 human editorial acceptances. No copies."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.book_editorial_acceptance_4b219.hashes import file_sha256
from app.book_generation_4b225.constants import (
    CH001_PRESERVED_SENTENCE,
    CH002_REMOVED_EMPTY_PARAGRAPH,
    DECISION_SOURCE,
    EDITORIAL_POLICY,
    EXPECTED_CH001_JSON_SHA256,
    EXPECTED_CH001_MD_SHA256,
    EXPECTED_CH002_RECOVERED_JSON_INMEMORY_4B224_SHA256,
    EXPECTED_CH002_RECOVERED_JSON_SHA256,
    EXPECTED_CH002_RECOVERED_MD_SHA256,
    EXPECTED_EDITORIAL_PLAN,
    EXPECTED_SOURCE_MAP,
    EXPECTED_TRANSCRIPT,
    HUMAN_ACCEPTANCE_STATUS,
    NARRATIVE_VOICE_CONTRACT,
    PHASE,
    RECORDING_DATE,
)
from app.book_generation_4b225.guard import BookGeneration4225Error
from app.book_generation_4b225.paths import (
    ch001_approved_json_path,
    ch001_approved_md_path,
    ch001_structural_path,
    ch002_approved_json_path,
    ch002_approved_md_path,
    ch002_historical_lock_path,
    ch002_original_json_path,
    ch002_recovery_validation_path,
    production_map_path,
    production_plan_path,
    production_transcript_path,
)


def _rel(path: Path) -> str:
    return str(path).replace("\\", "/")


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise BookGeneration4225Error(f"Approved artifact missing: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise BookGeneration4225Error(f"Approved artifact is not an object: {path}")
    return payload


def _verify_hash(path: Path, expected: str, label: str) -> dict[str, Any]:
    hashed = file_sha256(path)
    if not hashed.get("exists"):
        raise BookGeneration4225Error(f"{label} is missing: {path}")
    if hashed.get("sha256") != expected:
        raise BookGeneration4225Error(
            f"{label} hash mismatch: {hashed.get('sha256')} ≠ {expected}. STOP."
        )
    return hashed


def _paragraph_ids(payload: dict[str, Any]) -> list[str]:
    found: list[str] = []
    for section in payload.get("sections") or []:
        for paragraph in section.get("paragraphs") or []:
            paragraph_id = str(paragraph.get("paragraph_id") or "")
            if paragraph_id:
                found.append(paragraph_id)
    return found


def inspect_ch001() -> dict[str, Any]:
    json_path = ch001_approved_json_path()
    md_path = ch001_approved_md_path()
    json_hash = _verify_hash(json_path, EXPECTED_CH001_JSON_SHA256, "CH001 JSON")
    md_hash = _verify_hash(md_path, EXPECTED_CH001_MD_SHA256, "CH001 Markdown")
    markdown = md_path.read_text(encoding="utf-8")
    if CH001_PRESERVED_SENTENCE not in markdown:
        raise BookGeneration4225Error(
            "Approved CH001 markdown no longer contains the preserved sentence. STOP."
        )
    structural = _load_json(ch001_structural_path())
    if structural.get("status") != "PASS":
        raise BookGeneration4225Error(
            f"CH001 existing structural validation is {structural.get('status')!r}. STOP."
        )
    return {
        "chapter_id": "CH001",
        "json": json_hash,
        "markdown": md_hash,
        "preserved_sentence_present": True,
        "structural_validation_status": structural.get("status"),
        "structural_validator_version": structural.get("validator_version"),
        "copied": False,
        "modified": False,
    }


def inspect_ch002() -> dict[str, Any]:
    json_path = ch002_approved_json_path()
    md_path = ch002_approved_md_path()
    json_hash = _verify_hash(
        json_path, EXPECTED_CH002_RECOVERED_JSON_SHA256, "CH002 recovered JSON"
    )
    md_hash = _verify_hash(
        md_path, EXPECTED_CH002_RECOVERED_MD_SHA256, "CH002 recovered Markdown"
    )
    payload = _load_json(json_path)
    paragraph_ids = _paragraph_ids(payload)
    if CH002_REMOVED_EMPTY_PARAGRAPH in paragraph_ids:
        raise BookGeneration4225Error(
            "Approved recovered CH002 still contains P000008. STOP."
        )
    original = _load_json(ch002_original_json_path())
    if CH002_REMOVED_EMPTY_PARAGRAPH not in _paragraph_ids(original):
        raise BookGeneration4225Error(
            "Original CH002 no longer contains historical P000008. STOP."
        )
    lock = _load_json(ch002_historical_lock_path())
    if lock.get("state") != "FAILED" or lock.get("consumed") is not True:
        raise BookGeneration4225Error(
            "CH002 consumed historical lock was reset or altered. STOP."
        )
    validation = _load_json(ch002_recovery_validation_path())
    if validation.get("status") != "PASS":
        raise BookGeneration4225Error(
            f"CH002 recovered structural validation is {validation.get('status')!r}. STOP."
        )
    in_memory = json.dumps(payload, ensure_ascii=True, indent=2).encode("utf-8")
    import hashlib

    in_memory_sha = hashlib.sha256(in_memory).hexdigest()
    if in_memory_sha != EXPECTED_CH002_RECOVERED_JSON_INMEMORY_4B224_SHA256:
        raise BookGeneration4225Error(
            "Recovered CH002 JSON content diverged from the 4B.2.24 in-memory dump. STOP."
        )
    return {
        "chapter_id": "CH002",
        "json": json_hash,
        "markdown": md_hash,
        "empty_paragraph_restored": False,
        "original_anthropic_response_unmodified": True,
        "consumed_lock_reset": False,
        "approved_version": "offline_derived_recovered",
        "structural_validation_status": validation.get("status"),
        "4b224_inmemory_dump_sha256": in_memory_sha,
        "copied": False,
        "modified": False,
    }


def _manifest(
    *,
    chapter_id: str,
    json_path: Path,
    md_path: Path,
    json_sha256: str,
    md_sha256: str,
    structural_status: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = {
        "phase": PHASE,
        "chapter_id": chapter_id,
        "approved_artifact_paths": {
            "json": _rel(json_path),
            "markdown": _rel(md_path),
        },
        "json_sha256": json_sha256,
        "markdown_sha256": md_sha256,
        "recording_date": RECORDING_DATE,
        "recorded_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "approval_origin": DECISION_SOURCE,
        "existing_structural_validation": structural_status,
        "status": HUMAN_ACCEPTANCE_STATUS,
        "automated_semantic_certification": "not_performed",
        "publication_authorization": "not_granted",
        "chapter_copied": False,
        "chapter_modified": False,
        "canonical_dependencies": {
            "source_map_path": _rel(production_map_path()),
            "source_map_sha256": EXPECTED_SOURCE_MAP,
            "editorial_plan_path": _rel(production_plan_path()),
            "editorial_plan_sha256": EXPECTED_EDITORIAL_PLAN,
            "clean_transcript_path": _rel(production_transcript_path()),
            "clean_transcript_sha256": EXPECTED_TRANSCRIPT,
        },
        "applicable_editorial_policy": EDITORIAL_POLICY,
        "applicable_narrative_voice_contract": NARRATIVE_VOICE_CONTRACT,
        "secrets_included": False,
    }
    if extra:
        payload.update(extra)
    return payload


def record_acceptances() -> dict[str, Any]:
    ch001 = inspect_ch001()
    ch002 = inspect_ch002()
    ch001_manifest = _manifest(
        chapter_id="CH001",
        json_path=ch001_approved_json_path(),
        md_path=ch001_approved_md_path(),
        json_sha256=ch001["json"]["sha256"],
        md_sha256=ch001["markdown"]["sha256"],
        structural_status=ch001["structural_validation_status"],
        extra={
            "preserved_sentence": CH001_PRESERVED_SENTENCE,
            "preserved_sentence_present": True,
            "approved_version": "4b223_generated_candidate",
        },
    )
    ch002_manifest = _manifest(
        chapter_id="CH002",
        json_path=ch002_approved_json_path(),
        md_path=ch002_approved_md_path(),
        json_sha256=ch002["json"]["sha256"],
        md_sha256=ch002["markdown"]["sha256"],
        structural_status=ch002["structural_validation_status"],
        extra={
            "approved_version": "offline_derived_recovered",
            "empty_paragraph_p000008_restored": False,
            "original_anthropic_response_unmodified": True,
            "consumed_lock_reset": False,
            "4b224_inmemory_dump_sha256": ch002["4b224_inmemory_dump_sha256"],
            "on_disk_file_sha256_is_the_accepted_hash": True,
        },
    )
    verify_ch001 = inspect_ch001()
    verify_ch002 = inspect_ch002()
    if verify_ch001["json"]["sha256"] != ch001_manifest["json_sha256"]:
        raise BookGeneration4225Error("CH001 JSON changed after recording. STOP.")
    if verify_ch001["markdown"]["sha256"] != ch001_manifest["markdown_sha256"]:
        raise BookGeneration4225Error("CH001 Markdown changed after recording. STOP.")
    if verify_ch002["json"]["sha256"] != ch002_manifest["json_sha256"]:
        raise BookGeneration4225Error("CH002 recovered JSON changed after recording. STOP.")
    if verify_ch002["markdown"]["sha256"] != ch002_manifest["markdown_sha256"]:
        raise BookGeneration4225Error(
            "CH002 recovered Markdown changed after recording. STOP."
        )
    return {
        "phase": PHASE,
        "CH001_HUMAN_ACCEPTANCE": HUMAN_ACCEPTANCE_STATUS,
        "CH002_HUMAN_ACCEPTANCE": HUMAN_ACCEPTANCE_STATUS,
        "ch001": ch001_manifest,
        "ch002": ch002_manifest,
        "post_record_hash_verification": "PASS",
        "chapters_copied": False,
        "chapters_modified": False,
        "publication": False,
        "secrets_included": False,
    }


__all__ = ["inspect_ch001", "inspect_ch002", "record_acceptances"]
