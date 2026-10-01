"""Production cache/signature. Must not collide with A.1 synthetic cache."""

from __future__ import annotations

from typing import Any

from app.editorial_planner_canary_4a1.fixture import build_synthetic_source_map
from app.editorial_planner_canary_4a1.payload import canary_settings
from app.editorial_planner_preflight_4a2.payload import production_settings
from app.editorial_planning.pipeline import signature_for_source_map
from app.editorial_planning.prompt import prompt_bundle
from app.editorial_planning.schema import schema_identity
from app.file_utils import content_hash
from app.source_analysis.models import SourceMap


def _source_map_sha(source_map: SourceMap) -> str:
    import json

    raw = json.dumps(source_map.to_dict(), ensure_ascii=False, sort_keys=True)
    return content_hash(raw)


def cache_signature_audit(
    *,
    source_map_sha256: str,
    max_output_tokens: int,
) -> dict[str, Any]:
    prompt = prompt_bundle()
    schema = schema_identity()
    settings = production_settings(max_output_tokens=max_output_tokens)
    signature, inputs = signature_for_source_map(
        source_map_sha256,
        prompt["prompt_sha256"],
        schema["raw_schema_sha256"],
        settings,
    )
    signature2, _ = signature_for_source_map(
        source_map_sha256,
        prompt["prompt_sha256"],
        schema["raw_schema_sha256"],
        settings,
    )
    synthetic = build_synthetic_source_map()
    canary_sig, canary_inputs = signature_for_source_map(
        _source_map_sha(synthetic),
        prompt["prompt_sha256"],
        schema["raw_schema_sha256"],
        canary_settings(),
    )
    return {
        "signature": signature,
        "deterministic": signature == signature2,
        "inputs": inputs.to_dict(),
        "production_max_output_tokens": max_output_tokens,
        "a1_synthetic_signature": canary_sig,
        "a1_synthetic_inputs": canary_inputs.to_dict(),
        "distinct_from_a1_synthetic": signature != canary_sig,
        "distinct_reasons": [
            "source_map_sha256 differs (production pastoral vs synthetic garden)",
            "max_output_tokens differs (production selected vs canary 4096)",
        ],
        "cache_populated_for_production": False,
        "a1_cache_cannot_collide": signature != canary_sig,
    }


__all__ = ["cache_signature_audit"]
