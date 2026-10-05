"""Cache invalidation rules. Historical PARTIAL is never converted to PASS."""

from __future__ import annotations

from typing import Any

from app.book_generation_integration_4b213.cache import IsolatedChapterCache, validation_key
from app.book_generation_integration_4b213.constants import (
    HISTORICAL_4B211_STATUS,
    HISTORICAL_H01_STATUS,
    PHASE,
    PROMPT_VERSION_201_CANDIDATE,
    PROMPT_VERSION_202_CANDIDATE,
)
from app.book_generation_integration_4b213.evidence import evidence_bundle_hash
from app.book_generation_integration_4b213.orchestrator import orchestrate_chapter
from app.file_utils import content_hash


def cache_invalidation() -> dict[str, Any]:
    cache = IsolatedChapterCache()
    first = orchestrate_chapter(scenario="fully_supported", cache=cache)
    original_key = first["key"]
    chapter = dict(first["chapter"])
    paragraphs = []
    for section in chapter.get("sections") or []:
        for para in section.get("paragraphs") or []:
            paragraphs.append(str(para.get("paragraph_id") or ""))
    handles = [
        handle
        for section in chapter.get("sections") or []
        for para in section.get("paragraphs") or []
        for handle in para.get("evidence_handles") or []
    ]
    base = dict(
        generated_text_sha256=str(chapter.get("generated_text_sha256") or ""),
        chapter_id=str(chapter.get("chapter_id") or ""),
        paragraph_ids=paragraphs,
        source_map_sha256=str(chapter.get("source_map_sha256") or ""),
        editorial_plan_sha256=str(chapter.get("editorial_plan_sha256") or ""),
        evidence_bundle_sha256=evidence_bundle_hash(handles),
    )
    text_changed = validation_key(
        **{**base, "generated_text_sha256": content_hash("mutated generated text")}
    )
    contract_changed = validation_key(
        **{**base, "semantic_contract_version": PROMPT_VERSION_201_CANDIDATE}
    )
    evidence_changed = validation_key(
        **{**base, "evidence_bundle_sha256": evidence_bundle_hash(["SYN-SRC-CHANGED"])}
    )
    same = validation_key(**base)
    historical_partial_reused = (
        HISTORICAL_H01_STATUS == "PARTIAL"
        and HISTORICAL_4B211_STATUS == "PARTIAL"
        and first.get("decision") == "PASS"
        and first.get("cache_record", {}).get("historical_partial_converted") is False
    )
    return {
        "phase": PHASE,
        "original_key": original_key,
        "same_inputs_same_key": same == original_key,
        "text_change_invalidates": text_changed != original_key,
        "contract_change_invalidates": contract_changed != original_key,
        "evidence_change_invalidates": evidence_changed != original_key,
        "historical_partial_not_converted_to_pass": historical_partial_reused,
        "historical_h01": HISTORICAL_H01_STATUS,
        "historical_4b211": HISTORICAL_4B211_STATUS,
        "old_contract": PROMPT_VERSION_201_CANDIDATE,
        "new_contract": PROMPT_VERSION_202_CANDIDATE,
        "do_not_reuse_historical_validation_under_new_contract": True,
        "ok": (
            same == original_key
            and text_changed != original_key
            and contract_changed != original_key
            and evidence_changed != original_key
            and historical_partial_reused
        ),
        "secrets_included": False,
    }


__all__ = ["cache_invalidation"]
