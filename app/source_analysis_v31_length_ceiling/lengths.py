"""Définition de « 200 caractères » et inventaire des plafonds. Offline."""

from __future__ import annotations

from typing import Any, Mapping

from app.source_analysis.errors import WindowGranularityLimitExceeded
from app.source_analysis_local_v2.constants import HARD_CEILINGS, TOTAL_HARD_CEILING
from app.source_analysis_local_v2.granularity import V11_MINIMAL_TEXT_HARD_LIMITS
from app.source_analysis_local_v3 import prompt as v140_prompt
from app.source_analysis.window_granularity import (
    LOCAL_STRING_TRUNCATION,
    TEXT_HARD_LIMITS as V10_LIMITS,
)
from app.source_analysis_v31_length_ceiling.constants import (
    CURRENT_EXAMPLE_LIMIT,
    CURRENT_IDEA_LIMIT,
    CURRENT_THEME_LIMIT,
    LENGTH_MECHANISM,
    MODE,
    PHASE,
    SCHEMA_VERSION,
)


def character_definition() -> dict[str, Any]:
    sample = "é"
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "mechanism": LENGTH_MECHANISM,
        "code": "len(value) on a Python str after decode; no strip/normalize/encode",
        "files": [
            "app/source_analysis/window_granularity.py:_text_violations",
            "app/source_analysis_local_v2/granularity.py:_text_violations",
        ],
        "python_len_str": True,
        "unicode_code_points": True,
        "bytes": False,
        "tokens": False,
        "trimmed_length": False,
        "normalized_length": False,
        "local_string_truncation": LOCAL_STRING_TRUNCATION,
        "proof_sample": {
            "text": sample,
            "python_len": len(sample),
            "utf8_bytes": len(sample.encode("utf-8")),
            "note": "len('é')==1 code point, 2 UTF-8 bytes — validation uses 1.",
        },
    }


def length_occurrences() -> list[dict[str, Any]]:
    return [
        {
            "file": "app/source_analysis/window_granularity.py",
            "constant": "TEXT_HARD_LIMITS",
            "policy": "window-granularity-1.0",
            "values": dict(V10_LIMITS),
            "consumers": [
                "validate_window_transport_granularity",
                "validate_window_result_granularity",
                "app/source_analysis_window_output_bounding/size_study.py",
            ],
            "record_kinds_affected": [
                "theme",
                "intent",
                "aud",
                "TOPIC.v",
                "TOPIC.m0",
                "IDEA.v",
                "EXAMPLE.v",
                "REFERENCE.v",
                "UNCERTAINTY.v",
                "REPETITION.v",
                "RELATION.v",
                "VOICE.v",
                "INTENT_KIND.v",
                "AUDIENCE_KIND.v",
                "metadata_item",
            ],
            "stage": "local post-parse validator (Generation C / v1 windows)",
            "historical_reason": (
                "A.2 output-bounding redesign. Hard character limits for "
                "worst-case synthetic token budget. Local reject, never slice."
            ),
        },
        {
            "file": "app/source_analysis_local_v2/granularity.py",
            "constant": "TEXT_HARD_LIMITS",
            "policy": "window-granularity-1.1-minimal",
            "values": dict(V11_MINIMAL_TEXT_HARD_LIMITS),
            "consumers": [
                "validate_v2_transport_granularity",
                "validate_v3_transport",
                "interpret_local_lite_response",
                "window-analysis-1.2 / 1.3 / 1.4.0 prompt (TOPIC.v and IDEA.v only)",
            ],
            "record_kinds_affected": [
                "theme",
                "intent",
                "aud",
                "TOPIC.v",
                "TOPIC.m0",
                "IDEA.v",
                "EXAMPLE.v",
                "REFERENCE.v",
                "UNCERTAINTY.v",
                "RELATION.v",
                "metadata_item",
            ],
            "stage": "local post-parse validator (v2 / v3 / v3.1-local-lite)",
            "historical_reason": (
                "Copied from window-granularity-1.0. IDEA.v remains 280, not 200. "
                "A.28 inventory incorrectly treated IDEA as a 200 field."
            ),
        },
    ]


def prompt_length_contract() -> dict[str, Any]:
    task = v140_prompt._TASK_BLOCK_V140
    return {
        "prompt_version": "window-analysis-1.4.0",
        "explicit_length_instructions": {
            "theme": False,
            "TOPIC.v": True,
            "IDEA.v": True,
            "RELATION.v": False,
            "EXAMPLE.v": False,
            "REFERENCE.v": False,
            "UNCERTAINTY.v": False,
        },
        "stated_limits": {
            "TOPIC.v": V11_MINIMAL_TEXT_HARD_LIMITS["TOPIC.v"],
            "IDEA.v": V11_MINIMAL_TEXT_HARD_LIMITS["IDEA.v"],
        },
        "verbatim_contract_line": (
            f"TOPIC.v ≤ {V11_MINIMAL_TEXT_HARD_LIMITS['TOPIC.v']} ; "
            f"IDEA.v ≤ {V11_MINIMAL_TEXT_HARD_LIMITS['IDEA.v']}."
        ),
        "theme_mentioned_as_200": False,
        "example_mentioned_as_200": False,
        "cardinality_ceilings_stated": True,
        "source_refs_hard_max_stated": True,
        "task_contains_topic_limit": (
            f"TOPIC.v ≤ {V11_MINIMAL_TEXT_HARD_LIMITS['TOPIC.v']}" in task
        ),
        "task_contains_idea_limit": (
            f"IDEA.v ≤ {V11_MINIMAL_TEXT_HARD_LIMITS['IDEA.v']}" in task
        ),
        "task_contains_theme_200": "theme ≤ 200" not in task and "theme <= 200" not in task,
        "note": (
            "1.4.0 states cardinality ceilings and TOPIC.v/IDEA.v only. "
            "theme and EXAMPLE.v 200 are validator-only, not prompt-stated."
        ),
    }


def text_violations_with_limits(
    transport: Mapping[str, Any],
    limits: Mapping[str, int],
) -> list[str]:
    errors: list[str] = []
    for field in ("theme", "intent", "aud"):
        value = transport.get(field)
        limit = limits.get(field)
        if isinstance(value, str) and limit is not None and len(value) > limit:
            errors.append(f"{field} : {len(value)} caractères > {limit}")
    records = transport.get("records")
    if not isinstance(records, list):
        return errors
    for index, item in enumerate(records):
        if not isinstance(item, Mapping):
            continue
        kind = str(item.get("k") or "")
        value = item.get("v")
        if isinstance(value, str):
            limit = limits.get(f"{kind}.v")
            if limit is not None and len(value) > limit:
                errors.append(f"records[{index}].v ({kind}) : {len(value)} > {limit}")
    return errors


def validate_with_limits(transport: Mapping[str, Any], limits: Mapping[str, int]) -> None:
    errors = text_violations_with_limits(transport, limits)
    if errors:
        raise WindowGranularityLimitExceeded(" | ".join(errors))


def candidate_limits(ceiling: int) -> dict[str, int]:
    """
    Counterfactual only. Does not mutate production TEXT_HARD_LIMITS.

    Raises only the fields that are currently 200 (theme / EXAMPLE.v / TOPIC.m0).
    IDEA.v stays 280.
    """
    updated = dict(V11_MINIMAL_TEXT_HARD_LIMITS)
    for key, current in list(updated.items()):
        if current == 200:
            updated[key] = ceiling
    return updated


def current_limit_facts() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "production_limits": dict(V11_MINIMAL_TEXT_HARD_LIMITS),
        "v10_limits": dict(V10_LIMITS),
        "theme": CURRENT_THEME_LIMIT,
        "IDEA.v": CURRENT_IDEA_LIMIT,
        "EXAMPLE.v": CURRENT_EXAMPLE_LIMIT,
        "uniform_200": False,
        "hard_ceilings": dict(HARD_CEILINGS),
        "total_hard_ceiling": TOTAL_HARD_CEILING,
        "provider_schema_maxLength": False,
        "canonical_model_max_length": False,
    }


__all__ = [
    "candidate_limits",
    "character_definition",
    "current_limit_facts",
    "length_occurrences",
    "prompt_length_contract",
    "text_violations_with_limits",
    "validate_with_limits",
]
