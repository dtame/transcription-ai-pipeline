"""4B.2.2 pre-call identities. Any mismatch = BLOCKED_PRECALL, 0 provider calls."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from app.ai.estimation import estimate_tokens
from app.book_generation.budget import measure_request_budget
from app.book_generation.cache import ChapterCache, ChapterSignatureInputs, build_chapter_signature
from app.book_generation.coverage import assigned_idea_ids_for_chapter, reused_idea_ids
from app.book_generation.evidence import (
    build_chapter_evidence,
    evidence_identity,
    evidence_metrics,
)
from app.book_generation.fixtures import (
    empty_text_transport,
    tiny_book_source_map,
    tiny_editorial_plan,
    tiny_transcript_index,
    whitespace_text_transport,
)
from app.book_generation.hydrate import load_clean_transcript_index
from app.book_generation.language import resolve_canonical_language
from app.book_generation.payload import (
    build_chapter_request,
    build_future_anthropic_payload,
    payload_audit,
)
from app.book_generation.pipeline import materialize_chapter
from app.book_generation.preflight import audit_request_content
from app.book_generation.prompt import prompt_bundle as prompt_bundle_v10
from app.book_generation.prompt_v101 import prompt_bundle as prompt_bundle_v101
from app.book_generation.schema import schema_identity
from app.book_generation.settings import frozen_production_settings
from app.book_generation.constants import BOOK_GENERATOR_VALIDATOR_VERSION
from app.book_generation.validator import validator_contract_dict
from app.book_generator_canary_4b22.constants import (
    AUTHORIZATION_SCOPE,
    EXPECTED_CACHE_SIGNATURE_V10,
    EXPECTED_CACHE_SIGNATURE_V101,
    EXPECTED_CLEAN_TRANSCRIPT_SHA256,
    EXPECTED_EDITORIAL_PLAN_SHA256,
    EXPECTED_EVIDENCE_SHA256,
    EXPECTED_MAX_OUTPUT,
    EXPECTED_REQUEST_SHA256,
    EXPECTED_SOURCE_MAP_SHA256,
    FROZEN_INSTRUCTIONS_V10_SHA256,
    FROZEN_INSTRUCTIONS_V101_SHA256,
    FROZEN_PROMPT_V10_SHA256,
    FROZEN_PROMPT_V101_SHA256,
    FROZEN_SYSTEM_V10_SHA256,
    FROZEN_SYSTEM_V101_SHA256,
    HISTORICAL_CANDIDATE_CANONICAL_SHA256,
    HISTORICAL_CANDIDATE_FILE_SHA256,
    HISTORICAL_PROMPT_VERSION,
    HISTORICAL_RAW_SHA256,
    HISTORICAL_REQUEST_SHA256,
    HISTORICAL_4B2_STATUS,
    MODEL,
    PHASE,
    PHASE_4B1_ADAPTED_SCHEMA_BYTES,
    PHASE_4B1_ADAPTED_SCHEMA_SHA256,
    PHASE_4B1_RAW_SCHEMA_BYTES,
    PHASE_4B1_RAW_SCHEMA_SHA256,
    PROJECT_NAME,
    PROMPT_VERSION,
    PROVIDER,
    TARGET_CHAPTER_ID,
    THINKING_MODE,
    TRANSPORT_VERSION,
    VALIDATOR_VERSION,
)
from app.book_generator_canary_4b22.costing import estimate_chapter_cost
from app.book_generator_canary_4b22.guard import BookGeneratorCanaryError
from app.book_generator_canary_4b22.paths import (
    historical_4b21_dir,
    historical_4b2_dir,
    production_book_path,
    production_map_path,
    production_plan_path,
    production_preclean_transcript_path,
    production_transcript_path,
)
from app.editorial_planning.language_policy import DOCUMENT_LANGUAGE_POLICY
from app.editorial_planning.pipeline import (
    load_published_editorial_plan,
    load_published_source_map,
)
from app.source_analysis.transcript_input import TranscriptInputMode


def _file_identity(path: Path) -> dict[str, Any]:
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


def _status(ok: bool) -> str:
    return "MATCH" if ok else "MISMATCH"


def _chapter_inventory(chapter) -> dict[str, Any]:
    reused = []
    sections = []
    for section in chapter.sections:
        extra = (
            list(section.additional_idea_refs)
            if hasattr(section, "additional_idea_refs")
            else []
        )
        reused.extend(extra)
        sections.append(
            {
                "id": section.section_id,
                "title": section.working_title,
                "purpose": section.purpose,
                "idea_refs": list(section.idea_refs),
                "example_refs": list(section.example_refs),
                "reference_refs": list(section.reference_refs),
                "uncertainty_refs": list(section.uncertainty_refs),
                "source_refs": list(section.source_refs),
            }
        )
    return {
        "chapter_id": chapter.chapter_id,
        "title": chapter.working_title,
        "purpose": chapter.purpose,
        "summary": chapter.summary,
        "section_ids": [section.section_id for section in chapter.sections],
        "section_titles": [section.working_title for section in chapter.sections],
        "section_purposes": [section.purpose for section in chapter.sections],
        "assigned_idea_refs": list(assigned_idea_ids_for_chapter(chapter)),
        "approved_reused_refs": reused,
        "sections": sections,
    }


def _hydration_audit(evidence: dict[str, Any], transcript_index) -> dict[str, Any]:
    required = [str(item) for item in evidence.get("src") or []]
    hydrated_rows = list(evidence.get("src_text") or [])
    hydrated_ids = [str(row.get("id") or "") for row in hydrated_rows]
    lookup = transcript_index.by_src() if transcript_index is not None else {}
    unknown = [src_id for src_id in required if src_id not in lookup]
    missing = [src_id for src_id in required if src_id not in set(hydrated_ids)]
    chars = sum(len(str(row.get("t") or "")) for row in hydrated_rows)
    estimate = estimate_tokens(
        "\n".join(str(row.get("t") or "") for row in hydrated_rows),
        model=MODEL,
    )
    ordered = hydrated_ids == sorted(
        hydrated_ids,
        key=lambda src: (int("".join(ch for ch in src if ch.isdigit()) or 0), src),
    )
    return {
        "hydrated_src_count": len(hydrated_ids),
        "required_src_count": len(required),
        "hydrated_chars": chars,
        "estimated_tokens": estimate.to_dict(),
        "first_src_id": hydrated_ids[0] if hydrated_ids else None,
        "last_src_id": hydrated_ids[-1] if hydrated_ids else None,
        "ordering_valid": ordered,
        "unknown_src_count": len(unknown),
        "missing_src_count": len(missing),
        "unknown_src_ids": unknown,
        "missing_src_ids": missing,
        "complete": not unknown and not missing and set(required) == set(hydrated_ids),
        "whole_transcript_sent": False,
        "strategy": "SOURCE_MAP_PLUS_TARGETED_TRANSCRIPT_HYDRATION",
    }


def verify_prompt_contracts() -> dict[str, Any]:
    historical = prompt_bundle_v10()
    successor = prompt_bundle_v101()
    system = successor["system"]
    instructions = successor["instructions"]
    system_flat = " ".join(system.split())
    instructions_flat = " ".join(instructions.split())
    empty_rule = (
        "Never emit an empty paragraph" in system_flat
        and "meaningful manuscript text" in system_flat
        and "omit the paragraph object entirely" in system_flat
    )
    connective_rule = (
        "must not introduce a new argument" in system_flat
        and "conclusion" in system_flat
        and "factual claim" in system_flat
        and "doctrinal claim" in system_flat
        and "example" in system_flat
        and "implication" in system_flat
    )
    example_rule = (
        "Do not create new examples, illustrations, anecdotes, scenarios, or"
        in system_flat
        and "hypotheticals" in system_flat
    )
    example_source_rule = (
        "Use an example only when it is explicitly present" in system_flat
    )
    self_check = (
        "verify silently" in instructions_flat
        and "every paragraph contains text" in instructions_flat
        and "every substantive paragraph is supported" in instructions_flat
        and "connective prose introduces no new claim" in instructions_flat
        and "no example, illustration, anecdote, or hypothetical was invented"
        in instructions_flat
        and "every planned IDEA is represented" in instructions_flat
        and "every planned section is present exactly once" in instructions_flat
        and "Do not expose internal reasoning" in instructions_flat
    )
    chain_of_thought = (
        "chain-of-thought" not in system_flat.lower()
        and "chain-of-thought" not in instructions_flat.lower()
        and "step by step" not in instructions_flat.lower()
    )
    return {
        "historical_prompt": historical["version"],
        "historical_mutated": False,
        "historical_system_sha256": historical["system_sha256"],
        "historical_instructions_sha256": historical["instructions_sha256"],
        "historical_prompt_sha256": historical["prompt_sha256"],
        "expected_historical_prompt_sha256": FROZEN_PROMPT_V10_SHA256,
        "historical_identity_match": (
            historical["prompt_sha256"] == FROZEN_PROMPT_V10_SHA256
            and historical["system_sha256"] == FROZEN_SYSTEM_V10_SHA256
            and historical["instructions_sha256"] == FROZEN_INSTRUCTIONS_V10_SHA256
        ),
        "successor_prompt": successor["version"],
        "successor_system_sha256": successor["system_sha256"],
        "successor_instructions_sha256": successor["instructions_sha256"],
        "successor_prompt_sha256": successor["prompt_sha256"],
        "expected_successor_prompt_sha256": FROZEN_PROMPT_V101_SHA256,
        "successor_identity_match": (
            successor["prompt_sha256"] == FROZEN_PROMPT_V101_SHA256
            and successor["system_sha256"] == FROZEN_SYSTEM_V101_SHA256
            and successor["instructions_sha256"] == FROZEN_INSTRUCTIONS_V101_SHA256
        ),
        "successor_differs": successor["prompt_sha256"] != historical["prompt_sha256"],
        "empty_paragraph_rule": empty_rule,
        "connective_rule": connective_rule,
        "example_rule": example_rule,
        "example_source_rule": example_source_rule,
        "pre_return_self_check": self_check,
        "chain_of_thought_requested": not chain_of_thought,
        "ch016_specific_hacks": (
            "p9b" in system
            or "p9b" in instructions
            or "funeral" in system.lower()
            or "funeral" in instructions.lower()
            or "CH016" in system
            or "CH016" in instructions
        ),
    }


def verify_local_validator_hardening() -> dict[str, Any]:
    source_map = tiny_book_source_map()
    plan = tiny_editorial_plan(source_map)
    chapter = plan.chapters[0]
    evidence = build_chapter_evidence(
        plan,
        source_map,
        chapter,
        language=source_map.primary_language,
        hydrate=True,
        transcript_index=tiny_transcript_index(source_map),
    )
    allowed = list(evidence.get("allowed") or [])
    empty_candidate, empty_validation, _empty = materialize_chapter(
        empty_text_transport(chapter),
        plan,
        source_map,
        chapter,
        language=source_map.primary_language,
        allowed_handles=allowed,
    )
    white_candidate, white_validation, _white = materialize_chapter(
        whitespace_text_transport(chapter),
        plan,
        source_map,
        chapter,
        language=source_map.primary_language,
        allowed_handles=allowed,
    )
    empty_kept = any(
        paragraph.provider_handle == "empty-text" and paragraph.text == ""
        for section in empty_candidate.sections
        for paragraph in section.paragraphs
    )
    white_kept = any(
        paragraph.provider_handle == "whitespace-text"
        for section in white_candidate.sections
        for paragraph in section.paragraphs
    )
    empty_fail = empty_validation.status == "FAIL" and any(
        "empty text" in item for item in empty_validation.errors
    )
    white_fail = white_validation.status == "FAIL" and any(
        "empty text" in item for item in white_validation.errors
    )
    contract = validator_contract_dict()
    return {
        "validator_version": VALIDATOR_VERSION,
        "contract_version": contract.get("version"),
        "version_match": VALIDATOR_VERSION == "book-generation-validator-1.0.1"
        and contract.get("version") == BOOK_GENERATOR_VALIDATOR_VERSION,
        "empty_text_rejected": empty_fail,
        "whitespace_text_rejected": white_fail,
        "empty_paragraph_never_dropped": empty_kept and white_kept,
        "empty_errors": list(empty_validation.errors),
        "whitespace_errors": list(white_validation.errors),
        "minLength_not_introduced": True,
    }


def _historical_preservation(*, root: Path | None = None) -> dict[str, Any]:
    # Historical 4B.2 / 4B.2.1 artifacts live in the real repo audit tree.
    # Test roots may redirect 4B.2.2 writes only.
    del root
    historical = historical_4b2_dir()
    forensics = historical_4b21_dir()
    raw = _file_identity(historical / "book_generator_4b2_raw_structured_response.json")
    candidate = _file_identity(historical / "chapter_CH016_candidate.json")
    future = _file_identity(forensics / "book_generator_4b21_future_CH016_request_identity.json")
    return {
        "historical_4b2_status": HISTORICAL_4B2_STATUS,
        "raw_exists": raw["exists"],
        "raw_file_sha256": raw["sha256"],
        "candidate_file_sha256": candidate["sha256"],
        "expected_candidate_file_sha256": HISTORICAL_CANDIDATE_FILE_SHA256,
        "expected_candidate_canonical_sha256": HISTORICAL_CANDIDATE_CANONICAL_SHA256,
        "expected_raw_sha256": HISTORICAL_RAW_SHA256,
        "candidate_file_match": candidate["sha256"] == HISTORICAL_CANDIDATE_FILE_SHA256,
        "future_request_audit_exists": future["exists"],
        "4b21_audits_present": forensics.is_dir(),
    }


def precall_identity(*, root: Path | None = None) -> dict[str, Any]:
    block_reasons: list[str] = []
    settings = frozen_production_settings()
    schema = schema_identity()
    plan_path = production_plan_path()
    map_path = production_map_path()
    transcript_path = production_transcript_path()
    preclean_path = production_preclean_transcript_path()
    book_path = production_book_path()

    plan_pre = _file_identity(plan_path)
    map_pre = _file_identity(map_path)
    transcript_pre = _file_identity(transcript_path)
    preclean = _file_identity(preclean_path)
    prompts = verify_prompt_contracts()
    validator_hardening = verify_local_validator_hardening()
    historical = _historical_preservation(root=root)

    publication_absent = not book_path.is_file()
    if not publication_absent:
        block_reasons.append("book_json_already_present")
    if not plan_pre["exists"]:
        block_reasons.append("editorial_plan_missing")
    if not map_pre["exists"]:
        block_reasons.append("source_map_missing")
    if not transcript_pre["exists"]:
        block_reasons.append("clean_transcript_missing")

    schema_raw_ok = (
        schema["raw_schema_bytes"] == PHASE_4B1_RAW_SCHEMA_BYTES
        and schema["adapted_schema_bytes"] == PHASE_4B1_ADAPTED_SCHEMA_BYTES
        and schema["raw_schema_sha256"] == PHASE_4B1_RAW_SCHEMA_SHA256
        and schema["adapted_schema_sha256"] == PHASE_4B1_ADAPTED_SCHEMA_SHA256
    )
    if not schema_raw_ok:
        block_reasons.append("schema_identity")
    if settings.provider != PROVIDER or settings.model != MODEL:
        block_reasons.append("model_settings")
    if settings.thinking_mode != THINKING_MODE:
        block_reasons.append("thinking_mode")
    if not prompts["historical_identity_match"]:
        block_reasons.append("historical_prompt_mutated")
    if not prompts["successor_identity_match"]:
        block_reasons.append("successor_prompt_identity")
    if not prompts["empty_paragraph_rule"]:
        block_reasons.append("empty_paragraph_rule")
    if not prompts["connective_rule"]:
        block_reasons.append("connective_rule")
    if not prompts["example_rule"] or not prompts["example_source_rule"]:
        block_reasons.append("example_rule")
    if not prompts["pre_return_self_check"]:
        block_reasons.append("pre_return_self_check")
    if prompts["chain_of_thought_requested"] or prompts["ch016_specific_hacks"]:
        block_reasons.append("prompt_policy")
    if not validator_hardening["empty_text_rejected"]:
        block_reasons.append("validator_empty_text")
    if not validator_hardening["whitespace_text_rejected"]:
        block_reasons.append("validator_whitespace_text")
    if not validator_hardening["empty_paragraph_never_dropped"]:
        block_reasons.append("empty_paragraph_dropped")
    if not validator_hardening["version_match"]:
        block_reasons.append("validator_version")
    if not historical["candidate_file_match"]:
        block_reasons.append("historical_candidate_mutated")

    plan = None
    source_map = None
    plan_digest = plan_pre.get("sha256") or ""
    map_digest = map_pre.get("sha256") or ""
    plan_raw = b""
    map_raw = b""
    language = ""
    transcript_index = None
    transcript_identity: dict[str, Any] = {}
    inventory: dict[str, Any] = {}
    evidence: dict[str, Any] = {}
    hydration: dict[str, Any] = {}
    request_audit: dict[str, Any] = {}
    payload: dict[str, Any] = {}
    budget: dict[str, Any] = {}
    cost_estimate: dict[str, Any] = {}
    content: dict[str, Any] = {}
    expected_ideas: list[str] = []
    expected_sections: list[str] = []
    cache_audit: dict[str, Any] = {}
    historical_request_sha = ""

    if plan_pre["exists"] and map_pre["exists"]:
        plan, plan_raw, plan_digest, _plan_path = load_published_editorial_plan(
            PROJECT_NAME
        )
        source_map, map_raw, map_digest, _map_path = load_published_source_map(
            PROJECT_NAME
        )
        if plan_digest.lower() != EXPECTED_EDITORIAL_PLAN_SHA256.lower():
            block_reasons.append("editorial_plan_sha256")
        if map_digest.lower() != EXPECTED_SOURCE_MAP_SHA256.lower():
            block_reasons.append("source_map_sha256")
        if plan_pre["sha256"] != plan_digest:
            block_reasons.append("editorial_plan_file_hash_reader_mismatch")
        if map_pre["sha256"] != map_digest:
            block_reasons.append("source_map_file_hash_reader_mismatch")

    if transcript_pre["exists"]:
        try:
            transcript_index = load_clean_transcript_index(PROJECT_NAME)
            transcript_identity = transcript_index.to_identity()
        except Exception as exc:  # noqa: BLE001 — precall must record and block
            block_reasons.append("clean_transcript_load")
            transcript_identity = {"error": str(exc), "available": False}
        path_value = str(transcript_identity.get("path") or transcript_pre["path"])
        if "transcripts/clean/transcript_data.json" not in path_value.replace("\\", "/"):
            block_reasons.append("transcript_not_clean_artifact")
        if transcript_pre["sha256"] != EXPECTED_CLEAN_TRANSCRIPT_SHA256:
            block_reasons.append("transcript_sha256")
        content_sha = transcript_identity.get("content_sha256")
        if content_sha not in {None, "", EXPECTED_CLEAN_TRANSCRIPT_SHA256}:
            if content_sha != EXPECTED_CLEAN_TRANSCRIPT_SHA256:
                block_reasons.append("transcript_content_sha256")
        if transcript_identity.get("primary_language") not in {None, "", "en"}:
            block_reasons.append("transcript_language")
        if preclean["exists"] and preclean["sha256"] == transcript_pre["sha256"]:
            block_reasons.append("transcript_equals_preclean")
        transcript_identity["mode"] = TranscriptInputMode.DERIVED.value
        transcript_identity["post_interpreter_cleanup"] = True
        transcript_identity["preclean_path"] = preclean["path"]
        transcript_identity["preclean_distinct"] = (
            preclean["exists"] and preclean["sha256"] != transcript_pre["sha256"]
        )

    if plan is not None and source_map is not None and transcript_index is not None:
        language = resolve_canonical_language(
            source_map_primary_language=source_map.primary_language,
            transcript_primary_language=transcript_index.primary_language
            or source_map.primary_language,
        )
        if language != "en":
            block_reasons.append("canonical_language")
        if DOCUMENT_LANGUAGE_POLICY != "TRANSCRIPTION_DERIVED_PRIMARY_LANGUAGE":
            block_reasons.append("language_policy")

        target = next(
            (item for item in plan.chapters if item.chapter_id == TARGET_CHAPTER_ID),
            None,
        )
        if target is None:
            block_reasons.append("ch016_missing")
        else:
            inventory = _chapter_inventory(target)
            expected_ideas = list(assigned_idea_ids_for_chapter(target))
            expected_sections = [section.section_id for section in target.sections]
            reused_plan = reused_idea_ids(plan)
            inventory["approved_reused_refs"] = [
                idea_id for idea_id in expected_ideas if idea_id in reused_plan
            ]
            evidence = build_chapter_evidence(
                plan,
                source_map,
                target,
                language=language,
                hydrate=True,
                transcript_index=transcript_index,
            )
            ev_sha = evidence_identity(evidence)
            if ev_sha != EXPECTED_EVIDENCE_SHA256:
                block_reasons.append("evidence_sha256")
            hydration = _hydration_audit(evidence, transcript_index)
            if not hydration["complete"]:
                block_reasons.append("hydration_incomplete")
            if hydration["unknown_src_count"] or hydration["missing_src_count"]:
                block_reasons.append("required_src_unresolved")

            budget = measure_request_budget(
                evidence,
                settings=settings,
                idea_count=len(expected_ideas),
                section_count=len(expected_sections),
                prompt_version=PROMPT_VERSION,
            )
            selected_max = int(budget["recommended_max_output"])
            if selected_max != EXPECTED_MAX_OUTPUT:
                block_reasons.append("max_output")
            if not budget["context_safe"]:
                block_reasons.append("context_budget")
            if budget["fallback_triggered"]:
                block_reasons.append("fallback_triggered")
            usable = dict(budget.get("usable") or {})
            model_cap = int(usable.get("model_max_output_tokens") or 0)
            if model_cap and selected_max >= model_cap:
                block_reasons.append("output_capability")

            first = payload_audit(
                evidence,
                settings=settings,
                max_output_tokens=selected_max,
                prompt_version=PROMPT_VERSION,
            )
            second = payload_audit(
                evidence,
                settings=settings,
                max_output_tokens=selected_max,
                prompt_version=PROMPT_VERSION,
            )
            historical_payload = payload_audit(
                evidence,
                settings=settings,
                max_output_tokens=selected_max,
                prompt_version=HISTORICAL_PROMPT_VERSION,
            )
            payload = build_future_anthropic_payload(
                evidence,
                settings=settings,
                max_output_tokens=selected_max,
                prompt_version=PROMPT_VERSION,
            )
            request = build_chapter_request(
                evidence,
                settings=settings,
                max_output_tokens=selected_max,
                prompt_version=PROMPT_VERSION,
            )
            content = audit_request_content(
                evidence,
                target,
                language=language,
                all_chapter_ids=[item.chapter_id for item in plan.chapters],
            )
            request_ideas = [row.get("id") for row in evidence.get("ideas") or []]
            request_sections = [row.get("id") for row in evidence.get("sections") or []]
            idea_exact = request_ideas == expected_ideas
            section_exact = request_sections == expected_sections
            historical_request_sha = str(historical_payload["payload_sha256"])
            if first["payload_sha256"] != second["payload_sha256"]:
                block_reasons.append("request_not_deterministic")
            if first["payload_sha256"] != EXPECTED_REQUEST_SHA256:
                block_reasons.append("request_sha256")
            if historical_request_sha != HISTORICAL_REQUEST_SHA256:
                block_reasons.append("historical_request_identity")
            if first["payload_sha256"] == HISTORICAL_REQUEST_SHA256:
                block_reasons.append("request_not_hardened")
            if first["payload_bytes"] != second["payload_bytes"]:
                block_reasons.append("request_bytes_not_deterministic")
            if first["payload_chars"] != second["payload_chars"]:
                block_reasons.append("request_chars_not_deterministic")
            if payload.get("model") != MODEL:
                block_reasons.append("payload_model")
            if payload.get("max_tokens") != selected_max:
                block_reasons.append("payload_max_tokens")
            thinking = payload.get("thinking")
            if not isinstance(thinking, dict) or thinking.get("type") != "disabled":
                block_reasons.append("thinking_not_disabled")
            if first.get("effort_present"):
                block_reasons.append("effort_injected")
            if request.thinking_mode != THINKING_MODE:
                block_reasons.append("request_thinking_mode")
            if request.metadata.get("prompt_version") != PROMPT_VERSION:
                block_reasons.append("request_prompt_version")
            if not content.get("chapter_id_match"):
                block_reasons.append("request_chapter")
            if not content.get("all_planned_sections") or not section_exact:
                block_reasons.append("request_sections")
            if not content.get("all_assigned_ideas") or not idea_exact:
                block_reasons.append("request_ideas")
            if not content.get("canonical_language"):
                block_reasons.append("request_language")
            if not content.get("voice_present"):
                block_reasons.append("request_voice")
            if not content.get("traceability_src_present"):
                block_reasons.append("request_src")
            if not content.get("unrelated_chapter_excluded"):
                block_reasons.append("unrelated_chapter")
            if not hydration["complete"]:
                block_reasons.append("src_not_hydrated")
            if content.get("whole_transcript_sent"):
                block_reasons.append("whole_transcript_sent")

            prompt_v10 = prompt_bundle_v10()
            prompt_v101 = prompt_bundle_v101()
            sig_v10 = build_chapter_signature(
                ChapterSignatureInputs(
                    source_map_sha256=map_digest,
                    editorial_plan_sha256=plan_digest,
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
                    max_output_tokens=selected_max,
                    canonical_language=language,
                    evidence_bundle_sha256=ev_sha,
                )
            )
            sig_v101 = build_chapter_signature(
                ChapterSignatureInputs(
                    source_map_sha256=map_digest,
                    editorial_plan_sha256=plan_digest,
                    chapter_id=TARGET_CHAPTER_ID,
                    prompt_version=PROMPT_VERSION,
                    prompt_sha256=prompt_v101["prompt_sha256"],
                    transport_version=TRANSPORT_VERSION,
                    schema_version="1.0",
                    response_schema_sha256=schema["raw_schema_sha256"],
                    provider=settings.provider,
                    model=settings.model,
                    thinking_mode=settings.thinking_mode,
                    effort=settings.effort or "",
                    max_output_tokens=selected_max,
                    canonical_language=language,
                    evidence_bundle_sha256=ev_sha,
                )
            )
            cache = ChapterCache()
            cache.remember(sig_v10, HISTORICAL_CANDIDATE_CANONICAL_SHA256)
            isolated = cache.lookup(sig_v101) is None and not cache.is_hit(sig_v101)
            if sig_v10 != EXPECTED_CACHE_SIGNATURE_V10:
                block_reasons.append("cache_signature_v10")
            if sig_v101 != EXPECTED_CACHE_SIGNATURE_V101:
                block_reasons.append("cache_signature_v101")
            if not isolated:
                block_reasons.append("cache_isolation")
            cache_audit = {
                "historical": sig_v10,
                "hardened": sig_v101,
                "expected_historical": EXPECTED_CACHE_SIGNATURE_V10,
                "expected_hardened": EXPECTED_CACHE_SIGNATURE_V101,
                "changed": sig_v10 != sig_v101,
                "isolation": isolated,
                "historical_result_satisfies_101": False,
                "production_cache_reuse": False,
            }

            request_audit = {k: v for k, v in first.items() if k != "prompt"}
            request_audit["request_sha256"] = first["payload_sha256"]
            request_audit["request_sha256_repeat"] = second["payload_sha256"]
            request_audit["determinism"] = (
                first["payload_sha256"] == second["payload_sha256"]
                and first["payload_bytes"] == second["payload_bytes"]
                and first["payload_chars"] == second["payload_chars"]
            )
            request_audit["chars"] = first["payload_chars"]
            request_audit["bytes"] = first["payload_bytes"]
            request_audit["content_audit"] = content
            request_audit["idea_set_exact"] = idea_exact
            request_audit["section_set_exact"] = section_exact
            request_audit["src_handles_hydrated"] = hydration["complete"]
            request_audit["expected_chapter_ideas"] = expected_ideas
            request_audit["expected_chapter_sections"] = expected_sections
            request_audit["prompt_version"] = PROMPT_VERSION
            request_audit["historical_prompt_version"] = HISTORICAL_PROMPT_VERSION
            request_audit["transport_version"] = TRANSPORT_VERSION
            request_audit["thinking_mode"] = request.thinking_mode
            request_audit["thinking_payload"] = thinking
            request_audit["historical_request_sha256"] = historical_request_sha
            request_audit["future_differs_from_historical"] = (
                first["payload_sha256"] != historical_request_sha
            )
            request_audit["http_sent"] = False
            request_audit["production_request_builder"] = True
            request_audit["canary_specific_content_hacks"] = False
            cost_estimate = estimate_chapter_cost(budget)

    blocked = bool(block_reasons)
    return {
        "phase": PHASE,
        "authorization_scope": AUTHORIZATION_SCOPE,
        "blocked_precall": blocked,
        "block_reasons": block_reasons,
        "block_reason": "; ".join(block_reasons) if block_reasons else None,
        "project_name": PROJECT_NAME,
        "target_chapter_id": TARGET_CHAPTER_ID,
        "historical_4b2_status": HISTORICAL_4B2_STATUS,
        "language_policy": DOCUMENT_LANGUAGE_POLICY,
        "canonical_document_language": language or None,
        "schema": schema,
        "schema_identity": _status(schema_raw_ok),
        "schema_changed": "NO",
        "schema_raw_adapted": (
            f"{schema['raw_schema_bytes']} / {schema['adapted_schema_bytes']}"
        ),
        "schema_sha256": schema["raw_schema_sha256"],
        "adapted_schema_sha256": schema["adapted_schema_sha256"],
        "schema_limitation": (
            "Anthropic structured-output subset does not permit minLength. "
            "Empty string remains schema-legal."
        ),
        "source_map_sha256_pre": map_digest or map_pre.get("sha256"),
        "editorial_plan_sha256_pre": plan_digest or plan_pre.get("sha256"),
        "transcript_sha256_pre": transcript_pre.get("sha256"),
        "source_map_bytes": map_pre.get("bytes") or len(map_raw),
        "editorial_plan_bytes": plan_pre.get("bytes") or len(plan_raw),
        "transcript_bytes": transcript_pre.get("bytes"),
        "transcript_chars": transcript_pre.get("chars"),
        "source_map_path": map_pre["path"],
        "editorial_plan_path": plan_pre["path"],
        "transcript_path": transcript_pre["path"],
        "transcript": transcript_identity,
        "file_identity_pre": {
            "source_map": map_pre,
            "editorial_plan": plan_pre,
            "clean_transcript": transcript_pre,
            "preclean_transcript": preclean,
        },
        "publication_absent": publication_absent,
        "chapter_inventory": inventory,
        "expected_chapter_ideas": expected_ideas,
        "expected_chapter_sections": expected_sections,
        "evidence_sha256": evidence_identity(evidence) if evidence else None,
        "expected_evidence_sha256": EXPECTED_EVIDENCE_SHA256,
        "evidence_unchanged": (
            evidence_identity(evidence) == EXPECTED_EVIDENCE_SHA256 if evidence else False
        ),
        "hydration": hydration,
        "budget": {k: v for k, v in budget.items() if k != "payload_audit"}
        if budget
        else {},
        "recommended_max_output": (budget or {}).get("recommended_max_output"),
        "expected_max_output": EXPECTED_MAX_OUTPUT,
        "request": request_audit,
        "request_sha256": request_audit.get("request_sha256"),
        "request_determinism": request_audit.get("determinism"),
        "expected_request_sha256": EXPECTED_REQUEST_SHA256,
        "historical_request_sha256": historical_request_sha or HISTORICAL_REQUEST_SHA256,
        "request_identity": _status(
            request_audit.get("request_sha256") == EXPECTED_REQUEST_SHA256
            and bool(request_audit.get("determinism"))
        ),
        "request_differs_from_historical": (
            request_audit.get("request_sha256") != HISTORICAL_REQUEST_SHA256
        ),
        "content_audit": content,
        "cost_estimate": cost_estimate,
        "model": f"{PROVIDER} / {MODEL}",
        "prompt": PROMPT_VERSION,
        "validator": VALIDATOR_VERSION,
        "transport": TRANSPORT_VERSION,
        "thinking": THINKING_MODE,
        "settings": settings.to_dict(),
        "payload": payload,
        "evidence": evidence,
        "prompts": prompts,
        "validator_hardening": validator_hardening,
        "cache": cache_audit,
        "historical_preservation": historical,
        "generation_unit": "CHAPTER",
        "secrets_included": False,
        "http_sent": False,
        "evidence_metrics": evidence_metrics(evidence) if evidence else {},
    }


def require_precall_identity(
    identity: dict[str, Any] | None = None,
    *,
    root: Path | None = None,
) -> dict[str, Any]:
    identity = identity or precall_identity(root=root)
    if identity.get("blocked_precall"):
        raise BookGeneratorCanaryError(
            "BLOCKED_PRECALL: " + str(identity.get("block_reason"))
        )
    return identity


def post_input_hashes() -> dict[str, Any]:
    return {
        "source_map": _file_identity(production_map_path()),
        "editorial_plan": _file_identity(production_plan_path()),
        "clean_transcript": _file_identity(production_transcript_path()),
    }


__all__ = [
    "post_input_hashes",
    "precall_identity",
    "require_precall_identity",
    "verify_local_validator_hardening",
    "verify_prompt_contracts",
]
