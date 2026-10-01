"""Phase 4B.2.1 — Book Generator canary forensics. Offline only."""

from app.book_generator_forensics_4b21.constants import (
    PHASE,
    REAL_PROVIDER_CALLS,
)

assert REAL_PROVIDER_CALLS == 0

__all__ = ["PHASE", "REAL_PROVIDER_CALLS"]
