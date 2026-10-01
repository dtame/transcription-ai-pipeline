"""Runner offline Phase 4A. 0 provider. 0 publication editorial_plan.json."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.ai.cost import CostTracker
from app.ai.providers.fake import FakeAIEngine, FakeReply
from app.editorial_planning.budget import measure_input_budget, measure_output_budget
from app.editorial_planning.constants import (
    EXPECTED_IDEA_COUNT,
    PHASE,
    PUBLICATION_AUTHORIZED,
    REAL_PROVIDER_CALLS_THIS_PHASE,
    STAGE_EDITORIAL_PLANNING,
    VALIDATION_PROJECT_NAME,
)
from app.editorial_planning.coverage import coverage_policy_dict
from app.editorial_planning.fixtures import covering_transport
from app.editorial_planning.guard import (
    assert_analyzer_untouched,
    assert_no_book_generator,
    assert_offline_package,
)
from app.editorial_planning.payload import build_planner_request, payload_audit
from app.editorial_planning.pipeline import materialize_plan
from app.editorial_planning.preflight import run_real_source_map_preflight
from app.editorial_planning.prompt import prompt_bundle
from app.editorial_planning.schema import schema_identity
from app.editorial_planning.settings import frozen_production_settings, thinking_recommendation
from app.editorial_planning.signature import EditorialPlanCache
from app.editorial_planning.validator import validator_contract_dict
from app.source_analysis.writer import source_map_path


def _status(ok: bool) -> str:
    return "PASS" if ok else "FAIL"


def build_bundle(
    *,
    project_name: str = VALIDATION_PROJECT_NAME,
    sortie_dir: Path | None = None,
    tests: str = "offline Phase 4A",
    test_delta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    assert_offline_package()
    assert_analyzer_untouched()
    assert_no_book_generator()
    settings = frozen_production_settings()
    preflight = run_real_source_map_preflight(
        project_name=project_name, sortie_dir=sortie_dir
    )
    from app.editorial_planning.pipeline import load_published_source_map

    source_map, raw, digest, path = load_published_source_map(
        project_name, sortie_dir=sortie_dir
    )
    text = raw.decode("utf-8")
    input_budget = measure_input_budget(source_map, text, settings=settings)
    prompt = prompt_bundle()
    schema = schema_identity()
    transport = covering_transport(source_map, chapter_count=12)
    output_budget = measure_output_budget(transport)
    plan, validation, plan_hash = materialize_plan(
        transport,
        source_map,
        source_map_sha256=digest,
        source_map_bytes=len(raw),
        prompt_sha256=prompt["prompt_sha256"],
        response_schema_sha256=schema["raw_schema_sha256"],
        source_map_path_value=str(path).replace("\\", "/"),
        settings=settings,
    )
    plan2, validation2, plan_hash2 = materialize_plan(
        transport,
        source_map,
        source_map_sha256=digest,
        source_map_bytes=len(raw),
        prompt_sha256=prompt["prompt_sha256"],
        response_schema_sha256=schema["raw_schema_sha256"],
        source_map_path_value=str(path).replace("\\", "/"),
        settings=settings,
    )
    deterministic = plan_hash == plan_hash2 and validation.status == validation2.status
    assigned = sum(1 for item in plan.idea_coverage if item.disposition == "ASSIGNED")
    cache = EditorialPlanCache()
    cache.remember(plan.planner.signature, plan_hash)
    cache_hit = cache.is_hit(plan.planner.signature)
    miss_inputs_changed = not cache.is_hit(plan.planner.signature + "x")

    request = build_planner_request(source_map, settings=settings)
    engine = FakeAIEngine(
        script=[
            FakeReply(
                parsed=transport,
                input_tokens=1000,
                output_tokens=2000,
                model=settings.model,
            )
        ]
    )
    response = engine.generate(request)
    tracker = CostTracker()
    tracker.record_response(response)
    fake_plan, fake_validation, fake_hash = materialize_plan(
        response.parsed,
        source_map,
        source_map_sha256=digest,
        source_map_bytes=len(raw),
        prompt_sha256=prompt["prompt_sha256"],
        response_schema_sha256=schema["raw_schema_sha256"],
        source_map_path_value=str(path).replace("\\", "/"),
        settings=settings,
    )
    fake_ok = (
        fake_validation.status != "FAIL"
        and fake_hash == plan_hash
        and engine.call_count == 1
        and request.stage == STAGE_EDITORIAL_PLANNING
    )
    payload = payload_audit(source_map, settings=settings)
    published_plan = source_map_path(project_name, sortie_dir=sortie_dir).with_name(
        "editorial_plan.json"
    )
    publication_absent = not published_plan.is_file()
    delta = dict(test_delta or {})
    reconstruction_ok = validation.status != "FAIL"
    one_call = bool(input_budget.get("one_global_call_feasible"))
    output_ok = bool(output_budget.get("output_fits_proposed"))
    preflight_ok = preflight.get("status") == "PASS"
    overall = (
        preflight_ok
        and reconstruction_ok
        and deterministic
        and fake_ok
        and one_call
        and output_ok
        and publication_absent
        and REAL_PROVIDER_CALLS_THIS_PHASE == 0
        and PUBLICATION_AUTHORIZED is False
        and int(delta.get("new_failure_count") or 0) == 0
    )
    result = "PASS" if overall else "FAIL"
    if preflight.get("status") == "BLOCKED":
        result = "BLOCKED"
    header = {
        "phase": PHASE,
        "result": result,
        "real_provider_calls": REAL_PROVIDER_CALLS_THIS_PHASE,
        "phase_3b": "COMPLETE",
        "source_map_path": preflight.get("path"),
        "source_map_sha256": digest,
        "source_map_inventory": (
            f"{len(source_map.topics)} TOPIC / {len(source_map.ideas)} IDEA / "
            f"{len(source_map.examples)} EXAMPLE / {len(source_map.references)} REFERENCE / "
            f"{len(source_map.uncertainties)} UNCERTAINTY"
        ),
        "source_map_validation": preflight.get("source_map_validation"),
        "planner_provider": settings.provider,
        "planner_model": settings.model,
        "planner_prompt": prompt["version"],
        "planner_transport": payload["stage"] and "editorial-plan-transport-1.0",
        "canonical_schema": "1.0",
        "provider_schema_raw_bytes": schema["raw_schema_bytes"],
        "provider_schema_adapted_bytes": schema["adapted_schema_bytes"],
        "provider_schema_hash": schema["adapted_schema_sha256"],
        "source_map_chars": preflight.get("chars"),
        "source_map_bytes": preflight.get("bytes"),
        "local_input_token_estimate": input_budget["request"]["local_token_estimate"][
            "tokens"
        ],
        "provider_adjusted_input_estimate": input_budget["request"][
            "provider_adjusted_pessimistic"
        ],
        "usable_input_budget": input_budget["usable_with_proposed_max_output"][
            "usable_input_tokens"
        ],
        "one_global_call_feasible": "YES" if one_call else "NO",
        "proposed_max_output": output_budget["proposed_max_output"],
        "expected_output": output_budget["expected_output_tokens"],
        "conservative_output": output_budget["conservative_output_tokens"],
        "hard_output": output_budget["hard_output_tokens"],
        "idea_coverage_policy": "ASSIGNED | DEFERRED | EXCLUDED",
        "silent_idea_omission": "FORBIDDEN",
        "technical_windows_used_as_editorial_units": "NO",
        "relation_quality_debt": "PRESERVED",
        "canonical_reconstruction": _status(reconstruction_ok),
        "editorial_plan_validator": validation.status,
        "full_scale_fakeai_idea_coverage": f"{assigned} / {EXPECTED_IDEA_COUNT}",
        "deterministic_replay": _status(deterministic),
        "cache_signature": plan.planner.signature,
        "tests": tests,
        "new_failures": int(delta.get("new_failure_count") or 0),
        "editorial_plan_json": "NOT PUBLISHED",
        "book_generator": "NOT STARTED",
        "phase_4a": "COMPLETE" if result == "PASS" else "INCOMPLETE",
        "ready_for_editorial_planner_grammar_canary": "YES" if result == "PASS" else "NO",
        "ready_for_real_editorial_planner_call": "NO",
        "next_action": "HUMAN REVIEW",
    }
    return {
        "header": header,
        "preflight": preflight,
        "input_budget": input_budget,
        "output_budget": output_budget,
        "contract": {
            "hierarchy": ["BOOK", "CHAPTER", "SECTION"],
            "publication_authorized": PUBLICATION_AUTHORIZED,
            "real_provider_calls": REAL_PROVIDER_CALLS_THIS_PHASE,
            "provider": settings.provider,
            "model": settings.model,
            "thinking": thinking_recommendation(),
            "settings": settings.to_dict(),
            "failure_behavior": {
                "silent_provider_fallback": False,
                "response_repair": False,
                "automatic_second_expensive_call": False,
            },
        },
        "schema_identity": schema,
        "coverage_policy": coverage_policy_dict(),
        "validator_contract": validator_contract_dict(),
        "fakeai": {
            "status": _status(fake_ok),
            "engine_calls": engine.call_count,
            "validation": fake_validation.to_dict(),
            "plan_sha256": fake_hash,
            "cost_stage": STAGE_EDITORIAL_PLANNING,
            "cost_records": len(tracker.records),
        },
        "full_scale": {
            "idea_count": len(source_map.ideas),
            "assigned": assigned,
            "validation": validation.to_dict(),
            "plan_sha256": plan_hash,
            "chapters": plan.stats.chapter_count,
            "sections": plan.stats.section_count,
            "deterministic": deterministic,
        },
        "cache": {
            "signature": plan.planner.signature,
            "hit_same_signature": cache_hit,
            "miss_when_signature_changes": miss_inputs_changed,
        },
        "payload": payload,
        "publication": {
            "editorial_plan_json": "NOT PUBLISHED",
            "path_absent": publication_absent,
            "authorized": PUBLICATION_AUTHORIZED,
        },
        "tests": tests,
        "test_delta": delta,
        "readiness": {
            "PHASE_4A": "COMPLETE" if result == "PASS" else "INCOMPLETE",
            "READY_FOR_EDITORIAL_PLANNER_GRAMMAR_CANARY": result == "PASS",
            "READY_FOR_REAL_EDITORIAL_PLANNER_CALL": False,
            "NEXT_ACTION": "HUMAN REVIEW",
        },
    }
