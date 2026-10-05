"""Phase 4B.2.9 — Offline Semantic Gate 2.0 candidate. Zero provider calls."""

from app.book_semantic_gate_4b29.constants import (
    AUTHORIZED_TERRA_CALLS,
    PHASE,
    PRODUCTION_PIPELINE_HOOK,
    SEMANTIC_GATE_20_ENABLED,
    TERRA_EXECUTION_AUTHORIZED,
)

assert AUTHORIZED_TERRA_CALLS == 0
assert TERRA_EXECUTION_AUTHORIZED is False
assert SEMANTIC_GATE_20_ENABLED is False
assert PRODUCTION_PIPELINE_HOOK is False

__all__ = [
    "PHASE",
    "AUTHORIZED_TERRA_CALLS",
    "TERRA_EXECUTION_AUTHORIZED",
    "SEMANTIC_GATE_20_ENABLED",
    "PRODUCTION_PIPELINE_HOOK",
]
