"""Audit first-class des longueurs kind-specific A.30/A.31. Pas de réparation."""

from __future__ import annotations

from typing import Any, Mapping

from app.source_analysis_local_v2.constants import OVERFLOW_TOKEN
from app.source_analysis_local_v2.granularity import (
    TEXT_HARD_LIMITS,
    V11_MINIMAL_TEXT_HARD_LIMITS,
    validate_v11_minimal_transport_granularity,
    validate_v2_transport_granularity,
)
from app.source_analysis_v31_final_three.constants import (
    GRANULARITY_POLICY,
    GRANULARITY_POLICY_VERSION,
    MODE,
    PHASE,
    SCHEMA_VERSION,
)
from app.source_analysis_v31_kind_specific_limits.policy import approved_limits


def _field_limit(field: str) -> int | None:
    return TEXT_HARD_LIMITS.get(field)


def audit_length_policy(transport: Mapping[str, Any] | None) -> dict[str, Any]:
    approved = approved_limits()
    fields: dict[str, dict[str, Any]] = {}
    violations: list[dict[str, Any]] = []

    def observe(field: str, length: int, *, index: int | None = None) -> None:
        allowed = approved.get(field)
        if allowed is None:
            allowed = _field_limit(field)
        row = fields.setdefault(
            field,
            {
                "field": field,
                "maximum_observed": 0,
                "allowed_maximum": allowed,
                "violations": 0,
            },
        )
        if length > int(row["maximum_observed"] or 0):
            row["maximum_observed"] = length
        if allowed is not None and length > allowed:
            row["violations"] = int(row["violations"] or 0) + 1
            violations.append(
                {
                    "field": field,
                    "index": index,
                    "observed": length,
                    "allowed": allowed,
                }
            )

    if not isinstance(transport, Mapping):
        return {
            "schema_version": SCHEMA_VERSION,
            "phase": PHASE,
            "mode": MODE,
            "policy_version": GRANULARITY_POLICY,
            "historical_1_1_minimal_frozen": GRANULARITY_POLICY_VERSION,
            "universal_ceiling": False,
            "repair": False,
            "payload_present": False,
            "fields": {},
            "violations": [],
            "violation_count": 0,
            "pass": False,
            "note": "no transport payload to audit",
        }

    for field in ("theme", "intent", "aud"):
        value = transport.get(field)
        if isinstance(value, str):
            observe(field, len(value))

    records = transport.get("records")
    if isinstance(records, list):
        for index, item in enumerate(records):
            if not isinstance(item, Mapping):
                continue
            kind = str(item.get("k") or "")
            value = item.get("v")
            if isinstance(value, str) and value != OVERFLOW_TOKEN:
                observe(f"{kind}.v", len(value), index=index)
            metadata = item.get("m") or []
            if isinstance(metadata, list):
                for meta_index, raw in enumerate(metadata):
                    if not isinstance(raw, str):
                        continue
                    if kind == "TOPIC" and meta_index == 0:
                        observe("TOPIC.m0", len(raw), index=index)
                    else:
                        observe("metadata_item", len(raw), index=index)

    live_ok = False
    live_error = None
    try:
        validate_v2_transport_granularity(dict(transport))
        live_ok = True
    except Exception as exc:  # noqa: BLE001
        live_error = str(exc)

    historical_ok = False
    historical_error = None
    try:
        validate_v11_minimal_transport_granularity(dict(transport))
        historical_ok = True
    except Exception as exc:  # noqa: BLE001
        historical_error = str(exc)

    passed = live_ok and not violations
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "policy_version": GRANULARITY_POLICY,
        "historical_1_1_minimal_frozen": GRANULARITY_POLICY_VERSION,
        "historical_1_1_minimal_limits": dict(V11_MINIMAL_TEXT_HARD_LIMITS),
        "approved_limits": approved,
        "universal_ceiling": False,
        "repair": False,
        "truncation": False,
        "compression": False,
        "payload_present": True,
        "fields": fields,
        "violations": violations,
        "violation_count": len(violations),
        "max_theme_length": (fields.get("theme") or {}).get("maximum_observed") or 0,
        "max_idea_length": (fields.get("IDEA.v") or {}).get("maximum_observed") or 0,
        "max_example_length": (fields.get("EXAMPLE.v") or {}).get("maximum_observed") or 0,
        "live_validator": "PASS" if live_ok else "FAIL",
        "live_validator_error": live_error,
        "historical_1_1_replay": "PASS" if historical_ok else "FAIL",
        "historical_1_1_error": historical_error,
        "pass": passed,
    }


__all__ = ["audit_length_policy"]
