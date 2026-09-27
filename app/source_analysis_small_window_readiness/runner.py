"""Runner offline 3B.7.7A.8 — artefacts déterministes, 0 appel provider."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any

from app.file_utils import content_hash
from app.semantic_canary.integrity import sha256_of_file
from app.source_analysis.window_analyzer import build_window_ai_request
from app.source_analysis.window_prompt import (
    WINDOW_ANALYSIS_PROMPT_VERSION,
    WINDOW_ANALYSIS_PROMPT_VERSION_V10,
)
from app.source_analysis_execution_strategy.windows import load_clean_transcript
from app.source_analysis_hybrid_readiness.canary import run_win001_canary
from app.source_analysis_hybrid_readiness.constants import MAX_ATTEMPTS, MAX_NEW_CALLS_WIN001
from app.source_analysis_small_window_hierarchy.constants import CANDIDATE_PLANNER_VERSION
from app.source_analysis_small_window_hierarchy.planner import plan_windows_v21_small
from app.source_analysis_small_window_readiness.boundary import review_boundaries
from app.source_analysis_small_window_readiness.cache_audit import (
    inspect_small_window_real_cache,
)
from app.source_analysis_small_window_readiness.collision import audit_forensic_collisions
from app.source_analysis_small_window_readiness.constants import (
    AUTHORIZATION_SCOPE,
    DRY_RUN_COMMAND,
    FUTURE_REAL_COMMAND,
    GRANULARITY_POLICY_VERSION,
    HISTORICAL_CALL2_COST,
    HISTORICAL_SPEND_USD,
    MODE,
    NEXT_ACTION,
    PHASE,
    PHASE_3B_STATUS,
    PLANNER_VERSION_REQUIRED,
    PRODUCTION_DEFAULT_CHANGED,
    PRODUCTION_PLANNER_VERSION,
    PROJECT_NAME,
    PROMPT_VERSION_REQUIRED,
    REAL_PROVIDER_CALLS_THIS_PHASE,
    REAL_WINDOWS_EXECUTED,
    SCHEMA_VERSION,
    TRANSPORT_VERSION,
    WINDOW_ID,
)
from app.source_analysis_small_window_readiness.cost_risk import build_cost_risk
from app.source_analysis_small_window_readiness.facts import implementation_facts
from app.source_analysis_small_window_readiness.fixtures import run_fakeai_matrix
from app.source_analysis_small_window_readiness.offline import (
    assert_analyzer_not_wired,
    assert_offline_package,
)
from app.source_analysis_small_window_readiness.report import render_report
from app.source_analysis_small_window_readiness.request import (
    rebuild_candidate_plan,
    rebuild_small_win001_request,
)
from app.source_analysis_small_window_readiness.taxonomy import (
    inspect_error_taxonomy,
    inspect_retry_and_timeout,
)
from app.source_analysis_small_window_readiness.writer import (
    boundary_path,
    cache_path,
    contract_path,
    cost_path,
    dry_run_path,
    readiness_path,
    report_path,
    write_bytes_atomic,
)


def _execution_contract(request: dict[str, Any], cache: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "authorization_scope": AUTHORIZATION_SCOPE,
        "planner_version": request["planner_version"],
        "window": request["window_id"],
        "window_input_hash": request["window_input_hash"],
        "analysis_signature": request["analysis_signature"],
        "prompt": request["prompt_version"],
        "prompt_sha256": request["prompt_sha256"],
        "granularity": request["granularity_policy_version"],
        "transport": request["transport_version"],
        "provider": request["provider"],
        "model": request["model"],
        "local_estimate": request["local_estimated_input"],
        "max_output": request["max_output"],
        "timeout": {
            "connect": request["connect_timeout_seconds"],
            "read": request["read_timeout_seconds"],
        },
        "max_attempts": MAX_ATTEMPTS,
        "max_new_calls": MAX_NEW_CALLS_WIN001,
        "retry": False,
        "fallback": False,
        "continuation": False,
        "forensic_paths": (
            "structured_output_forensics/WIN001/<analysis_signature>/ and "
            "provider_forensics/WIN001/<analysis_signature>/"
        ),
        "success_gates": (
            "one Anthropic POST; usable envelope; structured parse PASS; "
            "transport persisted; no capacity signal; granularity PASS; "
            "decoder PASS; WindowResultValidator PASS; result persisted; "
            "cache HIT on revalidation; usage/cost captured; no continuation"
        ),
        "failure_gates": {
            "provider_boundary": "forensics preserved; no retry; STOP.",
            "structured_parse": "forensics preserved; no repair; no retry; STOP.",
            "capacity_signal": "transport preserved; result NOT READY; no retry; STOP.",
            "hard_limit": "transport preserved; result absent; no retry; STOP.",
            "output_ceiling": "OUTPUT_CEILING_REACHED; STOP for human review.",
        },
        "mandatory_post_call_stop": True,
        "success_does_not_authorize_win002": True,
        "expected_cache_state": "MISS",
        "current_cache_state": cache["by_id"][WINDOW_ID]["cache_state"],
        "future_real_command": FUTURE_REAL_COMMAND,
        "future_real_command_executed": False,
        "human_authorization_required": True,
        "real_calls": 0,
    }


def _dry_run_artifact(canary) -> dict[str, Any]:
    payload = dict(canary.dry_run)
    payload.update(
        {
            "schema_version": SCHEMA_VERSION,
            "phase": PHASE,
            "command": DRY_RUN_COMMAND,
            "accepted": canary.accepted,
            "error": canary.error,
            "provider_calls": canary.provider_calls,
            "engine_generate_attempted": canary.engine_generate_attempted,
            "secrets_included": False,
            "provider_response_included": False,
        }
    )
    return payload


def _signature_mutations(project_name: str, *, sortie_dir: Path | None) -> dict[str, Any]:
    transcript = load_clean_transcript(project_name, sortie_dir=sortie_dir)
    plan = plan_windows_v21_small(transcript)
    window = next(item for item in plan.windows if item.window_id == WINDOW_ID)
    base = build_window_ai_request(
        window, transcript, prompt_version=WINDOW_ANALYSIS_PROMPT_VERSION
    ).signature
    planner = build_window_ai_request(
        replace(window, planner_version="window-planner-v2.0"),
        transcript,
        prompt_version=WINDOW_ANALYSIS_PROMPT_VERSION,
    ).signature
    prompt = build_window_ai_request(
        window, transcript, prompt_version=WINDOW_ANALYSIS_PROMPT_VERSION_V10
    ).signature
    other = plan.windows[1]
    owned_set = build_window_ai_request(
        other, transcript, prompt_version=WINDOW_ANALYSIS_PROMPT_VERSION
    ).signature
    return {
        "base_signature": base,
        "planner_version_changes_identity": planner != base,
        "prompt_version_changes_identity": prompt != base,
        "owned_src_set_changes_identity": owned_set != base,
        "win001_label_insufficient": True,
    }


def _risk_register() -> list[dict[str, str]]:
    rows = [
        (
            "provider envelope may still fail",
            "CALL #2 lost raw body; 3B.7.7A.5 hardening now persists envelope",
            "canary unusable; cost may become known",
            "forensics before interpretation",
            "STOP. No retry.",
        ),
        (
            "structured JSON may still fail",
            "CALL #1 AIStructuredOutputError after 32000 output",
            "no WindowResult",
            "structured forensics; no JSON repair",
            "STOP. No retry.",
        ),
        (
            "output may still hit 32000",
            "CALL #1 output=32000; max_output remains 32000",
            "possible truncation",
            "OUTPUT_CEILING_REACHED flag",
            "STOP for human review.",
        ),
        (
            "semantic capacity signal may appear",
            "window-granularity-1.0 overflow token",
            "result NOT READY",
            "transport preserved; validator fail-closed",
            "STOP. No retry.",
        ),
        (
            "model may ignore soft targets",
            "soft targets are advisory",
            "hard ceilings still enforced locally",
            "hard ceilings + overflow",
            "over-limit is NOT READY.",
        ),
        (
            "boundary without context may reduce coherence",
            "WIN001 now ends at SRC001201; context=NONE",
            "possible interrupted semantic unit",
            "offline boundary review; no silent overlap",
            "if CLEAR splits frequent: BLOCKED.",
        ),
        (
            "provider token accounting remains uncertain",
            "historical ratio 2.155975 is one observation",
            "local estimate is not billing",
            "usage captured best-effort",
            "UNKNOWN cost if usage absent.",
        ),
        (
            "cost remains uncertain until usage",
            "CALL #2 cost UNKNOWN",
            "no dollar cap; one-call budget",
            "MAX_NEW_CALLS=1",
            "authorization consumed after generate.",
        ),
        (
            "small-window strategy remains unvalidated on real provider",
            "v2.1-small is candidate only",
            "production stays v2.0",
            "isolated SMALL_V21_WIN001_ONLY canary",
            "do not activate production default.",
        ),
        (
            "forensics may reveal a new provider shape",
            "3B.7.7A.5 capture is generic HTTP",
            "new classification possible",
            "raw bytes + safe headers persisted",
            "STOP and review evidence.",
        ),
    ]
    return [
        {
            "risk": risk,
            "evidence": evidence,
            "impact": impact,
            "mitigation": mitigation,
            "stop_behavior": stop,
        }
        for risk, evidence, impact, mitigation, stop in rows
    ]


def build_payload(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> dict[str, Any]:
    assert_offline_package()
    assert_analyzer_not_wired()
    plan = rebuild_candidate_plan(project_name, sortie_dir=sortie_dir)
    request = rebuild_small_win001_request(project_name, sortie_dir=sortie_dir)
    cache = inspect_small_window_real_cache(project_name, sortie_dir=sortie_dir)
    collision = audit_forensic_collisions(
        project_name=project_name,
        small_signature=request["analysis_signature"],
        large_signature=request["large_win001"]["analysis_signature_1_1"],
        sortie_dir=sortie_dir,
    )
    transcript = load_clean_transcript(project_name, sortie_dir=sortie_dir)
    small_plan = plan_windows_v21_small(transcript)
    boundary = review_boundaries(transcript, small_plan)
    cost = build_cost_risk(local_estimated_input=int(request["local_estimated_input"]))
    first = run_win001_canary(
        project_name,
        window_id=WINDOW_ID,
        dry_run=True,
        execute_real=False,
        authorization_scope=AUTHORIZATION_SCOPE,
        planner_version=PLANNER_VERSION_REQUIRED,
        prompt_version=WINDOW_ANALYSIS_PROMPT_VERSION,
        sortie_dir=sortie_dir,
    )
    second = run_win001_canary(
        project_name,
        window_id=WINDOW_ID,
        dry_run=True,
        execute_real=False,
        authorization_scope=AUTHORIZATION_SCOPE,
        planner_version=PLANNER_VERSION_REQUIRED,
        prompt_version=WINDOW_ANALYSIS_PROMPT_VERSION,
        sortie_dir=sortie_dir,
    )
    dry = _dry_run_artifact(first)
    dry_keys = (
        "planner_version",
        "window_id",
        "first_src",
        "last_src",
        "owned_src_count",
        "word_count",
        "window_input_hash",
        "analysis_signature",
        "prompt_version",
        "prompt_sha256",
        "estimated_input_tokens",
        "cache_state",
    )
    dry_deterministic = all(
        first.dry_run.get(key) == second.dry_run.get(key) for key in dry_keys
    )
    taxonomy = inspect_error_taxonomy()
    retry = inspect_retry_and_timeout()
    fakeai = run_fakeai_matrix()
    mutations = _signature_mutations(project_name, sortie_dir=sortie_dir)
    facts = implementation_facts(
        request=request,
        plan=plan,
        cache=cache,
        collision=collision,
        dry_run=dry,
        boundary=boundary,
        fakeai=fakeai,
        taxonomy=taxonomy,
        retry=retry,
        project_name=project_name,
        sortie_dir=sortie_dir,
    )
    contract = _execution_contract(request, cache)
    readiness = facts["readiness"]
    result = "PASS" if readiness == "READY_FOR_SMALL_WIN001_CANARY" else "PARTIAL"
    if facts["blockers"]["prompt_1_1_changed"] or facts["blockers"]["generation_c_changed"]:
        result = "FAIL"
        readiness = "BLOCKED"
        facts["readiness"] = readiness
    if facts["blockers"]["production_default_changed"] or facts["blockers"]["clean_changed"]:
        result = "FAIL"
        readiness = "BLOCKED"
        facts["readiness"] = readiness
    publication = cache["project_state"]
    body = {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "result": result,
        "readiness": readiness,
        "real_provider_calls": REAL_PROVIDER_CALLS_THIS_PHASE,
        "real_windows_executed": REAL_WINDOWS_EXECUTED,
        "production_default": PRODUCTION_PLANNER_VERSION,
        "production_default_changed": PRODUCTION_DEFAULT_CHANGED,
        "candidate_planner": PLANNER_VERSION_REQUIRED,
        "prompt": PROMPT_VERSION_REQUIRED,
        "granularity": GRANULARITY_POLICY_VERSION,
        "transport": TRANSPORT_VERSION,
        "plan": plan,
        "request": request,
        "cache": cache,
        "collision": collision,
        "boundary": boundary,
        "cost_risk": cost,
        "dry_run": dry,
        "dry_run_determinism": {
            "identical_key_fields": dry_deterministic,
            "keys": list(dry_keys),
        },
        "execution_contract": contract,
        "implementation": facts,
        "fakeai": fakeai,
        "signature_mutations": mutations,
        "risk_register": _risk_register(),
        "source_map_published": cache["source_map_present"],
        "project_state": publication,
        "phase_3b": PHASE_3B_STATUS,
        "next_action": NEXT_ACTION,
        "historical_spend_usd": HISTORICAL_SPEND_USD,
        "historical_unknown_spend": HISTORICAL_CALL2_COST,
        "network": 0,
        "future_real_command_executed": False,
    }
    body["content_hash"] = content_hash(
        json.dumps(
            {key: value for key, value in body.items() if key != "content_hash"},
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return body


def write_readiness_artifacts(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    body = payload or build_payload(project_name, sortie_dir=sortie_dir)
    readiness = {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "result": body["result"],
        "readiness": body["readiness"],
        "request": body["request"],
        "plan": body["plan"],
        "cache": body["cache"],
        "collision": body["collision"],
        "implementation": body["implementation"],
        "real_provider_calls": REAL_PROVIDER_CALLS_THIS_PHASE,
        "content_hash": body["content_hash"],
    }
    cost = {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        **body["cost_risk"],
    }
    boundary = {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        **body["boundary"],
    }
    cache = {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        **body["cache"],
    }
    paths = {
        "readiness": write_bytes_atomic(
            readiness_path(project_name, sortie_dir=sortie_dir), readiness
        ),
        "cost_risk": write_bytes_atomic(
            cost_path(project_name, sortie_dir=sortie_dir), cost
        ),
        "execution_contract": write_bytes_atomic(
            contract_path(project_name, sortie_dir=sortie_dir),
            body["execution_contract"],
        ),
        "boundary": write_bytes_atomic(
            boundary_path(project_name, sortie_dir=sortie_dir), boundary
        ),
        "dry_run": write_bytes_atomic(
            dry_run_path(project_name, sortie_dir=sortie_dir), body["dry_run"]
        ),
        "cache": write_bytes_atomic(
            cache_path(project_name, sortie_dir=sortie_dir), cache
        ),
        "report": write_bytes_atomic(
            report_path(project_name, sortie_dir=sortie_dir),
            render_report(body),
        ),
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "result": body["result"],
        "readiness": body["readiness"],
        "real_provider_calls": REAL_PROVIDER_CALLS_THIS_PHASE,
        "paths": {key: str(path) for key, path in paths.items()},
        "sha256": {key: sha256_of_file(path) for key, path in paths.items()},
        "content_hash": body["content_hash"],
    }


def write_twice_and_verify(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> dict[str, Any]:
    first = write_readiness_artifacts(project_name, sortie_dir=sortie_dir)
    second = write_readiness_artifacts(project_name, sortie_dir=sortie_dir)
    if first["sha256"] != second["sha256"]:
        raise RuntimeError(
            f"artefacts non déterministes : {first['sha256']} ≠ {second['sha256']}"
        )
    return first


def run_small_window_production_readiness(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> dict[str, Any]:
    return write_twice_and_verify(project_name, sortie_dir=sortie_dir)


if __name__ == "__main__":
    run_small_window_production_readiness()
