"""Runner Phase 4A.3.4. Offline. 0 provider. 0 editorial_plan.json."""

from __future__ import annotations

import json
from typing import Any

from app.editorial_planner_canary_4a33.constants import EXPECTED_REQUEST_UTF8_BYTES
from app.editorial_planner_forensics_4a34.budget import (
    future_cost_estimate,
    measure_input_budget,
    measure_output_budget,
)
from app.editorial_planner_forensics_4a34.constants import (
    A3_COVERAGE,
    A33_COVERAGE,
    A33_HISTORICAL_STATUS,
    A33_MISSING_IDEAS,
    A33_REQUEST_SHA256,
    A34_COST_USD,
    BOOK_GENERATOR,
    CONNECT_TIMEOUT_SECONDS,
    EXPECTED_IDEA_COUNT,
    FUTURE_REAL_CALL_COUNT,
    FUTURE_RETRIES,
    MAX_OUTPUT_TOKENS,
    MODEL,
    NEW_GRAMMAR_CANARY_REQUIRED,
    NEW_SYNTHETIC_CONTRACT_CANARY_REQUIRED,
    NEXT_ACTION,
    PHASE,
    PROVIDER,
    READ_TIMEOUT_SECONDS,
    REAL_PROVIDER_CALLS,
    SUCCESSOR_PROMPT,
    THINKING_MODE,
    TRANSPORT_VERSION,
)
from app.editorial_planner_forensics_4a34.coverage_stress import run_coverage_stress
from app.editorial_planner_forensics_4a34.forensics import (
    content_audit,
    request_presence_audit,
    survival_audit,
)
from app.editorial_planner_forensics_4a34.guard import (
    PlannerOmissionForensicsError,
    assert_no_book_generator,
    assert_no_publication,
    assert_offline_package,
    assert_phase3b_untouched,
)
from app.editorial_planner_forensics_4a34.hardening import contract_hardening_decision
from app.editorial_planner_forensics_4a34.identity import (
    a33_candidate_identity,
    a33_raw_identity,
    compare_historical_prompt,
    compare_prompt_101,
    compare_schema,
    source_map_identity_audit,
)
from app.editorial_planner_forensics_4a34.paths import (
    a33_candidate_path,
    production_editorial_plan_path,
    repo_root,
)
from app.editorial_planner_forensics_4a34.payload import (
    build_production_request,
    request_identity,
)
from app.editorial_planner_forensics_4a34.prompt_audit import prompt_coverage_analysis
from app.editorial_planner_forensics_4a34.report import render_report
from app.editorial_planner_forensics_4a34.root_cause import classify_root_cause
from app.editorial_planner_forensics_4a34.transport_audit import (
    transport_schema_responsibility,
)
from app.editorial_planner_language_policy_4a32.language import load_language_provenance
from app.editorial_planner_preflight_4a2.coverage import input_coverage_audit
from app.editorial_planning.errors import DocumentLanguageBlocked
from app.editorial_planning.pipeline import load_published_source_map


def _yn(value: bool) -> str:
    return "YES" if value else "NO"


def _status(ok: bool) -> str:
    return "PASS" if ok else "FAIL"


def build_bundle(
    *,
    tests: str = "offline Phase 4A.3.4",
    test_delta: dict[str, Any] | None = None,
    root=None,
) -> dict[str, Any]:
    assert_offline_package()
    assert_phase3b_untouched()
    assert_no_book_generator()
    publication = production_editorial_plan_path(root=repo_root())
    assert_no_publication(publication)

    source_identity = source_map_identity_audit()
    schema = compare_schema()
    historical_prompt = compare_historical_prompt()
    prompt_101 = compare_prompt_101()
    a33_candidate = a33_candidate_identity(root=repo_root())
    a33_raw = a33_raw_identity(root=repo_root())
    if source_identity.get("blocked"):
        raise PlannerOmissionForensicsError(
            "BLOCKED: SourceMap identity mismatch "
            f"(sha={source_identity.get('sha256')})"
        )
    if schema["identity"] != "MATCH":
        raise PlannerOmissionForensicsError("BLOCKED: schema identity mismatch")
    if historical_prompt["identity"] != "MATCH":
        raise PlannerOmissionForensicsError("BLOCKED: historical prompt 1.0 mutated")

    source_map, raw, digest, path = load_published_source_map(
        "pastoral_retreat_v2_validation"
    )
    provenance = load_language_provenance(source_map)
    language = str(provenance["canonical_document_language"])
    presence = request_presence_audit(source_map)
    content = content_audit(source_map)
    survival = survival_audit(source_map, root=repo_root())
    prompt = prompt_coverage_analysis()
    candidate = json.loads(
        a33_candidate_path(root=repo_root()).read_text(encoding="utf-8")
    )
    transport = transport_schema_responsibility(source_map, candidate)
    root_cause = classify_root_cause(
        presence=presence,
        survival=survival,
        prompt=prompt,
        transport=transport,
    )
    hardening = contract_hardening_decision(
        root_cause=root_cause,
        prompt=prompt,
        transport=transport,
    )
    request = request_identity(source_map, canonical_document_language=language)
    ai_request = build_production_request(
        source_map, canonical_document_language=language
    )
    input_budget = measure_input_budget(
        system=ai_request.system_prompt or "",
        user=ai_request.prompt,
        payload=request["payload"],
        a33_payload_utf8_bytes=EXPECTED_REQUEST_UTF8_BYTES,
    )
    output_budget = measure_output_budget()
    coverage = input_coverage_audit(source_map)
    cost = future_cost_estimate(
        input_tokens=int(input_budget["planning_input_estimate"]),
        expected_output=int(output_budget["expected_output_tokens"]),
        conservative_output=int(output_budget["conservative_output_tokens"]),
        hard_output=int(output_budget["hard_output_tokens"]),
    )
    stress = run_coverage_stress(source_map)

    future_hash = str(request.get("request_sha256") or "")
    request_changed = future_hash != A33_REQUEST_SHA256
    if not request_changed:
        raise PlannerOmissionForensicsError(
            "FAIL: 1.0.2 request hash identical to historical A.3.3. "
            "Coverage hardening was not incorporated."
        )

    publication_absent = not publication.is_file()
    delta = dict(test_delta or {})
    new_failures = int(delta.get("new_failure_count") or 0)

    schema_ok = schema["identity"] == "MATCH"
    prompt_ok = historical_prompt["identity"] == "MATCH"
    source_ok = source_identity.get("status") == "PASS"
    request_ok = bool(request.get("request_determinism")) and bool(
        request.get("no_technical_chunks")
    )
    language_ok = bool(request.get("request_explicitly_requires_language"))
    coverage_ok = bool(coverage.get("pass"))
    input_ok = input_budget.get("context_safety") == "PASS"
    output_ok = bool(output_budget.get("output_fits_selected"))
    candidate_ok = bool(a33_candidate.get("unchanged"))
    raw_ok = bool(a33_raw.get("unchanged"))
    presence_ok = (
        presence.get("IDEA007_present_in_request") == "YES"
        and presence.get("IDEA008_present_in_request") == "YES"
    )
    stress_ok = stress.get("status") == "PASS"
    hardening_ok = (
        hardening.get("successor_prompt") == SUCCESSOR_PROMPT
        and hardening.get("idea_specific_prompting") is False
        and prompt.get("v102", {}).get("mentions_IDEA007") is False
        and prompt.get("v102", {}).get("mentions_IDEA008") is False
    )
    v102_ok = (
        request.get("prompt_version") == SUCCESSOR_PROMPT
        and request.get("hardening_in_system") is True
        and request.get("expected_idea_count") == EXPECTED_IDEA_COUNT
    )
    provider_compliance = (
        root_cause.get("primary_root_cause") == "PROVIDER_COMPLIANCE_FAILURE"
    )

    ready_canary = (
        input_ok
        and output_ok
        and schema_ok
        and prompt_ok
        and v102_ok
        and request_ok
        and request_changed
        and language_ok
        and coverage_ok
        and source_ok
        and candidate_ok
        and raw_ok
        and presence_ok
        and stress_ok
        and hardening_ok
        and publication_absent
        and new_failures == 0
        and REAL_PROVIDER_CALLS == 0
        and language == "en"
        and NEW_GRAMMAR_CANARY_REQUIRED == "NO"
        and A34_COST_USD == 0.0
    )
    overall_ok = ready_canary and provider_compliance
    result = "PASS" if overall_ok else "FAIL"

    header = {
        "phase": PHASE,
        "result": result,
        "real_provider_calls": REAL_PROVIDER_CALLS,
        "a33_historical_status": A33_HISTORICAL_STATUS,
        "a33_raw_unchanged": _yn(raw_ok),
        "a33_candidate_unchanged": _yn(candidate_ok),
        "source_map_unchanged": _yn(bool(source_identity.get("unchanged"))),
        "historical_coverage": A33_COVERAGE,
        "missing_ideas": " / ".join(A33_MISSING_IDEAS),
        "idea007_present_in_request": presence.get("IDEA007_present_in_request"),
        "idea008_present_in_request": presence.get("IDEA008_present_in_request"),
        "idea007_content_survival": survival.get("IDEA007_content_survival"),
        "idea008_content_survival": survival.get("IDEA008_content_survival"),
        "request_input_defect": presence.get("request_input_defect"),
        "output_cap_failure": (transport.get("output_budget") or {}).get(
            "output_cap_failure"
        ),
        "transport_defect": transport.get("transport_defect"),
        "schema_defect": transport.get("schema_defect"),
        "validator_defect": transport.get("validator_defect"),
        "prompt_coverage_weakness": prompt.get("prompt_coverage_weakness"),
        "provider_compliance_failure": _yn(provider_compliance),
        "primary_root_cause": root_cause.get("primary_root_cause"),
        "secondary_contributors": ", ".join(
            str(item) for item in (root_cause.get("secondary_contributors") or [])
        ),
        "historical_a3_coverage": A3_COVERAGE,
        "historical_a33_coverage": A33_COVERAGE,
        "selected_fix": hardening.get("selected_fix"),
        "successor_prompt": SUCCESSOR_PROMPT,
        "transport": TRANSPORT_VERSION,
        "schema_changed": schema.get("schema_changed"),
        "new_grammar_canary_required": NEW_GRAMMAR_CANARY_REQUIRED,
        "new_synthetic_contract_canary_required": NEW_SYNTHETIC_CONTRACT_CANARY_REQUIRED,
        "future_canonical_language": language,
        "future_max_output": MAX_OUTPUT_TOKENS,
        "future_exact_request_sha256": future_hash,
        "future_request_determinism": _status(bool(request.get("request_determinism"))),
        "future_idea_input_coverage": coverage.get("idea_input_coverage"),
        "future_input_estimate": input_budget.get("planning_input_estimate"),
        "context_safety": input_budget.get("context_safety"),
        "future_estimated_cost": f"ESTIMATED {cost.get('estimated_cost')}",
        "fakeai_coverage_stress": stress.get("status"),
        "tests": tests,
        "new_failures": new_failures,
        "editorial_plan_json": "NOT PUBLISHED",
        "ready_for_one_final_controlled_editorial_planner_canary": _yn(ready_canary),
        "ready_for_editorial_plan_publication": "NO",
        "book_generator": BOOK_GENERATOR,
        "next_action": NEXT_ACTION,
        "engine_generate_called": False,
        "anthropic_post_called": False,
        "a34_cost_usd": A34_COST_USD,
        "provider": "Anthropic",
        "model": MODEL,
        "thinking": THINKING_MODE,
        "connect_timeout_seconds": CONNECT_TIMEOUT_SECONDS,
        "read_timeout_seconds": READ_TIMEOUT_SECONDS,
        "future_retries": FUTURE_RETRIES,
        "future_real_call_count": FUTURE_REAL_CALL_COUNT,
        "source_map_path": str(path).replace("\\", "/"),
        "source_map_sha256": digest,
        "source_map_bytes": len(raw),
        "provider_name": PROVIDER,
        "historical_prompt_mutated": historical_prompt.get("historical_prompt_mutated"),
        "prompt_101_version": prompt_101.get("version"),
    }

    idea007 = {
        **content["IDEA007"],
        "request": presence["ideas"]["IDEA007"],
        "survival": survival["omitted"]["IDEA007"],
    }
    idea008 = {
        **content["IDEA008"],
        "request": presence["ideas"]["IDEA008"],
        "survival": survival["omitted"]["IDEA008"],
    }
    omission = {
        "historical_status": A33_HISTORICAL_STATUS,
        "coverage": A33_COVERAGE,
        "missing": list(A33_MISSING_IDEAS),
        "presence": presence,
        "neighbors": content.get("neighbors"),
        "semantic_proximity": content.get("semantic_proximity"),
        "survival": {
            "IDEA007": survival.get("IDEA007_content_survival"),
            "IDEA008": survival.get("IDEA008_content_survival"),
            "implicit_coverage_allowed": False,
            "related_topic_cluster_note": survival.get("related_topic_cluster_note"),
        },
        "a3_comparison": {
            "a3_coverage": A3_COVERAGE,
            "a33_coverage": A33_COVERAGE,
            "a3_chapters": survival.get("a3_chapters"),
            "a3_sections": survival.get("a3_sections"),
            "a33_chapters": survival.get("a33_chapters"),
            "a33_sections": survival.get("a33_sections"),
            "a3_IDEA007_IDEA008": survival.get("a3_IDEA007_IDEA008"),
            "same_transport_schema": True,
        },
        "historical_repair_performed": False,
    }
    request_audit = {
        **{key: value for key, value in request.items() if key != "payload"},
        "historical_a33_request_sha256": A33_REQUEST_SHA256,
        "request_changed": request_changed,
        "payload_keys": sorted((request.get("payload") or {}).keys()),
    }
    budget_audit = {
        "input": input_budget,
        "output": output_budget,
        "cost": cost,
        "timeouts": {
            "connect_seconds": CONNECT_TIMEOUT_SECONDS,
            "read_seconds": READ_TIMEOUT_SECONDS,
        },
        "future_call": {
            "count": FUTURE_REAL_CALL_COUNT,
            "retries": FUTURE_RETRIES,
            "provider": "Anthropic",
            "model": MODEL,
            "thinking": THINKING_MODE,
            "max_tokens": MAX_OUTPUT_TOKENS,
        },
        "a34_actual_usd": A34_COST_USD,
    }
    readiness = {
        "READY_FOR_ONE_FINAL_CONTROLLED_EDITORIAL_PLANNER_CANARY": ready_canary,
        "READY_FOR_EDITORIAL_PLAN_PUBLICATION": False,
        "BOOK_GENERATOR": BOOK_GENERATOR,
        "NEW_GRAMMAR_CANARY_REQUIRED": NEW_GRAMMAR_CANARY_REQUIRED,
        "NEW_SYNTHETIC_CONTRACT_CANARY_REQUIRED": NEW_SYNTHETIC_CONTRACT_CANARY_REQUIRED,
        "NEXT_ACTION": NEXT_ACTION,
        "why": (
            "Root failure classified. Prompt 1.0.2 hardening is generic. "
            "Transport/schema unchanged. FakeAI coverage stress passed. "
            "Future 1.0.2 request is deterministic and 286/286. Context "
            "safety PASS. Next phase may authorize exactly one real "
            "Anthropic Opus 5 call. Do not auto-publish. Do not repair "
            "the historical A.3.3 candidate."
            if ready_canary
            else "Offline forensics did not authorize a final controlled canary."
        ),
    }
    bundle = {
        "header": header,
        "omission": omission,
        "idea007": idea007,
        "idea008": idea008,
        "prompt": prompt,
        "transport": transport,
        "root_cause": root_cause,
        "hardening": hardening,
        "future_request": request_audit,
        "budget": budget_audit,
        "readiness": readiness,
        "coverage": coverage,
        "coverage_stress": stress,
        "source_identity": source_identity,
        "a33_candidate": a33_candidate,
        "a33_raw": a33_raw,
        "survival": survival,
        "publication": {
            "authorized": False,
            "path_absent": publication_absent,
            "path": str(publication).replace("\\", "/"),
        },
    }
    bundle["report_text"] = render_report(bundle)
    return bundle


def run_preflight(
    *,
    tests: str = "offline Phase 4A.3.4",
    test_delta: dict[str, Any] | None = None,
    write_artifacts: bool = True,
    root=None,
) -> dict[str, Any]:
    from app.editorial_planner_forensics_4a34.writer import write_phase_artifacts

    try:
        bundle = build_bundle(tests=tests, test_delta=test_delta, root=root)
    except (PlannerOmissionForensicsError, DocumentLanguageBlocked) as exc:
        bundle = {
            "header": {
                "phase": PHASE,
                "result": "BLOCKED",
                "real_provider_calls": 0,
                "error": str(exc),
                "ready_for_one_final_controlled_editorial_planner_canary": "NO",
                "ready_for_editorial_plan_publication": "NO",
                "editorial_plan_json": "NOT PUBLISHED",
                "book_generator": BOOK_GENERATOR,
                "next_action": NEXT_ACTION,
                "a33_historical_status": A33_HISTORICAL_STATUS,
            },
            "error": str(exc),
        }
        bundle["report_text"] = render_report(bundle)
    if write_artifacts:
        write_phase_artifacts(bundle, root=root)
    return bundle


__all__ = ["build_bundle", "run_preflight"]
