"""Phase 4B.2.8 — Offline comparative forensics. Zero provider calls."""

from app.book_semantic_gate_4b28.constants import (
    AUTHORIZED_TERRA_CALLS,
    PHASE,
    TERRA_EXECUTION_AUTHORIZED,
)

assert AUTHORIZED_TERRA_CALLS == 0
assert TERRA_EXECUTION_AUTHORIZED is False

__all__ = ["PHASE", "AUTHORIZED_TERRA_CALLS", "TERRA_EXECUTION_AUTHORIZED"]
