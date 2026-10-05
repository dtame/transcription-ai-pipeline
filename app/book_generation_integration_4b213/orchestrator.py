"""Isolated chapter orchestration. FakeAI only. Not connected to production."""

from __future__ import annotations

from typing import Any, Mapping

from app.book_generation.constants import PARAGRAPH_KIND_SUBSTANTIVE
from app.book_generation_integration_4b213.cache import (
    IsolatedChapterCache,
    state_from_decision,
    validation_key,
)
from app.book_generation_integration_4b213.constants import (
    CACHE_GENERATION_OBTAINED,
    CACHE_INTERRUPTED,
    CACHE_VALIDATION_PENDING,
    CODE_VERSION,
    DECISION_BLOCK,
    FAKEAI_SOURCE,
    INTEGRATION_CONTRACT_VERSION,
    INTERRUPT_AFTER_BLOCK,
    INTERRUPT_AFTER_GENERATION,
    INTERRUPT_AFTER_PASS,
    INTERRUPT_AFTER_REVIEW,
    INTERRUPT_BEFORE_VALIDATION,
    INTERRUPT_DURING_VALIDATION,
    OFFSET_CONVENTION,
    PHASE,
    PREPARATION_ALGORITHM_VERSION,
    PRODUCTION_CACHE_ACCEPTANCE,
    PRODUCTION_PIPELINE_HOOK,
    PROMPT_VERSION_202_CANDIDATE,
    TRANSPORT_VERSION_20_CANDIDATE,
    VALIDATOR_IMPLEMENTATION_VERSION,
)
from app.book_generation_integration_4b213.evidence import (
    evidence_bundle_hash,
    validate_paragraph_evidence,
)
from app.book_generation_integration_4b213.fakeai import (
    FakeGeneratorTransport,
    FakeSemanticTransport,
)
from app.book_generation_integration_4b213.guard import (
    BookGenerationIntegration213Error,
    assert_offline_only,
)
from app.book_generation_integration_4b213.policy import (
    apply_chapter_policy,
    apply_paragraph_policy,
)
from app.book_generation_integration_4b213.request import build_semantic_request
from app.book_generation_integration_4b213.structure import (
    iter_paragraphs,
    validate_chapter_structure,
)
from app.book_semantic_gate_4b29.coverage import validate_prepared_coverage
from app.book_semantic_gate_4b29.preparation import prepare_paragraph_units
from app.book_semantic_gate_4b212.validator import validate_response_202
from app.file_utils import content_hash


def _empty_validation(*, errors: list[str], prepared: Mapping[str, Any], raw: Any) -> dict[str, Any]:
    return {
        "ok": False,
        "status": DECISION_BLOCK,
        "errors": errors,
        "parsed": None,
        "verdicts": [],
        "required_unit_ids": [unit["unit_id"] for unit in prepared.get("units") or []],
        "raw_preserved": True,
        "raw_type": type(raw).__name__,
    }


def orchestrate_chapter(
    *,
    scenario: str,
    generator: FakeGeneratorTransport | None = None,
    semantic: FakeSemanticTransport | None = None,
    cache: IsolatedChapterCache | None = None,
    interrupt_at: str | None = None,
) -> dict[str, Any]:
    """Run the isolated candidate pipeline on one FakeAI chapter.

    Never contacts a provider. Never writes production cache.
    """
    assert_offline_only()
    if PRODUCTION_PIPELINE_HOOK:
        raise BookGenerationIntegration213Error("Production hook must stay disconnected.")
    generator = generator or FakeGeneratorTransport(scenario)
    semantic = semantic or FakeSemanticTransport(scenario)
    cache = cache or IsolatedChapterCache()
    chapter = generator.produce_chapter({"scenario": scenario})
    paragraphs = iter_paragraphs(chapter)
    paragraph_ids = [str(item.get("paragraph_id") or "") for item in paragraphs]
    all_handles = [
        str(handle)
        for para in paragraphs
        for handle in para.get("evidence_handles") or []
    ]
    bundle_hash = evidence_bundle_hash(all_handles)
    text_hash = str(chapter.get("generated_text_sha256") or content_hash(""))
    key = validation_key(
        generated_text_sha256=text_hash,
        chapter_id=str(chapter.get("chapter_id") or ""),
        paragraph_ids=paragraph_ids,
        source_map_sha256=str(chapter.get("source_map_sha256") or ""),
        editorial_plan_sha256=str(chapter.get("editorial_plan_sha256") or ""),
        evidence_bundle_sha256=bundle_hash,
    )
    generation_record = {
        "state": CACHE_GENERATION_OBTAINED,
        "chapter_id": chapter.get("chapter_id"),
        "scenario": scenario,
        "source": FAKEAI_SOURCE,
        "not_sonnet": True,
        "generated_text_sha256": text_hash,
        "key": key,
        "presented_as_validated_chapter": False,
        "isolated_acceptance_candidate": False,
        "decision": None,
    }
    cache.store(key, generation_record)
    if interrupt_at == INTERRUPT_AFTER_GENERATION:
        return _result(
            chapter,
            cache,
            key,
            decision=None,
            state=CACHE_GENERATION_OBTAINED,
            interrupted=True,
            interrupt_at=interrupt_at,
            paragraph_results=[],
            structure=None,
        )
    structure = validate_chapter_structure(chapter)
    pending = dict(generation_record)
    pending["state"] = CACHE_VALIDATION_PENDING
    cache.store(key, pending)
    if interrupt_at == INTERRUPT_BEFORE_VALIDATION:
        return _result(
            chapter,
            cache,
            key,
            decision=None,
            state=CACHE_VALIDATION_PENDING,
            interrupted=True,
            interrupt_at=interrupt_at,
            paragraph_results=[],
            structure=structure,
        )

    paragraph_results: list[dict[str, Any]] = []
    interrupted = False
    technical_error = False
    for index, para in enumerate(paragraphs):
        if interrupt_at == INTERRUPT_DURING_VALIDATION and index >= 1:
            interrupted = True
            paragraph_results.append(
                {
                    "paragraph_id": para.get("paragraph_id"),
                    "decision": DECISION_BLOCK,
                    "interrupted": True,
                    "raw": None,
                    "structure_ok": True,
                    "evidence_ok": True,
                    "source": FAKEAI_SOURCE,
                }
            )
            break
        evidence = validate_paragraph_evidence(
            para,
            allowed_handles=list(chapter.get("allowed_evidence_handles") or []),
            synthetic_chapter=bool(chapter.get("synthetic")),
        )
        prepared = prepare_paragraph_units(
            str(para.get("paragraph_id") or ""),
            str(para.get("text") or ""),
            context={
                "chapter_id": chapter.get("chapter_id"),
                "section_id": para.get("section_id"),
            },
            evidence_handles=list(para.get("evidence_handles") or []),
        )
        coverage = validate_prepared_coverage(prepared)
        request = build_semantic_request(
            prepared,
            chapter_id=str(chapter.get("chapter_id") or ""),
            section_id=str(para.get("section_id") or ""),
            generator_prompt_version=str(chapter.get("generator_prompt_version") or ""),
            source_map_sha256=str(chapter.get("source_map_sha256") or ""),
            editorial_plan_sha256=str(chapter.get("editorial_plan_sha256") or ""),
        )
        request["paragraph_kind"] = para.get("kind")
        raw: Any = None
        if not structure.get("ok") or not evidence.get("ok") or not coverage.get("ok"):
            errors = list(structure.get("errors") or [])
            errors.extend(evidence.get("errors") or [])
            if not coverage.get("ok"):
                errors.append("coverage_invalid")
            validation = _empty_validation(errors=errors, prepared=prepared, raw=None)
        else:
            try:
                raw = semantic.evaluate(request)
            except BookGenerationIntegration213Error as exc:
                interrupted = True
                technical_error = "interrupt" not in str(exc).lower()
                paragraph_results.append(
                    {
                        "paragraph_id": para.get("paragraph_id"),
                        "decision": DECISION_BLOCK,
                        "interrupted": True,
                        "error": str(exc),
                        "raw": None,
                        "structure_ok": structure.get("ok"),
                        "evidence_ok": evidence.get("ok"),
                        "source": FAKEAI_SOURCE,
                    }
                )
                break
            if raw is None:
                validation = _empty_validation(
                    errors=["missing_response"],
                    prepared=prepared,
                    raw=None,
                )
            else:
                validation = validate_response_202(
                    raw,
                    prepared,
                    allowed_evidence=list(prepared.get("evidence_handles") or []),
                    expected_chapter=str(chapter.get("chapter_id") or ""),
                )
        policy = apply_paragraph_policy(prepared, coverage, validation)
        reconstructed = "".join(
            str(unit.get("text") or "") for unit in prepared.get("units") or []
        )
        paragraph_results.append(
            {
                "paragraph_id": para.get("paragraph_id"),
                "section_id": para.get("section_id"),
                "chapter_id": chapter.get("chapter_id"),
                "kind": para.get("kind"),
                "text": para.get("text"),
                "evidence_handles": list(para.get("evidence_handles") or []),
                "source_refs": list(para.get("source_refs") or []),
                "prepared": prepared,
                "coverage": coverage,
                "request": {
                    "request_sha256": request.get("request_sha256"),
                    "model_asked_to_emit_offsets": False,
                    "human_labels_included": False,
                    "not_a_terra_request": True,
                },
                "raw": raw,
                "validation": validation,
                "policy": policy,
                "decision": policy.get("decision"),
                "structure_ok": structure.get("ok"),
                "evidence_ok": evidence.get("ok"),
                "coverage_ok": coverage.get("ok"),
                "reconstructed_equals_paragraph": reconstructed == str(para.get("text") or ""),
                "offset_convention": OFFSET_CONVENTION,
                "source": FAKEAI_SOURCE,
                "not_terra": True,
                "substantive": para.get("kind") == PARAGRAPH_KIND_SUBSTANTIVE,
            }
        )

    chapter_policy = apply_chapter_policy(paragraph_results)
    decision = str(chapter_policy.get("decision") or DECISION_BLOCK)
    if interrupt_at == INTERRUPT_AFTER_PASS and decision != "PASS":
        interrupt_at = None
    if interrupt_at == INTERRUPT_AFTER_REVIEW and decision != "REVIEW":
        interrupt_at = None
    if interrupt_at == INTERRUPT_AFTER_BLOCK and decision != "BLOCK":
        interrupt_at = None
    if interrupt_at in {
        INTERRUPT_AFTER_PASS,
        INTERRUPT_AFTER_REVIEW,
        INTERRUPT_AFTER_BLOCK,
    }:
        interrupted = True
    state = state_from_decision(
        decision,
        interrupted=interrupted,
        error=technical_error,
    )
    if interrupted and interrupt_at in {INTERRUPT_DURING_VALIDATION}:
        state = CACHE_INTERRUPTED
        decision = DECISION_BLOCK
        chapter_policy = dict(chapter_policy)
        chapter_policy["decision"] = DECISION_BLOCK
        chapter_policy["isolated_acceptance_candidate"] = False
        chapter_policy["reasons"] = list(chapter_policy.get("reasons") or []) + [
            "interrupted_during_validation"
        ]
    if interrupted and interrupt_at in {
        INTERRUPT_AFTER_GENERATION,
        INTERRUPT_BEFORE_VALIDATION,
    }:
        state = CACHE_INTERRUPTED if interrupt_at == INTERRUPT_AFTER_GENERATION else CACHE_VALIDATION_PENDING
    candidate = (
        state == "VALIDATION_PASS"
        and decision == "PASS"
        and not interrupted
        and not PRODUCTION_CACHE_ACCEPTANCE
    )
    presented = False
    cache.store(
        key,
        {
            "state": state if not interrupted else (
                CACHE_INTERRUPTED
                if interrupt_at
                in {
                    INTERRUPT_AFTER_GENERATION,
                    INTERRUPT_DURING_VALIDATION,
                    INTERRUPT_AFTER_PASS,
                    INTERRUPT_AFTER_REVIEW,
                    INTERRUPT_AFTER_BLOCK,
                }
                else CACHE_VALIDATION_PENDING
            ),
            "decision": decision,
            "chapter_id": chapter.get("chapter_id"),
            "scenario": scenario,
            "source": FAKEAI_SOURCE,
            "not_sonnet": True,
            "not_terra": True,
            "generated_text_sha256": text_hash,
            "key": key,
            "versions": {
                "semantic_contract": PROMPT_VERSION_202_CANDIDATE,
                "semantic_transport": TRANSPORT_VERSION_20_CANDIDATE,
                "preparation": PREPARATION_ALGORITHM_VERSION,
                "validator": VALIDATOR_IMPLEMENTATION_VERSION,
                "integration": INTEGRATION_CONTRACT_VERSION,
                "code": CODE_VERSION,
            },
            "isolated_acceptance_candidate": candidate,
            "presented_as_validated_chapter": presented,
            "production_cache_write": False,
            "historical_partial_converted": False,
            "paragraph_ids": paragraph_ids,
            "evidence_bundle_sha256": bundle_hash,
        },
    )
    return _result(
        chapter,
        cache,
        key,
        decision=decision,
        state=cache.lookup(key).get("state") if cache.lookup(key) else state,
        interrupted=interrupted,
        interrupt_at=interrupt_at,
        paragraph_results=paragraph_results,
        structure=structure,
        chapter_policy=chapter_policy,
        candidate=candidate,
    )


def _result(
    chapter: Mapping[str, Any],
    cache: IsolatedChapterCache,
    key: str,
    *,
    decision: str | None,
    state: str,
    interrupted: bool,
    interrupt_at: str | None,
    paragraph_results: list[dict[str, Any]],
    structure: Mapping[str, Any] | None,
    chapter_policy: Mapping[str, Any] | None = None,
    candidate: bool = False,
) -> dict[str, Any]:
    record = cache.lookup(key) or {}
    accepted = bool(candidate) and state != CACHE_INTERRUPTED
    return {
        "phase": PHASE,
        "scenario": chapter.get("scenario"),
        "chapter": chapter,
        "chapter_id": chapter.get("chapter_id"),
        "decision": decision,
        "state": record.get("state") or state,
        "interrupted": interrupted,
        "interrupt_at": interrupt_at,
        "structure": structure,
        "paragraph_results": paragraph_results,
        "chapter_policy": chapter_policy or {},
        "key": key,
        "cache_record": record,
        "isolated_acceptance_candidate": accepted,
        "presented_as_validated_chapter": False,
        "production_cache_write": False,
        "production_pipeline_hook": PRODUCTION_PIPELINE_HOOK,
        "source": FAKEAI_SOURCE,
        "not_terra": True,
        "not_sonnet": True,
        "accepted_without_validation": False,
        "secrets_included": False,
    }


__all__ = ["orchestrate_chapter"]
