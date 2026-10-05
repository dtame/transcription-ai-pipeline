"""One-shot human authorization for future real execution. Synthetic tests only."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from app.book_generation_bridge_4b214.constants import (
    AUTHORIZATION_VERSION,
    PHASE,
)
from app.book_generation_bridge_4b214.guard import BookGenerationBridge214Error


@dataclass
class HumanAuthorization:
    authorization_id: str
    phase: str
    chapter_id: str
    provider: str
    model: str
    max_calls: int
    max_budget_usd: float
    objective: str
    expected_artifacts: tuple[str, ...]
    stop_conditions: tuple[str, ...]
    issued_at: float
    expires_at: float
    consumed: bool = False
    consumed_at: float | None = None
    synthetic: bool = True
    real_execution_authorized: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "authorization_id": self.authorization_id,
            "phase": self.phase,
            "chapter_id": self.chapter_id,
            "provider": self.provider,
            "model": self.model,
            "max_calls": self.max_calls,
            "max_budget_usd": self.max_budget_usd,
            "objective": self.objective,
            "expected_artifacts": list(self.expected_artifacts),
            "stop_conditions": list(self.stop_conditions),
            "issued_at": self.issued_at,
            "expires_at": self.expires_at,
            "consumed": self.consumed,
            "consumed_at": self.consumed_at,
            "synthetic": self.synthetic,
            "real_execution_authorized": self.real_execution_authorized,
            "one_shot": True,
            "secrets_included": False,
        }


def mint_synthetic_authorization(
    *,
    authorization_id: str,
    chapter_id: str,
    provider: str,
    model: str,
    max_calls: int,
    max_budget_usd: float,
    objective: str,
    expected_artifacts: tuple[str, ...] = ("isolated_chapter_result",),
    stop_conditions: tuple[str, ...] = ("budget_exhausted", "block", "uncertain_send"),
    ttl_seconds: float = 3600,
    now: float | None = None,
) -> HumanAuthorization:
    issued = now if now is not None else time.time()
    return HumanAuthorization(
        authorization_id=authorization_id,
        phase=PHASE,
        chapter_id=chapter_id,
        provider=provider,
        model=model,
        max_calls=max_calls,
        max_budget_usd=max_budget_usd,
        objective=objective,
        expected_artifacts=expected_artifacts,
        stop_conditions=stop_conditions,
        issued_at=issued,
        expires_at=issued + ttl_seconds,
        consumed=False,
        synthetic=True,
        real_execution_authorized=False,
    )


def consume_authorization(
    authorization: HumanAuthorization,
    *,
    phase: str,
    chapter_id: str,
    provider: str,
    model: str,
    calls: int,
    budget_usd: float,
    now: float | None = None,
) -> dict[str, Any]:
    clock = now if now is not None else time.time()
    reasons: list[str] = []
    if authorization.consumed:
        reasons.append("authorization_consumed")
    if clock > authorization.expires_at:
        reasons.append("authorization_expired")
    if authorization.phase != phase:
        reasons.append("phase_incompatible")
    if authorization.chapter_id != chapter_id:
        reasons.append("chapter_incompatible")
    if authorization.provider != provider:
        reasons.append("provider_incompatible")
    if authorization.model != model:
        reasons.append("model_incompatible")
    if calls > authorization.max_calls:
        reasons.append("max_calls_exceeded")
    if budget_usd > authorization.max_budget_usd:
        reasons.append("max_budget_exceeded")
    if authorization.real_execution_authorized:
        reasons.append("real_execution_must_remain_false_in_4b214")
    if reasons:
        raise BookGenerationBridge214Error(
            "Human authorization refused: " + ", ".join(reasons)
        )
    authorization.consumed = True
    authorization.consumed_at = clock
    return {
        "ok": True,
        "authorization_id": authorization.authorization_id,
        "consumed": True,
        "one_shot": True,
        "reusable": False,
        "synthetic": True,
        "real_execution_authorized": False,
        "secrets_included": False,
    }


def human_authorization_document() -> dict[str, Any]:
    return {
        "phase": PHASE,
        "version": AUTHORIZATION_VERSION,
        "real_authorization_created_this_phase": False,
        "synthetic_test_authorizations_only": True,
        "required_fields": [
            "phase",
            "chapter_id",
            "provider",
            "model",
            "max_calls",
            "max_budget_usd",
            "objective",
            "expected_artifacts",
            "stop_conditions",
        ],
        "one_authorization_one_call": True,
        "consumed_expired_or_incompatible_blocks": True,
        "does_not_authorize_19_chapters": True,
        "does_not_authorize_phase5": True,
        "does_not_authorize_word_pdf": True,
        "secrets_included": False,
    }


__all__ = [
    "HumanAuthorization",
    "consume_authorization",
    "human_authorization_document",
    "mint_synthetic_authorization",
]
