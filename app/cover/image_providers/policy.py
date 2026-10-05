"""Paid image calls stay refused until an explicit, bounded authorization exists."""

from __future__ import annotations

from typing import Any

from app.cover.constants import (
    AUTOMATIC_PAID_RETRIES,
    DEFAULT_PAID_PROVIDER,
    PAID_CALLS_AUTHORIZED,
)


class PaidCallRefused(RuntimeError):
    def __init__(self, reasons: list[str]) -> None:
        self.reasons = list(reasons)
        super().__init__("paid image call refused: " + ", ".join(self.reasons))


def empty_paid_authorization() -> dict[str, Any]:
    return {
        "explicit": False,
        "provider_id": None,
        "model_name": None,
        "max_images": None,
        "max_budget_usd": None,
        "network_calls_allowed": False,
        "prior_phase_unspent_budget_usd": None,
        "selected_paid_provider": DEFAULT_PAID_PROVIDER,
    }


def evaluate_paid_call(
    *,
    authorization: dict[str, Any],
    request: dict[str, Any],
    estimate_usd: float | None,
    foundation_lock: bool = True,
) -> dict[str, Any]:
    reasons: list[str] = []
    if not authorization.get("explicit"):
        reasons.append("explicit_authorization_missing")
    if authorization.get("prior_phase_unspent_budget_usd") not in (None, 0) and not authorization.get(
        "explicit"
    ):
        reasons.append("prior_phase_unspent_budget_is_not_authorization")
    if authorization.get("provider_id") != request.get("provider_id") or not request.get("provider_id"):
        reasons.append("provider_not_authorized")
    if authorization.get("model_name") != request.get("model_name") or not request.get("model_name"):
        reasons.append("model_not_authorized")
    max_images = authorization.get("max_images")
    image_count = int(request.get("image_count") or 0)
    if max_images is None:
        reasons.append("image_count_not_authorized")
    elif image_count > int(max_images):
        reasons.append("image_count_exceeds_authorization")
    budget = authorization.get("max_budget_usd")
    if budget is None:
        reasons.append("budget_cap_undefined")
    if estimate_usd is None:
        reasons.append("estimated_cost_unknown")
    elif budget is not None and float(estimate_usd) > float(budget):
        reasons.append("estimated_cost_exceeds_cap")
    if authorization.get("network_calls_allowed") is not True:
        reasons.append("network_calls_not_authorized")
    if foundation_lock:
        reasons.append("paid_calls_disabled")
    return {
        "allowed": not reasons,
        "reasons": reasons,
        "automatic_retries": AUTOMATIC_PAID_RETRIES,
        "estimate_usd": estimate_usd,
    }


def refuse_paid_call(
    *,
    authorization: dict[str, Any],
    request: dict[str, Any],
    estimate_usd: float | None,
    foundation_lock: bool = True,
) -> None:
    decision = evaluate_paid_call(
        authorization=authorization,
        request=request,
        estimate_usd=estimate_usd,
        foundation_lock=foundation_lock,
    )
    if not decision["allowed"]:
        raise PaidCallRefused(decision["reasons"])


def paid_retry_allowed() -> bool:
    return AUTOMATIC_PAID_RETRIES


def paid_provider_policy_document() -> dict[str, Any]:
    return {
        "default_paid_provider": DEFAULT_PAID_PROVIDER,
        "paid_calls_authorized": PAID_CALLS_AUTHORIZED,
        "automatic_retries": AUTOMATIC_PAID_RETRIES,
        "secrets": {
            "storage": "environment_variable_reference_only",
            "values_written_to_repository": False,
            "values_written_to_cover_record": False,
        },
        "required_before_a_paid_call": [
            "explicit_authorization",
            "authorized_provider",
            "authorized_model",
            "authorized_image_count",
            "defined_budget_cap",
            "known_estimate_at_or_below_cap",
            "network_calls_allowed",
        ],
        "prior_phase_unspent_budget_is_authorization": False,
        "failure_policy": "stop_without_automatic_paid_retry",
        "cost_history": [],
    }


__all__ = [
    "PaidCallRefused",
    "empty_paid_authorization",
    "evaluate_paid_call",
    "paid_provider_policy_document",
    "paid_retry_allowed",
    "refuse_paid_call",
]
