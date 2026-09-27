"""Préflight A.15. Doit échouer localement avant tout HTTP."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

from app.source_analysis_v2_real_win001.constants import (
    AUTHORIZATION_SCOPE,
    AUTO_CONTINUE,
    AUTO_FALLBACK,
    AUTO_RETRY,
    CANDIDATE_HARD_MAX_INPUT_TOKENS,
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
    THINKING_MODE,
    TRANSPORT_VERSION,
    WINDOW_ID,
)
from app.source_analysis_v2_real_win001.engine import credential_available, describe_engine
from app.source_analysis_v2_real_win001.facts import inspect_isolation
from app.source_analysis_v2_real_win001.guard import (
    RealWin001Error,
    validate_authorization_scope,
    validate_target,
)
from app.source_analysis_v2_real_win001.paths import (
    a15_lock_path,
    candidate_cache_dir,
    forensic_windows_root,
)
from app.source_analysis_v2_real_win001.payload import build_audited_request
from app.source_analysis_v2_real_win001.window import (
    load_candidate_win001,
    verify_win001_identity,
)


def openai_dependency_status() -> dict[str, Any]:
    spec = importlib.util.find_spec("openai")
    version = None
    if spec is not None:
        try:
            import openai

            version = getattr(openai, "__version__", None)
        except Exception:
            version = None
    return {
        "intended_dependency": True,
        "declared_in_requirements": True,
        "declared_in_requirements_dev": True,
        "present_in_active_venv": spec is not None,
        "version": version,
        "production_semantics_changed": False,
    }


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
    return {
        "path": str(path),
        "exists": exists,
        "status": "HIT" if exists else "MISS",
        "trusted_automatically": False,
        "historical_result_must_not_satisfy_new_signature": True,
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
    openai = openai_dependency_status()
    if not openai["present_in_active_venv"]:
        raise RealWin001Error(
            "Intended openai package missing from active venv — "
            "BLOCKED_PRECALL. REAL PROVIDER CALLS = 0."
        )
    write_dir = artifact_sortie_dir if artifact_sortie_dir is not None else sortie_dir
    bundle = load_candidate_win001(project_name, sortie_dir=sortie_dir)
    identity = verify_win001_identity(bundle)
    if identity["analysis_signature"] != EXPECTED_ANALYSIS_SIGNATURE:
        raise RealWin001Error("Analysis signature differs from A.14 — STOP.")
    if identity["local_input_estimate"] > CANDIDATE_HARD_MAX_INPUT_TOKENS:
        raise RealWin001Error("WIN001 local estimate exceeds candidate hard max.")
    cache = inspect_candidate_cache(
        project_name, identity["analysis_signature"], sortie_dir=write_dir
    )
    if cache["status"] == "HIT":
        raise RealWin001Error(
            "Candidate cache HIT for new A.15 signature — do not trust "
            "automatically. STOP WITHOUT NETWORK."
        )
    built = build_audited_request(bundle["window"], bundle["transcript"])
    isolation = inspect_isolation(project_name, sortie_dir=sortie_dir)
    if isolation["source_map_present"]:
        raise RealWin001Error("source_map already present — STOP WITHOUT NETWORK.")
    lock = a15_lock_path(project_name, sortie_dir=write_dir)
    if lock.exists():
        raise RealWin001Error(
            "A.15 real-call lock already present — authorization consumed. NO RETRY."
        )
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
        "window_id": target,
        "planner": CANDIDATE_PLANNER,
        "production_default": PRODUCTION_PLANNER_VERSION,
        "prompt_version": PROMPT_VERSION,
        "prompt_sha256": identity["prompt_sha256"],
        "prompt_fingerprint": identity["prompt_fingerprint"],
        "transport": TRANSPORT_VERSION,
        "schema_sha256": identity["schema_sha256"],
        "schema_metrics": built["schema_metrics"],
        "window": {
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
            "clean_provenance": identity["clean_provenance"],
        },
        "analysis_signature": identity["analysis_signature"],
        "forensic_identity": identity["forensic_identity"],
        "local_input_estimate": identity["local_input_estimate"],
        "cache": cache,
        "thinking_mode": THINKING_MODE,
        "effort": None,
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
            "policy": "A.7/A.9/A.12 candidate window stage 30/1800",
        },
        "call_budget": {
            "max_engine_generate": MAX_ENGINE_GENERATE,
            "max_anthropic_post": MAX_ANTHROPIC_POST,
            "max_real_provider_calls": 1,
            "max_real_window_calls": 1,
            "authorized_target": WINDOW_ID,
        },
        "forensic_path": str(forensic_windows_root(project_name, sortie_dir=write_dir)),
        "payload_audit": built["audit"],
        "openai_dependency": openai,
        "baseline_tests": tests,
        "test_suite_real_provider_calls": 0,
        "credential_available": credential_available(),
        "credential_secret_printed": False,
        "source_map": "NOT PUBLISHED",
        "source_map_present": isolation["source_map_present"],
        "production_win001_present": isolation["production_win001_present"],
        "isolation": isolation,
        "provider": PROVIDER,
        "model": MODEL,
        "engine": engine_desc,
        "secrets_included": False,
        "provider_called": False,
        "request": built["request"],
        "window_obj": bundle["window"],
        "transcript_obj": bundle["transcript"],
    }


__all__ = [
    "inspect_candidate_cache",
    "openai_dependency_status",
    "run_preflight",
]
