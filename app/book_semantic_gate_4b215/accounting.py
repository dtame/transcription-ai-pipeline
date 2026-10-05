"""
4B.2.15 call accounting.

A local precall failure is not a remote invocation.
A remote SDK invocation consumes the authorized slot even on HTTP error.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from app.ai.provider_preflight import future_call_accounting_contract
from app.book_semantic_gate_4b215.constants import (
    AUTHORIZED_REMOTE_TERRA_INVOCATIONS,
    FALLBACKS,
    PHASE,
    RETRIES,
)


@dataclass
class CallAccounting:
    authorized_remote_invocations: int = AUTHORIZED_REMOTE_TERRA_INVOCATIONS
    execution_attempts: int = 0
    remote_invocations: int = 0
    http_requests: int = 0
    provider_responses: int = 0
    successful_payloads: int = 0
    retries: int = RETRIES
    fallbacks: int = FALLBACKS
    sonnet_calls: int = 0
    lock_consumed: bool = False
    boundary_crossed: bool = False

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["phase"] = PHASE
        payload["historical_h01_unchanged"] = True
        payload["historical_h02_unchanged"] = True
        payload["historical_h11_unchanged"] = True
        payload["historical_4b211_unchanged"] = True
        payload["contract"] = future_call_accounting_contract()["future_counters"]
        payload["secrets_included"] = False
        payload["note"] = (
            "A local precall failure is not a remote invocation. "
            "A remote SDK invocation counts against the authorized slot "
            "even if it returns HTTP 400, times out, or has no usable content. "
            "A timeout does not prove the provider did not receive or bill the request."
        )
        return payload


def empty_accounting() -> CallAccounting:
    return CallAccounting()


__all__ = ["CallAccounting", "empty_accounting"]
