"""Phase 4B.2.4.1 — OpenAI runtime remediation. Offline only."""

from app.book_semantic_gate_4b241.constants import (
    AUTHORIZED_TERRA_CALLS,
    PHASE,
    TERRA_EXECUTION_AUTHORIZED,
)

assert AUTHORIZED_TERRA_CALLS == 0
assert TERRA_EXECUTION_AUTHORIZED is False

__all__ = ["PHASE", "AUTHORIZED_TERRA_CALLS", "TERRA_EXECUTION_AUTHORIZED"]
