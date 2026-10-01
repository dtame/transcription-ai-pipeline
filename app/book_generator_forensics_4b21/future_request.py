"""Build the future hardened CH016 request twice. Do not send it."""

from __future__ import annotations

from typing import Any

from app.book_generation.budget import measure_request_budget
from app.book_generation.cache import ChapterSignatureInputs, build_chapter_signature
from app.book_generation.coverage import assigned_idea_ids_for_chapter
from app.book_generation.evidence import evidence_identity
from app.book_generation.payload import (
    build_chapter_request,
    build_future_anthropic_payload,
    payload_audit,
)
from app.book_generation.preflight import audit_request_content
from app.book_generation.prompt import prompt_bundle as prompt_bundle_v10
from app.book_generation.prompt_v101 import prompt_bundle as prompt_bundle_v101
from app.book_generation.schema import schema_identity
from app.book_generation.settings import frozen_production_settings
from app.book_generator_forensics_4b21.constants import (
    EXPECTED_EVIDENCE_SHA256,
    EXPECTED_MAX_OUTPUT,
    HISTORICAL_PROMPT_VERSION,
    HISTORICAL_REQUEST_SHA256,
    SUCCESSOR_PROMPT_VERSION,
    TARGET_CHAPTER_ID,
    TRANSPORT_VERSION,
)


def build_future_ch016_request(
    evidence: dict[str, Any],
    chapter,
    *,
    language: str,
    all_chapter_ids: list[str],
    source_map_sha256: str,
    editorial_plan_sha256: str,
) -> dict[str, Any]:
    settings = frozen_production_settings()
    first = payload_audit(
        evidence,
        settings=settings,
        max_output_tokens=EXPECTED_MAX_OUTPUT,
        prompt_version=SUCCESSOR_PROMPT_VERSION,
    )
    second = payload_audit(
        evidence,
        settings=settings,
        max_output_tokens=EXPECTED_MAX_OUTPUT,
        prompt_version=SUCCESSOR_PROMPT_VERSION,
    )
    request = build_chapter_request(
        evidence,
        settings=settings,
        max_output_tokens=EXPECTED_MAX_OUTPUT,
        prompt_version=SUCCESSOR_PROMPT_VERSION,
    )
    payload = build_future_anthropic_payload(
        evidence,
        settings=settings,
        max_output_tokens=EXPECTED_MAX_OUTPUT,
        prompt_version=SUCCESSOR_PROMPT_VERSION,
    )
    historical = payload_audit(
        evidence,
        settings=settings,
        max_output_tokens=EXPECTED_MAX_OUTPUT,
        prompt_version=HISTORICAL_PROMPT_VERSION,
    )
    content = audit_request_content(
        evidence,
        chapter,
        language=language,
        all_chapter_ids=all_chapter_ids,
    )
    expected_ideas = list(assigned_idea_ids_for_chapter(chapter))
    expected_sections = [section.section_id for section in chapter.sections]
    request_ideas = [row.get("id") for row in evidence.get("ideas") or []]
    request_sections = [row.get("id") for row in evidence.get("sections") or []]
    hydrated = [row.get("id") for row in evidence.get("src_text") or []]
    prompt_v10 = prompt_bundle_v10()
    prompt_v101 = prompt_bundle_v101()
    schema = schema_identity()
    evidence_sha = evidence_identity(evidence)
    budget = measure_request_budget(
        evidence,
        settings=settings,
        idea_count=len(expected_ideas),
        section_count=len(expected_sections),
        prompt_version=SUCCESSOR_PROMPT_VERSION,
    )
    sig_v10 = build_chapter_signature(
        ChapterSignatureInputs(
            source_map_sha256=source_map_sha256,
            editorial_plan_sha256=editorial_plan_sha256,
            chapter_id=TARGET_CHAPTER_ID,
            prompt_version=HISTORICAL_PROMPT_VERSION,
            prompt_sha256=prompt_v10["prompt_sha256"],
            transport_version=TRANSPORT_VERSION,
            schema_version="1.0",
            response_schema_sha256=schema["raw_schema_sha256"],
            provider=settings.provider,
            model=settings.model,
            thinking_mode=settings.thinking_mode,
            effort=settings.effort or "",
            max_output_tokens=EXPECTED_MAX_OUTPUT,
            canonical_language=language,
            evidence_bundle_sha256=evidence_sha,
        )
    )
    sig_v101 = build_chapter_signature(
        ChapterSignatureInputs(
            source_map_sha256=source_map_sha256,
            editorial_plan_sha256=editorial_plan_sha256,
            chapter_id=TARGET_CHAPTER_ID,
            prompt_version=SUCCESSOR_PROMPT_VERSION,
            prompt_sha256=prompt_v101["prompt_sha256"],
            transport_version=TRANSPORT_VERSION,
            schema_version="1.0",
            response_schema_sha256=schema["raw_schema_sha256"],
            provider=settings.provider,
            model=settings.model,
            thinking_mode=settings.thinking_mode,
            effort=settings.effort or "",
            max_output_tokens=EXPECTED_MAX_OUTPUT,
            canonical_language=language,
            evidence_bundle_sha256=evidence_sha,
        )
    )
    thinking = payload.get("thinking")
    return {
        "target_chapter_id": TARGET_CHAPTER_ID,
        "prompt_version": SUCCESSOR_PROMPT_VERSION,
        "historical_prompt_version": HISTORICAL_PROMPT_VERSION,
        "transport_version": TRANSPORT_VERSION,
        "model": payload.get("model"),
        "max_tokens": payload.get("max_tokens"),
        "thinking": thinking,
        "thinking_mode": request.thinking_mode,
        "language": language,
        "request_sha256": first["payload_sha256"],
        "request_sha256_repeat": second["payload_sha256"],
        "determinism": first["payload_sha256"] == second["payload_sha256"],
        "chars": first["payload_chars"],
        "bytes": first["payload_bytes"],
        "historical_request_sha256": historical["payload_sha256"],
        "expected_historical_request_sha256": HISTORICAL_REQUEST_SHA256,
        "historical_request_identity": historical["payload_sha256"]
        == HISTORICAL_REQUEST_SHA256,
        "future_differs_from_historical": first["payload_sha256"]
        != HISTORICAL_REQUEST_SHA256,
        "http_sent": False,
        "secrets_included": False,
        "content_audit": content,
        "idea_set_exact": request_ideas == expected_ideas,
        "section_set_exact": request_sections == expected_sections,
        "src_handles_hydrated": set(hydrated) == set(evidence.get("src") or []),
        "expected_chapter_ideas": expected_ideas,
        "expected_chapter_sections": expected_sections,
        "evidence_sha256": evidence_sha,
        "expected_evidence_sha256": EXPECTED_EVIDENCE_SHA256,
        "evidence_unchanged": evidence_sha == EXPECTED_EVIDENCE_SHA256,
        "cache_signature_v10": sig_v10,
        "cache_signature_v101": sig_v101,
        "cache_signature_changed": sig_v10 != sig_v101,
        "context_safe": budget.get("context_safe"),
        "recommended_max_output": budget.get("recommended_max_output"),
        "fallback_triggered": budget.get("fallback_triggered"),
        "system_prompt_chars": first["system_prompt_chars"],
        "user_prompt_chars": first["user_prompt_chars"],
        "local_input_token_estimate": first["local_input_token_estimate"],
        "canary_specific_content_hacks": False,
        "production_request_builder": True,
    }
