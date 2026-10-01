"""Runner Phase 4A.2. Offline. 0 provider. 0 editorial_plan.json."""

from __future__ import annotations

from typing import Any

from app.editorial_planner_preflight_4a2.cache import cache_signature_audit
from app.editorial_planner_preflight_4a2.constants import (
    ADAPTED_SCHEMA_BYTES,
    ADAPTED_SCHEMA_SHA256,
    A1_ELAPSED_MS,
    A1_FINISH,
    BOOK_GENERATOR,
    EXPECTED_EXAMPLE_COUNT,
    EXPECTED_IDEA_COUNT,
    EXPECTED_REFERENCE_COUNT,
    EXPECTED_SOURCE_MAP_BYTES,
    EXPECTED_SOURCE_MAP_SHA256,
    EXPECTED_TOPIC_COUNT,
    EXPECTED_UNCERTAINTY_COUNT,
    FUTURE_REAL_CALL_COUNT,
    FUTURE_RETRIES,
    MODEL,
    NEXT_ACTION,
    OLD_PROPOSED_MAX_OUTPUT,
    OPUS5_PROVIDER_DEFAULT_THINKING_OBSERVED,
    PHASE,
    PHASE_3B_STATUS,
    PHASE_4A1_STATUS,
    PHASE_4A_PROVIDER_ADJUSTED_PESSIMISTIC,
    PHASE_4A_STATUS,
    PROMPT_VERSION,
    PROVIDER,
    RAW_SCHEMA_BYTES,
    REAL_PROVIDER_CALLS_THIS_PHASE,
    RECOMMENDED_CONNECT_TIMEOUT_SECONDS,
    RECOMMENDED_READ_TIMEOUT_SECONDS,
    THINKING_HEADROOM_TOKENS,
    THINKING_MODE,
    TRANSPORT_VERSION,
)
from app.editorial_planner_preflight_4a2.costing import production_cost_estimate
from app.editorial_planner_preflight_4a2.coverage import input_coverage_audit
from app.editorial_planner_preflight_4a2.gates import (
    future_real_call_gates,
    semantic_review_plan,
)
from app.editorial_planner_preflight_4a2.guard import (
    PlannerPreflightError,
    assert_no_book_generator,
    assert_offline_package,
    assert_phase3b_untouched,
)
from app.editorial_planner_preflight_4a2.identity import (
    contract_identity,
    require_identities,
    source_map_identity_audit,
)
from app.editorial_planner_preflight_4a2.input_budget import measure_input_budget_selected
from app.editorial_planner_preflight_4a2.output_budget import measure_output_budget
from app.editorial_planner_preflight_4a2.paths import production_editorial_plan_path
from app.editorial_planner_preflight_4a2.payload import (
    build_production_request,
    request_identity,
)
from app.editorial_planner_preflight_4a2.report import render_report
from app.editorial_planner_preflight_4a2.stress import full_scale_stress
from app.editorial_planner_preflight_4a2.thinking import thinking_budget_audit
from app.editorial_planning.pipeline import load_published_source_map
from app.editorial_planning.prompt import prompt_bundle


def _yn(value: bool) -> str:
    return "YES" if value else "NO"


def _status(ok: bool) -> str:
    return "PASS" if ok else "FAIL"


def build_bundle(
    *,
    tests: str = "offline Phase 4A.2",
    test_delta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    assert_offline_package()
    assert_phase3b_untouched()
    assert_no_book_generator()
    source_identity = source_map_identity_audit()
    contract = contract_identity()
    blocked = bool(source_identity.get("blocked_precall") or contract.get("blocked_precall"))
    if blocked:
        require_identities(source_identity, contract)

    source_map, raw, digest, path = load_published_source_map(
        "pastoral_retreat_v2_validation"
    )

    output_budget = measure_output_budget(source_map)
    selected = int(output_budget.get("selected_max_output") or OLD_PROPOSED_MAX_OUTPUT)
    if output_budget.get("output_budget_decision") in {"REDESIGN_TRANSPORT", "NEEDS_MORE_EVIDENCE"}:
        selected = int(output_budget.get("selected_max_output") or OLD_PROPOSED_MAX_OUTPUT)

    request = request_identity(source_map, max_output_tokens=selected)
    ai_request = build_production_request(source_map, max_output_tokens=selected)
    input_budget = measure_input_budget_selected(
        system=ai_request.system_prompt or "",
        user=ai_request.prompt,
        payload=request["payload"],
        selected_max_output=selected,
    )
    thinking = thinking_budget_audit(selected_max_output=selected)
    coverage = input_coverage_audit(source_map)
    cache = cache_signature_audit(
        source_map_sha256=digest, max_output_tokens=selected
    )
    stress = full_scale_stress(
        source_map,
        source_map_sha256=digest,
        source_map_bytes=len(raw),
        max_output_tokens=selected,
    )
    semantic = semantic_review_plan()
    gates = {**future_real_call_gates(), "semantic_review_plan": semantic}
    cost = production_cost_estimate(
        input_tokens=int(input_budget["planning_input_estimate"]),
        expected_output=int(output_budget["expected_output_tokens"]),
        conservative_output=int(output_budget["conservative_output_tokens"]),
        hard_output=int(output_budget["hard_output_tokens"]),
    )

    publication_absent = not production_editorial_plan_path().is_file()
    delta = dict(test_delta or {})
    new_failures = int(delta.get("new_failure_count") or 0)

    schema_ok = contract["schema_identity"] == "MATCH"
    prompt_ok = contract["prompt_identity"] == "MATCH"
    source_ok = source_identity.get("status") == "PASS"
    request_ok = bool(request.get("request_determinism")) and bool(
        request.get("no_technical_chunks")
    )
    coverage_ok = bool(coverage.get("pass"))
    input_ok = input_budget.get("input_safety") == "PASS"
    output_ok = bool(output_budget.get("output_fits_selected"))
    decision = str(output_budget.get("output_budget_decision") or "")
    transport_change = str(output_budget.get("transport_change_required") or "NO")
    prompt_change = str(output_budget.get("prompt_change_required") or "NO")
    new_grammar = str(output_budget.get("new_grammar_canary_required") or "NO")
    stress_ok = stress.get("status") == "PASS"
    cache_ok = bool(cache.get("deterministic") and cache.get("a1_cache_cannot_collide"))
    compact_ok = bool((request.get("compact_by_reference") or {}).get("pass"))

    output_safety = output_ok and decision in {"KEEP_16384", "RAISE_MAX_OUTPUT"}
    ready_canary = (
        input_ok
        and output_safety
        and schema_ok
        and prompt_ok
        and transport_change == "NO"
        and prompt_change == "NO"
        and stress_ok
        and new_failures == 0
        and coverage_ok
        and request_ok
        and source_ok
        and publication_absent
        and REAL_PROVIDER_CALLS_THIS_PHASE == 0
    )
    overall_ok = (
        ready_canary
        and cache_ok
        and compact_ok
        and not blocked
    )
    result = "PASS" if overall_ok else "FAIL"
    if blocked:
        result = "BLOCKED"

    inventory = (
        f"{EXPECTED_TOPIC_COUNT} TOPIC / {EXPECTED_IDEA_COUNT} IDEA / "
        f"{EXPECTED_EXAMPLE_COUNT} EXAMPLE / {EXPECTED_REFERENCE_COUNT} REFERENCE / "
        f"{EXPECTED_UNCERTAINTY_COUNT} UNCERTAINTY"
    )
    header = {
        "phase": PHASE,
        "result": result,
        "real_provider_calls": REAL_PROVIDER_CALLS_THIS_PHASE,
        "phase_4a": PHASE_4A_STATUS,
        "phase_4a1": PHASE_4A1_STATUS,
        "phase_3b": PHASE_3B_STATUS,
        "source_map_sha256": digest,
        "source_map_bytes": len(raw),
        "source_map_chars": source_identity.get("chars"),
        "source_map_inventory": inventory,
        "prompt": PROMPT_VERSION,
        "transport": TRANSPORT_VERSION,
        "schema_raw_adapted": f"{RAW_SCHEMA_BYTES} / {ADAPTED_SCHEMA_BYTES}",
        "schema_hash": ADAPTED_SCHEMA_SHA256,
        "schema_identity": contract["schema_identity"],
        "prompt_identity": contract["prompt_identity"],
        "model": MODEL,
        "provider": PROVIDER,
        "thinking_mode": THINKING_MODE,
        "opus_default_thinking_previously_observed": OPUS5_PROVIDER_DEFAULT_THINKING_OBSERVED,
        "exact_request_sha256": request.get("request_sha256"),
        "exact_request_chars": request.get("request_chars"),
        "exact_request_bytes": request.get("request_utf8_bytes"),
        "request_determinism": _status(bool(request.get("request_determinism"))),
        "local_input_token_estimate": input_budget["local_token_estimate"]["tokens"],
        "provider_adjusted_input_estimate": input_budget["provider_adjusted_pessimistic"],
        "planning_input_estimate": input_budget["planning_input_estimate"],
        "phase_4a_provider_adjusted_estimate": PHASE_4A_PROVIDER_ADJUSTED_PESSIMISTIC,
        "input_estimate_delta": input_budget["provider_adjusted_delta_vs_phase4a"],
        "expected_output": output_budget["expected_output_tokens"],
        "conservative_output": output_budget["conservative_output_tokens"],
        "hard_output": output_budget["hard_output_tokens"],
        "old_proposed_max_output": OLD_PROPOSED_MAX_OUTPUT,
        "selected_production_max_output": selected,
        "hard_output_utilization": output_budget.get("hard_output_utilization"),
        "thinking_headroom": THINKING_HEADROOM_TOKENS,
        "output_budget_decision": decision,
        "transport_change_required": transport_change,
        "prompt_change_required": prompt_change,
        "new_grammar_canary_required": new_grammar,
        "usable_context_budget": input_budget["usable_input_tokens"],
        "input_headroom": input_budget["headroom_tokens"],
        "long_context_pricing_status": cost["long_context"]["status"],
        "expected_cost": cost["expected_cost"],
        "conservative_cost": cost["conservative_cost"],
        "hard_cost": cost["hard_cost"],
        "recommended_connect_timeout": RECOMMENDED_CONNECT_TIMEOUT_SECONDS,
        "recommended_read_timeout": RECOMMENDED_READ_TIMEOUT_SECONDS,
        "future_real_call_count": FUTURE_REAL_CALL_COUNT,
        "future_retries": FUTURE_RETRIES,
        "idea_input_coverage": coverage.get("idea_input_coverage"),
        "unknown_input_refs": coverage.get("unknown_input_refs"),
        "source_map_mutated": "NO",
        "cache_signature": cache.get("signature"),
        "fakeai_full_scale_stress": stress.get("status"),
        "tests": tests,
        "new_failures": new_failures,
        "editorial_plan_json": "NOT PUBLISHED",
        "ready_for_one_real_editorial_planner_canary": _yn(ready_canary),
        "ready_for_editorial_plan_publication": "NO",
        "book_generator": BOOK_GENERATOR,
        "next_action": NEXT_ACTION,
        "a1_elapsed_ms_preserved": A1_ELAPSED_MS,
        "a1_finish_preserved": A1_FINISH,
        "engine_generate_called": False,
        "anthropic_post_called": False,
        "source_map_path": str(path).replace("\\", "/"),
        "prompt_version_live": prompt_bundle()["version"],
        "compact_by_reference": _yn(compact_ok),
        "no_technical_chunks": _yn(bool(request.get("no_technical_chunks"))),
        "input_safety": input_budget.get("input_safety"),
        "output_safety": _status(output_safety),
    }
    readiness = {
        "READY_FOR_ONE_REAL_EDITORIAL_PLANNER_CANARY": ready_canary,
        "READY_FOR_EDITORIAL_PLAN_PUBLICATION": False,
        "BOOK_GENERATOR": BOOK_GENERATOR,
        "PRODUCTION_OUTPUT_BUDGET_REVIEW_REQUIRED": not output_safety,
        "OUTPUT_BUDGET_DECISION": decision,
        "SELECTED_PRODUCTION_MAX_OUTPUT": selected,
        "NEW_GRAMMAR_CANARY_REQUIRED": new_grammar,
        "TRANSPORT_CHANGE_REQUIRED": transport_change,
        "PROMPT_CHANGE_REQUIRED": prompt_change,
        "NEXT_ACTION": NEXT_ACTION,
        "why": (
            "Input, output, schema, transport, FakeAI stress and tests passed. "
            "Next phase may authorize exactly one real Opus production canary "
            "using this frozen request identity. Do not auto-publish "
            "editorial_plan.json."
            if ready_canary
            else "Preflight did not authorize a real production call."
        ),
    }
    bundle = {
        "header": header,
        "source_identity": source_identity,
        "contract": contract,
        "request_identity": request,
        "input_budget": input_budget,
        "output_budget": output_budget,
        "thinking": thinking,
        "cost": cost,
        "cache": cache,
        "coverage": coverage,
        "stress": stress,
        "gates": gates,
        "semantic": semantic,
        "readiness": readiness,
        "publication": {
            "authorized": False,
            "path_absent": publication_absent,
            "path": str(production_editorial_plan_path()).replace("\\", "/"),
        },
    }
    bundle["report_text"] = render_report(bundle)
    return bundle


def run_preflight(
    *,
    tests: str = "offline Phase 4A.2",
    test_delta: dict[str, Any] | None = None,
    write_artifacts: bool = True,
    root=None,
) -> dict[str, Any]:
    from app.editorial_planner_preflight_4a2.writer import write_preflight_artifacts

    try:
        bundle = build_bundle(tests=tests, test_delta=test_delta)
    except PlannerPreflightError as exc:
        bundle = {
            "header": {
                "phase": PHASE,
                "result": "BLOCKED",
                "real_provider_calls": 0,
                "error": str(exc),
                "ready_for_one_real_editorial_planner_canary": "NO",
                "editorial_plan_json": "NOT PUBLISHED",
                "book_generator": BOOK_GENERATOR,
                "next_action": NEXT_ACTION,
            },
            "error": str(exc),
        }
        bundle["report_text"] = render_report(bundle)
    if write_artifacts:
        write_preflight_artifacts(bundle, root=root)
    return bundle


__all__ = ["build_bundle", "run_preflight"]
