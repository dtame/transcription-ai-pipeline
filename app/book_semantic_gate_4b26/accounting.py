"""
4B.2.6 call accounting.

Do not conflate local initialization with remote invocation.
Do not rewrite historical 4B.2.4 or 4B.2.5 counters.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from app.ai.provider_preflight import future_call_accounting_contract
from app.book_semantic_gate_4b26.constants import (
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
        payload["historical_4b24_unchanged"] = True
        payload["historical_4b25_unchanged"] = True
        payload["contract"] = future_call_accounting_contract()["future_counters"]
        payload["secrets_included"] = False
        payload["note"] = (
            "A local precall failure is not a remote invocation. "
            "A remote SDK invocation counts against the authorized slot "
            "even if it returns HTTP 400 or no usable content."
        )
        return payload


def empty_accounting() -> CallAccounting:
    return CallAccounting()


__all__ = ["CallAccounting", "empty_accounting"]
