"""Deterministic offline replay of the saved Terra 2.0.1 response. No provider calls."""

from __future__ import annotations

import json
from typing import Any, Mapping

from app.book_semantic_gate_4b211.constants import PHASE, PROMPT_VERSION
from app.book_semantic_gate_4b211.validation import apply_policy, validate_contract
from app.file_utils import content_hash


def _canonical(payload: Mapping[str, Any]) -> str:
    return content_hash(json.dumps(dict(payload), ensure_ascii=False, sort_keys=True))


def replay_saved_response(
    raw_text: str | None,
    *,
    prepared: Mapping[str, Any],
    allowed_handles: list[str] | None = None,
) -> dict[str, Any]:
    first = validate_contract(raw_text, prepared, allowed_evidence=allowed_handles)
    second = validate_contract(raw_text, prepared, allowed_evidence=allowed_handles)
    first_policy = apply_policy(prepared, first)
    second_policy = apply_policy(prepared, second)
    first_hash = _canonical(
        {
            "status": first.get("status"),
            "errors": first.get("errors"),
            "verdicts": first.get("verdicts"),
            "decision": first_policy.get("decision"),
        }
    )
    second_hash = _canonical(
        {
            "status": second.get("status"),
            "errors": second.get("errors"),
            "verdicts": second.get("verdicts"),
            "decision": second_policy.get("decision"),
        }
    )
    identical = (
        first_hash == second_hash
        and first.get("json_parse") == second.get("json_parse")
        and first_policy.get("decision") == second_policy.get("decision")
    )
    return {
        "phase": PHASE,
        "provider_calls": 0,
        "first_parse": first.get("json_parse"),
        "second_parse": second.get("json_parse"),
        "first_status": first.get("status"),
        "second_status": second.get("status"),
        "first_decision": first_policy.get("decision"),
        "second_decision": second_policy.get("decision"),
        "first_sha256": first_hash,
        "second_sha256": second_hash,
        "identical": identical,
        "pass": identical,
        "repaired": False,
        "contract_candidate": PROMPT_VERSION,
        "first": {
            "json_parse": first.get("json_parse"),
            "status": first.get("status"),
            "errors": first.get("errors"),
            "decision": first_policy.get("decision"),
        },
        "second": {
            "json_parse": second.get("json_parse"),
            "status": second.get("status"),
            "errors": second.get("errors"),
            "decision": second_policy.get("decision"),
        },
        "secrets_included": False,
    }


__all__ = ["replay_saved_response"]
