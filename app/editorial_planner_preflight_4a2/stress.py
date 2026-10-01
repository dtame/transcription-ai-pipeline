"""FakeAI / synthetic full-scale stress. 0 real provider calls."""

from __future__ import annotations

import json
from typing import Any

from app.ai.providers.fake import FakeAIEngine, FakeReply
from app.ai.retry import no_delay_policy
from app.editorial_planner_preflight_4a2.payload import (
    build_production_request,
    production_settings,
)
from app.editorial_planner_preflight_4a2.scenarios import (
    all_assigned_transport,
    expected_transport,
    max_structure_transport,
    mixed_transport,
    reuse_transport,
    strip_meta,
)
from app.editorial_planning.pipeline import materialize_plan
from app.editorial_planning.prompt import prompt_bundle
from app.editorial_planning.schema import schema_identity
from app.source_analysis.models import SourceMap


def _materialize(
    transport: dict[str, Any],
    source_map: SourceMap,
    *,
    source_map_sha256: str,
    source_map_bytes: int,
    max_output_tokens: int,
) -> dict[str, Any]:
    prompt = prompt_bundle()
    schema = schema_identity()
    settings = production_settings(max_output_tokens=max_output_tokens)
    payload = strip_meta(transport)
    plan, validation, digest = materialize_plan(
        payload,
        source_map,
        source_map_sha256=source_map_sha256,
        source_map_bytes=source_map_bytes,
        prompt_sha256=prompt["prompt_sha256"],
        response_schema_sha256=schema["raw_schema_sha256"],
        source_map_path_value="sortie/pastoral_retreat_v2_validation/analysis/source_map.json",
        settings=settings,
    )
    plan2, validation2, digest2 = materialize_plan(
        payload,
        source_map,
        source_map_sha256=source_map_sha256,
        source_map_bytes=source_map_bytes,
        prompt_sha256=prompt["prompt_sha256"],
        response_schema_sha256=schema["raw_schema_sha256"],
        source_map_path_value="sortie/pastoral_retreat_v2_validation/analysis/source_map.json",
        settings=settings,
    )
    assigned = sum(1 for item in plan.idea_coverage if item.disposition == "ASSIGNED")
    deferred = sum(1 for item in plan.idea_coverage if item.disposition == "DEFERRED")
    excluded = sum(1 for item in plan.idea_coverage if item.disposition == "EXCLUDED")
    reused = sum(1 for item in plan.idea_coverage if item.additional_section_ids)
    covered = len(plan.idea_coverage)
    return {
        "validation_status": validation.status,
        "errors": list(validation.errors)[:12],
        "warnings": list(validation.warnings)[:12],
        "covered": covered,
        "assigned": assigned,
        "deferred": deferred,
        "excluded": excluded,
        "reused": reused,
        "chapters": len(plan.chapters),
        "sections": len(plan.all_sections()),
        "coverage_complete": covered == len(source_map.ideas),
        "silent_omissions": len(source_map.ideas) - covered,
        "deterministic_replay": digest == digest2 and validation.status == validation2.status,
        "plan_sha256": digest,
        "fail": validation.status == "FAIL",
    }


def _fakeai_roundtrip(
    transport: dict[str, Any],
    source_map: SourceMap,
    *,
    max_output_tokens: int,
) -> dict[str, Any]:
    payload = strip_meta(transport)
    request = build_production_request(
        source_map, max_output_tokens=max_output_tokens
    )
    engine = FakeAIEngine(
        script=[
            FakeReply(
                parsed=payload,
                text=json.dumps(payload, ensure_ascii=False),
                finish_reason="end_turn",
                input_tokens=1000,
                output_tokens=2000,
                thinking_tokens=0,
                model=request.model,
            )
        ],
        retry_policy=no_delay_policy(max_attempts=1),
    )
    response = engine.generate(request)
    return {
        "fakeai_generate_calls": engine.call_count,
        "parsed_is_transport": isinstance(response.parsed, dict),
        "finish_reason": response.finish_reason,
        "real_provider": False,
    }


def full_scale_stress(
    source_map: SourceMap,
    *,
    source_map_sha256: str,
    source_map_bytes: int,
    max_output_tokens: int,
) -> dict[str, Any]:
    scenarios = {
        "all_assigned": all_assigned_transport(source_map),
        "mixed_disposition": mixed_transport(source_map),
        "reuse": reuse_transport(source_map),
        "max_structure": max_structure_transport(source_map),
        "expected_budget": expected_transport(source_map),
    }
    results: dict[str, Any] = {}
    fake_calls = 0
    failures: list[str] = []
    for name, transport in scenarios.items():
        materialized = _materialize(
            transport,
            source_map,
            source_map_sha256=source_map_sha256,
            source_map_bytes=source_map_bytes,
            max_output_tokens=max_output_tokens,
        )
        fake = _fakeai_roundtrip(
            transport, source_map, max_output_tokens=max_output_tokens
        )
        fake_calls += int(fake["fakeai_generate_calls"])
        row = {**materialized, "fakeai": fake}
        results[name] = row
        if materialized["fail"] or not materialized["coverage_complete"]:
            failures.append(name)
        if not materialized["deterministic_replay"]:
            failures.append(f"{name}:determinism")
    idea_n = len(source_map.ideas)
    all_assigned_ok = (
        results["all_assigned"]["assigned"] == idea_n
        and results["all_assigned"]["deferred"] == 0
        and results["all_assigned"]["excluded"] == 0
    )
    mixed_ok = (
        results["mixed_disposition"]["assigned"] > 0
        and results["mixed_disposition"]["deferred"] > 0
        and results["mixed_disposition"]["excluded"] > 0
    )
    reuse_ok = results["reuse"]["reused"] > 0
    max_ok = (
        results["max_structure"]["chapters"] >= 2
        and results["max_structure"]["sections"] >= results["max_structure"]["chapters"]
        and not results["max_structure"]["fail"]
    )
    status = "PASS" if not failures and all_assigned_ok and mixed_ok and reuse_ok and max_ok else "FAIL"
    return {
        "status": status,
        "fakeai_generate_calls": fake_calls,
        "real_provider_calls": 0,
        "idea_inventory": idea_n,
        "all_assigned_286": all_assigned_ok,
        "mixed_disposition": mixed_ok,
        "reuse": reuse_ok,
        "max_structure": max_ok,
        "failures": failures,
        "scenarios": results,
    }


__all__ = ["full_scale_stress"]
