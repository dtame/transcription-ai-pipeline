"""Carte des plafonds de longueur à chaque frontière. Offline."""

from __future__ import annotations

from typing import Any

from app.ai.providers._anthropic_schema import _UNSUPPORTED_KEYWORDS
from app.source_analysis.validator import validate_source_map
from app.source_analysis_local_v2.granularity import V11_MINIMAL_TEXT_HARD_LIMITS
from app.source_analysis_local_v3.schema import (
    build_semantic_transport_v3_schema,
    build_semantic_transport_v31_local_lite_schema,
    measure_v31_local_lite_schema_pair,
    semantic_transport_v31_local_lite_fingerprint,
)
from app.source_analysis_v3_second_window.constants import EXPECTED_SCHEMA_HASH
from app.source_analysis_v3_symbolic_grammar_canary.constants import (
    EXPECTED_ADAPTED_SCHEMA_BYTES,
    EXPECTED_RAW_SCHEMA_BYTES,
)
from app.source_analysis_v31_length_ceiling.constants import (
    MODE,
    PHASE,
    SCHEMA_VERSION,
)
from app.source_analysis_v31_length_ceiling.lengths import (
    character_definition,
    current_limit_facts,
    length_occurrences,
    prompt_length_contract,
)


def _schema_has_max_length(schema: dict[str, Any]) -> bool:
    serialized = str(schema)
    return "maxLength" in serialized or "minLength" in serialized


def build_boundary_map() -> dict[str, Any]:
    raw = build_semantic_transport_v31_local_lite_schema()
    v3 = build_semantic_transport_v3_schema()
    measured = measure_v31_local_lite_schema_pair()
    prompt = prompt_length_contract()
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "character_definition": character_definition(),
        "occurrences": length_occurrences(),
        "current_limits": current_limit_facts(),
        "prompt": prompt,
        "boundaries": [
            {
                "boundary": "provider_response_schema",
                "limit": None,
                "affected_fields": ["theme", "intent", "aud", "records[].v", "records[].m[]"],
                "hard_soft": "none",
                "reason": (
                    "Proven grammar 588/650 has type=string only. "
                    "Anthropic adapter strips minLength/maxLength as unsupported."
                ),
                "maxLength_present": _schema_has_max_length(raw),
                "unsupported_keywords_include_maxLength": "maxLength"
                in _UNSUPPORTED_KEYWORDS,
            },
            {
                "boundary": "semantic_transport_schema",
                "limit": None,
                "affected_fields": ["theme", "v"],
                "hard_soft": "none",
                "reason": (
                    "semantic-transport-v3 and v3.1-local-lite share the same "
                    "wire schema. No minLength/maxLength."
                ),
                "v3_identical_wire": raw == v3,
                "raw_bytes": measured.get("raw_bytes"),
                "adapted_bytes": measured.get("adapted_bytes"),
                "schema_hash": semantic_transport_v31_local_lite_fingerprint(),
                "expected_schema_hash": EXPECTED_SCHEMA_HASH,
                "matches_a18": (
                    measured.get("raw_bytes") == EXPECTED_RAW_SCHEMA_BYTES
                    and measured.get("adapted_bytes") == EXPECTED_ADAPTED_SCHEMA_BYTES
                ),
            },
            {
                "boundary": "transport_decoder",
                "limit": None,
                "affected_fields": ["structural kinds/handles/src"],
                "hard_soft": "none_for_length",
                "reason": "Decoder validates shape, handles, SRC. It does not cap string length.",
            },
            {
                "boundary": "local_normalized_representation",
                "limit": None,
                "affected_fields": ["WindowSemanticResult.value"],
                "hard_soft": "none",
                "reason": "Normalized records store the decoded string unchanged.",
            },
            {
                "boundary": "local_validator",
                "limit": dict(V11_MINIMAL_TEXT_HARD_LIMITS),
                "affected_fields": list(V11_MINIMAL_TEXT_HARD_LIMITS),
                "hard_soft": "hard",
                "reason": (
                    "validate_v2_transport_granularity uses len(str). "
                    "WindowGranularityLimitExceeded. No truncation."
                ),
                "enforced_by": "Python post-parse validator only",
            },
            {
                "boundary": "consolidation",
                "limit": None,
                "affected_fields": ["canonical summaries after reconstruction"],
                "hard_soft": "none_for_local_value_length",
                "reason": (
                    "Consolidation consumes reconstructed SourceMap, not raw "
                    "local-lite v strings. No 200-character gate found."
                ),
            },
            {
                "boundary": "canonical_sourcemap_model",
                "limit": None,
                "affected_fields": [
                    "header.main_theme",
                    "Idea.summary",
                    "Example.summary",
                    "Topic.label",
                ],
                "hard_soft": "none",
                "reason": (
                    "Canonical validator requires non-empty main_theme and "
                    "controlled vocabularies. No independent 200-character cap. "
                    f"validate_source_map exists: {callable(validate_source_map)}."
                ),
            },
            {
                "boundary": "canonical_validator",
                "limit": None,
                "affected_fields": ["required/non-empty/vocab"],
                "hard_soft": "none_for_length",
                "reason": "No len(field) > 200 check in app/source_analysis/validator.py.",
            },
            {
                "boundary": "serialization_publication",
                "limit": None,
                "affected_fields": ["source_map.json"],
                "hard_soft": "none",
                "reason": "Publication is blocked (NOT PUBLISHED). No length serializer cap.",
            },
        ],
        "provider_schema_enforces_200": False,
        "canonical_model_requires_200": False,
        "200_enforced_by": "local Python validator (window-granularity-1.1-minimal)",
        "200_limit_origin": (
            "A.2 token-budget / anti-verbosity conservative bound, "
            "carried from window-granularity-1.0 into v2/v3.1 without "
            "re-validation against real local-lite outputs"
        ),
        "how_win003_exceeded_if_schema_had_maxlength": (
            "N/A — schema does not encode maxLength. Provider returned 212/213 "
            "because nothing in the grammar forbade it. Prompt stated IDEA.v≤280 "
            "only; theme/EXAMPLE 200 are post-parse only."
        ),
    }


__all__ = ["build_boundary_map"]
