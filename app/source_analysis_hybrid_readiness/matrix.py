"""Matrice d'échec déterministe — 3B.7.6."""

from __future__ import annotations

from typing import Any


def _row(
    failure: str,
    *,
    transport: str,
    result: str,
    source_map: str = "absent",
    new_call: str = "NO",
    human: str = "YES",
    next_action: str,
) -> dict[str, Any]:
    return {
        "failure": failure,
        "artifacts_preserved": {
            "transport": transport,
            "result": result,
            "source_map": source_map,
        },
        "automatic_new_call": new_call,
        "human_review_required": human,
        "next_legal_action": next_action,
    }


def build_failure_matrix() -> list[dict[str, Any]]:
    return [
        _row(
            "window_provider_timeout",
            transport="absent",
            result="absent",
            next_action="STOP. cost=UNKNOWN if usage unavailable. No retry.",
        ),
        _row(
            "window_http_error",
            transport="absent",
            result="absent",
            next_action="STOP. Budget consumed. Diagnose HTTP class. No retry.",
        ),
        _row(
            "window_invalid_structured_response",
            transport="preserved_if_parsed_body",
            result="absent",
            next_action="STOP. Offline diagnosis of transport. No retry.",
        ),
        _row(
            "window_transport_write_error",
            transport="partial_cleaned",
            result="absent",
            next_action="STOP. No READY. Do not invent transport.",
        ),
        _row(
            "window_decoder_error",
            transport="preserved",
            result="absent",
            next_action="STOP. Offline decode diagnosis. Recovery later if transport valid.",
        ),
        _row(
            "window_validator_error",
            transport="preserved",
            result="absent",
            next_action="STOP. Offline validator diagnosis. No retry.",
        ),
        _row(
            "window_result_write_error",
            transport="preserved",
            result="partial_cleaned",
            next_action="STOP. No fake READY. Recover from transport locally.",
        ),
        _row(
            "interrupted_between_windows",
            transport="previous_windows_preserved",
            result="previous_windows_preserved",
            next_action="STOP. Do not start next window. Resume from cache.",
        ),
        _row(
            "stale_cache",
            transport="classified_STALE",
            result="not_trusted",
            next_action="Do not overwrite blindly. Explicit execution policy required.",
        ),
        _row(
            "consolidation_context_overflow",
            transport="absent",
            result="absent",
            next_action="STOP. No truncation. No call. Guard 80000.",
        ),
        _row(
            "consolidation_grammar_rejection",
            transport="absent_or_error_body",
            result="absent",
            next_action="STOP. Grammar canary/review. No semantic retry.",
        ),
        _row(
            "consolidation_provider_timeout",
            transport="absent",
            result="absent",
            next_action="STOP. cost=UNKNOWN if usage unavailable. No retry.",
        ),
        _row(
            "consolidation_decoder_failure",
            transport="preserved",
            result="absent",
            next_action="STOP. No reconstruction. No publication.",
        ),
        _row(
            "consolidation_validator_failure",
            transport="preserved",
            result="absent",
            next_action="STOP. No reconstruction. No publication.",
        ),
        _row(
            "canonical_reconstruction_failure",
            transport="windows_and_consolidation_preserved",
            result="consolidation_preserved",
            next_action="STOP. Local only. 0 provider calls. No publication.",
        ),
        _row(
            "canonical_validator_failure",
            transport="windows_and_consolidation_preserved",
            result="consolidation_preserved",
            next_action="STOP. Do not publish. Do not mark SUCCESS.",
        ),
        _row(
            "publication_failure",
            transport="windows_and_consolidation_preserved",
            result="consolidation_preserved",
            source_map="not_canonical_if_partial",
            next_action="No SUCCESS. Partial must not become source_map.json.",
        ),
        _row(
            "keyboard_interrupt",
            transport="existing_preserved",
            result="existing_preserved",
            next_action="No success. No automatic continuation.",
        ),
        _row(
            "process_crash_before_transport",
            transport="absent",
            result="absent",
            next_action="MISS. New authorized call only after human review.",
        ),
        _row(
            "process_crash_after_transport",
            transport="preserved",
            result="absent",
            next_action="Local transport recovery. 0 new provider calls if binding valid.",
        ),
        _row(
            "process_crash_after_result",
            transport="preserved",
            result="preserved",
            next_action="Revalidate cache. HIT if signature current.",
        ),
    ]
