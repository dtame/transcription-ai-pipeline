"""Phase 4B.2.7.5 — Semantic gate 1.1.2 stabilization. Zero provider calls."""

from app.book_semantic_gate_4b275.constants import (
    AUTHORIZED_TERRA_CALLS,
    PHASE,
    TERRA_EXECUTION_AUTHORIZED,
)

assert AUTHORIZED_TERRA_CALLS == 0
assert TERRA_EXECUTION_AUTHORIZED is False

__all__ = ["PHASE", "AUTHORIZED_TERRA_CALLS", "TERRA_EXECUTION_AUTHORIZED"]
