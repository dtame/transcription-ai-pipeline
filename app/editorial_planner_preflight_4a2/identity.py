"""Identités SourceMap / schéma / prompt — mismatch = BLOCKED_PRECALL."""

from __future__ import annotations

from typing import Any

from app.editorial_planner_preflight_4a2.constants import (
    ADAPTED_SCHEMA_BYTES,
    ADAPTED_SCHEMA_SHA256,
    EXPECTED_EXAMPLE_COUNT,
    EXPECTED_IDEA_COUNT,
    EXPECTED_REFERENCE_COUNT,
    EXPECTED_SOURCE_MAP_BYTES,
    EXPECTED_SOURCE_MAP_CHARS,
    EXPECTED_SOURCE_MAP_SHA256,
    EXPECTED_TOPIC_COUNT,
    EXPECTED_UNCERTAINTY_COUNT,
    INSTRUCTIONS_SHA256,
    PROMPT_SHA256,
    PROMPT_VERSION,
    RAW_SCHEMA_BYTES,
    RAW_SCHEMA_SHA256,
    SYSTEM_SHA256,
    TRANSPORT_VERSION,
)
from app.editorial_planner_preflight_4a2.guard import PlannerPreflightError
from app.editorial_planning.preflight import run_real_source_map_preflight
from app.editorial_planning.prompt import prompt_bundle
from app.editorial_planning.schema import schema_identity


def compare_schema(live: dict[str, Any] | None = None) -> dict[str, Any]:
    live = dict(live or schema_identity())
    expected = {
        "transport_version": TRANSPORT_VERSION,
        "raw_schema_sha256": RAW_SCHEMA_SHA256,
        "adapted_schema_sha256": ADAPTED_SCHEMA_SHA256,
        "raw_schema_bytes": RAW_SCHEMA_BYTES,
        "adapted_schema_bytes": ADAPTED_SCHEMA_BYTES,
    }
    mismatches = [
        key for key, value in expected.items() if live.get(key) != value
    ]
    return {
        "expected": expected,
        "live": {
            "transport_version": live.get("transport_version"),
            "raw_schema_sha256": live.get("raw_schema_sha256"),
            "adapted_schema_sha256": live.get("adapted_schema_sha256"),
            "raw_schema_bytes": live.get("raw_schema_bytes"),
            "adapted_schema_bytes": live.get("adapted_schema_bytes"),
            "anthropic_known_incompatibilities": live.get(
                "anthropic_known_incompatibilities"
            ),
            "additional_properties_false_on_adapted": live.get(
                "additional_properties_false_on_adapted"
            ),
        },
        "mismatches": mismatches,
        "identity": "MATCH" if not mismatches else "MISMATCH",
        "full_live": live,
    }


def compare_prompt(live: dict[str, Any] | None = None) -> dict[str, Any]:
    bundle = prompt_bundle()
    live = dict(
        live
        or {
            "version": bundle["version"],
            "system_sha256": bundle["system_sha256"],
            "instructions_sha256": bundle["instructions_sha256"],
            "prompt_sha256": bundle["prompt_sha256"],
        }
    )
    expected = {
        "version": PROMPT_VERSION,
        "system_sha256": SYSTEM_SHA256,
        "instructions_sha256": INSTRUCTIONS_SHA256,
        "prompt_sha256": PROMPT_SHA256,
    }
    mismatches = [key for key, value in expected.items() if live.get(key) != value]
    return {
        "expected": expected,
        "live": live,
        "mismatches": mismatches,
        "identity": "MATCH" if not mismatches else "MISMATCH",
    }


def source_map_identity_audit() -> dict[str, Any]:
    preflight = run_real_source_map_preflight()
    chars_ok = int(preflight.get("chars") or 0) == EXPECTED_SOURCE_MAP_CHARS
    hash_ok = bool(preflight.get("hash_match"))
    bytes_ok = bool(preflight.get("bytes_match"))
    inventory_ok = bool(preflight.get("inventory_match"))
    validation_ok = preflight.get("source_map_validation") == "PASS"
    blocked = not (hash_ok and bytes_ok)
    status = "BLOCKED_PRECALL" if blocked else str(preflight.get("status") or "FAIL")
    if not blocked and (not inventory_ok or not chars_ok or not validation_ok):
        status = "FAIL"
    return {
        "status": status,
        "blocked_precall": blocked,
        "path": preflight.get("path"),
        "sha256": preflight.get("sha256"),
        "expected_sha256": EXPECTED_SOURCE_MAP_SHA256,
        "hash_match": hash_ok,
        "bytes": preflight.get("bytes"),
        "expected_bytes": EXPECTED_SOURCE_MAP_BYTES,
        "bytes_match": bytes_ok,
        "chars": preflight.get("chars"),
        "expected_chars": EXPECTED_SOURCE_MAP_CHARS,
        "chars_match": chars_ok,
        "inventory": preflight.get("inventory"),
        "expected_inventory": {
            "topics": EXPECTED_TOPIC_COUNT,
            "ideas": EXPECTED_IDEA_COUNT,
            "examples": EXPECTED_EXAMPLE_COUNT,
            "references": EXPECTED_REFERENCE_COUNT,
            "uncertainties": EXPECTED_UNCERTAINTY_COUNT,
            "repetitions": 0,
        },
        "inventory_match": inventory_ok,
        "canonical_source_map_validation": preflight.get("source_map_validation"),
        "traceability": preflight.get("traceability"),
        "source_map_validation_errors": preflight.get("source_map_validation_errors"),
        "forbidden_editorial_fields": preflight.get("forbidden_editorial_fields"),
        "forbidden_editorial_structure": preflight.get("forbidden_editorial_structure"),
        "relations_present": preflight.get("relations_present"),
        "relation_quality_debt": preflight.get("relation_quality_debt"),
        "source_map_not_modified": True,
        "preflight": preflight,
    }


def contract_identity() -> dict[str, Any]:
    schema = compare_schema()
    prompt = compare_prompt()
    blocked = (
        schema["identity"] != "MATCH"
        or prompt["identity"] != "MATCH"
        or schema["live"].get("anthropic_known_incompatibilities") not in (0, None)
    )
    return {
        "schema": schema,
        "prompt": prompt,
        "transport_version": TRANSPORT_VERSION,
        "prompt_version": PROMPT_VERSION,
        "schema_identity": schema["identity"],
        "prompt_identity": prompt["identity"],
        "blocked_precall": blocked,
        "block_reason": (
            None
            if not blocked
            else "schema/prompt identity mismatch with Phase 4A.1 freeze"
        ),
    }


def require_identities(
    source_identity: dict[str, Any],
    contract: dict[str, Any],
) -> None:
    if source_identity.get("blocked_precall"):
        raise PlannerPreflightError(
            "BLOCKED_PRECALL: SourceMap identity mismatch "
            f"(sha={source_identity.get('sha256')})"
        )
    if contract.get("blocked_precall"):
        raise PlannerPreflightError(
            "BLOCKED_PRECALL: " + str(contract.get("block_reason"))
        )


__all__ = [
    "compare_prompt",
    "compare_schema",
    "contract_identity",
    "require_identities",
    "source_map_identity_audit",
]
