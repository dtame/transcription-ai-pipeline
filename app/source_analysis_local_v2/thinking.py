"""
Audit local de la capacité thinking Anthropic.

Code + contrats installés + forensics CALL C uniquement.
Aucun appel provider. Aucun paramètre inventé.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path
from typing import Any, Mapping

from app.ai.contracts import AIRequest
from app.ai.providers.anthropic_engine import AnthropicEngine
from app.source_analysis_local_v2.constants import (
    CALL_C_FINISH,
    CALL_C_OUTPUT,
    CALL_C_PROVIDER_INPUT,
    CALL_C_THINKING_TOKENS,
    PHASE,
    SCHEMA_VERSION,
    SMALL_SIGNATURE,
)
from app.source_analysis_output_ceiling_review.facts import (
    forensic_paths,
    load_small_forensics,
)

_ENGINE_PATH = Path(inspect.getfile(AnthropicEngine))
_GUESSED_PARAMS = (
    "thinking",
    "thinking_budget",
    "budget_tokens",
    "reasoning_effort",
    "reasoning",
    "extended_thinking",
)


def _payload_source_fields() -> dict[str, Any]:
    source = _ENGINE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    assigned: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "build_payload":
            for child in ast.walk(node):
                if isinstance(child, ast.Subscript) and isinstance(
                    child.slice, ast.Constant
                ):
                    if isinstance(child.slice.value, str):
                        assigned.append(child.slice.value)
    unique = list(dict.fromkeys(assigned))
    return {
        "build_payload_keys_literal": unique,
        "thinking_related_keys": [
            key for key in unique if any(token in key.lower() for token in _GUESSED_PARAMS)
        ],
        "source_contains_guessed_param": {
            name: name in source for name in _GUESSED_PARAMS
        },
    }


def _airequest_fields() -> list[str]:
    return list(AIRequest.__dataclass_fields__)


def _call_c_thinking_metadata(forensics: Mapping[str, Any] | None = None) -> dict[str, Any]:
    data = forensics or load_small_forensics()
    composition = data.get("output_composition") or {}
    http = data.get("http_envelope") or {}
    return {
        "signature": SMALL_SIGNATURE,
        "provider_input_tokens": CALL_C_PROVIDER_INPUT,
        "provider_output_tokens": CALL_C_OUTPUT,
        "finish_reason": CALL_C_FINISH,
        "thinking_tokens": CALL_C_THINKING_TOKENS,
        "thinking_tokens_from_forensics": composition.get("provider_thinking_tokens"),
        "implied_non_thinking_output_tokens": composition.get(
            "implied_non_thinking_output_tokens"
        ),
        "thinking_share_of_output_tokens": composition.get(
            "thinking_share_of_output_tokens"
        ),
        "thinking_plaintext_present": composition.get("thinking_plaintext_present"),
        "http_block_types": (http.get("content_metadata") or {}).get("block_types")
        if isinstance(http, Mapping)
        else None,
        "request_payload_persisted_in_envelope": False,
        "envelope_has_thinking_request_field": False,
    }


def audit_thinking_capability(
    *,
    project_name: str | None = None,
    sortie_dir: Path | None = None,
) -> dict[str, Any]:
    payload_fields = _payload_source_fields()
    request_fields = _airequest_fields()
    guessed_on_request = [
        name for name in _GUESSED_PARAMS if name in request_fields
    ]
    thinking_configured = bool(payload_fields["thinking_related_keys"] or guessed_on_request)
    call_c = _call_c_thinking_metadata()
    verified_locally = False
    classification = "UNVERIFIED"
    if thinking_configured:
        classification = "PRESENT_IN_LOCAL_CODE_UNVERIFIED_SERVER"
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "THINKING_CAP_CONTROL": classification,
        "verified_locally": "YES" if verified_locally else "NO",
        "supported_parameter_name": None,
        "minimum_constraint": None,
        "maximum_constraint": None,
        "relationship_with_max_tokens": (
            "CALL C evidence: thinking tokens are counted inside "
            "usage.output_tokens / max_tokens. No separate request field "
            "is present in the current Anthropic payload builder."
        ),
        "current_payload_thinking_config": {
            "explicit_thinking_field_sent": False,
            "safe_configuration_fields": [
                "model",
                "max_tokens",
                "messages",
                "system",
                "temperature",
                "output_config.format",
            ],
            "build_payload_literal_keys": payload_fields["build_payload_keys_literal"],
            "guessed_parameters_not_implemented": list(_GUESSED_PARAMS),
        },
        "ai_request_fields": request_fields,
        "call_c_thinking_metadata": call_c,
        "thinking_mode_observed": {
            "explicitly_requested_by_app": False,
            "provider_model_default": "UNKNOWN",
            "adaptive": "UNKNOWN",
            "classification": "UNKNOWN",
            "evidence": (
                "Application build_payload sends no thinking field. "
                "CALL C envelope persists response usage/blocks, not the "
                "request body. Response contained a thinking content block "
                f"and usage thinking_tokens={CALL_C_THINKING_TOKENS}. "
                "Whether the model defaulted or adapted cannot be proven "
                "from local evidence."
            ),
        },
        "implemented_guessed_parameter": False,
        "activated_for_historical_stages": False,
        "unknowns": [
            "whether this model accepts an explicit thinking cap",
            "parameter name if any",
            "min/max constraints",
            "whether CALL A/B used thinking",
            "whether JSON would close if thinking were capped",
        ],
        "forensic_paths": {
            str(key): str(path)
            for key, path in forensic_paths(
                project_name or "pastoral_retreat_v2_validation",
                sortie_dir=sortie_dir,
            ).items()
        },
        "real_provider_call_authorized": False,
    }


__all__ = ["audit_thinking_capability"]
