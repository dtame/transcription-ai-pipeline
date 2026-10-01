"""Runner Phase 4A.3.2. Offline. 0 provider. 0 editorial_plan.json."""

from __future__ import annotations

from typing import Any

from app.editorial_planner_language_policy_4a32.budget import (
    measure_input_budget,
    measure_output_budget,
)
from app.editorial_planner_language_policy_4a32.constants import (
    A2_CONSERVATIVE_OUTPUT_TOKENS,
    A2_EXPECTED_OUTPUT_TOKENS,
    A2_HARD_OUTPUT_TOKENS,
    A3_CANDIDATE_STATUS,
    A3_HISTORICAL_STATUS,
    A3_REQUEST_SHA256,
    A31_STATUS,
    ADAPTED_SCHEMA_BYTES,
    ADAPTED_SCHEMA_SHA256,
    BOOK_GENERATOR,
    CONNECT_TIMEOUT_SECONDS,
    EXPECTED_IDEA_COUNT,
    FUTURE_REAL_CALL_COUNT,
    FUTURE_RETRIES,
    HISTORICAL_PROMPT,
    LANGUAGE_POLICY,
    MAX_OUTPUT_TOKENS,
    MODEL,
    NEW_GRAMMAR_CANARY_REQUIRED,
    NEW_PROMPT,
    NEXT_ACTION,
    PHASE,
    PROVIDER,
    RAW_SCHEMA_BYTES,
    READ_TIMEOUT_SECONDS,
    REAL_PROVIDER_CALLS,
    THINKING_MODE,
    TRANSLATION_AFTER_SOURCE_DOCUMENT,
    TRANSLATION_DURING_SOURCE_GENERATION,
    TRANSPORT_VERSION,
)
from app.editorial_planner_language_policy_4a32.costing import future_cost_estimate
from app.editorial_planner_language_policy_4a32.guard import (
    PlannerLanguagePolicyError,
    assert_no_book_generator,
    assert_no_publication,
    assert_offline_package,
    assert_phase3b_untouched,
)
from app.editorial_planner_language_policy_4a32.identity import (
    candidate_identity_audit,
    compare_historical_prompt,
    compare_schema,
    source_map_identity_audit,
)
from app.editorial_planner_language_policy_4a32.language import load_language_provenance
from app.editorial_planner_language_policy_4a32.paths import (
    production_editorial_plan_path,
    repo_root,
)
from app.editorial_planner_language_policy_4a32.payload import (
    build_production_request,
    request_identity,
)
from app.editorial_planner_language_policy_4a32.report import render_report
from app.editorial_planner_preflight_4a2.coverage import input_coverage_audit
from app.editorial_planning.errors import DocumentLanguageBlocked
from app.editorial_planning.language_policy import (
    DOCUMENT_LANGUAGE_POLICY_VERSION,
    FIELD_TRANSCRIPT_PRIMARY,
)
from app.editorial_planning.language_validate import language_validation_policy
from app.editorial_planning.pipeline import load_published_source_map
from app.editorial_planning.prompt import prompt_bundle as historical_prompt_bundle
from app.editorial_planning.prompt_v101 import prompt_bundle as prompt_bundle_v101


def _yn(value: bool) -> str:
    return "YES" if value else "NO"


def _status(ok: bool) -> str:
    return "PASS" if ok else "FAIL"


def _future_translation_architecture() -> dict[str, Any]:
    return {
        "implemented_now": False,
        "requires_explicit_target_language": True,
        "never_silently_replaces_source_book": True,
        "source_artifact_preserved": True,
        "stages": [
            "completed validated source-language book",
            "explicit translation request",
            "translated book artifact",
            "translation validation",
            "translated Word/PDF",
        ],
        "not_in": [
            "Editorial Planner",
            "Book Generator",
            "SourceMap",
            "A.3 candidate",
        ],
    }


def build_bundle(
    *,
    tests: str = "offline Phase 4A.3.2",
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
    candidate = candidate_identity_audit(root=repo_root())
    if source_identity.get("blocked"):
        raise PlannerLanguagePolicyError(
            "BLOCKED: SourceMap identity mismatch "
            f"(sha={source_identity.get('sha256')})"
        )
    if schema["identity"] != "MATCH":
        raise PlannerLanguagePolicyError("BLOCKED: schema identity mismatch")
    if historical_prompt["identity"] != "MATCH":
        raise PlannerLanguagePolicyError("BLOCKED: historical prompt 1.0 mutated")

    source_map, raw, digest, path = load_published_source_map(
        "pastoral_retreat_v2_validation"
    )
    provenance = load_language_provenance(source_map, root=repo_root())
    language = str(provenance["canonical_document_language"])
    request = request_identity(source_map, canonical_document_language=language)
    ai_request = build_production_request(
        source_map, canonical_document_language=language
    )
    input_budget = measure_input_budget(
        system=ai_request.system_prompt or "",
        user=ai_request.prompt,
        payload=request["payload"],
    )
    output_budget = measure_output_budget()
    coverage = input_coverage_audit(source_map)
    cost = future_cost_estimate(
        input_tokens=int(input_budget["planning_input_estimate"]),
        expected_output=int(output_budget["expected_output_tokens"]),
        conservative_output=int(output_budget["conservative_output_tokens"]),
        hard_output=int(output_budget["hard_output_tokens"]),
    )
    validation_policy = language_validation_policy()
    v101 = prompt_bundle_v101(language)
    v10 = historical_prompt_bundle()

    new_hash = str(request.get("request_sha256") or "")
    request_changed = new_hash != A3_REQUEST_SHA256
    if not request_changed:
        raise PlannerLanguagePolicyError(
            "FAIL: 1.0.1 request hash identical to historical A.3. "
            "Language instruction was not incorporated."
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
    candidate_ok = bool(candidate.get("unchanged"))
    v101_ok = (
        v101["version"] == NEW_PROMPT
        and "canonical_document_language" in v101["instructions"]
        and "LANGUE DE SORTIE OBLIGATOIRE" in v101["system"]
        and v10["version"] == HISTORICAL_PROMPT
    )

    ready_canary = (
        input_ok
        and output_ok
        and schema_ok
        and prompt_ok
        and v101_ok
        and request_ok
        and request_changed
        and language_ok
        and coverage_ok
        and source_ok
        and candidate_ok
        and publication_absent
        and new_failures == 0
        and REAL_PROVIDER_CALLS == 0
        and language == "en"
    )
    overall_ok = ready_canary
    result = "PASS" if overall_ok else "FAIL"

    header = {
        "phase": PHASE,
        "result": result,
        "real_provider_calls": REAL_PROVIDER_CALLS,
        "a3_historical_status": A3_HISTORICAL_STATUS,
        "a31_status": A31_STATUS,
        "canonical_language_source": FIELD_TRANSCRIPT_PRIMARY,
        "canonical_document_language": language,
        "language_policy": LANGUAGE_POLICY,
        "language_policy_version": DOCUMENT_LANGUAGE_POLICY_VERSION,
        "translation_during_source_generation": TRANSLATION_DURING_SOURCE_GENERATION,
        "translation_after_source_document": TRANSLATION_AFTER_SOURCE_DOCUMENT,
        "historical_prompt": HISTORICAL_PROMPT,
        "new_prompt": NEW_PROMPT,
        "historical_prompt_mutated": historical_prompt.get("historical_prompt_mutated"),
        "transport": TRANSPORT_VERSION,
        "schema_raw_adapted": f"{RAW_SCHEMA_BYTES} / {ADAPTED_SCHEMA_BYTES}",
        "schema_hash": ADAPTED_SCHEMA_SHA256,
        "schema_changed": schema.get("schema_changed"),
        "new_grammar_canary_required": NEW_GRAMMAR_CANARY_REQUIRED,
        "provider": "Anthropic",
        "model": MODEL,
        "thinking": THINKING_MODE,
        "max_output": MAX_OUTPUT_TOKENS,
        "connect_timeout_seconds": CONNECT_TIMEOUT_SECONDS,
        "read_timeout_seconds": READ_TIMEOUT_SECONDS,
        "historical_a3_request_sha256": A3_REQUEST_SHA256,
        "new_exact_request_sha256": new_hash,
        "request_changed": _yn(request_changed),
        "request_determinism": _status(bool(request.get("request_determinism"))),
        "request_chars": request.get("request_chars"),
        "request_utf8_bytes": request.get("request_utf8_bytes"),
        "idea_input_coverage": coverage.get("idea_input_coverage"),
        "unknown_refs": coverage.get("unknown_input_refs"),
        "input_estimate": input_budget.get("planning_input_estimate"),
        "local_input_token_estimate": (input_budget.get("local_token_estimate") or {}).get(
            "tokens"
        ),
        "output_expected_conservative_hard": (
            f"{A2_EXPECTED_OUTPUT_TOKENS} / {A2_CONSERVATIVE_OUTPUT_TOKENS} / "
            f"{A2_HARD_OUTPUT_TOKENS}"
        ),
        "context_safety": input_budget.get("context_safety"),
        "estimated_cost": f"ESTIMATED {cost.get('estimated_cost')}",
        "language_validation_policy": validation_policy.get("mechanism"),
        "a3_french_candidate": A3_CANDIDATE_STATUS,
        "new_provider_calls_required": FUTURE_REAL_CALL_COUNT,
        "future_retries": FUTURE_RETRIES,
        "ready_for_one_real_english_editorial_planner_canary": _yn(ready_canary),
        "ready_for_editorial_plan_publication": "NO",
        "book_generator": BOOK_GENERATOR,
        "next_action": NEXT_ACTION,
        "editorial_plan_json": "NOT PUBLISHED",
        "engine_generate_called": False,
        "anthropic_post_called": False,
        "source_map_path": str(path).replace("\\", "/"),
        "source_map_sha256": digest,
        "source_map_bytes": len(raw),
        "tests": tests,
        "new_failures": new_failures,
        "provider_name": PROVIDER,
    }

    language_policy_audit = {
        "policy": LANGUAGE_POLICY,
        "policy_version": DOCUMENT_LANGUAGE_POLICY_VERSION,
        "pipeline": [
            "transcription language",
            "canonical document language",
            "Source Analyzer",
            "Editorial Planner",
            "Book Generator",
            "Book Validator",
            "Word/PDF",
        ],
        "preserves_canonical_language": True,
        "hard_coded_en": False,
        "hard_coded_fr": False,
        "unknown_blocks": True,
        "mismatch_blocks": True,
        "llm_does_not_choose_language": True,
        "current_project_language": language,
        "resolution": provenance.get("resolution"),
        "future_translation": _future_translation_architecture(),
    }
    prompt_identity = {
        "historical": historical_prompt,
        "successor": {
            "version": v101["version"],
            "system_sha256": v101["system_sha256"],
            "instructions_sha256": v101["instructions_sha256"],
            "prompt_sha256": v101["prompt_sha256"],
            "contains_canonical_language_rule": True,
            "historical_prompt_mutated": False,
        },
    }
    request_audit = {
        **{key: value for key, value in request.items() if key != "payload"},
        "historical_a3_request_sha256": A3_REQUEST_SHA256,
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
    }
    readiness = {
        "READY_FOR_ONE_REAL_ENGLISH_EDITORIAL_PLANNER_CANARY": ready_canary,
        "READY_FOR_EDITORIAL_PLAN_PUBLICATION": False,
        "BOOK_GENERATOR": BOOK_GENERATOR,
        "NEW_GRAMMAR_CANARY_REQUIRED": NEW_GRAMMAR_CANARY_REQUIRED,
        "NEXT_ACTION": NEXT_ACTION,
        "why": (
            "Language policy, 1.0.1 request identity, schema, coverage, and "
            "context budget passed. Next phase may authorize exactly one real "
            "Anthropic Opus 5 call using this request. Do not auto-publish."
            if ready_canary
            else "Preflight did not authorize a real English planner call."
        ),
    }
    bundle = {
        "header": header,
        "language_policy": language_policy_audit,
        "language_provenance": provenance,
        "prompt_identity": prompt_identity,
        "schema_identity": schema,
        "request_identity": request_audit,
        "budget": budget_audit,
        "language_validation": validation_policy,
        "readiness": readiness,
        "coverage": coverage,
        "source_identity": source_identity,
        "candidate": candidate,
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
    tests: str = "offline Phase 4A.3.2",
    test_delta: dict[str, Any] | None = None,
    write_artifacts: bool = True,
    root=None,
) -> dict[str, Any]:
    from app.editorial_planner_language_policy_4a32.writer import write_phase_artifacts

    try:
        bundle = build_bundle(tests=tests, test_delta=test_delta, root=root)
    except (PlannerLanguagePolicyError, DocumentLanguageBlocked) as exc:
        bundle = {
            "header": {
                "phase": PHASE,
                "result": "BLOCKED",
                "real_provider_calls": 0,
                "error": str(exc),
                "ready_for_one_real_english_editorial_planner_canary": "NO",
                "ready_for_editorial_plan_publication": "NO",
                "editorial_plan_json": "NOT PUBLISHED",
                "book_generator": BOOK_GENERATOR,
                "next_action": NEXT_ACTION,
                "a3_historical_status": A3_HISTORICAL_STATUS,
                "a31_status": A31_STATUS,
            },
            "error": str(exc),
        }
        bundle["report_text"] = render_report(bundle)
    if write_artifacts:
        write_phase_artifacts(bundle, root=root)
    return bundle


__all__ = ["build_bundle", "run_preflight"]
