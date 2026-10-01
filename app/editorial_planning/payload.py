"""Construction offline de la future requête Anthropic. Aucun POST."""

from __future__ import annotations

import json
from typing import Any

from app.ai.contracts import AIRequest
from app.ai.estimation import estimate_tokens
from app.ai.providers._anthropic_schema import prepare_anthropic_json_schema
from app.ai.providers.anthropic_engine import AnthropicEngine
from app.editorial_planning.constants import (
    EDITORIAL_PLAN_TRANSPORT_VERSION,
    EDITORIAL_PLANNER_PROMPT_VERSION,
    STAGE_EDITORIAL_PLANNING,
)
from app.editorial_planning.digest import render_digest
from app.editorial_planning.prompt import (
    prompt_bundle,
    prompt_fingerprint,
    render_user_prompt,
    system_prompt,
)
from app.editorial_planning.schema import build_editorial_plan_transport_schema
from app.editorial_planning.settings import PlannerSettings, frozen_production_settings
from app.file_utils import content_hash
from app.source_analysis.models import SourceMap


def build_planner_request(
    source_map: SourceMap,
    *,
    settings: PlannerSettings | None = None,
) -> AIRequest:
    settings = settings or frozen_production_settings()
    digest = render_digest(source_map)
    user = render_user_prompt(digest)
    schema = build_editorial_plan_transport_schema()
    return AIRequest(
        prompt=user,
        system_prompt=system_prompt(),
        model=settings.model,
        temperature=settings.temperature,
        max_output_tokens=settings.max_output_tokens,
        response_schema=schema,
        thinking_mode=settings.thinking_mode,
        effort=settings.effort,
        thinking_budget_tokens=None,
        metadata={
            "stage": STAGE_EDITORIAL_PLANNING,
            "prompt_version": EDITORIAL_PLANNER_PROMPT_VERSION,
            "transport_version": EDITORIAL_PLAN_TRANSPORT_VERSION,
            "authorization_scope": "phase4a-offline-payload-only",
            "schema_sha256": content_hash(
                json.dumps(schema, ensure_ascii=False, sort_keys=True)
            ),
        },
    )


def build_future_anthropic_payload(
    source_map: SourceMap,
    *,
    settings: PlannerSettings | None = None,
) -> dict[str, Any]:
    """
    Payload Messages exact, sans HTTP. api_key factice : build_payload
    n'appelle pas resolve_api_key.
    """
    settings = settings or frozen_production_settings()
    request = build_planner_request(source_map, settings=settings)
    engine = AnthropicEngine(model=settings.model, api_key="offline-phase4a-unused")
    payload = engine.build_payload(request, settings.model)
    secrets = ("x-api-key", "api_key", "authorization")
    for key in secrets:
        payload.pop(key, None)
    return payload


def payload_audit(
    source_map: SourceMap,
    *,
    settings: PlannerSettings | None = None,
) -> dict[str, Any]:
    settings = settings or frozen_production_settings()
    request = build_planner_request(source_map, settings=settings)
    payload = build_future_anthropic_payload(source_map, settings=settings)
    system = request.system_prompt or ""
    user = request.prompt
    digest = render_digest(source_map)
    schema = build_editorial_plan_transport_schema()
    adapted = prepare_anthropic_json_schema(schema)
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return {
        "secrets_included": False,
        "model": payload.get("model"),
        "max_tokens": payload.get("max_tokens"),
        "thinking_present": "thinking" in payload,
        "effort_present": "effort" in (payload.get("output_config") or {}),
        "temperature_present": "temperature" in payload,
        "structured_output": (
            ((payload.get("output_config") or {}).get("format") or {}).get("type")
        ),
        "prompt_fingerprint": prompt_fingerprint(system, user),
        "digest_chars": len(digest),
        "digest_bytes": len(digest.encode("utf-8")),
        "user_prompt_chars": len(user),
        "system_prompt_chars": len(system),
        "payload_chars": len(encoded),
        "payload_bytes": len(encoded.encode("utf-8")),
        "payload_sha256": content_hash(encoded),
        "local_input_token_estimate": estimate_tokens(
            system + "\n" + user, model=settings.model
        ).to_dict(),
        "adapted_schema_in_payload": adapted
        == ((payload.get("output_config") or {}).get("format") or {}).get("schema"),
        "prompt": prompt_bundle(),
        "stage": STAGE_EDITORIAL_PLANNING,
    }
