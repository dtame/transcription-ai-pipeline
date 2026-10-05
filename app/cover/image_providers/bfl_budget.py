"""Explicit authorization and a persistent one-shot reservation.

A reservation is consumed even when the provider outcome is unknown.
It is never released for an automatic retry, and a budget left from an
earlier phase is not an authorization.
"""

from __future__ import annotations

import json
import os
import time
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.cover.image_providers.bfl_spec import OFFICIAL_MODEL_ID, PROVIDER_ID
from app.cover.image_providers.policy import evaluate_paid_call


class BudgetError(RuntimeError):
    """The reservation ledger could not be updated safely."""


def default_authorization() -> dict[str, Any]:
    return {
        "enabled": False,
        "explicit": False,
        "provider_id": PROVIDER_ID,
        "model_name": OFFICIAL_MODEL_ID,
        "max_images": 0,
        "max_budget_usd": 0,
        "max_total_cost_usd": 0,
        "allow_paid_calls": False,
        "network_calls_allowed": False,
        "dry_run": True,
        "prior_phase_unspent_budget_usd": None,
    }


def collect_block_reasons(
    *,
    authorization: dict[str, Any] | None,
    request: dict[str, Any],
    estimate_usd: float | None,
    api_key_present: bool,
    dry_run: bool,
    honor_global_paid_lock: bool,
    allow_mock_submission: bool,
    ledger_summary: dict[str, Any],
) -> list[str]:
    auth = authorization or {}
    reasons: list[str] = []
    if authorization is None or not auth.get("explicit"):
        reasons.append("explicit_authorization_missing")
    if not auth.get("enabled"):
        reasons.append("authorization_disabled")
    if auth.get("allow_paid_calls") is not True:
        reasons.append("paid_calls_not_allowed")
    if dry_run or auth.get("dry_run") is True:
        reasons.append("dry_run")
    if not api_key_present:
        reasons.append("api_key_missing")
    if honor_global_paid_lock:
        reasons.append("paid_calls_disabled")
    if not allow_mock_submission:
        reasons.append("network_transport_sealed")
    shared = evaluate_paid_call(
        authorization={
            "explicit": bool(auth.get("explicit")),
            "provider_id": auth.get("provider_id"),
            "model_name": auth.get("model_name"),
            "max_images": auth.get("max_images"),
            "max_budget_usd": auth.get("max_budget_usd", auth.get("max_total_cost_usd")),
            "network_calls_allowed": auth.get("network_calls_allowed"),
            "prior_phase_unspent_budget_usd": auth.get("prior_phase_unspent_budget_usd"),
        },
        request=request,
        estimate_usd=estimate_usd,
        foundation_lock=False,
    )
    reasons.extend(reason for reason in shared["reasons"] if reason not in reasons)
    budget = auth.get("max_budget_usd", auth.get("max_total_cost_usd"))
    if budget is not None and float(budget) <= 0:
        reasons.append("budget_zero")
    images_reserved = int(ledger_summary.get("images_reserved") or 0)
    max_images = auth.get("max_images")
    image_count = int(request.get("image_count") or 0)
    if max_images is not None and images_reserved >= int(max_images):
        reasons.append("images_exhausted")
    if images_reserved > 0:
        reasons.append("authorization_already_consumed")
    if ledger_summary.get("outcome_unknown"):
        reasons.append("prior_outcome_unknown")
    reserved_cents = int(ledger_summary.get("reserved_cents") or 0)
    if budget is not None and estimate_usd is not None:
        if reserved_cents + usd_to_cents(estimate_usd) > usd_to_cents(budget):
            if reserved_cents:
                reasons.append("budget_exhausted")
    if image_count != 1:
        reasons.append("endpoint_accepts_one_image")
    return list(dict.fromkeys(reasons))


def usd_to_cents(value: float) -> int:
    quantized = (Decimal(str(value)) * Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return int(quantized)


class ReservationLedger:
    """File ledger guarded by an exclusive lock file."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.lock_path = self.path.with_suffix(".lock")

    def summary(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"images_reserved": 0, "reserved_cents": 0, "outcome_unknown": False, "reservations": []}
        with self._locked():
            return self._summary(self._read())

    def reserve(self, *, estimate_usd: float, image_count: int, max_images: int, max_budget_usd: float) -> dict[str, Any]:
        with self._locked():
            state = self._read()
            current = self._summary(state)
            reasons: list[str] = []
            if current["images_reserved"] + image_count > max_images or current["images_reserved"]:
                reasons.append("authorization_already_consumed")
            if current["outcome_unknown"]:
                reasons.append("prior_outcome_unknown")
            incoming = usd_to_cents(estimate_usd)
            if current["reserved_cents"] + incoming > usd_to_cents(max_budget_usd):
                reasons.append("budget_exhausted")
            if reasons:
                from app.cover.image_providers.policy import PaidCallRefused

                raise PaidCallRefused(list(dict.fromkeys(reasons)))
            record = {
                "reservation_id": uuid4().hex,
                "status": "reserved",
                "image_count": image_count,
                "reserved_cents": incoming,
                "task_id": None,
                "retry_count": 0,
                "automatic_retry": False,
            }
            state["reservations"].append(record)
            self._write(state)
            return dict(record)

    def mark(self, reservation_id: str, status: str, **fields: Any) -> dict[str, Any]:
        with self._locked():
            state = self._read()
            found = None
            for record in state["reservations"]:
                if record["reservation_id"] == reservation_id:
                    record["status"] = status
                    record["retry_count"] = 0
                    record.update(fields)
                    found = dict(record)
            if found is None:
                raise BudgetError("reservation disappeared before it could be marked")
            self._write(state)
            return found

    def get_authorization(self, authorization_id: str | None) -> dict[str, Any] | None:
        """Read one authorization row. Does not create a ledger."""

        if not authorization_id or not self.path.exists():
            return None
        with self._locked():
            state = self._read()
            for record in state.get("authorizations") or []:
                if record.get("authorization_id") == authorization_id:
                    return dict(record)
        return None

    def mutate(self, function: Any) -> Any:
        """Apply one locked update to the existing ledger.

        ``function`` receives the ledger dict and returns
        ``{"write": bool, "result": ..., "error": list[str] | None}``.
        A policy error is raised after a requested write so a terminal
        status such as EXPIRED is durable.
        """

        with self._locked():
            state = self._read()
            state.setdefault("authorizations", [])
            outcome = function(state)
            if not isinstance(outcome, dict):
                raise BudgetError("ledger mutation returned an unreadable result")
            if outcome.get("write"):
                self._write(state)
            error = outcome.get("error")
            if error:
                from app.cover.image_providers.policy import PaidCallRefused

                raise PaidCallRefused(list(error))
            return outcome.get("result")

    def _summary(self, state: dict[str, Any]) -> dict[str, Any]:
        rows = list(state.get("reservations") or [])
        return {
            "images_reserved": sum(int(row.get("image_count") or 0) for row in rows),
            "reserved_cents": sum(int(row.get("reserved_cents") or 0) for row in rows),
            "outcome_unknown": any(row.get("status") == "outcome_unknown" for row in rows),
            "reservations": rows,
        }

    def _read(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"reservations": []}
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or not isinstance(payload.get("reservations"), list):
            raise BudgetError("reservation ledger is unreadable")
        return payload

    def _write(self, state: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        partial = self.path.with_suffix(".json.partial")
        partial.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
        os.replace(partial, self.path)

    def _locked(self) -> _FileLock:
        return _FileLock(self.lock_path)


class _FileLock:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._fd: int | None = None

    def __enter__(self) -> _FileLock:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        deadline = time.monotonic() + 5
        while True:
            try:
                self._fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_RDWR)
                return self
            except FileExistsError:
                if time.monotonic() >= deadline:
                    raise BudgetError("reservation lock timed out") from None
                time.sleep(0.01)

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        fd = self._fd
        self._fd = None
        if fd is not None:
            os.close(fd)
        self.path.unlink(missing_ok=True)


__all__ = [
    "BudgetError",
    "ReservationLedger",
    "collect_block_reasons",
    "default_authorization",
    "usd_to_cents",
]
