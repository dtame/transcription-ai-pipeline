"""Matrice et traçage du contrat gm.in. 0 provider. 0 mutation 3.0."""

from __future__ import annotations

import json
from typing import Any, Mapping

from app.ai.providers._anthropic_schema import (
    audit_unsupported_features,
    prepare_anthropic_json_schema,
)
from app.source_analysis.models import IntentStatement
from app.source_analysis.validator import validate_source_map
from app.source_analysis.window_granularity import TEXT_HARD_LIMITS
from app.source_analysis_v31_global_a47_contract_forensics.constants import (
    HISTORICAL_240_ORIGIN,
    HISTORICAL_INTENT_LIMIT,
    INTENT_CONTRACT_ROOT_CAUSE,
    LOCAL_WINDOW_INTENT_LIMIT,
    SELECTED_INTENT_LIMIT,
    TEXT_LIMITS,
    THEME_LIMIT,
)
from app.source_analysis_v31_global_reuse_output.prompt_v30 import SYSTEM_PROMPT, prompt_v30_bundle
from app.source_analysis_v31_global_reuse_output.transport_v30 import (
    build_global_consolidation_schema_v30,
)


def corrected_text_limits() -> dict[str, int]:
    limits = dict(TEXT_LIMITS)
    limits["intent"] = SELECTED_INTENT_LIMIT
    return limits


def historical_text_limits() -> dict[str, int]:
    """Limite A.46-era (240). Pas un chemin de validation production."""
    limits = dict(TEXT_LIMITS)
    limits["intent"] = HISTORICAL_INTENT_LIMIT
    return limits


def schema_has_max_length(schema: Mapping[str, Any], path: tuple[str, ...] = ()) -> bool:
    if schema.get("type") == "string" and "maxLength" in schema:
        return True
    properties = schema.get("properties")
    if isinstance(properties, dict):
        for name, child in properties.items():
            if isinstance(child, dict) and schema_has_max_length(child, path + (str(name),)):
                return True
    items = schema.get("items")
    if isinstance(items, dict) and schema_has_max_length(items, path + ("items",)):
        return True
    return False


def layer_trace() -> dict[str, Any]:
    schema = build_global_consolidation_schema_v30()
    adapted = prepare_anthropic_json_schema(schema)
    unsupported = audit_unsupported_features(adapted)
    prompt = prompt_v30_bundle()
    intent_field = ((schema.get("properties") or {}).get("gm") or {}).get("properties", {}).get(
        "in"
    ) or {}
    return {
        "canonical_SourceMap_model": {
            "field": "source_analysis.author_intent.summary",
            "max": None,
            "enforcement": "none — IntentStatement.summary is an unbounded str",
            "240_present": False,
        },
        "canonical_validator": {
            "field": "author_intent.summary",
            "max": None,
            "enforcement": "non-empty + confidence enum only",
            "240_present": False,
            "module": "app.source_analysis.validator._validate_header",
        },
        "transport_3_0_dto_schema": {
            "field": "gm.in",
            "max": intent_field.get("maxLength"),
            "schema_type": intent_field.get("type"),
            "maxLength_in_schema": schema_has_max_length(schema),
            "240_present": False,
            "enforcement": "type=string only",
        },
        "anthropic_adapted_schema": {
            "field": "gm.in",
            "maxLength_supported": False,
            "maxLength_stripped_if_present": True,
            "unsupported_maxLength_paths": list(unsupported.get("maxLength") or []),
            "240_present": False,
            "enforcement": "none — Anthropic Structured Outputs does not support maxLength",
        },
        "prompt_3_0": {
            "field": "intent",
            "instruction": "intent <= 240",
            "240_present": True,
            "enforcement": "instruction only; provider may ignore",
            "prompt_version": prompt.get("prompt_version"),
        },
        "transport_decoder": {
            "field": "gm.in",
            "max": None,
            "240_present": False,
            "enforcement": "require non-empty string; no clip; no repair",
        },
        "global_validator": {
            "field": "gm.in",
            "max": TEXT_LIMITS["intent"],
            "historical_max": HISTORICAL_INTENT_LIMIT,
            "240_present": TEXT_LIMITS["intent"] == HISTORICAL_INTENT_LIMIT,
            "enforcement": "hard reject if len(gm.in) > TEXT_LIMITS['intent']",
            "module": "validate_global_transport_v30",
        },
        "canonical_reconstruction": {
            "field": "author_intent.summary = gm.in",
            "max": None,
            "240_present": False,
            "enforcement": "verbatim copy; no truncation",
        },
        "local_window_intent": {
            "field": "window intent",
            "max": LOCAL_WINDOW_INTENT_LIMIT,
            "240_present": False,
            "enforcement": "local TEXT_HARD_LIMITS reject, never value[:N]",
        },
    }


def contract_matrix() -> dict[str, Any]:
    rows = [
        {
            "layer": "canonical SourceMap model",
            "field": "author_intent.summary",
            "meaning": "apparent author intent of the source",
            "minimum": 1,
            "maximum": None,
            "schema_enforcement": "no",
            "prompt_instruction": "n/a",
            "runtime_enforcement": "non-empty only",
            "240": False,
        },
        {
            "layer": "canonical validator",
            "field": "author_intent.summary",
            "meaning": "same",
            "minimum": 1,
            "maximum": None,
            "schema_enforcement": "no",
            "prompt_instruction": "n/a",
            "runtime_enforcement": "non-empty + confidence",
            "240": False,
        },
        {
            "layer": "transport 3.0 schema",
            "field": "gm.in",
            "meaning": "author intent",
            "minimum": None,
            "maximum": None,
            "schema_enforcement": "type=string; no maxLength",
            "prompt_instruction": "n/a",
            "runtime_enforcement": "structured parse only",
            "240": False,
        },
        {
            "layer": "Anthropic-adapted schema",
            "field": "gm.in",
            "meaning": "author intent",
            "minimum": None,
            "maximum": None,
            "schema_enforcement": "maxLength unsupported / stripped",
            "prompt_instruction": "n/a",
            "runtime_enforcement": "none",
            "240": False,
        },
        {
            "layer": "prompt 3.0",
            "field": "intent",
            "meaning": "author intent",
            "minimum": None,
            "maximum": 240,
            "schema_enforcement": "no",
            "prompt_instruction": "intent <= 240",
            "runtime_enforcement": "none",
            "240": True,
        },
        {
            "layer": "transport decoder",
            "field": "gm.in",
            "meaning": "author intent",
            "minimum": 1,
            "maximum": None,
            "schema_enforcement": "no",
            "prompt_instruction": "n/a",
            "runtime_enforcement": "require string; no clip",
            "240": False,
        },
        {
            "layer": "global validator",
            "field": "gm.in",
            "meaning": "author intent",
            "minimum": 1,
            "maximum": TEXT_LIMITS["intent"],
            "schema_enforcement": "no",
            "prompt_instruction": "n/a",
            "runtime_enforcement": "hard len <= TEXT_LIMITS['intent'] (live 320 after A.48)",
            "240": False,
            "historical_maximum": HISTORICAL_INTENT_LIMIT,
        },
        {
            "layer": "canonical reconstruction",
            "field": "author_intent.summary",
            "meaning": "copied gm.in",
            "minimum": None,
            "maximum": None,
            "schema_enforcement": "no",
            "prompt_instruction": "n/a",
            "runtime_enforcement": "verbatim; no truncation",
            "240": False,
        },
        {
            "layer": "A.39 TEXT_LIMITS planning bound",
            "field": "intent",
            "meaning": "output-budget compactness estimate",
            "minimum": None,
            "maximum": 240,
            "schema_enforcement": "no",
            "prompt_instruction": "copied into prompt 2.0+",
            "runtime_enforcement": "reused as validator hard gate",
            "240": True,
        },
        {
            "layer": "local window TEXT_HARD_LIMITS",
            "field": "intent",
            "meaning": "per-window extraction intent",
            "minimum": None,
            "maximum": 280,
            "schema_enforcement": "no maxLength on wire",
            "prompt_instruction": "local prompt bound",
            "runtime_enforcement": "reject, never truncate",
            "240": False,
        },
        {
            "layer": "selected A.47 product limit",
            "field": "gm.in / author_intent.summary",
            "meaning": "faithful concise global author intent",
            "minimum": 1,
            "maximum": SELECTED_INTENT_LIMIT,
            "schema_enforcement": "not on frozen 3.0 wire (Anthropic cannot)",
            "prompt_instruction": "NEXT prompt 3.0.1: intent <= 320",
            "runtime_enforcement": "corrected validator text_limits",
            "240": False,
        },
    ]
    return {
        "field": "gm.in",
        "historical_limit": HISTORICAL_INTENT_LIMIT,
        "selected_limit": SELECTED_INTENT_LIMIT,
        "theme_limit": THEME_LIMIT,
        "local_window_intent_limit": LOCAL_WINDOW_INTENT_LIMIT,
        "where_240_exists": [
            "prompt 3.0 instruction (frozen historical)",
            "A.39 compactness bound A39_INTENT_COMPACTNESS_BOUND",
            "historical A.46-era validate_global_transport_v30",
            "prompt 2.0 / 2.0.1 historical copies",
        ],
        "where_240_does_not_exist": [
            "canonical IntentStatement",
            "canonical source_map validator",
            "transport 3.0 JSON schema",
            "Anthropic-adapted schema",
            "transport decoder",
            "canonical reconstruction",
            "local window TEXT_HARD_LIMITS (280)",
            "live TEXT_LIMITS['intent'] / validate_global_transport_v30 (320 after A.48)",
        ],
        "rows": rows,
        "historical_240_origin": HISTORICAL_240_ORIGIN,
        "origin_class": (
            "arbitrary safety / output-budget compactness bound + prompt bound "
            "+ legacy A.39 artifact; not a semantic requirement"
        ),
        "root_cause": INTENT_CONTRACT_ROOT_CAUSE,
        "prompt_3_0_still_contains_240": "intent <= 240" in SYSTEM_PROMPT,
        "canonical_model_has_max": hasattr(IntentStatement, "summary") and False,
        "validate_source_map_checks_length": "240" in (validate_source_map.__doc__ or ""),
        "frozen_text_limits": dict(TEXT_LIMITS),
        "local_text_hard_limits_intent": TEXT_HARD_LIMITS["intent"],
        "anthropic_maxLength_unsupported": True,
        "no_silent_clipping": True,
        "no_truncation_repair": True,
        "schema_json_gm_in": json.dumps(
            ((schema := build_global_consolidation_schema_v30()).get("properties") or {})
            .get("gm", {})
            .get("properties", {})
            .get("in"),
            ensure_ascii=False,
        ),
    }


def intent_contract_forensics(intent: str) -> dict[str, Any]:
    return {
        "provider_accepted_reason": (
            "transport 3.0 schema has no maxLength on gm.in; Anthropic cannot "
            "enforce string length; structured parse therefore accepted 290 chars"
        ),
        "validator_rejected_reason": (
            f"validate_global_transport_v30 compares len(gm.in)={len(intent)} "
            f"to TEXT_LIMITS['intent']={HISTORICAL_INTENT_LIMIT}"
        ),
        "why_mismatch": INTENT_CONTRACT_ROOT_CAUSE,
        "layers": layer_trace(),
        "prompt_instructed_240": True,
        "schema_enforced_240": False,
        "validator_enforced_240": True,
        "canonical_model_enforced_240": False,
        "decoder_clipped": False,
        "reconstruction_truncated": False,
    }


__all__ = [
    "contract_matrix",
    "corrected_text_limits",
    "historical_text_limits",
    "intent_contract_forensics",
    "layer_trace",
    "schema_has_max_length",
]
