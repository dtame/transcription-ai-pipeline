"""Préflight A.31. Doit échouer localement avant tout HTTP."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.source_analysis_v3_hardened_win001.preflight import openai_dependency_status
from app.source_analysis_v31_final_three.constants import (
    AUTHORIZATION_SCOPE,
    AUTHORIZED_WINDOW_IDS,
    AUTO_CONTINUE,
    AUTO_FALLBACK,
    AUTO_RETRY,
    CANDIDATE_HARD_MAX_INPUT_TOKENS,
    CANDIDATE_PLANNER,
    CONNECT_TIMEOUT_SECONDS,
    EXECUTION_ORDER,
    EXPECTED_SCHEMA_HASH,
    FORBIDDEN_WINDOW_IDS,
    GRANULARITY_POLICY,
    HISTORICAL_READY_IDS,
    HISTORICAL_READ_TIMEOUT_SECONDS,
    MAX_ANTHROPIC_POST,
    MAX_ATTEMPTS,
    MAX_ENGINE_GENERATE,
    MAX_OUTPUT_TOKENS,
    MODE,
    MODEL,
    PHASE,
    PRODUCTION_PLANNER_VERSION,
    PROJECT_NAME,
    PROMPT_VERSION,
    PROVIDER,
    READ_TIMEOUT_SECONDS,
    READY_BEFORE,
    SCHEMA_VERSION,
    SELECTED_ARCHITECTURE,
    SERVER_GRAMMAR_STATUS,
    THINKING_MODE,
    TRANSPORT_VERSION,
    WIN003_PROVENANCE,
    WINDOW_SPECS,
)
from app.source_analysis_v31_final_three.engine import (
    credential_available,
    describe_engine,
)
from app.source_analysis_v31_final_three.facts import inspect_isolation
from app.source_analysis_v31_final_three.guard import (
    FinalThreeError,
    validate_authorization_scope,
    validate_provider,
)
from app.source_analysis_v31_final_three.paths import (
    a28_candidate_cache_dir,
    a31_lock_path,
    candidate_cache_dir,
    forensic_windows_root,
)
from app.source_analysis_v31_final_three.payload import (
    assert_schema_identity,
    build_audited_request,
    dry_run_twice,
)
from app.source_analysis_v31_remaining_windows.guard import RemainingWindowsError
from app.source_analysis_v31_remaining_windows.window import (
    load_candidate_plan,
    verify_all_windows,
)


def _dir_nonempty(path: Path) -> bool:
    return path.exists() and any(path.iterdir())


def inspect_candidate_cache(
    project_name: str,
    window_id: str,
    analysis_signature: str,
    *,
    sortie_dir: Path | None = None,
    allow_validated_hit: bool = False,
) -> dict[str, Any]:
    path = candidate_cache_dir(
        project_name, analysis_signature, window_id, sortie_dir=sortie_dir
    )
    exists = _dir_nonempty(path)
    a28_path = a28_candidate_cache_dir(
        project_name, analysis_signature, window_id, sortie_dir=sortie_dir
    )
    a28_exists = _dir_nonempty(a28_path)
    if exists and not allow_validated_hit:
        raise FinalThreeError(
            f"Candidate cache HIT for A.31 {window_id} 1.4.0 local-lite "
            "signature — do not trust automatically. STOP WITHOUT NETWORK."
        )
    if a28_exists:
        raise FinalThreeError(
            f"A.28 remaining cache HIT for {window_id} — not a validated "
            "A.31 candidate. Do not reuse forensic leftovers. BLOCKED_PRECALL."
        )
    return {
        "path": str(path),
        "exists": exists,
        "status": "HIT" if exists else "MISS",
        "trusted_automatically": False,
        "a28_remaining_cache_path": str(a28_path),
        "a28_remaining_cache_exists": a28_exists,
        "a28_forensic_must_not_satisfy_a31": True,
    }


def run_preflight(
    project_name: str = PROJECT_NAME,
    *,
    authorization_scope: str | None,
    sortie_dir: Path | None = None,
    artifact_sortie_dir: Path | None = None,
    tests: str | None = None,
    engine=None,
) -> dict[str, Any]:
    scope = validate_authorization_scope(authorization_scope)
    validate_provider(provider=PROVIDER, model=MODEL)
    openai = openai_dependency_status()
    write_dir = artifact_sortie_dir if artifact_sortie_dir is not None else sortie_dir
    schema = assert_schema_identity()
    if schema["raw_hash"] != EXPECTED_SCHEMA_HASH:
        raise FinalThreeError("Schema hash changed unexpectedly — BLOCKED_PRECALL.")
    try:
        bundle = load_candidate_plan(project_name, sortie_dir=sortie_dir)
        verified = verify_all_windows(bundle)
    except RemainingWindowsError as exc:
        raise FinalThreeError(str(exc)) from exc
    isolation = inspect_isolation(project_name, sortie_dir=sortie_dir)
    if isolation["source_map_present"]:
        raise FinalThreeError("source_map already present — STOP WITHOUT NETWORK.")
    lock = a31_lock_path(project_name, sortie_dir=write_dir)
    lock_consumed: list[str] = []
    if lock.exists():
        text = lock.read_text(encoding="utf-8")
        for line in text.splitlines():
            if line.startswith("consumed="):
                raw = line.split("=", 1)[1].strip()
                lock_consumed = [part for part in raw.split(",") if part]
        if not lock_consumed:
            raise FinalThreeError(
                "A.31 real-call lock already present with no completed window "
                "— authorization consumed. NO RETRY."
            )
    windows_preflight: dict[str, Any] = {}
    for window_id in EXECUTION_ORDER:
        window = bundle["windows"][window_id]
        identity = verified[window_id]
        cache = inspect_candidate_cache(
            project_name,
            window_id,
            identity["analysis_signature"],
            sortie_dir=write_dir,
            allow_validated_hit=window_id in lock_consumed,
        )
        built = build_audited_request(window, bundle["transcript"])
        twice = dry_run_twice(window, bundle["transcript"])
        if identity["local_input_estimate"] > CANDIDATE_HARD_MAX_INPUT_TOKENS:
            raise FinalThreeError(
                f"{window_id} local estimate exceeds 35000 — BLOCKED_PRECALL."
            )
        if twice.get("deterministic") is not True:
            raise FinalThreeError(
                f"{window_id} dry-run twice is not deterministic — BLOCKED_PRECALL."
            )
        windows_preflight[window_id] = {
            "window_id": window_id,
            "src_range": (
                f"{identity['first_owned_src_ref']} → {identity['last_owned_src_ref']}"
            ),
            "first_owned_src_ref": identity["first_owned_src_ref"],
            "last_owned_src_ref": identity["last_owned_src_ref"],
            "owned_src_count": identity["owned_src_count"],
            "word_count": identity["word_count"],
            "input_hash": identity["input_hash"],
            "analysis_signature": identity["analysis_signature"],
            "forensic_identity": identity["forensic_identity"],
            "prompt_sha256": identity["prompt_sha256"],
            "prompt_fingerprint": identity["prompt_fingerprint"],
            "schema_sha256": identity["schema_sha256"],
            "local_input_estimate": identity["local_input_estimate"],
            "granularity_policy": GRANULARITY_POLICY,
            "prompt_version": PROMPT_VERSION,
            "transport": TRANSPORT_VERSION,
            "schema_identity": schema.get("raw_hash"),
            "cache": cache,
            "dry_run_twice": twice,
            "payload_audit": built["audit"],
            "schema_py_exclusion": built["schema_py_exclusion"],
            "authorized": True,
        }
    historical = {
        window_id: {
            "window_id": window_id,
            "src_range": (
                f"{verified[window_id]['first_owned_src_ref']} → "
                f"{verified[window_id]['last_owned_src_ref']}"
            ),
            "owned_src_count": verified[window_id]["owned_src_count"],
            "word_count": verified[window_id]["word_count"],
            "input_hash": verified[window_id]["input_hash"],
            "analysis_signature": verified[window_id]["analysis_signature"],
            "local_input_estimate": verified[window_id]["local_input_estimate"],
            "authorized": False,
            "ready": True,
            "regenerate": False,
            "win003_provenance": WIN003_PROVENANCE if window_id == "WIN003" else None,
        }
        for window_id in HISTORICAL_READY_IDS
    }
    engine_desc = describe_engine(engine) if engine is not None else {
        "class_name": None,
        "retry_max_attempts": MAX_ATTEMPTS,
        "connect_timeout_seconds": CONNECT_TIMEOUT_SECONDS,
        "read_timeout_seconds": READ_TIMEOUT_SECONDS,
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "project_name": project_name,
        "authorization_scope": scope,
        "planner": CANDIDATE_PLANNER,
        "production_default": PRODUCTION_PLANNER_VERSION,
        "architecture": SELECTED_ARCHITECTURE,
        "prompt_version": PROMPT_VERSION,
        "transport": TRANSPORT_VERSION,
        "granularity_policy": GRANULARITY_POLICY,
        "schema_metrics": schema,
        "server_grammar_status": SERVER_GRAMMAR_STATUS,
        "authorized_windows": list(AUTHORIZED_WINDOW_IDS),
        "forbidden_windows": list(FORBIDDEN_WINDOW_IDS),
        "execution_order": list(EXECUTION_ORDER),
        "windows": windows_preflight,
        "historical_ready": historical,
        "win003_provenance": WIN003_PROVENANCE,
        "window_specs": {
            window_id: {
                "local_input_estimate": WINDOW_SPECS[window_id]["local_input_estimate"],
                "analysis_signature": WINDOW_SPECS[window_id]["analysis_signature"],
            }
            for window_id in WINDOW_SPECS
        },
        "thinking_mode": THINKING_MODE,
        "effort": None,
        "budget_tokens": None,
        "task_budget": None,
        "max_output_tokens": MAX_OUTPUT_TOKENS,
        "temperature_behavior": "omitted / provider-compatible disabled-thinking",
        "retry": {
            "engine_retry": False,
            "max_attempts": MAX_ATTEMPTS,
            "provider_sdk_retry": False,
            "http_retry": False,
            "fallback": AUTO_FALLBACK,
            "auto_continue": AUTO_CONTINUE,
            "auto_retry": AUTO_RETRY,
        },
        "timeouts": {
            "connect_timeout_seconds": CONNECT_TIMEOUT_SECONDS,
            "read_timeout_seconds": READ_TIMEOUT_SECONDS,
            "historical_7200_used": False,
            "historical_read_timeout_seconds": HISTORICAL_READ_TIMEOUT_SECONDS,
        },
        "call_budget": {
            "max_engine_generate": MAX_ENGINE_GENERATE,
            "max_anthropic_post": MAX_ANTHROPIC_POST,
            "max_real_provider_calls": 3,
            "max_real_window_calls": 3,
            "max_per_window": 1,
            "authorized_targets": list(AUTHORIZED_WINDOW_IDS),
            "win001_authorized": False,
            "win002_authorized": False,
            "win003_authorized": False,
            "win004_authorized": False,
        },
        "forensic_path": str(forensic_windows_root(project_name, sortie_dir=write_dir)),
        "openai_dependency": openai,
        "openai_required_for_a31": False,
        "baseline_tests": tests,
        "test_suite_real_provider_calls": 0,
        "credential_available": credential_available(),
        "credential_secret_printed": False,
        "source_map": "NOT PUBLISHED",
        "source_map_present": isolation["source_map_present"],
        "isolation": isolation,
        "provider": PROVIDER,
        "model": MODEL,
        "engine": engine_desc,
        "secrets_included": False,
        "provider_called": False,
        "engine_generate_attempts": 0,
        "anthropic_post_attempts": 0,
        "ready_before": READY_BEFORE,
        "lock_consumed": lock_consumed,
        "bundle": bundle,
        "verified": verified,
    }


__all__ = ["inspect_candidate_cache", "openai_dependency_status", "run_preflight"]
