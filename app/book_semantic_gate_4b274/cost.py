"""Observed cost comparison. No new provider spend. No Terra internals claimed."""

from __future__ import annotations

from typing import Any, Mapping

from app.book_semantic_gate_4b261.candidates import candidate_prompt_bundle
from app.book_semantic_gate_4b271.calibration import candidate_111_prompt_bundle
from app.book_semantic_gate_4b274.constants import (
    H01_CASE_HANDLE,
    H01_COMPLETION_TOKENS,
    H01_COST_USD,
    H01_INPUT_TOKENS,
    H01_REASONING_TOKENS,
    H02_CASE_HANDLE,
    H02_COMPLETION_TOKENS,
    H02_COST_USD,
    H02_INPUT_TOKENS,
    H02_REASONING_TOKENS,
    PHASE,
)
from app.book_semantic_gate_4b274.contract import candidate_112_prompt_bundle


def _payload_stats(payload: Mapping[str, Any] | None, handle: str) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        return {"missing": True}
    para = next((item for item in payload.get("pr") or [] if item.get("h") == handle), {})
    claims = list(para.get("c") or [])
    reservations = [
        item for item in claims if str(item.get("k") or "") in {"QUESTIONABLE", "UNSUPPORTED"}
    ]
    evidence = sorted(
        {
            str(handle_id)
            for item in claims
            for handle_id in (item.get("ev") or [])
        }
    )
    raw = str(payload)
    return {
        "chapter_verdict": payload.get("v"),
        "paragraph_verdict": para.get("v"),
        "claim_count": len(claims),
        "reservation_count": len(reservations),
        "supported_count": sum(1 for item in claims if item.get("k") == "SUPPORTED"),
        "questionable_count": sum(1 for item in claims if item.get("k") == "QUESTIONABLE"),
        "unsupported_count": sum(1 for item in claims if item.get("k") == "UNSUPPORTED"),
        "evidence_handles_cited": evidence,
        "evidence_handle_count": len(evidence),
        "reason_codes": sorted(
            {
                str(code)
                for item in claims
                for code in (item.get("r") or [])
            }
        ),
        "compact_json_chars": len(raw),
    }


def cost_comparison(
    *,
    h01_payload: Mapping[str, Any] | None,
    h02_payload: Mapping[str, Any] | None,
) -> dict[str, Any]:
    c11 = candidate_prompt_bundle()
    c111 = candidate_111_prompt_bundle()
    c112 = candidate_112_prompt_bundle()
    h01 = _payload_stats(h01_payload, H01_CASE_HANDLE)
    h02 = _payload_stats(h02_payload, H02_CASE_HANDLE)
    return {
        "phase": PHASE,
        "provider_cost_in_this_phase": 0,
        "observed": {
            "h01": {
                "input_tokens": H01_INPUT_TOKENS,
                "completion_tokens": H01_COMPLETION_TOKENS,
                "reasoning_tokens": H01_REASONING_TOKENS,
                "cost_usd": H01_COST_USD,
                **h01,
            },
            "h02": {
                "input_tokens": H02_INPUT_TOKENS,
                "completion_tokens": H02_COMPLETION_TOKENS,
                "reasoning_tokens": H02_REASONING_TOKENS,
                "cost_usd": H02_COST_USD,
                **h02,
            },
        },
        "deltas": {
            "input_tokens": H02_INPUT_TOKENS - H01_INPUT_TOKENS,
            "completion_tokens": H02_COMPLETION_TOKENS - H01_COMPLETION_TOKENS,
            "reasoning_tokens": H02_REASONING_TOKENS - H01_REASONING_TOKENS,
            "cost_usd": round(H02_COST_USD - H01_COST_USD, 6),
            "claim_count": (h02.get("claim_count") or 0) - (h01.get("claim_count") or 0),
            "reservation_count": (h02.get("reservation_count") or 0)
            - (h01.get("reservation_count") or 0),
        },
        "prompt_bytes": {
            "1.1-candidate": len(c11["system"].encode("utf-8"))
            + len(c11["instructions"].encode("utf-8")),
            "1.1.1-candidate": len(c111["system"].encode("utf-8"))
            + len(c111["instructions"].encode("utf-8")),
            "1.1.2-candidate": len(c112["system"].encode("utf-8"))
            + len(c112["instructions"].encode("utf-8")),
        },
        "observable_differences": [
            "h02 compact JSON is larger and enumerates more claims.",
            "h02 has more reservations than h01.",
            "h02 input tokens are only slightly higher than h01.",
            "h02 completion and reasoning tokens are substantially higher.",
            "1.1.2 prompt is larger than 1.1.1 because the catalog is listed.",
        ],
        "not_claimed": [
            "Terra internal reasoning mechanisms are not known.",
            "Cost increase is not attributed to a single proven factor.",
        ],
        "prudent_future_canary_band_usd": {
            "lower_observed_like_h01": 0.02,
            "upper_observed_like_h02": 0.07,
            "if_8192_output_exhausted_approx": 0.11,
            "input_tokens_planning_range": [1700, 2300],
            "unknown_reasoning_tokens_remain": True,
            "not_a_guarantee": True,
        },
        "no_provider_cost_here": True,
        "secrets_included": False,
    }


__all__ = ["cost_comparison"]
