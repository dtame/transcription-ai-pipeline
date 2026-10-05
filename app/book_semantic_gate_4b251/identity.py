"""Corrected Terra request identity. Historical 4B.2.5 SHA stays frozen."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from app.ai.openai_compat import (
    TOKEN_PARAM_MAX_COMPLETION_TOKENS,
    TOKEN_PARAM_MAX_TOKENS,
    conflicting_token_fields,
)
from app.book_semantic_gate_4b23.identity import load_json
from app.book_semantic_gate_4b24.constants import CONSERVATIVE_MAX_OUTPUT_TOKENS
from app.book_semantic_gate_4b24.identity import (
    benchmark_identity,
    contract_identities,
    snapshot_identities,
    verify_canonical_inputs,
)
from app.book_semantic_gate_4b24.leak import audit_label_leak
from app.book_semantic_gate_4b24.payload import build_request_twice, serialize_payload
from app.book_semantic_gate_4b24.precall import build_precall
from app.book_semantic_gate_4b251.constants import (
    EXPECTED_REQUEST_SHA256_HISTORICAL,
    EXPECTED_SCORED_CASES,
    MODEL,
    PHASE,
    SEMANTIC_TOKEN_BUDGET,
)
from app.book_semantic_gate_4b251.paths import historical_4b25_request_path
from app.file_utils import content_hash


ALLOWED_PAYLOAD_FIELD_CHANGES = frozenset(
    {TOKEN_PARAM_MAX_TOKENS, TOKEN_PARAM_MAX_COMPLETION_TOKENS}
)


def load_historical_4b25_request(*, root: Path | None = None) -> dict[str, Any]:
    path = historical_4b25_request_path(root=root)
    payload = load_json(path) if path.is_file() else {}
    return {
        "path": str(path).replace("\\", "/"),
        "exists": path.is_file(),
        "request_sha256": payload.get("request_sha256"),
        "payload": dict(payload.get("payload") or {}),
        "max_tokens": payload.get("max_tokens"),
        "model": payload.get("model"),
        "temperature_present": payload.get("temperature_present"),
        "thinking_present": payload.get("thinking_present"),
        "response_format": payload.get("response_format"),
        "raw": payload,
    }


def _payload_without_token_fields(payload: Mapping[str, Any]) -> dict[str, Any]:
    cleaned = dict(payload)
    for name in (TOKEN_PARAM_MAX_TOKENS, TOKEN_PARAM_MAX_COMPLETION_TOKENS):
        cleaned.pop(name, None)
    return cleaned


def semantic_payload_diff(
    historical: Mapping[str, Any],
    corrected: Mapping[str, Any],
) -> dict[str, Any]:
    hist = dict(historical)
    corr = dict(corrected)
    hist_keys = set(hist)
    corr_keys = set(corr)
    added = sorted(corr_keys - hist_keys)
    removed = sorted(hist_keys - corr_keys)
    changed: list[dict[str, Any]] = []
    for key in sorted(hist_keys & corr_keys):
        if hist.get(key) != corr.get(key):
            changed.append({"field": key, "historical": hist.get(key), "corrected": corr.get(key)})
    unexpected = [
        name
        for name in added + removed + [item["field"] for item in changed]
        if name not in ALLOWED_PAYLOAD_FIELD_CHANGES
    ]
    semantic_hist = _payload_without_token_fields(hist)
    semantic_corr = _payload_without_token_fields(corr)
    semantic_identical = semantic_hist == semantic_corr
    only_compat = semantic_identical and not unexpected
    return {
        "added_fields": added,
        "removed_fields": removed,
        "changed_fields": changed,
        "unexpected_field_changes": unexpected,
        "semantic_content_identical": semantic_identical,
        "only_api_compatibility_fields_changed": only_compat,
        "blocker": not only_compat,
        "historical_token_fields": conflicting_token_fields(hist),
        "corrected_token_fields": conflicting_token_fields(corr),
        "historical_max_tokens": hist.get(TOKEN_PARAM_MAX_TOKENS),
        "corrected_max_tokens": corr.get(TOKEN_PARAM_MAX_TOKENS),
        "historical_max_completion_tokens": hist.get(TOKEN_PARAM_MAX_COMPLETION_TOKENS),
        "corrected_max_completion_tokens": corr.get(TOKEN_PARAM_MAX_COMPLETION_TOKENS),
    }


def build_corrected_identity(*, root: Path | None = None) -> dict[str, Any]:
    historical = load_historical_4b25_request(root=root)
    before = verify_canonical_inputs(root=root)
    frozen = build_precall(root=root)
    after = verify_canonical_inputs(root=root)
    twice_payload = dict(frozen.get("payload") or {})
    request_meta = dict(frozen.get("request") or {})
    gate_input = frozen.get("gate_input") or {}
    rebuilt = build_request_twice(
        gate_input, max_output_tokens=CONSERVATIVE_MAX_OUTPUT_TOKENS
    )
    first = rebuilt["payload"]
    second = rebuilt.get("second") or {}
    first_sha = content_hash(serialize_payload(first))
    second_sha = str(second.get("sha256") or rebuilt["second"]["sha256"])
    historical_sha = str(
        historical.get("request_sha256") or EXPECTED_REQUEST_SHA256_HISTORICAL
    )
    diff = semantic_payload_diff(historical.get("payload") or {}, first)
    request = rebuilt["request"]
    leak = audit_label_leak(
        first,
        request={
            "system_prompt": request.system_prompt,
            "prompt": request.prompt,
        },
    )
    contracts = contract_identities()
    benchmark = benchmark_identity(root=root)
    expected_compat = (
        first.get(TOKEN_PARAM_MAX_COMPLETION_TOKENS) == SEMANTIC_TOKEN_BUDGET
        and TOKEN_PARAM_MAX_TOKENS not in first
        and first.get("model") == MODEL
        and "temperature" not in first
        and "thinking" not in first
        and first.get("response_format") == {"type": "json_object"}
        and first_sha != historical_sha
        and first_sha == second_sha
        and first_sha == request_meta.get("sha256")
        and not diff["blocker"]
        and leak.get("pass") is True
        and int(leak.get("label_leakage") or 0) == 0
        and len(frozen.get("candidate_handles") or []) == EXPECTED_SCORED_CASES
    )
    live_blockers = [
        reason
        for reason in (frozen.get("block_reasons") or [])
        if reason != "request_sha256"
    ]
    return {
        "phase": PHASE,
        "historical_request_sha256": historical_sha,
        "historical_request_preserved": (
            historical_sha == EXPECTED_REQUEST_SHA256_HISTORICAL
            and historical.get("exists") is True
            and (historical.get("payload") or {}).get("max_tokens") == SEMANTIC_TOKEN_BUDGET
        ),
        "canonical_request_sha256": first_sha,
        "canonical_request_sha256_repeat": second_sha,
        "deterministic": first_sha == second_sha,
        "differs_from_historical": first_sha != historical_sha,
        "exact_changed_fields": (
            ["max_tokens -> removed", "max_completion_tokens=8192 -> added"]
            if expected_compat
            else diff["changed_fields"] + diff["added_fields"] + diff["removed_fields"]
        ),
        "prompt_identity": (contracts.get("prompt") or {}),
        "transport_identity": (contracts.get("transport") or {}),
        "schema_identity": (contracts.get("schema") or {}),
        "benchmark_identity": benchmark,
        "case_count": len(frozen.get("candidate_handles") or []),
        "label_leakage": int(leak.get("label_leakage") or 0),
        "label_leak": leak,
        "context_budget": frozen.get("cost_estimate") or frozen.get("budget"),
        "estimated_cost": (frozen.get("cost_estimate") or {}).get("total_cost_display"),
        "cost_estimate": frozen.get("cost_estimate"),
        "contracts": contracts,
        "diff": diff,
        "payload": first,
        "historical_payload": historical.get("payload") or {},
        "request": request_meta,
        "ai_request": request,
        "gate_input": gate_input,
        "candidate_handles": frozen.get("candidate_handles") or [],
        "identities_before": before,
        "identities_after": after,
        "inputs_unchanged": snapshot_identities(before) == snapshot_identities(after),
        "expected_compat": expected_compat,
        "live_4b24_precall_blockers_excluding_historical_sha": live_blockers,
        "http_sent": False,
        "secrets_included": False,
    }


__all__ = [
    "ALLOWED_PAYLOAD_FIELD_CHANGES",
    "build_corrected_identity",
    "load_historical_4b25_request",
    "semantic_payload_diff",
]
