"""Préflight A.27. Doit échouer localement avant tout HTTP."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.source_analysis_v3_hardened_win001.preflight import openai_dependency_status
from app.source_analysis_v31_real_win004.constants import (
    A22_V3_SIGNATURE,
    A24_V3_SIGNATURE,
    AUTHORIZATION_SCOPE,
    AUTO_CONTINUE,
    AUTO_FALLBACK,
    AUTO_RETRY,
    CANDIDATE_PLANNER,
    CONNECT_TIMEOUT_SECONDS,
    EXPECTED_ANALYSIS_SIGNATURE,
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
    SCHEMA_VERSION,
    SELECTED_ARCHITECTURE,
    SERVER_GRAMMAR_STATUS,
    THINKING_MODE,
    TRANSPORT_VERSION,
    WINDOW_ID,
)
from app.source_analysis_v31_real_win004.engine import credential_available, describe_engine
from app.source_analysis_v31_real_win004.facts import inspect_isolation
from app.source_analysis_v31_real_win004.guard import (
    LocalLiteWin004Error,
    validate_authorization_scope,
    validate_provider,
    validate_target,
)
from app.source_analysis_v31_real_win004.paths import (
    a22_candidate_cache_dir,
    a24_candidate_cache_dir,
    a27_lock_path,
    candidate_cache_dir,
    forensic_windows_root,
)
from app.source_analysis_v31_real_win004.payload import build_audited_request, dry_run_twice
from app.source_analysis_v31_real_win004.window import (
    load_candidate_win004,
    verify_win004_identity,
)


def inspect_candidate_cache(
    project_name: str,
    analysis_signature: str,
    *,
    sortie_dir: Path | None = None,
) -> dict[str, Any]:
    path = candidate_cache_dir(
        project_name, analysis_signature, sortie_dir=sortie_dir
    )
    exists = path.exists() and any(path.iterdir()) if path.exists() else False
    a22_path = a22_candidate_cache_dir(
        project_name, A22_V3_SIGNATURE, WINDOW_ID, sortie_dir=sortie_dir
    )
    a24_path = a24_candidate_cache_dir(
        project_name, A24_V3_SIGNATURE, sortie_dir=sortie_dir
    )
    a22_exists = (
        a22_path.exists() and any(a22_path.iterdir()) if a22_path.exists() else False
    )
    a24_exists = (
        a24_path.exists() and any(a24_path.iterdir()) if a24_path.exists() else False
    )
    if exists:
        raise LocalLiteWin004Error(
            "Candidate cache HIT for A.27 1.4.0 local-lite signature — do not "
            "trust automatically. STOP WITHOUT NETWORK."
        )
    if analysis_signature in {A22_V3_SIGNATURE, A24_V3_SIGNATURE}:
        raise LocalLiteWin004Error(
            "A.27 signature collided with A.22/A.24 cache identity — STOP."
        )
    return {
        "path": str(path),
        "exists": exists,
        "status": "HIT" if exists else "MISS",
        "trusted_automatically": False,
        "a22_invalid_must_not_satisfy_a27": True,
        "a24_invalid_must_not_satisfy_a27": True,
        "a22_candidate_cache_exists": a22_exists,
        "a22_candidate_cache_path": str(a22_path),
        "a24_candidate_cache_exists": a24_exists,
        "a24_candidate_cache_path": str(a24_path),
        "a21_valid_must_not_satisfy_a27": True,
        "a19_invalid_must_not_satisfy_a27": True,
    }


def run_preflight(
    project_name: str = PROJECT_NAME,
    *,
    authorization_scope: str | None,
    window_id: str | None = WINDOW_ID,
    sortie_dir: Path | None = None,
    artifact_sortie_dir: Path | None = None,
    tests: str | None = None,
    engine=None,
) -> dict[str, Any]:
    scope = validate_authorization_scope(authorization_scope)
    target = validate_target(window_id)
    validate_provider(provider=PROVIDER, model=MODEL)
    openai = openai_dependency_status()
    write_dir = artifact_sortie_dir if artifact_sortie_dir is not None else sortie_dir
    bundle = load_candidate_win004(project_name, sortie_dir=sortie_dir)
    identity = verify_win004_identity(bundle)
    if identity["analysis_signature"] != EXPECTED_ANALYSIS_SIGNATURE:
        raise LocalLiteWin004Error("Analysis signature differs from A.26 freeze — STOP.")
    cache = inspect_candidate_cache(
        project_name, identity["analysis_signature"], sortie_dir=write_dir
    )
    built = build_audited_request(bundle["window"], bundle["transcript"])
    twice = dry_run_twice(bundle["window"], bundle["transcript"])
    isolation = inspect_isolation(project_name, sortie_dir=sortie_dir)
    if isolation["source_map_present"]:
        raise LocalLiteWin004Error("source_map already present — STOP WITHOUT NETWORK.")
    lock = a27_lock_path(project_name, sortie_dir=write_dir)
    if lock.exists():
        raise LocalLiteWin004Error(
            "A.27 real-call lock already present — authorization consumed. NO RETRY."
        )
    engine_desc = describe_engine(engine) if engine is not None else {
        "class_name": None,
        "retry_max_attempts": MAX_ATTEMPTS,
        "connect_timeout_seconds": CONNECT_TIMEOUT_SECONDS,
        "read_timeout_seconds": READ_TIMEOUT_SECONDS,
    }
    window_meta = {
        "window_id": identity["window_id"],
        "src_range": (
            f"{identity['first_owned_src_ref']} → {identity['last_owned_src_ref']}"
        ),
        "first_owned_src_ref": identity["first_owned_src_ref"],
        "last_owned_src_ref": identity["last_owned_src_ref"],
        "owned_src_count": identity["owned_src_count"],
        "word_count": identity["word_count"],
        "input_hash": identity["input_hash"],
        "context_src_count": identity["context_src_count"],
        "context_policy": identity["context_policy"],
        "clean_sha256": identity["clean_sha256"],
        "clean_file_sha256": identity["clean_file_sha256"],
        "clean_provenance": identity["clean_provenance"],
        "same_a22_ownership": identity["same_a22_ownership"],
        "same_a22_clean": identity["same_a22_clean"],
        "same_a24_ownership": identity["same_a24_ownership"],
        "same_a24_clean": identity["same_a24_clean"],
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "project_name": project_name,
        "authorization_scope": scope,
        "window_id": target,
        "planner": CANDIDATE_PLANNER,
        "production_default": PRODUCTION_PLANNER_VERSION,
        "architecture": SELECTED_ARCHITECTURE,
        "prompt_version": PROMPT_VERSION,
        "prompt_sha256": identity["prompt_sha256"],
        "prompt_fingerprint": identity["prompt_fingerprint"],
        "transport": TRANSPORT_VERSION,
        "schema_sha256": identity["schema_sha256"],
        "schema_metrics": built["schema_metrics"],
        "schema_py_exclusion": built["schema_py_exclusion"],
        "server_grammar_status": SERVER_GRAMMAR_STATUS,
        "window": window_meta,
        "analysis_signature": identity["analysis_signature"],
        "forensic_identity": identity["forensic_identity"],
        "local_input_estimate": identity["local_input_estimate"],
        "cache": cache,
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
            "engine_layer": "CountingAnthropicEngine.generate max=1",
            "provider_layer": "CountingAnthropicEngine._invoke max=1",
            "sdk_layer": "RetryPolicy(max_attempts=1)",
            "http_layer": "no HTTP retry wrapper",
        },
        "timeouts": {
            "connect_timeout_seconds": CONNECT_TIMEOUT_SECONDS,
            "read_timeout_seconds": READ_TIMEOUT_SECONDS,
            "historical_7200_used": False,
            "historical_read_timeout_seconds": HISTORICAL_READ_TIMEOUT_SECONDS,
            "policy": "A.22/A.24 bounded semantic-window timeout 30/1800",
        },
        "call_budget": {
            "max_engine_generate": MAX_ENGINE_GENERATE,
            "max_anthropic_post": MAX_ANTHROPIC_POST,
            "max_real_provider_calls": 1,
            "max_real_window_calls": 1,
            "authorized_target": WINDOW_ID,
            "win001_authorized": False,
            "other_windows_authorized": False,
        },
        "dry_run_twice": twice,
        "forensic_path": str(forensic_windows_root(project_name, sortie_dir=write_dir)),
        "payload_audit": built["audit"],
        "openai_dependency": openai,
        "openai_required_for_a27": False,
        "baseline_tests": tests,
        "test_suite_real_provider_calls": 0,
        "credential_available": credential_available(),
        "credential_secret_printed": False,
        "source_map": "NOT PUBLISHED",
        "source_map_present": isolation["source_map_present"],
        "production_win001_present": isolation["production_win001_present"],
        "production_win004_present": isolation["production_win004_present"],
        "isolation": isolation,
        "provider": PROVIDER,
        "model": MODEL,
        "engine": engine_desc,
        "secrets_included": False,
        "provider_called": False,
        "engine_generate_attempts": 0,
        "anthropic_post_attempts": 0,
        "real_windows": 0,
        "request": built["request"],
        "window_obj": bundle["window"],
        "transcript_obj": bundle["transcript"],
    }


__all__ = [
    "inspect_candidate_cache",
    "openai_dependency_status",
    "run_preflight",
]
