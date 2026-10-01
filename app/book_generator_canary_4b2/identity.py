"""4B.2 pre-call identities. Any mismatch = BLOCKED_PRECALL, 0 provider calls."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from app.ai.estimation import estimate_tokens
from app.book_generation.budget import measure_request_budget
from app.book_generation.coverage import assigned_idea_ids_for_chapter, reused_idea_ids
from app.book_generation.evidence import (
    build_chapter_evidence,
    evidence_identity,
    evidence_metrics,
)
from app.book_generation.hydrate import load_clean_transcript_index
from app.book_generation.language import resolve_canonical_language
from app.book_generation.payload import (
    build_chapter_request,
    build_future_anthropic_payload,
    payload_audit,
)
from app.book_generation.preflight import (
    audit_request_content,
    select_representative_chapters,
)
from app.book_generation.schema import schema_identity
from app.book_generation.settings import frozen_production_settings
from app.book_generator_canary_4b2.constants import (
    AUTHORIZATION_SCOPE,
    EXPECTED_EDITORIAL_PLAN_SHA256,
    EXPECTED_SOURCE_MAP_SHA256,
    MODEL,
    PHASE,
    PHASE_4B1_ADAPTED_SCHEMA_BYTES,
    PHASE_4B1_ADAPTED_SCHEMA_SHA256,
    PHASE_4B1_CH016_EVIDENCE_SHA256,
    PHASE_4B1_CH016_MAX_OUTPUT,
    PHASE_4B1_CH016_REQUEST_SHA256,
    PHASE_4B1_RAW_SCHEMA_BYTES,
    PHASE_4B1_RAW_SCHEMA_SHA256,
    PHASE_4B1_TRANSCRIPT_CONTENT_SHA256,
    PROJECT_NAME,
    PROMPT_VERSION,
    PROVIDER,
    TARGET_CHAPTER_ID,
    THINKING_MODE,
    TRANSPORT_VERSION,
)
from app.book_generator_canary_4b2.costing import estimate_chapter_cost
from app.book_generator_canary_4b2.guard import BookGeneratorCanaryError
from app.book_generator_canary_4b2.paths import (
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


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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
        text = raw.decode("utf-8")
        chars = len(text)
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
        extra = list(section.additional_idea_refs) if hasattr(section, "additional_idea_refs") else []
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


def _hydration_audit(
    evidence: dict[str, Any],
    transcript_index,
) -> dict[str, Any]:
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
        hydrated_ids, key=lambda src: (int("".join(ch for ch in src if ch.isdigit()) or 0), src)
    )
    first_id = hydrated_ids[0] if hydrated_ids else None
    last_id = hydrated_ids[-1] if hydrated_ids else None
    return {
        "hydrated_src_count": len(hydrated_ids),
        "required_src_count": len(required),
        "hydrated_chars": chars,
        "estimated_tokens": estimate.to_dict(),
        "first_src_id": first_id,
        "last_src_id": last_id,
        "ordering_valid": ordered,
        "unknown_src_count": len(unknown),
        "missing_src_count": len(missing),
        "unknown_src_ids": unknown,
        "missing_src_ids": missing,
        "complete": not unknown and not missing and set(required) == set(hydrated_ids),
        "whole_transcript_sent": False,
    }


def precall_identity() -> dict[str, Any]:
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
    smallest_id = None
    ranking: list[dict[str, Any]] = []
    expected_ideas: list[str] = []
    expected_sections: list[str] = []
    chapter = None

    if plan_pre["exists"] and map_pre["exists"]:
        plan, plan_raw, plan_digest, _plan_path = load_published_editorial_plan(PROJECT_NAME)
        source_map, map_raw, map_digest, _map_path = load_published_source_map(PROJECT_NAME)
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

        clean_marker = "transcripts/clean/transcript_data.json"
        path_value = str(transcript_identity.get("path") or transcript_pre["path"])
        if clean_marker.replace("\\", "/") not in path_value.replace("\\", "/"):
            block_reasons.append("transcript_not_clean_artifact")
        if transcript_pre["sha256"] != PHASE_4B1_TRANSCRIPT_CONTENT_SHA256:
            block_reasons.append("transcript_sha256")
        if transcript_identity.get("content_sha256") not in {
            None,
            "",
            PHASE_4B1_TRANSCRIPT_CONTENT_SHA256,
        }:
            if transcript_identity.get("content_sha256") != PHASE_4B1_TRANSCRIPT_CONTENT_SHA256:
                block_reasons.append("transcript_content_sha256")
        if transcript_identity.get("primary_language") not in {None, "", "en"}:
            block_reasons.append("transcript_language")
        if preclean["exists"] and preclean["sha256"] == transcript_pre["sha256"]:
            block_reasons.append("transcript_equals_preclean")
        if transcript_index is not None:
            mode = getattr(transcript_index, "primary_language", None)
            _ = mode
        # Loader uses DERIVED mode for the clean artifact.
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

        chapter_rows: list[dict[str, Any]] = []
        for item in plan.chapters:
            ideas = assigned_idea_ids_for_chapter(item)
            wet = build_chapter_evidence(
                plan,
                source_map,
                item,
                language=language,
                hydrate=True,
                transcript_index=transcript_index,
            )
            wet_budget = measure_request_budget(
                wet,
                settings=settings,
                idea_count=len(ideas),
                section_count=len(item.sections),
                prompt_version=PROMPT_VERSION,
            )
            chapter_rows.append(
                {
                    "chapter_id": item.chapter_id,
                    "idea_count": len(ideas),
                    "evidence": evidence_metrics(wet),
                    "recommended_max_output": wet_budget["recommended_max_output"],
                    "context_safe": wet_budget["context_safe"],
                    "fallback_triggered": wet_budget["fallback_triggered"],
                    "generation_unit": wet_budget["generation_unit"],
                }
            )
        selected = select_representative_chapters(plan, chapter_rows)
        smallest = selected.get("smallest")
        smallest_id = smallest.chapter_id if smallest is not None else None
        ranking = [
            {
                "chapter_id": row["chapter_id"],
                "idea_count": row["idea_count"],
                "evidence_chars": row["evidence"]["chars"],
            }
            for row in sorted(
                chapter_rows,
                key=lambda row: (
                    int(row["idea_count"]),
                    int(row["evidence"]["chars"]),
                    str(row["chapter_id"]),
                ),
            )
        ]
        if smallest_id != TARGET_CHAPTER_ID:
            block_reasons.append("ch016_not_smallest")

        target = None
        for item in plan.chapters:
            if item.chapter_id == TARGET_CHAPTER_ID:
                target = item
                break
        if target is None:
            block_reasons.append("ch016_missing")
        else:
            chapter = target
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
            if ev_sha != PHASE_4B1_CH016_EVIDENCE_SHA256:
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
            if selected_max != PHASE_4B1_CH016_MAX_OUTPUT:
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
            src_resolved = hydration["complete"]
            if first["payload_sha256"] != second["payload_sha256"]:
                block_reasons.append("request_not_deterministic")
            if first["payload_sha256"] != PHASE_4B1_CH016_REQUEST_SHA256:
                block_reasons.append("request_sha256")
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
            if not src_resolved:
                block_reasons.append("src_not_hydrated")
            other_chapters = [
                item.chapter_id
                for item in plan.chapters
                if item.chapter_id != TARGET_CHAPTER_ID
            ]
            leaked = [
                chapter_id
                for chapter_id in other_chapters
                if chapter_id in str(evidence.get("chapter") or {})
            ]
            if leaked:
                block_reasons.append("unrelated_chapter_material")

            request_audit = {
                k: v for k, v in first.items() if k != "prompt"
            }
            request_audit["request_sha256"] = first["payload_sha256"]
            request_audit["request_sha256_repeat"] = second["payload_sha256"]
            request_audit["determinism"] = (
                first["payload_sha256"] == second["payload_sha256"]
            )
            request_audit["content_audit"] = content
            request_audit["idea_set_exact"] = idea_exact
            request_audit["section_set_exact"] = section_exact
            request_audit["src_handles_hydrated"] = src_resolved
            request_audit["expected_chapter_ideas"] = expected_ideas
            request_audit["expected_chapter_sections"] = expected_sections
            request_audit["prompt_version"] = PROMPT_VERSION
            request_audit["transport_version"] = TRANSPORT_VERSION
            request_audit["thinking_mode"] = request.thinking_mode
            request_audit["thinking_payload"] = thinking
            request_audit["http_sent"] = False
            cost_estimate = estimate_chapter_cost(budget)

    blocked = bool(block_reasons)
    # Post hashes are filled by the runner after any call (or immediately
    # for dry-run). Precall records the before snapshot only.
    return {
        "phase": PHASE,
        "authorization_scope": AUTHORIZATION_SCOPE,
        "blocked_precall": blocked,
        "block_reasons": block_reasons,
        "block_reason": "; ".join(block_reasons) if block_reasons else None,
        "project_name": PROJECT_NAME,
        "target_chapter_id": TARGET_CHAPTER_ID,
        "smallest_recomputed": smallest_id,
        "smallest_is_ch016": smallest_id == TARGET_CHAPTER_ID,
        "chapter_ranking": ranking,
        "language_policy": DOCUMENT_LANGUAGE_POLICY,
        "canonical_document_language": language or None,
        "schema": schema,
        "schema_identity": _status(schema_raw_ok),
        "schema_raw_adapted": (
            f"{schema['raw_schema_bytes']} / {schema['adapted_schema_bytes']}"
        ),
        "schema_sha256": schema["raw_schema_sha256"],
        "adapted_schema_sha256": schema["adapted_schema_sha256"],
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
        "expected_evidence_sha256": PHASE_4B1_CH016_EVIDENCE_SHA256,
        "hydration": hydration,
        "budget": {
            k: v
            for k, v in budget.items()
            if k != "payload_audit"
        }
        if budget
        else {},
        "recommended_max_output": (budget or {}).get("recommended_max_output"),
        "expected_max_output": PHASE_4B1_CH016_MAX_OUTPUT,
        "request": request_audit,
        "request_sha256": request_audit.get("request_sha256"),
        "request_determinism": request_audit.get("determinism"),
        "expected_request_sha256": PHASE_4B1_CH016_REQUEST_SHA256,
        "request_identity": _status(
            request_audit.get("request_sha256") == PHASE_4B1_CH016_REQUEST_SHA256
            and bool(request_audit.get("determinism"))
        ),
        "content_audit": content,
        "cost_estimate": cost_estimate,
        "model": f"{PROVIDER} / {MODEL}",
        "prompt": PROMPT_VERSION,
        "transport": TRANSPORT_VERSION,
        "thinking": THINKING_MODE,
        "settings": settings.to_dict(),
        "payload": payload,
        "evidence": evidence,
        "secrets_included": False,
        "http_sent": False,
    }


def require_precall_identity(identity: dict[str, Any] | None = None) -> dict[str, Any]:
    identity = identity or precall_identity()
    if identity.get("blocked_precall"):
        raise BookGeneratorCanaryError(
            "BLOCKED_PRECALL: " + str(identity.get("block_reason"))
        )
    return identity


def post_input_hashes() -> dict[str, Any]:
    plan = _file_identity(production_plan_path())
    source_map = _file_identity(production_map_path())
    transcript = _file_identity(production_transcript_path())
    return {
        "source_map": source_map,
        "editorial_plan": plan,
        "clean_transcript": transcript,
    }


__all__ = ["post_input_hashes", "precall_identity", "require_precall_identity"]
