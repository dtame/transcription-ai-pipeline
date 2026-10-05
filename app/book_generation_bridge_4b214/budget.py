"""Fail-closed execution budget. UNKNOWN is never treated as zero."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Mapping
from uuid import uuid4

from app.book_generation_bridge_4b214.constants import (
    BUDGET_POLICY_VERSION,
    COST_COMMITTED,
    COST_ESTIMATED,
    COST_OBSERVED,
    COST_RESERVED,
    COST_UNKNOWN,
    LEDGER_BOOK_GENERATOR,
    LEDGER_BOOK_VALIDATOR,
    LEDGER_GLOBAL,
    LEDGER_NAMES,
    LEDGER_SEMANTIC_GATE,
    PHASE,
    PRICING_EFFECTIVE_DATE,
    SEMANTIC_GATE_MODEL,
    SEMANTIC_GATE_PROVIDER,
    TERRA_INPUT_COST_PER_1M,
    TERRA_OUTPUT_COST_PER_1M,
)
from app.book_generation_bridge_4b214.guard import BookGenerationBridge214Error


def _money(value: Decimal | None) -> float | None:
    if value is None:
        return None
    return float(value.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP))


def tokens_to_usd(
    *,
    input_tokens: int | None,
    output_tokens: int | None,
    input_rate: Decimal | None = None,
    output_rate: Decimal | None = None,
) -> dict[str, Any]:
    if input_tokens is None or output_tokens is None:
        return {
            "status": COST_UNKNOWN,
            "usd": None,
            "counted_as_zero": False,
            "reason": "token usage missing; UNKNOWN is not zero",
        }
    million = Decimal("1000000")
    in_rate = input_rate if input_rate is not None else Decimal(str(TERRA_INPUT_COST_PER_1M))
    out_rate = (
        output_rate if output_rate is not None else Decimal(str(TERRA_OUTPUT_COST_PER_1M))
    )
    usd = (Decimal(input_tokens) / million) * in_rate + (
        Decimal(output_tokens) / million
    ) * out_rate
    return {
        "status": COST_ESTIMATED,
        "usd": _money(usd),
        "decimal": usd,
        "counted_as_zero": False,
        "pricing_effective_date": PRICING_EFFECTIVE_DATE,
        "provider": SEMANTIC_GATE_PROVIDER,
        "model": SEMANTIC_GATE_MODEL,
        "unmodeled_regimes": "long_context_not_modeled",
        "not_a_provider_invoice": True,
    }


@dataclass
class BudgetGuard:
    """Pre-call reservation and post-call reconciliation. Fail closed."""

    ceilings: dict[str, Decimal | None] = field(default_factory=dict)
    per_operation_ceiling: Decimal | None = None
    per_chapter_ceilings: dict[str, Decimal | None] = field(default_factory=dict)
    observed: dict[str, Decimal] = field(default_factory=dict)
    reserved: dict[str, Decimal] = field(default_factory=dict)
    unknown_held: dict[str, Decimal] = field(default_factory=dict)
    reservations: dict[str, dict[str, Any]] = field(default_factory=dict)
    operation_log: dict[str, dict[str, Any]] = field(default_factory=dict)
    refusals: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        for name in LEDGER_NAMES:
            self.ceilings.setdefault(name, None)
            self.observed.setdefault(name, Decimal("0"))
            self.reserved.setdefault(name, Decimal("0"))
            self.unknown_held.setdefault(name, Decimal("0"))

    def _ledger_load(self, ledger: str) -> Decimal:
        return (
            self.observed.get(ledger, Decimal("0"))
            + self.reserved.get(ledger, Decimal("0"))
            + self.unknown_held.get(ledger, Decimal("0"))
        )

    def available(self, ledger: str) -> Decimal | None:
        ceiling = self.ceilings.get(ledger)
        if ceiling is None:
            return None
        return ceiling - self._ledger_load(ledger)

    def snapshot(self) -> dict[str, Any]:
        rows = {}
        for name in LEDGER_NAMES:
            available = self.available(name)
            rows[name] = {
                "ceiling_usd": _money(self.ceilings.get(name)),
                "estimated_usd": None,
                "observed_usd": _money(self.observed[name]),
                "reserved_usd": _money(self.reserved[name]),
                "committed_usd": _money(self.observed[name]),
                "unknown_held_usd": _money(self.unknown_held[name]),
                "available_usd": _money(available) if available is not None else None,
                "unknown_not_treated_as_zero": True,
            }
        return {
            "phase": PHASE,
            "version": BUDGET_POLICY_VERSION,
            "ledgers": rows,
            "unknown_never_becomes_zero": True,
            "control_is_before_call": True,
            "secrets_included": False,
        }

    def estimate_operation(
        self,
        *,
        provider: str,
        model: str,
        chapter_id: str,
        operation: str,
        input_tokens: int | None,
        output_token_cap: int | None,
        ledger: str,
    ) -> dict[str, Any]:
        if ledger not in LEDGER_NAMES:
            raise BookGenerationBridge214Error(f"unknown ledger {ledger}")
        if input_tokens is None or output_token_cap is None:
            return {
                "status": COST_UNKNOWN,
                "usd": None,
                "counted_as_zero": False,
                "provider": provider,
                "model": model,
                "chapter_id": chapter_id,
                "operation": operation,
                "ledger": ledger,
                "reason": "insufficient token estimate; execution blocked or needs human authorization",
            }
        priced = tokens_to_usd(
            input_tokens=input_tokens, output_tokens=output_token_cap
        )
        conservative = priced["decimal"] * Decimal("1.25")
        public_priced = {key: value for key, value in priced.items() if key != "decimal"}
        return {
            "status": COST_ESTIMATED,
            "usd": _money(conservative),
            "decimal": conservative,
            "base_usd": priced["usd"],
            "safety_factor": "1.25",
            "counted_as_zero": False,
            "provider": provider,
            "model": model,
            "chapter_id": chapter_id,
            "operation": operation,
            "ledger": ledger,
            "input_tokens": input_tokens,
            "output_token_cap": output_token_cap,
            "pricing_effective_date": PRICING_EFFECTIVE_DATE,
            "not_a_provider_invoice": True,
            **{k: v for k, v in public_priced.items() if k not in {"status", "usd", "counted_as_zero"}},
        }

    def _public_estimate(self, estimate: Mapping[str, Any]) -> dict[str, Any]:
        return {key: value for key, value in estimate.items() if key != "decimal"}

    def _refuse(self, reason: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        clean = dict(payload)
        if isinstance(clean.get("estimate"), Mapping):
            clean["estimate"] = self._public_estimate(clean["estimate"])
        record = {
            "ok": False,
            "authorized": False,
            "reason": reason,
            "reservation_id": None,
            **clean,
            "counted_as_zero": False,
        }
        self.refusals.append(record)
        return record

    def reserve(
        self,
        *,
        provider: str,
        model: str,
        chapter_id: str,
        operation: str,
        input_tokens: int | None,
        output_token_cap: int | None,
        ledger: str,
        operation_id: str | None = None,
        human_unknown_override: bool = False,
    ) -> dict[str, Any]:
        estimate = self.estimate_operation(
            provider=provider,
            model=model,
            chapter_id=chapter_id,
            operation=operation,
            input_tokens=input_tokens,
            output_token_cap=output_token_cap,
            ledger=ledger,
        )
        op_id = operation_id or str(uuid4())
        existing = self.operation_log.get(op_id)
        if existing and existing.get("state") in {COST_RESERVED, COST_COMMITTED, COST_UNKNOWN}:
            return {
                "ok": True,
                "authorized": False,
                "idempotent_reuse": True,
                "reservation_id": existing.get("reservation_id"),
                "operation_id": op_id,
                "state": existing.get("state"),
                "reason": "operation already recorded; no second reservation",
                "counted_as_zero": False,
            }
        if estimate["status"] == COST_UNKNOWN:
            if not human_unknown_override:
                return self._refuse(
                    "cost_unknown_blocks_execution",
                    {
                        "operation_id": op_id,
                        "estimate": estimate,
                        "human_unknown_override_required": True,
                    },
                )
            amount = Decimal("0")
            unknown = True
        else:
            amount = estimate["decimal"]
            unknown = False
        if self.per_operation_ceiling is not None and not unknown:
            if amount > self.per_operation_ceiling:
                return self._refuse(
                    "per_operation_ceiling_exceeded",
                    {"operation_id": op_id, "estimate": estimate},
                )
        chapter_ceiling = self.per_chapter_ceilings.get(chapter_id)
        if chapter_ceiling is not None and not unknown:
            chapter_load = Decimal("0")
            for item in self.reservations.values():
                if item.get("chapter_id") == chapter_id and item.get("state") != "released":
                    chapter_load += Decimal(str(item.get("amount") or 0))
            if chapter_load + amount > chapter_ceiling:
                return self._refuse(
                    "per_chapter_ceiling_exceeded",
                    {"operation_id": op_id, "estimate": estimate},
                )
        for name, extra in (
            (ledger, amount),
            (LEDGER_GLOBAL, amount),
        ):
            available = self.available(name)
            if available is None:
                if name == LEDGER_BOOK_VALIDATOR:
                    return self._refuse(
                        "ledger_ceiling_unknown_blocks_execution",
                        {"operation_id": op_id, "ledger": name, "estimate": estimate},
                    )
                continue
            if extra > available:
                return self._refuse(
                    f"insufficient_budget:{name}",
                    {
                        "operation_id": op_id,
                        "estimate": estimate,
                        "available_usd": _money(available),
                    },
                )
        reservation_id = str(uuid4())
        if unknown:
            self.unknown_held[ledger] += Decimal("0")
            self.unknown_held[LEDGER_GLOBAL] += Decimal("0")
            state = COST_UNKNOWN
        else:
            self.reserved[ledger] += amount
            self.reserved[LEDGER_GLOBAL] += amount
            state = COST_RESERVED
        record = {
            "reservation_id": reservation_id,
            "operation_id": op_id,
            "provider": provider,
            "model": model,
            "chapter_id": chapter_id,
            "operation": operation,
            "ledger": ledger,
            "amount": _money(amount),
            "decimal": amount,
            "state": state,
            "estimate": {k: v for k, v in estimate.items() if k != "decimal"},
            "not_an_invoice": True,
            "sent": False,
        }
        self.reservations[reservation_id] = record
        self.operation_log[op_id] = record
        return {
            "ok": True,
            "authorized": True,
            "reservation_id": reservation_id,
            "operation_id": op_id,
            "state": state,
            "reserved_usd": _money(amount) if not unknown else None,
            "status": state,
            "counted_as_zero": False,
            "not_an_invoice": True,
        }

    def mark_sent(self, reservation_id: str) -> dict[str, Any]:
        record = self.reservations.get(reservation_id)
        if not record:
            raise BookGenerationBridge214Error("unknown reservation")
        record["sent"] = True
        record["state"] = "sent_unconfirmed"
        return dict(record)

    def reconcile(
        self,
        reservation_id: str,
        *,
        outcome: str,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        already_recorded: bool = False,
    ) -> dict[str, Any]:
        record = self.reservations.get(reservation_id)
        if not record:
            raise BookGenerationBridge214Error("unknown reservation")
        if already_recorded or record.get("reconciled"):
            return {
                "ok": True,
                "idempotent": True,
                "reservation_id": reservation_id,
                "state": record.get("state"),
                "double_debit": False,
                "counted_as_zero": False,
            }
        ledger = str(record["ledger"])
        reserved_amount = Decimal(str(record.get("decimal") or 0))
        self.reserved[ledger] -= reserved_amount
        self.reserved[LEDGER_GLOBAL] -= reserved_amount
        if self.reserved[ledger] < 0:
            self.reserved[ledger] = Decimal("0")
        if self.reserved[LEDGER_GLOBAL] < 0:
            self.reserved[LEDGER_GLOBAL] = Decimal("0")

        priced = tokens_to_usd(input_tokens=input_tokens, output_tokens=output_tokens)
        observed_known = priced["status"] != COST_UNKNOWN
        observed_amount = priced.get("decimal") or Decimal("0")

        if outcome == "full_known" and observed_known:
            self.observed[ledger] += observed_amount
            self.observed[LEDGER_GLOBAL] += observed_amount
            record["state"] = COST_COMMITTED
            record["observed_usd"] = _money(observed_amount)
        elif outcome == "partial_known":
            if observed_known:
                self.observed[ledger] += observed_amount
                self.observed[LEDGER_GLOBAL] += observed_amount
            remainder = reserved_amount - (observed_amount if observed_known else Decimal("0"))
            if remainder < 0:
                remainder = Decimal("0")
            self.unknown_held[ledger] += remainder
            self.unknown_held[LEDGER_GLOBAL] += remainder
            record["state"] = COST_UNKNOWN
            record["observed_usd"] = _money(observed_amount) if observed_known else None
            record["unknown_held_usd"] = _money(remainder)
        elif outcome in {
            "usage_absent",
            "empty_response",
            "truncated",
            "provider_error",
            "timeout",
            "interrupt_after_send",
        }:
            hold = reserved_amount if reserved_amount > 0 else Decimal("0")
            if not observed_known:
                self.unknown_held[ledger] += hold if hold > 0 else Decimal("0")
                self.unknown_held[LEDGER_GLOBAL] += hold if hold > 0 else Decimal("0")
                if hold == 0:
                    self.unknown_held[ledger] += Decimal("0")
                record["state"] = COST_UNKNOWN
                record["observed_usd"] = None
                record["unknown_held_usd"] = _money(hold) if hold > 0 else None
                record["not_treated_as_free"] = True
            else:
                self.observed[ledger] += observed_amount
                self.observed[LEDGER_GLOBAL] += observed_amount
                record["state"] = COST_COMMITTED
                record["observed_usd"] = _money(observed_amount)
        else:
            self.unknown_held[ledger] += reserved_amount
            self.unknown_held[LEDGER_GLOBAL] += reserved_amount
            record["state"] = COST_UNKNOWN
            record["not_treated_as_free"] = True

        record["reconciled"] = True
        record["outcome"] = outcome
        record["counted_as_zero"] = False
        return {
            "ok": True,
            "reservation_id": reservation_id,
            "operation_id": record.get("operation_id"),
            "state": record["state"],
            "outcome": outcome,
            "observed_usd": record.get("observed_usd"),
            "unknown_held_usd": record.get("unknown_held_usd"),
            "double_debit": False,
            "not_treated_as_free": bool(record.get("not_treated_as_free")),
            "counted_as_zero": False,
            "not_an_invoice": True,
        }


def budget_policy() -> dict[str, Any]:
    return {
        "phase": PHASE,
        "version": BUDGET_POLICY_VERSION,
        "ledgers": list(LEDGER_NAMES),
        "cost_states": [
            COST_ESTIMATED,
            COST_OBSERVED,
            COST_RESERVED,
            COST_COMMITTED,
            COST_UNKNOWN,
        ],
        "unknown_never_becomes_zero": True,
        "unknown_blocks_or_requires_human_authorization": True,
        "control_before_call": True,
        "reservation_is_not_an_invoice": True,
        "interrupt_after_send_is_not_free": True,
        "no_automatic_retry_after_uncertain_send": True,
        "book_validator_cost": COST_UNKNOWN,
        "phase5_cost": COST_UNKNOWN,
        "pricing_effective_date": PRICING_EFFECTIVE_DATE,
        "tariffs_are_configured_local_rates_not_necessarily_current": True,
        "secrets_included": False,
    }


__all__ = ["BudgetGuard", "budget_policy", "tokens_to_usd"]
