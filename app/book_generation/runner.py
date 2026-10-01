"""Offline Phase 4B.1 runner. 0 provider. 0 book.json publication."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.ai.cost import CostTracker
from app.book_generation.budget import distribution, measure_request_budget
from app.book_generation.cache import ChapterCache, GenerationState
from app.book_generation.constants import (
    BOOK_GENERATION_TRANSPORT_VERSION,
    BOOK_GENERATOR_PROMPT_VERSION,
    EVIDENCE_STRATEGY_HYDRATED,
    EVIDENCE_STRATEGY_SOURCE_MAP_ONLY,
    FALLBACK_SECTION,
    GENERATION_UNIT_CHAPTER,
    LANGUAGE_POLICY,
    PHASE,
    PUBLICATION_AUTHORIZED,
    REAL_PROVIDER_CALLS_THIS_PHASE,
    READY_FOR_REAL_BOOK_GENERATION,
    VALIDATION_PROJECT_NAME,
)
from app.book_generation.costing import estimate_production_cost
from app.book_generation.coverage import (
    assigned_idea_ids_for_chapter,
    coverage_policy_dict,
    deferred_idea_ids,
    excluded_idea_ids,
)
from app.book_generation.evidence import build_chapter_evidence, evidence_metrics
from app.book_generation.fakeai import run_fake_chapter
from app.book_generation.fixtures import (
    covering_chapter_transport,
    deferred_idea_transport,
    excluded_idea_transport,
    extra_section_transport,
    missing_idea_transport,
    missing_section_transport,
    tiny_book_source_map,
    tiny_editorial_plan,
    tiny_transcript_index,
    unknown_idea_transport,
    unknown_source_transport,
    unsourced_paragraph_transport,
    wrong_language_transport,
    wrong_order_transport,
)
from app.book_generation.guard import assert_no_v1_dependency, assert_offline_package
from app.book_generation.hydrate import (
    hydration_policy_dict,
    load_clean_transcript_index,
)
from app.book_generation.identity import load_production_inputs
from app.book_generation.language import language_policy_dict, resolve_canonical_language
from app.book_generation.models import BookIdentity
from app.book_generation.pipeline import (
    assemble_book,
    assembled_book_sha256,
    chapter_signature_for,
    materialize_chapter,
    remember_chapter,
)
from app.book_generation.preflight import (
    build_preflight_request,
    select_representative_chapters,
)
from app.book_generation.prompt_select import resolve_prompt_module
from app.book_generation.schema import schema_identity
from app.book_generation.settings import frozen_production_settings, thinking_recommendation
from app.book_generation.validator import (
    validate_book_precheck,
    validator_contract_dict,
)
from app.book_generation.writer import production_book_absent
from app.editorial_planning.language_policy import DOCUMENT_LANGUAGE_POLICY


def _status(ok: bool) -> str:
    return "PASS" if ok else "FAIL"


def _run_case(name: str, expect_fail: bool, result: dict[str, Any]) -> dict[str, Any]:
    status = str((result.get("validation") or {}).get("status") or "")
    failed = status == "FAIL"
    ok = failed if expect_fail else status != "FAIL"
    return {
        "name": name,
        "expected": "FAIL" if expect_fail else "PASS_OR_REVIEW",
        "got": status,
        "ok": ok,
        "errors": list((result.get("validation") or {}).get("errors") or []),
    }


def _synthetic_fakeai() -> dict[str, Any]:
    source_map = tiny_book_source_map(idea_count=5)
    deferred = (source_map.ideas[-2].idea_id,)
    excluded = (source_map.ideas[-1].idea_id,)
    plan = tiny_editorial_plan(source_map, deferred_ids=deferred, excluded_ids=excluded)
    language = source_map.primary_language
    index = tiny_transcript_index(source_map)
    chapter = plan.chapters[0]
    evidence = build_chapter_evidence(
        plan, source_map, chapter, language=language, hydrate=True, transcript_index=index
    )
    cases = [
        _run_case(
            "valid_chapter",
            False,
            run_fake_chapter(
                covering_chapter_transport(chapter),
                plan,
                source_map,
                chapter,
                language=language,
                evidence=evidence,
            ),
        ),
        _run_case(
            "missing_section",
            True,
            run_fake_chapter(
                missing_section_transport(chapter),
                plan,
                source_map,
                chapter,
                language=language,
                evidence=evidence,
            ),
        ),
        _run_case(
            "extra_section",
            True,
            run_fake_chapter(
                extra_section_transport(chapter),
                plan,
                source_map,
                chapter,
                language=language,
                evidence=evidence,
            ),
        ),
        _run_case(
            "wrong_order",
            True,
            run_fake_chapter(
                wrong_order_transport(chapter),
                plan,
                source_map,
                chapter,
                language=language,
                evidence=evidence,
            ),
        ),
        _run_case(
            "missing_idea",
            True,
            run_fake_chapter(
                missing_idea_transport(chapter),
                plan,
                source_map,
                chapter,
                language=language,
                evidence=evidence,
            ),
        ),
        _run_case(
            "unknown_idea",
            True,
            run_fake_chapter(
                unknown_idea_transport(chapter),
                plan,
                source_map,
                chapter,
                language=language,
                evidence=evidence,
            ),
        ),
        _run_case(
            "unknown_source",
            True,
            run_fake_chapter(
                unknown_source_transport(chapter),
                plan,
                source_map,
                chapter,
                language=language,
                evidence=evidence,
            ),
        ),
        _run_case(
            "unsourced_paragraph",
            True,
            run_fake_chapter(
                unsourced_paragraph_transport(chapter),
                plan,
                source_map,
                chapter,
                language=language,
                evidence=evidence,
            ),
        ),
    ]
    wrong_lang = run_fake_chapter(
        wrong_language_transport(chapter),
        plan,
        source_map,
        chapter,
        language=language,
        evidence=evidence,
    )
    wrong_lang_case = _run_case("wrong_language", True, wrong_lang)
    wrong_lang_case["ok"] = str((wrong_lang.get("validation") or {}).get("status")) in {
        "FAIL",
        "REVIEW",
    }
    cases.append(wrong_lang_case)
    cases.extend(
        [
            _run_case(
                "deferred_idea",
                True,
                run_fake_chapter(
                    deferred_idea_transport(chapter, deferred[0]),
                    plan,
                    source_map,
                    chapter,
                    language=language,
                    evidence=evidence,
                ),
            ),
            _run_case(
                "excluded_idea",
                True,
                run_fake_chapter(
                    excluded_idea_transport(chapter, excluded[0]),
                    plan,
                    source_map,
                    chapter,
                    language=language,
                    evidence=evidence,
                ),
            ),
        ]
    )
    connective = run_fake_chapter(
        covering_chapter_transport(chapter, include_connective=True),
        plan,
        source_map,
        chapter,
        language=language,
        evidence=evidence,
    )
    cases.append(
        _run_case("connective_paragraph", False, connective)
    )
    first = run_fake_chapter(
        covering_chapter_transport(chapter),
        plan,
        source_map,
        chapter,
        language=language,
        evidence=evidence,
    )
    second = run_fake_chapter(
        covering_chapter_transport(chapter),
        plan,
        source_map,
        chapter,
        language=language,
        evidence=evidence,
    )
    candidates = []
    for ch in plan.chapters:
        ev = build_chapter_evidence(
            plan, source_map, ch, language=language, hydrate=True, transcript_index=index
        )
        result = run_fake_chapter(
            covering_chapter_transport(ch),
            plan,
            source_map,
            ch,
            language=language,
            evidence=ev,
        )
        candidates.append(result["candidate"])
    identity = BookIdentity(
        source_map_sha256="synthetic",
        editorial_plan_sha256="synthetic",
    )
    book = assemble_book(
        candidates, plan, language=language, identity=identity
    )
    book2 = assemble_book(
        candidates, plan, language=language, identity=identity
    )
    precheck = validate_book_precheck(book, plan, source_map, language=language)
    deterministic = (
        first["candidate_sha256"] == second["candidate_sha256"]
        and assembled_book_sha256(book) == assembled_book_sha256(book2)
        and [p.paragraph_id for p in book.all_paragraphs()]
        == [p.paragraph_id for p in book2.all_paragraphs()]
    )
    settings = frozen_production_settings()
    prompt = resolve_prompt_module().prompt_bundle()
    schema = schema_identity()
    sig_a = chapter_signature_for(
        source_map_sha256="synthetic",
        editorial_plan_sha256="synthetic",
        chapter_id=chapter.chapter_id,
        prompt_sha256=prompt["prompt_sha256"],
        response_schema_sha256=schema["raw_schema_sha256"],
        language=language,
        evidence_bundle_sha256=str(evidence_metrics(evidence)["sha256"]),
        settings=settings,
    )
    cache = ChapterCache()
    remember_chapter(cache, sig_a, first["candidate_sha256"])
    sig_prompt = chapter_signature_for(
        source_map_sha256="synthetic",
        editorial_plan_sha256="synthetic",
        chapter_id=chapter.chapter_id,
        prompt_sha256="changed-prompt",
        response_schema_sha256=schema["raw_schema_sha256"],
        language=language,
        evidence_bundle_sha256=str(evidence_metrics(evidence)["sha256"]),
        settings=settings,
    )
    sig_plan = chapter_signature_for(
        source_map_sha256="synthetic",
        editorial_plan_sha256="changed-plan",
        chapter_id=chapter.chapter_id,
        prompt_sha256=prompt["prompt_sha256"],
        response_schema_sha256=schema["raw_schema_sha256"],
        language=language,
        evidence_bundle_sha256=str(evidence_metrics(evidence)["sha256"]),
        settings=settings,
    )
    sig_map = chapter_signature_for(
        source_map_sha256="changed-map",
        editorial_plan_sha256="synthetic",
        chapter_id=chapter.chapter_id,
        prompt_sha256=prompt["prompt_sha256"],
        response_schema_sha256=schema["raw_schema_sha256"],
        language=language,
        evidence_bundle_sha256=str(evidence_metrics(evidence)["sha256"]),
        settings=settings,
    )
    sig_lang = chapter_signature_for(
        source_map_sha256="synthetic",
        editorial_plan_sha256="synthetic",
        chapter_id=chapter.chapter_id,
        prompt_sha256=prompt["prompt_sha256"],
        response_schema_sha256=schema["raw_schema_sha256"],
        language="fr",
        evidence_bundle_sha256=str(evidence_metrics(evidence)["sha256"]),
        settings=settings,
    )
    sig_ev = chapter_signature_for(
        source_map_sha256="synthetic",
        editorial_plan_sha256="synthetic",
        chapter_id=chapter.chapter_id,
        prompt_sha256=prompt["prompt_sha256"],
        response_schema_sha256=schema["raw_schema_sha256"],
        language=language,
        evidence_bundle_sha256="changed-evidence",
        settings=settings,
    )
    state = GenerationState()
    state.remember_validated(plan.chapters[0].chapter_id, sig_a, first["candidate_sha256"])
    ch2_sig = chapter_signature_for(
        source_map_sha256="synthetic",
        editorial_plan_sha256="synthetic",
        chapter_id=plan.chapters[1].chapter_id,
        prompt_sha256=prompt["prompt_sha256"],
        response_schema_sha256=schema["raw_schema_sha256"],
        language=language,
        evidence_bundle_sha256="ch2",
        settings=settings,
    )
    state.remember_validated(plan.chapters[1].chapter_id, ch2_sig, "ch2hash")
    state.remember_failed("CH003", "scripted failure")
    cache_ok = (
        cache.is_hit(sig_a)
        and not cache.is_hit(sig_prompt)
        and not cache.is_hit(sig_plan)
        and not cache.is_hit(sig_map)
        and not cache.is_hit(sig_lang)
        and not cache.is_hit(sig_ev)
    )
    resume_ok = (
        state.reusable(plan.chapters[0].chapter_id, sig_a)
        and state.reusable(plan.chapters[1].chapter_id, ch2_sig)
        and not state.reusable("CH003", "anything")
    )
    all_ok = (
        all(case["ok"] for case in cases)
        and deterministic
        and cache_ok
        and resume_ok
        and precheck.status != "FAIL"
    )
    return {
        "status": _status(all_ok),
        "cases": cases,
        "connective_allowed": connective["validation"]["status"] != "FAIL",
        "determinism": deterministic,
        "cache": {
            "same_signature_hit": cache.is_hit(sig_a),
            "changed_prompt_miss": not cache.is_hit(sig_prompt),
            "changed_plan_miss": not cache.is_hit(sig_plan),
            "changed_source_map_miss": not cache.is_hit(sig_map),
            "changed_language_miss": not cache.is_hit(sig_lang),
            "changed_evidence_miss": not cache.is_hit(sig_ev),
            "ok": cache_ok,
        },
        "resume": {
            "ch001_reused": state.reusable(plan.chapters[0].chapter_id, sig_a),
            "ch002_reused": state.reusable(plan.chapters[1].chapter_id, ch2_sig),
            "ch003_failed_isolated": "CH003" in state.failed,
            "ok": resume_ok,
        },
        "assembled_book_sha256": assembled_book_sha256(book),
        "precheck": precheck.to_dict(),
        "engine_is_fake": True,
    }


def build_bundle(
    *,
    project_name: str = VALIDATION_PROJECT_NAME,
    sortie_dir: Path | None = None,
    tests: str = "offline Phase 4B.1",
    test_delta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    assert_offline_package()
    assert_no_v1_dependency()
    settings = frozen_production_settings()
    inputs = load_production_inputs(project_name, sortie_dir=sortie_dir)
    plan = inputs.plan
    source_map = inputs.source_map
    transcript_index = None
    transcript_identity: dict[str, Any] = {}
    try:
        transcript_index = load_clean_transcript_index(
            project_name, sortie_dir=sortie_dir
        )
        transcript_identity = transcript_index.to_identity()
    except Exception as exc:  # noqa: BLE001 — offline measurement must record absence
        transcript_identity = {"error": str(exc), "available": False}

    language = resolve_canonical_language(
        source_map_primary_language=source_map.primary_language,
        transcript_primary_language=(
            transcript_index.primary_language if transcript_index else None
        )
        or source_map.primary_language,
    )
    prompt = resolve_prompt_module().prompt_bundle()
    schema = schema_identity()
    thinking = thinking_recommendation()

    chapter_rows: list[dict[str, Any]] = []
    hydrated_budgets: list[dict[str, Any]] = []
    for chapter in plan.chapters:
        ideas = assigned_idea_ids_for_chapter(chapter)
        dry = build_chapter_evidence(
            plan,
            source_map,
            chapter,
            language=language,
            hydrate=False,
            transcript_index=None,
        )
        wet = build_chapter_evidence(
            plan,
            source_map,
            chapter,
            language=language,
            hydrate=True,
            transcript_index=transcript_index,
        )
        dry_budget = measure_request_budget(
            dry,
            settings=settings,
            idea_count=len(ideas),
            section_count=len(chapter.sections),
        )
        wet_budget = measure_request_budget(
            wet,
            settings=settings,
            idea_count=len(ideas),
            section_count=len(chapter.sections),
        )
        hydrated_budgets.append(wet_budget)
        chapter_rows.append(
            {
                "chapter_id": chapter.chapter_id,
                "title": chapter.working_title,
                "section_count": len(chapter.sections),
                "idea_count": len(ideas),
                "source_map_only": dry_budget,
                "hydrated": wet_budget,
                "evidence": evidence_metrics(wet),
                "generation_unit": wet_budget["generation_unit"],
                "fallback_triggered": wet_budget["fallback_triggered"],
            }
        )

    idea_summary_chars = [
        int((row["source_map_only"]["evidence"] or {}).get("idea_summary_chars") or 0)
        for row in chapter_rows
    ]
    hydrated_src_chars = [
        int((row["hydrated"]["evidence"] or {}).get("hydrated_src_chars") or 0)
        for row in chapter_rows
    ]
    all_hydrated_safe = all(bool(row["hydrated"]["context_safe"]) for row in chapter_rows)
    src_richer = sum(hydrated_src_chars) > max(1, sum(idea_summary_chars))
    strategy = (
        EVIDENCE_STRATEGY_HYDRATED
        if all_hydrated_safe and transcript_index is not None
        else EVIDENCE_STRATEGY_SOURCE_MAP_ONLY
    )
    hydration_yes = strategy == EVIDENCE_STRATEGY_HYDRATED
    outliers = [
        row["chapter_id"]
        for row in chapter_rows
        if row["fallback_triggered"]
    ]
    selected = select_representative_chapters(plan, chapter_rows)
    preflight = {
        name: build_preflight_request(
            plan,
            source_map,
            chapter,
            language=language,
            hydrate=hydration_yes,
            transcript_index=transcript_index,
            settings=settings,
        )
        for name, chapter in selected.items()
    }
    preflight_ok = all(
        bool(item.get("determinism"))
        and bool((item.get("content_audit") or {}).get("chapter_id_match"))
        and bool((item.get("content_audit") or {}).get("all_planned_sections"))
        and bool((item.get("content_audit") or {}).get("all_assigned_ideas"))
        and bool((item.get("budget") or {}).get("context_safe"))
        for item in preflight.values()
    ) and bool(preflight)
    cost = estimate_production_cost(hydrated_budgets)
    fakeai = _synthetic_fakeai()
    tracker = CostTracker()
    book_absent = production_book_absent(project_name, sortie_dir=sortie_dir)
    delta = dict(test_delta or {})
    src_chars = sum(hydrated_src_chars)
    summary_chars = sum(idea_summary_chars)
    # Evidence-based manuscript range from actual source text, not a
    # commercial target and not the per-IDEA output-budget heuristic.
    src_words = max(1, src_chars // 5)
    summary_words = max(1, summary_chars // 5)
    word_low = int(min(src_words, summary_words) * 0.8)
    word_high = int(max(src_words, summary_words) * 1.4)
    context_safe = all(bool(row["hydrated"]["context_safe"]) for row in chapter_rows)
    recommended_outputs = [
        int(row["hydrated"]["recommended_max_output"]) for row in chapter_rows
    ]
    overall = (
        inputs.status == "PASS"
        and fakeai["status"] == "PASS"
        and preflight_ok
        and context_safe
        and book_absent
        and REAL_PROVIDER_CALLS_THIS_PHASE == 0
        and PUBLICATION_AUTHORIZED is False
        and int(delta.get("new_failure_count") or 0) == 0
        and strategy in {EVIDENCE_STRATEGY_HYDRATED, EVIDENCE_STRATEGY_SOURCE_MAP_ONLY}
    )
    result = "PASS" if overall else "FAIL"
    if inputs.status == "BLOCKED":
        result = "BLOCKED"
    header = {
        "phase": PHASE,
        "result": result,
        "real_provider_calls": REAL_PROVIDER_CALLS_THIS_PHASE,
        "source_map_sha256": inputs.source_map_sha256,
        "editorial_plan_sha256": inputs.plan_sha256,
        "editorial_plan_status": "FROZEN",
        "canonical_language": language,
        "language_policy": LANGUAGE_POLICY,
        "production_model": f"{settings.provider} / {settings.model}",
        "book_generator_prompt": BOOK_GENERATOR_PROMPT_VERSION,
        "book_generation_transport": BOOK_GENERATION_TRANSPORT_VERSION,
        "schema_raw_bytes": schema["raw_schema_bytes"],
        "schema_adapted_bytes": schema["adapted_schema_bytes"],
        "schema_sha256": schema["raw_schema_sha256"],
        "adapted_schema_sha256": schema["adapted_schema_sha256"],
        "generation_unit": GENERATION_UNIT_CHAPTER,
        "fallback_unit": FALLBACK_SECTION,
        "evidence_strategy": strategy,
        "transcript_hydration": "YES" if hydration_yes else "NO",
        "transcript_artifact": transcript_identity.get("path")
        or transcript_identity.get("artifact"),
        "chapters": len(plan.chapters),
        "sections": len(plan.all_sections()),
        "ideas": len(source_map.ideas),
        "chapter_size_distribution": {
            "sections": distribution([row["section_count"] for row in chapter_rows]),
            "ideas": distribution([row["idea_count"] for row in chapter_rows]),
            "evidence_chars": distribution(
                [int(row["evidence"]["chars"]) for row in chapter_rows]
            ),
        },
        "outlier_chapters": outliers,
        "smallest_request": (preflight.get("smallest") or {}).get("chapter_id"),
        "median_request": (preflight.get("median") or {}).get("chapter_id"),
        "largest_request": (preflight.get("largest") or {}).get("chapter_id"),
        "context_safety": "PASS" if context_safe else "FAIL",
        "recommended_max_output": {
            "min": min(recommended_outputs) if recommended_outputs else 0,
            "max": max(recommended_outputs) if recommended_outputs else 0,
        },
        "thinking_policy": thinking["phase4b1_thinking_mode"],
        "expected_book_length_range": (
            f"{word_low}-{word_high} words (from source evidence, not a target)"
        ),
        "estimated_production_calls": cost["estimated_production_calls"],
        "estimated_production_cost": cost.get("total_cost_display"),
        "paragraph_traceability": "substantive→SRC via handles; connective allowed",
        "idea_accountability": "assigned must appear; deferred/excluded blocked",
        "section_accountability": "planned sections exactly once, order preserved",
        "cache_resume": "designed",
        "fakeai_tests": fakeai["status"],
        "tests": tests,
        "new_failures": int(delta.get("new_failure_count") or 0),
        "book_json": "NOT PUBLISHED",
        "ready_for_book_generator_grammar_canary": "YES" if result == "PASS" else "NO",
        "ready_for_real_book_generation": "NO",
        "next_action": "HUMAN REVIEW",
        "working_title": plan.selected_title,
        "deferred": len(deferred_idea_ids(plan)),
        "excluded": len(excluded_idea_ids(plan)),
        "cost_tracker_records": len(tracker.records),
        "document_language_policy": DOCUMENT_LANGUAGE_POLICY,
    }
    return {
        "header": header,
        "identity": inputs.to_dict(),
        "architecture": {
            "package": "app.book_generation",
            "authority": {
                "editorial_plan": "WHERE",
                "source_map": "WHAT",
                "book_generator": "HOW expressed as prose",
            },
            "generation_unit": GENERATION_UNIT_CHAPTER,
            "fallback_unit": FALLBACK_SECTION,
            "why_not_whole_book": [
                "context pressure",
                "output ceiling",
                "traceability loss",
                "coverage loss",
                "repair difficulty",
                "retry cost",
                "replay complexity",
            ],
            "why_chapter_level": [
                "bounded context",
                "bounded output",
                "chapter-level retry isolation",
                "stronger traceability",
                "coverage validation",
                "lower failure blast radius",
            ],
            "no_technical_chunks": True,
            "no_word_pdf": True,
            "publication_authorized": PUBLICATION_AUTHORIZED,
        },
        "input_contract": {
            "editorial_plan_reader": "load_published_editorial_plan",
            "source_map_reader": "load_published_source_map",
            "a35_candidate_read": False,
            "identity": inputs.to_dict(),
            "language": language_policy_dict(),
            "canonical_language": language,
        },
        "output_contract": {
            "artifact": "book.json (future, not published)",
            "semantic_only": True,
            "title_status": "working",
            "front_matter": False,
            "back_cover": False,
            "canonical_paragraph_ids": "P000001 locally during assembly",
        },
        "traceability_contract": {
            "substantive": "handles → SRC resolution required",
            "connective": "allowed without source claims; no new assertions",
            "handles": ["IDEA", "EX", "REF", "UNC", "SRC"],
            "provider_canonical_ids": False,
            "limitation": validator_contract_dict()["limitation"],
        },
        "evidence_strategy": {
            "decision": strategy,
            "rationale": (
                "SourceMap summaries are planning compressions. Targeted SRC "
                "hydration restores author wording, examples, and rhetorical "
                "texture when the chapter context budget remains safe."
            ),
            "source_map_summary_chars": sum(idea_summary_chars),
            "hydrated_src_chars": sum(hydrated_src_chars),
            "src_text_richer_than_summaries": src_richer,
            "all_hydrated_requests_context_safe": all_hydrated_safe,
            "full_source_map_per_chapter": False,
        },
        "hydration": {
            "policy": hydration_policy_dict(),
            "transcript": transcript_identity,
            "selected": hydration_yes,
            "strategy": strategy,
            "chapter_comparison": [
                {
                    "chapter_id": row["chapter_id"],
                    "idea_summary_chars": row["source_map_only"]["evidence"][
                        "idea_summary_chars"
                    ],
                    "hydrated_src_chars": row["hydrated"]["evidence"]["hydrated_src_chars"],
                    "dry_input_pessimistic": row["source_map_only"]["request"][
                        "provider_adjusted_pessimistic"
                    ],
                    "wet_input_pessimistic": row["hydrated"]["request"][
                        "provider_adjusted_pessimistic"
                    ],
                    "wet_context_safe": row["hydrated"]["context_safe"],
                }
                for row in chapter_rows
            ],
        },
        "generation_strategy": {
            "unit": GENERATION_UNIT_CHAPTER,
            "fallback": FALLBACK_SECTION,
            "order": [chapter.chapter_id for chapter in plan.chapters],
            "retry": {
                "policy": "one_real_call_per_generation_unit",
                "automatic_retries_during_canary": 0,
            },
            "continuity": "plan-derived previous chapter title/purpose only",
            "raw_response_preservation": "required on future real generation",
            "chapter_candidate_before_book": True,
            "assembly_calls_ai": False,
        },
        "schema_identity": schema,
        "prompt": prompt,
        "transport_identity": {
            "version": BOOK_GENERATION_TRANSPORT_VERSION,
            "schema_raw_sha256": schema["raw_schema_sha256"],
            "schema_adapted_sha256": schema["adapted_schema_sha256"],
        },
        "real_corpus_budget": {
            "chapters": [
                {
                    "chapter_id": row["chapter_id"],
                    "title": row["title"],
                    "section_count": row["section_count"],
                    "idea_count": row["idea_count"],
                    "evidence_chars": row["evidence"]["chars"],
                    "evidence_src_refs": row["evidence"]["src_ref_count"],
                    "input_pessimistic": row["hydrated"]["request"][
                        "provider_adjusted_pessimistic"
                    ],
                    "expected_output": row["hydrated"]["output"]["expected_output_tokens"],
                    "recommended_max_output": row["hydrated"]["recommended_max_output"],
                    "context_utilization": row["hydrated"]["context_utilization_pessimistic"],
                    "context_safe": row["hydrated"]["context_safe"],
                    "generation_unit": row["generation_unit"],
                }
                for row in chapter_rows
            ]
        },
        "chapter_distribution": header["chapter_size_distribution"],
        "cost_estimate": cost,
        "fakeai": fakeai,
        "preflight": preflight,
        "coverage_policy": coverage_policy_dict(),
        "validator_contract": validator_contract_dict(),
        "thinking": thinking,
        "settings": settings.to_dict(),
        "publication": {
            "book_json": "NOT PUBLISHED",
            "path_absent": book_absent,
            "authorized": PUBLICATION_AUTHORIZED,
        },
        "readiness": {
            "PHASE_4B1": "COMPLETE" if result == "PASS" else "INCOMPLETE",
            "READY_FOR_BOOK_GENERATOR_GRAMMAR_CANARY": result == "PASS",
            "READY_FOR_REAL_BOOK_GENERATION": READY_FOR_REAL_BOOK_GENERATION,
            "NEXT_ACTION": "HUMAN REVIEW",
        },
        "tests": tests,
        "test_delta": delta,
        "preflight_ok": preflight_ok,
        "hydration_decision_evidence": {
            "summaries_are_not_assumed_sufficient": True,
            "src_richer": src_richer,
            "budget_permits_hydration": all_hydrated_safe,
        },
    }
