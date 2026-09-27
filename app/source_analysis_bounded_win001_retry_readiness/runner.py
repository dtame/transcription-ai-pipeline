"""Runner offline 3B.7.7A.3 — artefacts déterministes, 0 appel provider."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.file_utils import content_hash
from app.semantic_canary.integrity import sha256_of_file
from app.source_analysis.window_prompt import WINDOW_ANALYSIS_PROMPT_VERSION
from app.source_analysis_bounded_win001_retry_readiness.cache_audit import (
    inspect_versioned_cache,
)
from app.source_analysis_bounded_win001_retry_readiness.collision import (
    audit_collisions,
)
from app.source_analysis_bounded_win001_retry_readiness.constants import (
    AUTHORIZATION_SCOPE,
    DRY_RUN_COMMAND,
    FUTURE_REAL_COMMAND,
    GRANULARITY_POLICY_VERSION,
    HISTORICAL_SPEND_USD,
    MODE,
    NEXT_ACTION,
    PHASE,
    PROJECT_NAME,
    REAL_PROVIDER_CALLS_THIS_PHASE,
    SCHEMA_VERSION,
    SUCCESSOR_PROMPT,
    WIN001_RETRIED,
    WINDOW_ID,
)
from app.source_analysis_bounded_win001_retry_readiness.cost_risk import build_cost_risk
from app.source_analysis_bounded_win001_retry_readiness.facts import implementation_facts
from app.source_analysis_bounded_win001_retry_readiness.integrity import (
    clean_integrity,
    generation_c_integrity,
    prompt_integrity,
    protected_hashes,
)
from app.source_analysis_bounded_win001_retry_readiness.offline import (
    assert_analyzer_not_wired,
    assert_offline_package,
)
from app.source_analysis_bounded_win001_retry_readiness.report import render_report
from app.source_analysis_bounded_win001_retry_readiness.request import (
    rebuild_bounded_win001_request,
)
from app.source_analysis_bounded_win001_retry_readiness.writer import (
    contract_path,
    cost_path,
    dry_run_path,
    readiness_path,
    report_path,
    write_bytes_atomic,
)
from app.source_analysis_hybrid_readiness.canary import run_win001_canary
from app.source_analysis_hybrid_readiness.constants import (
    MAX_ATTEMPTS,
    MAX_NEW_CALLS_WIN001,
)
from app.source_analysis_window_output_bounding.size_study import run_size_study


def _execution_contract(request: dict[str, Any], cache: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "authorization_scope": AUTHORIZATION_SCOPE,
        "required_prompt_version": SUCCESSOR_PROMPT,
        "required_prompt_sha256": request["prompt_sha256"],
        "required_policy_version": GRANULARITY_POLICY_VERSION,
        "window_id": WINDOW_ID,
        "provider": request["provider"],
        "model": request["model"],
        "max_new_calls": MAX_NEW_CALLS_WIN001,
        "max_attempts": MAX_ATTEMPTS,
        "auto_retry": False,
        "auto_continue": False,
        "auto_fallback": False,
        "auto_consolidation": False,
        "auto_reconstruction": False,
        "auto_publication": False,
        "timeout_connect_seconds": request["connect_timeout_seconds"],
        "timeout_read_seconds": request["read_timeout_seconds"],
        "max_output": request["max_output"],
        "expected_cache_state": "MISS",
        "current_1_1_cache": cache["WIN001_1_1"]["cache_state"],
        "forensic_behavior": (
            "persist under structured_output_forensics/WIN001/<analysis_signature>/ "
            "before exception escapes; no JSON repair; no secrets"
        ),
        "success_gate": (
            "one Anthropic POST; parse succeeds; granularity valid; no overflow; "
            "WindowResultValidator PASS; result persisted; cache HIT; usage captured"
        ),
        "failure_gates": {
            "output_ceiling_again": "STOP. Do not authorize a third WIN001 call.",
            "capacity_signal": "STOP. Human review. No smaller-window retry.",
            "over_hard_limit": "transport preserved; result rejected; STOP.",
            "parse_below_ceiling": "diagnose from forensics before any further call.",
            "http_timeout": "fail closed. No retry.",
        },
        "post_call_stop": True,
        "success_does_not_authorize_win002": True,
        "future_real_command": FUTURE_REAL_COMMAND,
        "future_real_command_executed": False,
        "human_authorization_required": True,
        "real_calls": 0,
        "win001_retried": False,
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


def build_payload(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> dict[str, Any]:
    assert_offline_package()
    assert_analyzer_not_wired()
    request = rebuild_bounded_win001_request(project_name, sortie_dir=sortie_dir)
    cache = inspect_versioned_cache(project_name, sortie_dir=sortie_dir)
    collision = audit_collisions(
        project_name=project_name,
        future_signature=request["window_signature"],
        historical_signature=request["historical_signature"],
        sortie_dir=sortie_dir,
    )
    size_study = run_size_study()
    cost = build_cost_risk(
        local_estimated_input=int(request["local_estimated_input"]),
        size_study=size_study,
    )
    canary = run_win001_canary(
        project_name,
        window_id=WINDOW_ID,
        dry_run=True,
        execute_real=False,
        authorization_scope=AUTHORIZATION_SCOPE,
        prompt_version=WINDOW_ANALYSIS_PROMPT_VERSION,
        sortie_dir=sortie_dir,
    )
    dry = _dry_run_artifact(canary)
    prompts = prompt_integrity()
    generation = generation_c_integrity()
    facts = implementation_facts(
        request=request,
        cache=cache,
        collision=collision,
        cost=cost,
        dry_run=dry,
        prompts=prompts,
        generation_c=generation,
        project_name=project_name,
        sortie_dir=sortie_dir,
    )
    contract = _execution_contract(request, cache)
    readiness = facts["readiness"]
    result = "PASS" if readiness == "READY_FOR_BOUNDED_WIN001_CANARY" else "PARTIAL"
    if facts["blockers"]["prompt_1_1_changed"] or facts["blockers"]["generation_c_changed"]:
        result = "FAIL"
        readiness = "BLOCKED"
        facts["readiness"] = readiness
    body = {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "result": result,
        "readiness": readiness,
        "real_provider_calls": REAL_PROVIDER_CALLS_THIS_PHASE,
        "win001_retried": WIN001_RETRIED,
        "window_id": WINDOW_ID,
        "request": request,
        "cache": cache,
        "collision": collision,
        "size_study": size_study,
        "cost_risk": cost,
        "dry_run": dry,
        "execution_contract": contract,
        "implementation": facts,
        "prompts": prompts,
        "generation_c": generation,
        "clean": clean_integrity(project_name, sortie_dir=sortie_dir),
        "protected_hashes": protected_hashes(project_name, sortie_dir=sortie_dir),
        "baseline": {"passed": 2340, "failed": 0},
        "source_map_published": cache["source_map_present"],
        "project_state": cache["project_state"],
        "next_action": NEXT_ACTION,
        "historical_spend_usd": HISTORICAL_SPEND_USD,
        "network": 0,
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
        "cache": body["cache"],
        "collision": body["collision"],
        "implementation": body["implementation"],
        "prompts": body["prompts"],
        "generation_c": body["generation_c"],
        "protected_hashes": body["protected_hashes"],
        "real_provider_calls": REAL_PROVIDER_CALLS_THIS_PHASE,
        "win001_retried": WIN001_RETRIED,
        "content_hash": body["content_hash"],
    }
    cost = {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        **body["cost_risk"],
    }
    contract = body["execution_contract"]
    dry = body["dry_run"]
    paths = {
        "readiness": write_bytes_atomic(
            readiness_path(project_name, sortie_dir=sortie_dir), readiness
        ),
        "cost_risk": write_bytes_atomic(
            cost_path(project_name, sortie_dir=sortie_dir), cost
        ),
        "execution_contract": write_bytes_atomic(
            contract_path(project_name, sortie_dir=sortie_dir), contract
        ),
        "dry_run": write_bytes_atomic(
            dry_run_path(project_name, sortie_dir=sortie_dir), dry
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


def run_bounded_win001_retry_readiness(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> dict[str, Any]:
    return write_twice_and_verify(project_name, sortie_dir=sortie_dir)
