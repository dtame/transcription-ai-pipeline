"""Limites prompt / schéma / post-validation. Generation C inchangée."""

from __future__ import annotations

import json
from typing import Any

from app.ai.providers._anthropic_schema import (
    _UNSUPPORTED_KEYWORDS,
    audit_unsupported_features,
    prepare_anthropic_json_schema,
)
from app.source_analysis.schema_complexity import analyze_schema_complexity
from app.source_analysis.ultra_compact_schema import build_ultra_compact_response_schema
from app.source_analysis.window_analyzer import analyze_window, recover_window_from_transport
from app.source_analysis.window_granularity import (
    HARD_CEILINGS,
    SOURCE_REFS_HARD_MAX,
    TEXT_HARD_LIMITS,
    TOTAL_HARD_CEILING,
    validate_window_result_granularity,
    validate_window_transport_granularity,
)
from app.source_analysis_output_ceiling_review.constants import (
    GENERATION_C_ANTHROPIC_SHA,
    GENERATION_C_RAW_SHA,
)
from app.source_analysis_timeout_config.audit import generation_c_hashes


def _generation_c_limits() -> dict[str, Any]:
    schema = build_ultra_compact_response_schema()
    serialized = json.dumps(schema, ensure_ascii=False, sort_keys=True)
    adapted = prepare_anthropic_json_schema(schema)
    adapted_serialized = json.dumps(adapted, ensure_ascii=False, sort_keys=True)
    unsupported = audit_unsupported_features(adapted)
    hashes = generation_c_hashes()
    return {
        "version": "semantic-transport-v1 / Generation C",
        "mutated_this_phase": False,
        "raw_sha256": hashes.get("raw_sha256"),
        "raw_expected": GENERATION_C_RAW_SHA,
        "raw_unchanged": hashes.get("raw_sha256") == GENERATION_C_RAW_SHA,
        "anthropic_sha256": hashes.get("anthropic_sha256"),
        "anthropic_expected": GENERATION_C_ANTHROPIC_SHA,
        "anthropic_unchanged": hashes.get("anthropic_sha256") == GENERATION_C_ANTHROPIC_SHA,
        "raw_bytes": len(serialized.encode("utf-8")),
        "adapted_bytes": len(adapted_serialized.encode("utf-8")),
        "complexity": analyze_schema_complexity(schema),
        "adapted_complexity": analyze_schema_complexity(adapted),
        "constraints_on_records_length": False,
        "constraints_on_value_length": False,
        "constraints_on_source_ref_count": False,
        "constraints_on_record_kinds": False,
        "maxItems_present": "maxItems" not in serialized,
        "maxLength_present": "maxLength" not in serialized,
        "enum_present": "enum" not in serialized,
        "provider_unsupported_keywords_documented": list(_UNSUPPORTED_KEYWORDS),
        "adapted_unsupported_findings": {
            key: values for key, values in unsupported.items() if values
        },
        "maxItems_locally_classified": "UNSUPPORTED_BY_ANTHROPIC_STRUCTURED_OUTPUTS",
        "grammar_history": (
            "Compact schemas with richer constraints produced "
            "'compiled grammar is too large' in 3B.4 / 3B.4.1. "
            "Generation C removed enums, patterns, minItems, maxItems, "
            "and numeric constraints to gain grammar compatibility."
        ),
    }


def build_contract_analysis() -> dict[str, Any]:
    generation_c = _generation_c_limits()
    analyzer_source = __import__(
        "inspect"
    ).getsource(analyze_window)
    recover_source = __import__(
        "inspect"
    ).getsource(recover_window_from_transport)
    granularity_after_generate = (
        "validate_window_transport_granularity" in analyzer_source
        and analyzer_source.find("engine.generate")
        < analyzer_source.find("validate_window_transport_granularity")
    )
    return {
        "prompt_only_limits": {
            "soft_targets": "window-analysis-1.1 GRANULARITÉ block",
            "hard_ceilings_in_prompt": dict(HARD_CEILINGS),
            "total_hard_ceiling_in_prompt": TOTAL_HARD_CEILING,
            "source_refs_hard_max_in_prompt": SOURCE_REFS_HARD_MAX,
            "text_hard_limits_in_prompt": dict(TEXT_HARD_LIMITS),
            "grouping_instruction": True,
            "compactness_instruction": True,
            "overflow_token_instruction": True,
            "provider_enforced": False,
        },
        "provider_enforced_limits": {
            "records_maxItems": False,
            "string_maxLength": False,
            "source_ref_maxItems": False,
            "record_kind_enum": False,
            "thinking_budget": False,
            "status": (
                "Generation C schema is structurally permissive. "
                "Anthropic adapter documents maxItems as unsupported. "
                "No thinking budget is sent on the request."
            ),
        },
        "post_generation_limits": {
            "validate_window_transport_granularity": True,
            "validate_window_result_granularity": True,
            "functions": [
                validate_window_transport_granularity.__name__,
                validate_window_result_granularity.__name__,
            ],
            "runs_after_generate": granularity_after_generate,
            "recover_also_validates": "validate_window_transport_granularity"
            in recover_source,
            "can_reject_excessive_output": True,
            "can_prevent_spending_32000_tokens": False,
        },
        "lifecycle": [
            "engine.generate (provider spends tokens)",
            "parse_structured_output (fails on truncated JSON)",
            "persist forensics if AIStructuredOutputError",
            "validate_window_transport_granularity — NEVER REACHED on CALL C",
            "decode / validate_window_result / write result — NEVER REACHED",
        ],
        "generation_c": generation_c,
        "maxItems_feasibility": {
            "investigated_offline": True,
            "provider_canary_run": False,
            "local_adapter_classifies_maxItems": "unsupported",
            "historical_grammar_failures_with_richer_schemas": True,
            "reintroduced_this_phase": False,
            "could_a_simpler_schema_try_maxItems": (
                "UNKNOWN without a future grammar canary. Local docs say no."
            ),
            "grammar_complexity_if_maxItems_added": "HIGHER",
        },
        "max_output": {
            "current": 32000,
            "raise_above_32000": "NOT ADOPTED — may enlarge runaway thinking/cost",
            "lower_alone": "NOT ADOPTED — earlier truncation unless contract changes",
            "evaluated_only": True,
        },
        "input_size": {
            "shrinking_large_to_small_prevented_32k": False,
            "another_halving_assumed_to_solve_output": False,
            "small_planner_still_useful_for_input": True,
        },
        "output_risk_findings": [
            "Hard ceilings are prompt + post-generation only.",
            "Post-validation cannot prevent the 32000-token spend.",
            "Generation C does not bound records, value length, or source refs.",
            "Thinking tokens share max_tokens and are not request-capped.",
        ],
    }
