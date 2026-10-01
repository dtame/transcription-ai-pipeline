"""Schema, historical prompt, SourceMap, and A.3 candidate identity."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from app.editorial_planner_language_policy_4a32.constants import (
    A3_CANDIDATE_SHA256,
    ADAPTED_SCHEMA_BYTES,
    ADAPTED_SCHEMA_SHA256,
    EXPECTED_EXAMPLE_COUNT,
    EXPECTED_IDEA_COUNT,
    EXPECTED_REFERENCE_COUNT,
    EXPECTED_SOURCE_MAP_BYTES,
    EXPECTED_SOURCE_MAP_SHA256,
    EXPECTED_TOPIC_COUNT,
    EXPECTED_UNCERTAINTY_COUNT,
    HISTORICAL_PROMPT,
    INSTRUCTIONS_SHA256,
    PROMPT_SHA256,
    RAW_SCHEMA_BYTES,
    RAW_SCHEMA_SHA256,
    SYSTEM_SHA256,
    TRANSPORT_VERSION,
)
from app.editorial_planner_language_policy_4a32.guard import PlannerLanguagePolicyError
from app.editorial_planner_language_policy_4a32.paths import (
    a3_candidate_path,
    production_source_map_path,
)
from app.editorial_planning.preflight import run_real_source_map_preflight
from app.editorial_planning.prompt import prompt_bundle
from app.editorial_planning.schema import schema_identity


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compare_schema(live: dict[str, Any] | None = None) -> dict[str, Any]:
    live = dict(live or schema_identity())
    expected = {
        "transport_version": TRANSPORT_VERSION,
        "raw_schema_sha256": RAW_SCHEMA_SHA256,
        "adapted_schema_sha256": ADAPTED_SCHEMA_SHA256,
        "raw_schema_bytes": RAW_SCHEMA_BYTES,
        "adapted_schema_bytes": ADAPTED_SCHEMA_BYTES,
    }
    mismatches = [key for key, value in expected.items() if live.get(key) != value]
    return {
        "expected": expected,
        "live": {
            "transport_version": live.get("transport_version"),
            "raw_schema_sha256": live.get("raw_schema_sha256"),
            "adapted_schema_sha256": live.get("adapted_schema_sha256"),
            "raw_schema_bytes": live.get("raw_schema_bytes"),
            "adapted_schema_bytes": live.get("adapted_schema_bytes"),
        },
        "mismatches": mismatches,
        "identity": "MATCH" if not mismatches else "MISMATCH",
        "schema_changed": "NO" if not mismatches else "YES",
        "new_grammar_canary_required": "NO",
        "full_live": live,
    }


def compare_historical_prompt() -> dict[str, Any]:
    bundle = prompt_bundle()
    expected = {
        "version": HISTORICAL_PROMPT,
        "system_sha256": SYSTEM_SHA256,
        "instructions_sha256": INSTRUCTIONS_SHA256,
        "prompt_sha256": PROMPT_SHA256,
    }
    live = {
        "version": bundle["version"],
        "system_sha256": bundle["system_sha256"],
        "instructions_sha256": bundle["instructions_sha256"],
        "prompt_sha256": bundle["prompt_sha256"],
    }
    mismatches = [key for key, value in expected.items() if live.get(key) != value]
    return {
        "expected": expected,
        "live": live,
        "mismatches": mismatches,
        "identity": "MATCH" if not mismatches else "MISMATCH",
        "historical_prompt_mutated": "NO" if not mismatches else "YES",
    }


def source_map_identity_audit() -> dict[str, Any]:
    preflight = run_real_source_map_preflight()
    hash_ok = bool(preflight.get("hash_match"))
    bytes_ok = bool(preflight.get("bytes_match"))
    inventory_ok = bool(preflight.get("inventory_match"))
    validation_ok = preflight.get("source_map_validation") == "PASS"
    blocked = not (hash_ok and bytes_ok)
    status = "BLOCKED" if blocked else str(preflight.get("status") or "FAIL")
    if not blocked and (not inventory_ok or not validation_ok):
        status = "FAIL"
    return {
        "status": status,
        "blocked": blocked,
        "path": preflight.get("path"),
        "sha256": preflight.get("sha256"),
        "expected_sha256": EXPECTED_SOURCE_MAP_SHA256,
        "hash_match": hash_ok,
        "bytes": preflight.get("bytes"),
        "expected_bytes": EXPECTED_SOURCE_MAP_BYTES,
        "bytes_match": bytes_ok,
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
        "source_map_not_modified": True,
        "preflight": preflight,
    }


def candidate_identity_audit(*, root: Path | None = None) -> dict[str, Any]:
    path = a3_candidate_path(root=root)
    if not path.is_file():
        raise PlannerLanguagePolicyError(f"A.3 candidate missing: {path}")
    digest = file_sha256(path)
    match = digest == A3_CANDIDATE_SHA256
    if not match:
        raise PlannerLanguagePolicyError(
            "A.3 candidate hash changed. Forbidden. "
            f"live={digest} expected={A3_CANDIDATE_SHA256}"
        )
    source = production_source_map_path(root=root)
    source_digest = file_sha256(source) if source.is_file() else ""
    return {
        "path": str(path).replace("\\", "/"),
        "sha256": digest,
        "expected_sha256": A3_CANDIDATE_SHA256,
        "unchanged": True,
        "status": "AUDIT_ONLY_NOT_PUBLISHABLE",
        "translated": False,
        "published": False,
        "deleted": False,
        "source_map_sha256": source_digest,
        "source_map_unchanged": source_digest == EXPECTED_SOURCE_MAP_SHA256,
    }


__all__ = [
    "candidate_identity_audit",
    "compare_historical_prompt",
    "compare_schema",
    "file_sha256",
    "source_map_identity_audit",
]
