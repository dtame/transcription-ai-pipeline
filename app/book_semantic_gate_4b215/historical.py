"""Historical comparison. Does not rewrite prior canary results."""

from __future__ import annotations

from typing import Any, Mapping

from app.book_semantic_gate_4b215.constants import (
    HISTORICAL_4B210_STATUS,
    HISTORICAL_4B211_STATUS,
    HISTORICAL_4B212_STATUS,
    HISTORICAL_4B213_STATUS,
    HISTORICAL_4B214_STATUS,
    HISTORICAL_4B277_STATUS,
    HISTORICAL_H01_STATUS,
    HISTORICAL_H02_STATUS,
    HISTORICAL_H11_STATUS,
    PHASE,
)


def historical_comparison(*, current_result: str, semantic: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "phase": PHASE,
        "historical_h01": HISTORICAL_H01_STATUS,
        "historical_h02": HISTORICAL_H02_STATUS,
        "historical_h11": HISTORICAL_H11_STATUS,
        "historical_4b210": HISTORICAL_4B210_STATUS,
        "historical_4b211": HISTORICAL_4B211_STATUS,
        "historical_4b212": HISTORICAL_4B212_STATUS,
        "historical_4b213": HISTORICAL_4B213_STATUS,
        "historical_4b214": HISTORICAL_4B214_STATUS,
        "historical_4b277": HISTORICAL_4B277_STATUS,
        "do_not_rewrite_historical_results": True,
        "current_4b215": current_result,
        "current_finding": semantic.get("finding"),
        "current_guarantee": semantic.get("universal_guarantee_classification"),
        "current_supported_review": semantic.get("supported_claims_review"),
        "notes": (
            "4B.2.7.7 h11 (1.1.3) remains PARTIAL: guarantee detected, "
            "supported prefix rejected, coverage failed. "
            "4B.2.11 h01 (2.0.1) remains PARTIAL: paraphrase recognized, "
            "contract non-conformant. Neither result is a 2.0.2 h11 validation."
        ),
        "secrets_included": False,
    }


__all__ = ["historical_comparison"]
