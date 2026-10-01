"""Phase 4B.2.4 — one real Terra semantic-gate benchmark canary."""

from app.book_semantic_gate_4b24.constants import (
    AUTHORIZED_SONNET_CALLS,
    AUTHORIZED_TERRA_CALLS,
    PHASE,
)

assert AUTHORIZED_TERRA_CALLS == 1
assert AUTHORIZED_SONNET_CALLS == 0

__all__ = ["PHASE", "AUTHORIZED_TERRA_CALLS", "AUTHORIZED_SONNET_CALLS"]
