"""Isolated bridge orchestration. FakeAI only. Budget, auth, single-chapter."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.book_generation_bridge_4b214.adapter import adapt_chapter_candidate
from app.book_generation_bridge_4b214.authorization import (
    HumanAuthorization,
    consume_authorization,
)
from app.book_generation_bridge_4b214.budget import BudgetGuard
from app.book_generation_bridge_4b214.constants import (
    BRIDGE_ENABLED,
    CODE_VERSION,
    DECISION_BLOCK,
    FAKEAI_SOURCE,
    INTERRUPT_AFTER_BLOCK,
    INTERRUPT_AFTER_RESERVATION,
    INTERRUPT_AFTER_RESPONSE,
    INTERRUPT_AFTER_REVIEW,
    INTERRUPT_AFTER_SEND,
    INTERRUPT_AFTER_VALIDATION,
    INTERRUPT_BEFORE_RESERVATION,
    INTERRUPT_BEFORE_SEND,
    LEDGER_SEMANTIC_GATE,
    PHASE,
    PRODUCTION_PIPELINE_HOOK,
    REAL_PROVIDERS_ENABLED,
)
from app.book_generation_bridge_4b214.guard import (
    BookGenerationBridge214Error,
    assert_offline_only,
)
from app.book_generation_bridge_4b214.review import apply_human_review
from app.book_generation_bridge_4b214.single_chapter import (
    SingleChapterMode,
    assert_no_other_chapters,
)
from app.book_generation_integration_4b213.cache import IsolatedChapterCache
from app.book_generation_integration_4b213.fakeai import (
    FakeGeneratorTransport,
    FakeSemanticTransport,
)
from app.book_generation_integration_4b213.orchestrator import orchestrate_chapter
from app.book_generation_integration_4b213.structure import iter_paragraphs


def _operation_id(chapter_id: str, paragraph_id: str, request_sha256: str) -> str:
    return f"{chapter_id}:{paragraph_id}:{request_sha256 or 'pending'}"


def run_bridge_chapter(
    *,
    scenario: str,
    chapter_id: str | None = None,
    generator: FakeGeneratorTransport | None = None,
    semantic: FakeSemanticTransport | None = None,
    cache: IsolatedChapterCache | None = None,
    budget: BudgetGuard | None = None,
    authorization: HumanAuthorization | None = None,
    single_chapter: SingleChapterMode | None = None,
    interrupt_at: str | None = None,
    human_review_action: str | None = None,
    input_tokens_estimate: int = 1247,
    output_token_cap: int = 8192,
) -> dict[str, Any]:
    assert_offline_only()
    if BRIDGE_ENABLED or PRODUCTION_PIPELINE_HOOK:
        raise BookGenerationBridge214Error("Bridge must stay disabled and disconnected.")
    if REAL_PROVIDERS_ENABLED:
        raise BookGenerationBridge214Error("Real providers are disabled in 4B.2.14.")
    generator = generator or FakeGeneratorTransport(scenario, chapter_id=chapter_id)
    semantic = semantic or FakeSemanticTransport(scenario)
    cache = cache or IsolatedChapterCache()
    budget = budget or BudgetGuard(
        ceilings={
            LEDGER_SEMANTIC_GATE: Decimal("5"),
            "global": Decimal("10"),
            "book_generator": Decimal("5"),
            "book_validator": None,
        },
        per_operation_ceiling=Decimal("0.25"),
    )
    produced = generator.produce_chapter({"scenario": scenario})
    requested_id = str(chapter_id or produced.get("chapter_id") or "")
    if single_chapter is not None:
        single_chapter.assert_allowed(requested_id)
        assert_no_other_chapters(requested_id, [requested_id])
        if produced.get("chapter_id") != requested_id:
            raise BookGenerationBridge214Error("single_chapter_only chapter mismatch.")
    adapted = adapt_chapter_candidate(produced, synthetic=True)
    if not adapted.get("ok"):
        return {
            "phase": PHASE,
            "ok": False,
            "decision": DECISION_BLOCK,
            "reason": "adapter_failed",
            "adapter": adapted,
            "interrupted": False,
            "production_cache_write": False,
            "source": FAKEAI_SOURCE,
            "not_terra": True,
            "not_sonnet": True,
            "bridge_enabled": False,
        }
    paragraphs = iter_paragraphs(produced)
    calls_needed = max(1, len(paragraphs))
    if authorization is not None:
        consume_authorization(
            authorization,
            phase=PHASE,
            chapter_id=requested_id,
            provider=FAKEAI_SOURCE,
            model="fakeai",
            calls=calls_needed,
            budget_usd=0.05,
        )
    if interrupt_at == INTERRUPT_BEFORE_RESERVATION:
        return {
            "phase": PHASE,
            "interrupted": True,
            "interrupt_at": interrupt_at,
            "decision": None,
            "sent": False,
            "automatic_retry": False,
            "production_cache_write": False,
            "chapter_id": requested_id,
            "source": FAKEAI_SOURCE,
        }
    reservations = []
    for para in paragraphs:
        pid = str(para.get("paragraph_id") or "")
        op_id = _operation_id(requested_id, pid, "pre-request")
        reserved = budget.reserve(
            provider=FAKEAI_SOURCE,
            model="fakeai",
            chapter_id=requested_id,
            operation="semantic_gate_paragraph",
            input_tokens=input_tokens_estimate,
            output_token_cap=output_token_cap,
            ledger=LEDGER_SEMANTIC_GATE,
            operation_id=op_id,
        )
        if not reserved.get("authorized") and not reserved.get("idempotent_reuse"):
            return {
                "phase": PHASE,
                "ok": False,
                "decision": DECISION_BLOCK,
                "reason": reserved.get("reason"),
                "budget": reserved,
                "interrupted": False,
                "sent": False,
                "production_cache_write": False,
                "source": FAKEAI_SOURCE,
            }
        reservations.append(reserved)
    if interrupt_at == INTERRUPT_AFTER_RESERVATION:
        return {
            "phase": PHASE,
            "interrupted": True,
            "interrupt_at": interrupt_at,
            "decision": None,
            "sent": False,
            "reservations": reservations,
            "automatic_retry": False,
            "production_cache_write": False,
            "chapter_id": requested_id,
            "source": FAKEAI_SOURCE,
        }
    if interrupt_at == INTERRUPT_BEFORE_SEND:
        return {
            "phase": PHASE,
            "interrupted": True,
            "interrupt_at": interrupt_at,
            "decision": None,
            "sent": False,
            "reservations": reservations,
            "automatic_retry": False,
            "production_cache_write": False,
            "chapter_id": requested_id,
            "source": FAKEAI_SOURCE,
        }
    if interrupt_at == INTERRUPT_AFTER_SEND:
        for item in reservations:
            if item.get("idempotent_reuse") or not item.get("reservation_id"):
                continue
            budget.mark_sent(item["reservation_id"])
            budget.reconcile(
                item["reservation_id"],
                outcome="interrupt_after_send",
                input_tokens=None,
                output_tokens=None,
            )
        return {
            "phase": PHASE,
            "interrupted": True,
            "interrupt_at": interrupt_at,
            "decision": DECISION_BLOCK,
            "sent": True,
            "send_uncertain": True,
            "automatic_retry": False,
            "treated_as_free": False,
            "reservations": reservations,
            "budget_snapshot": budget.snapshot(),
            "production_cache_write": False,
            "chapter_id": requested_id,
            "source": FAKEAI_SOURCE,
        }

    result = orchestrate_chapter(
        scenario=scenario,
        generator=generator,
        semantic=semantic,
        cache=cache,
        interrupt_at=None,
    )
    if interrupt_at == INTERRUPT_AFTER_RESPONSE:
        for item in reservations:
            if item.get("idempotent_reuse") or not item.get("reservation_id"):
                continue
            budget.mark_sent(item["reservation_id"])
            budget.reconcile(
                item["reservation_id"],
                outcome="usage_absent",
                input_tokens=None,
                output_tokens=None,
            )
        result = dict(result)
        result["interrupted"] = True
        result["interrupt_at"] = interrupt_at
        result["automatic_retry"] = False
        result["bridge_enabled"] = False
        result["adapter"] = adapted
        return result

    usage_outcome = "full_known"
    in_tok: int | None = input_tokens_estimate
    out_tok: int | None = 316
    if interrupt_at == INTERRUPT_AFTER_VALIDATION:
        usage_outcome = "full_known"
    for item in reservations:
        if item.get("idempotent_reuse") or not item.get("reservation_id"):
            continue
        budget.mark_sent(item["reservation_id"])
        budget.reconcile(
            item["reservation_id"],
            outcome=usage_outcome,
            input_tokens=in_tok,
            output_tokens=out_tok,
        )
    review = None
    decision = result.get("decision")
    if human_review_action and decision in {DECISION_BLOCK, "REVIEW", "PASS"}:
        review = apply_human_review(
            result,
            action=human_review_action,
            reviewer="SYNTHETIC_REVIEWER",
            note="4B.2.14 simulated human review",
        )
    if interrupt_at == INTERRUPT_AFTER_VALIDATION:
        result = dict(result)
        result["interrupted"] = True
        result["interrupt_at"] = interrupt_at
    if interrupt_at == INTERRUPT_AFTER_REVIEW and decision == "REVIEW":
        result = dict(result)
        result["interrupted"] = True
        result["interrupt_at"] = interrupt_at
    if interrupt_at == INTERRUPT_AFTER_BLOCK and decision == DECISION_BLOCK:
        result = dict(result)
        result["interrupted"] = True
        result["interrupt_at"] = interrupt_at
    payload = dict(result)
    payload.update(
        {
            "phase": PHASE,
            "bridge_module": CODE_VERSION,
            "bridge_enabled": False,
            "adapter": adapted,
            "budget_snapshot": budget.snapshot(),
            "reservations": reservations,
            "human_review": review,
            "single_chapter_locked": bool(single_chapter and single_chapter.enabled),
            "automatic_retry": False,
            "real_providers_enabled": False,
            "source": FAKEAI_SOURCE,
            "not_terra": True,
            "not_sonnet": True,
        }
    )
    return payload


__all__ = ["run_bridge_chapter"]
