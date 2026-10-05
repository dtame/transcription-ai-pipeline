"""Deterministic offline replays of saved h01/h02 responses. No provider calls."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.book_semantic_gate_4b27.request import paragraph_context
from app.book_semantic_gate_4b271.evidence import load_saved_terra_payload as load_h01_payload
from app.book_semantic_gate_4b272.identity import load_p3_gate_paragraph
from app.book_semantic_gate_4b274.claims import load_saved_h02_payload
from app.book_semantic_gate_4b274.replay import historical_response_replays as replay_112
from app.book_semantic_gate_4b275.constants import (
    H01_CASE_HANDLE,
    H02_CASE_HANDLE,
    HISTORICAL_H01_STATUS,
    HISTORICAL_H02_STATUS,
    PHASE,
    PROMPT_VERSION_113,
)
from app.book_semantic_gate_4b275.coverage import validate_compact_payload_113
from app.book_semantic_gate_4b275.diagnostic import extract_failure_diagnostic
from app.book_semantic_gate_4b275.unknown import inspect_unknown_in_payload


def historical_response_replays(*, root: Path | None = None) -> dict[str, Any]:
    base = replay_112(root=root)
    h01_text = str(
        (paragraph_context(root=root).get("paragraph_texts") or {}).get(H01_CASE_HANDLE)
        or ""
    )
    h02_text = str(load_p3_gate_paragraph(root=root).get("text") or "")
    h01_parsed = load_h01_payload(root=root)
    h02_parsed = load_saved_h02_payload(root=root)
    h01_v113 = validate_compact_payload_113(
        h01_parsed,
        paragraph_texts={H01_CASE_HANDLE: h01_text},
        required_handles=[H01_CASE_HANDLE],
        paragraph_kinds={H01_CASE_HANDLE: "substantive"},
    )
    h02_v113 = validate_compact_payload_113(
        h02_parsed if "pr" in h02_parsed else None,
        paragraph_texts={H02_CASE_HANDLE: h02_text},
        required_handles=[H02_CASE_HANDLE],
        paragraph_kinds={H02_CASE_HANDLE: "substantive"},
    )
    h01_diag = extract_failure_diagnostic(
        h01_parsed,
        paragraph_texts={H01_CASE_HANDLE: h01_text},
        required_handles=[H01_CASE_HANDLE],
        paragraph_kinds={H01_CASE_HANDLE: "substantive"},
    )
    h02_diag = extract_failure_diagnostic(
        h02_parsed if "pr" in h02_parsed else None,
        paragraph_texts={H02_CASE_HANDLE: h02_text},
        required_handles=[H02_CASE_HANDLE],
        paragraph_kinds={H02_CASE_HANDLE: "substantive"},
    )
    h01 = dict(base.get("h01") or {})
    h02 = dict(base.get("h02") or {})
    h01["validator_1_1_3"] = {
        "status": h01_v113.get("status"),
        "errors": h01_v113.get("errors"),
        "coverage_errors": h01_v113.get("coverage_errors"),
        "reason_code_errors": h01_v113.get("reason_code_errors"),
    }
    h02["validator_1_1_3"] = {
        "status": h02_v113.get("status"),
        "errors": h02_v113.get("errors"),
        "coverage_errors": h02_v113.get("coverage_errors"),
        "reason_code_errors": h02_v113.get("reason_code_errors"),
    }
    h01["diagnostic"] = {
        "acceptance": h01_diag["acceptance"],
        "unknown_reason_codes": h01_diag["diagnostic"]["unknown_reason_codes"],
        "coverage_errors": h01_diag["diagnostic"]["coverage_errors"],
        "identifiable_reservations": len(
            h01_diag["diagnostic"]["identifiable_semantic_reservations"]
        ),
        "analyzable_propositions": len(
            h01_diag["diagnostic"]["analyzable_propositions"]
        ),
        "diagnostic_is_not_acceptance": True,
    }
    h02["diagnostic"] = {
        "acceptance": h02_diag["acceptance"],
        "unknown_reason_codes": h02_diag["diagnostic"]["unknown_reason_codes"],
        "coverage_errors": h02_diag["diagnostic"]["coverage_errors"],
        "identifiable_reservations": len(
            h02_diag["diagnostic"]["identifiable_semantic_reservations"]
        ),
        "analyzable_propositions": len(
            h02_diag["diagnostic"]["analyzable_propositions"]
        ),
        "unknown_inspection": inspect_unknown_in_payload(h02_parsed),
        "diagnostic_is_not_acceptance": True,
    }
    h01["historical_status_preserved"] = HISTORICAL_H01_STATUS
    h02["historical_status_preserved"] = HISTORICAL_H02_STATUS
    h01["known_false_rejection"] = "that fear can calculate or bargain with"
    h02["causal_clause_detected_historically"] = True
    return {
        "phase": PHASE,
        "provider_calls": 0,
        "h01": h01,
        "h02": h02,
        "notes": {
            **dict(base.get("notes") or {}),
            "h01_1_1_3": h01_v113.get("status"),
            "h02_1_1_3": h02_v113.get("status"),
            "historical_h01": HISTORICAL_H01_STATUS,
            "historical_h02": HISTORICAL_H02_STATUS,
            "replay_does_not_rewrite_historical_verdict": True,
            "replay_is_not_proof_terra_follows_1_1_3": True,
        },
        "candidate_versions_compared": list(
            dict.fromkeys(
                list(base.get("candidate_versions_compared") or [])
                + [PROMPT_VERSION_113]
            )
        ),
        "secrets_included": False,
    }


__all__ = ["historical_response_replays"]
