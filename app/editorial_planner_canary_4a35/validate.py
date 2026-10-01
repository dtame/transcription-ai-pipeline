"""Offline technical validation from a persisted 1.0.2 provider response."""

from __future__ import annotations

from typing import Any, Mapping

from app.editorial_planner_canary_4a3.validate import (
    interpret_production_response as _interpret_a3,
)
from app.editorial_planner_canary_4a35.accountability import exact_accountability
from app.editorial_planner_canary_4a35.constants import (
    PRODUCTION_MAX_OUTPUT_TOKENS,
    PROJECT_NAME,
    PROMPT_VERSION,
)
from app.editorial_planner_forensics_4a34.payload import production_settings
from app.editorial_planning.prompt_v102 import prompt_bundle
from app.editorial_planning.writer import render_editorial_plan
from app.file_utils import content_hash
from app.source_analysis.models import SourceMap


def interpret_production_response(
    parsed: Mapping[str, Any] | None,
    *,
    source_map: SourceMap,
    source_map_sha256: str,
    source_map_bytes: int,
    source_map_path_value: str,
    raw_text: str | None = None,
    canonical_document_language: str,
) -> dict[str, Any]:
    """
    Frozen reconstruction / validator path, with 1.0.2 prompt fingerprint.

    CH/SEC assignment stays the frozen local contract. Prompt provenance on
    the candidate records editorial-planner-1.0.2.
    """
    settings = production_settings(max_output_tokens=PRODUCTION_MAX_OUTPUT_TOKENS)
    prompt = prompt_bundle(canonical_document_language)
    result = _interpret_a3(
        parsed,
        source_map=source_map,
        source_map_sha256=source_map_sha256,
        source_map_bytes=source_map_bytes,
        source_map_path_value=source_map_path_value,
        raw_text=raw_text,
    )
    plan = result.get("plan")
    if isinstance(plan, dict):
        metadata = dict(plan.get("metadata") or {})
        metadata["prompt_version"] = PROMPT_VERSION
        plan["metadata"] = metadata
        rendered = render_editorial_plan(plan)
        stamped = content_hash(rendered)
        result["plan"] = plan
        result["plan_sha256"] = stamped
        result["plan_bytes"] = len(rendered.encode("utf-8"))
        result["plan_chars"] = len(rendered)
        if result.get("canonical_reconstruction") == "PASS":
            replay = _interpret_a3(
                parsed,
                source_map=source_map,
                source_map_sha256=source_map_sha256,
                source_map_bytes=source_map_bytes,
                source_map_path_value=source_map_path_value,
                raw_text=raw_text,
            )
            replay_plan = replay.get("plan")
            if isinstance(replay_plan, dict):
                replay_meta = dict(replay_plan.get("metadata") or {})
                replay_meta["prompt_version"] = PROMPT_VERSION
                replay_plan["metadata"] = replay_meta
                replay_hash = content_hash(render_editorial_plan(replay_plan))
                result["plan_sha256_replay"] = replay_hash
                result["deterministic_replay"] = (
                    "PASS" if replay_hash == stamped else "FAIL"
                )
    accountability = exact_accountability(
        result.get("plan") if isinstance(result.get("plan"), Mapping) else None,
        source_map,
        transport=result.get("transport")
        if isinstance(result.get("transport"), Mapping)
        else None,
    )
    result["accountability"] = accountability
    result["prompt_version"] = PROMPT_VERSION
    result["prompt_sha256"] = prompt["prompt_sha256"]
    result["settings_max_output_tokens"] = settings.max_output_tokens
    result["project"] = PROJECT_NAME
    result["canonical_document_language"] = canonical_document_language
    return result


__all__ = ["interpret_production_response"]
