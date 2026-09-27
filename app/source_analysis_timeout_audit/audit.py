"""
Audit offline de la hiérarchie de timeout 3B Final.

Aucun engine.generate(), aucun requests.post(), aucun appel réseau.
Le diagnostic est déterministe : pas d'horodatage, pas d'UUID, chemins relatifs.
"""

from __future__ import annotations

import ast
import inspect
import json
from dataclasses import fields
from pathlib import Path
from typing import Any, Mapping

import app.config as config

from app.ai.contracts import AIRequest
from app.ai.providers.anthropic_engine import AnthropicEngine
from app.ai.providers.base import BaseAIEngine
from app.ai.settings import StageSettings, default_timeout_seconds, resolve_stage_settings
from app.file_utils import content_hash
from app.language_cleanup.transcript_source import audit_dir
from app.project_state import load_project_state
from app.source_analysis import state as state_module
from app.source_analysis.writer import source_map_path
from app.source_analysis_global_clean.constants import (
    EXPECTED_MODEL,
    EXPECTED_MODEL_MAX_OUTPUT,
    EXPECTED_PROVIDER,
    MAX_ATTEMPTS,
    MAX_REAL_CALLS,
    REAL_CALL_TIMEOUT_SECONDS,
    STAGE,
)
from app.source_analysis_global_clean.writer import (
    dry_run_path,
    result_path,
    transport_path,
)
from app.source_analysis_timeout_audit.constants import (
    ANTHROPIC_RESPONSE_MODE,
    AUTHORIZATION_WAIT_COUNTS,
    CANARY_SCALING_IS_NOT_LINEARLY_PREDICTIVE,
    COST_MEANS,
    HTTP_TIMEOUT_FORM,
    INCREASE_3600_ONLY_SUFFICIENT,
    LOWER_TIMEOUT_ELSEWHERE,
    MODE,
    NEW_ANTHROPIC_CALL_AUTHORIZED,
    NEXT_STEP,
    NEXT_TIMEOUT_CANDIDATE,
    NEXT_TIMEOUT_CONFIDENCE,
    NEXT_TIMEOUT_JUSTIFICATION,
    PHASE,
    PRIMARY_CLASSIFICATION,
    PROVIDER_MAY_HAVE_CONTINUED,
    RECOMMENDATION_CONFIDENCE,
    REQUEST_ID_RECOVERABLE,
    SCHEMA_VERSION,
    SECONDARY_RISKS,
    TIMEOUT_CLOCK_STARTS_AT,
)

_EMPTY_NETWORK = {
    "anthropic": 0,
    "openai": 0,
    "whisper": 0,
    "ollama": 0,
    "lm_studio": 0,
    "other": 0,
}


def production_timeout_unchanged() -> bool:
    return float(REAL_CALL_TIMEOUT_SECONDS) == 3600.0


def stage_settings_has_timeout_field() -> bool:
    return any(item.name == "request_timeout_seconds" for item in fields(StageSettings))


def resolve_3b_final_timeout_seconds() -> float:
    """
    Résolution effective du timeout 3B Final.

    AIRequest.timeout_seconds n'est pas posé par le runner.
    L'engine est construit avec timeout_seconds=REAL_CALL_TIMEOUT_SECONDS.
    BaseAIEngine.resolve_timeout() retourne donc ce constructeur, pas le défaut 300.
    """
    request = AIRequest(prompt="timeout-audit-probe")
    engine = AnthropicEngine(
        model=EXPECTED_MODEL,
        api_key="timeout-audit-unused",
        timeout_seconds=REAL_CALL_TIMEOUT_SECONDS,
    )
    return float(engine.resolve_timeout(request))


def default_timeout_is_overridden() -> bool:
    return resolve_3b_final_timeout_seconds() != default_timeout_seconds()


def anthropic_payload_is_non_streaming() -> bool:
    engine = AnthropicEngine(model=EXPECTED_MODEL, api_key="timeout-audit-unused")
    payload = engine.build_payload(
        AIRequest(prompt="timeout-audit-probe"),
        EXPECTED_MODEL,
    )
    return "stream" not in payload


def http_timeout_is_scalar() -> bool:
    source = inspect.getsource(__import__("app.ai.providers._http", fromlist=["post_json"]))
    return "timeout=timeout" in source and "timeout=(" not in source


def generate_starts_latency_clock_before_invoke() -> bool:
    source = inspect.getsource(BaseAIEngine.generate)
    started = source.find("started = self._clock()")
    invoke = source.find("self._invoke")
    return started != -1 and invoke != -1 and started < invoke


def runner_calls_generate_after_preflight() -> bool:
    from app.source_analysis_global_clean import runner as runner_module

    source = inspect.getsource(runner_module._execute)
    dry = source.find("if dry_run:")
    generate = source.find("guarded.generate(request)")
    return dry != -1 and generate != -1 and dry < generate


def runner_has_no_authorization_wait() -> bool:
    from app.source_analysis_global_clean import runner as runner_module

    source = inspect.getsource(runner_module)
    forbidden = (
        "wait_for_approval",
        "human_authorization",
        "authorize_call",
        "input(\" ",
        "builtins.input",
    )
    return not any(token in source for token in forbidden)


def package_calls_generate_or_post(package_dir: Path | None = None) -> list[str]:
    root = Path(package_dir) if package_dir else Path(__file__).resolve().parent
    hits: list[str] = []
    for path in sorted(root.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = ""
            if isinstance(func, ast.Attribute):
                name = func.attr
            elif isinstance(func, ast.Name):
                name = func.id
            if name in {"generate", "post", "urlopen", "urlretrieve"}:
                hits.append(f"{path.name}:{name}")
    return hits


def timeout_layers() -> list[dict[str, Any]]:
    effective = resolve_3b_final_timeout_seconds()
    default = default_timeout_seconds()
    return [
        {
            "layer": "runner_constant",
            "file": "app/source_analysis_global_clean/constants.py",
            "symbol": "REAL_CALL_TIMEOUT_SECONDS",
            "type": "HARDCODED_CONSTANT",
            "configured_seconds": float(REAL_CALL_TIMEOUT_SECONDS),
            "default_seconds": float(REAL_CALL_TIMEOUT_SECONDS),
            "effective_seconds": effective,
            "timeout_kind": "SOURCE_OF_HTTP_TIMEOUT",
            "exception": None,
            "exception_wrapping": None,
            "retry_behavior": "none",
            "stage_specific": False,
            "active_in_failed_run": True,
        },
        {
            "layer": "engine_constructor",
            "file": "app/source_analysis_global_clean/runner.py",
            "symbol": "get_ai_engine(..., timeout_seconds=REAL_CALL_TIMEOUT_SECONDS)",
            "type": "ENGINE_INSTANCE_TIMEOUT",
            "configured_seconds": float(REAL_CALL_TIMEOUT_SECONDS),
            "default_seconds": default,
            "effective_seconds": effective,
            "timeout_kind": "RESOLVED_THEN_PASSED_TO_HTTP",
            "exception": None,
            "exception_wrapping": None,
            "retry_behavior": "none",
            "stage_specific": False,
            "active_in_failed_run": True,
        },
        {
            "layer": "ai_request",
            "file": "app/source_analysis_global_clean/runner.py",
            "symbol": "AIRequest(...)",
            "type": "REQUEST_TIMEOUT",
            "configured_seconds": None,
            "default_seconds": None,
            "effective_seconds": None,
            "timeout_kind": "NOT_SET",
            "exception": None,
            "exception_wrapping": None,
            "retry_behavior": "none",
            "stage_specific": False,
            "active_in_failed_run": False,
        },
        {
            "layer": "resolve_timeout",
            "file": "app/ai/providers/base.py",
            "symbol": "BaseAIEngine.resolve_timeout",
            "type": "RESOLUTION",
            "configured_seconds": float(REAL_CALL_TIMEOUT_SECONDS),
            "default_seconds": default,
            "effective_seconds": effective,
            "timeout_kind": "REQUEST_THEN_ENGINE_THEN_CONFIG",
            "exception": None,
            "exception_wrapping": None,
            "retry_behavior": "none",
            "stage_specific": False,
            "active_in_failed_run": True,
        },
        {
            "layer": "http_client",
            "file": "app/ai/providers/_http.py",
            "symbol": "post_json / requests.post",
            "type": "HTTP_CONNECT_AND_READ",
            "configured_seconds": effective,
            "default_seconds": None,
            "effective_seconds": effective,
            "timeout_kind": "SCALAR_CONNECT_AND_READ",
            "exception": "requests.exceptions.Timeout",
            "exception_wrapping": "AITimeoutError",
            "retry_behavior": "none_max_attempts_1",
            "stage_specific": False,
            "active_in_failed_run": True,
        },
        {
            "layer": "ai_default_timeout",
            "file": "app/config.py",
            "symbol": "AI_DEFAULT_TIMEOUT_SECONDS",
            "type": "GLOBAL_DEFAULT",
            "configured_seconds": default,
            "default_seconds": 300.0,
            "effective_seconds": default,
            "timeout_kind": "OVERRIDDEN_BY_ENGINE_CONSTRUCTOR",
            "exception": None,
            "exception_wrapping": None,
            "retry_behavior": "n/a",
            "stage_specific": False,
            "active_in_failed_run": False,
        },
        {
            "layer": "stage_settings",
            "file": "app/ai/settings.py",
            "symbol": "StageSettings",
            "type": "STAGE_CONFIG",
            "configured_seconds": None,
            "default_seconds": None,
            "effective_seconds": None,
            "timeout_kind": "NO_TIMEOUT_FIELD",
            "exception": None,
            "exception_wrapping": None,
            "retry_behavior": "n/a",
            "stage_specific": False,
            "active_in_failed_run": False,
        },
        {
            "layer": "sibling_real_run_constant",
            "file": "app/source_analysis/real_run.py",
            "symbol": "REAL_CALL_TIMEOUT_SECONDS",
            "type": "HARDCODED_CONSTANT",
            "configured_seconds": 3600.0,
            "default_seconds": 3600.0,
            "effective_seconds": 3600.0,
            "timeout_kind": "NOT_USED_BY_3B_FINAL",
            "exception": None,
            "exception_wrapping": None,
            "retry_behavior": "none",
            "stage_specific": False,
            "active_in_failed_run": False,
        },
        {
            "layer": "real_call_guard",
            "file": "app/source_analysis/guard.py",
            "symbol": "RealCallGuard.guarded_generate",
            "type": "CALL_COUNTER",
            "configured_seconds": None,
            "default_seconds": None,
            "effective_seconds": None,
            "timeout_kind": "NOT_A_TIMEOUT",
            "exception": "MaxRealCallsExceededError",
            "exception_wrapping": None,
            "retry_behavior": "blocks_second_call",
            "stage_specific": False,
            "active_in_failed_run": True,
        },
        {
            "layer": "retry_policy",
            "file": "app/ai/retry.py",
            "symbol": "RetryPolicy(max_attempts=MAX_ATTEMPTS)",
            "type": "RETRY",
            "configured_seconds": None,
            "default_seconds": 3,
            "effective_seconds": MAX_ATTEMPTS,
            "timeout_kind": "NOT_A_TIMEOUT",
            "exception": None,
            "exception_wrapping": None,
            "retry_behavior": "max_attempts_1_no_retry",
            "stage_specific": False,
            "active_in_failed_run": True,
        },
        {
            "layer": "future_thread_subprocess",
            "file": None,
            "symbol": None,
            "type": "ABSENT",
            "configured_seconds": None,
            "default_seconds": None,
            "effective_seconds": None,
            "timeout_kind": "NOT_PRESENT_ON_3B_FINAL_PATH",
            "exception": None,
            "exception_wrapping": None,
            "retry_behavior": "n/a",
            "stage_specific": False,
            "active_in_failed_run": False,
        },
        {
            "layer": "provider_upstream",
            "file": None,
            "symbol": None,
            "type": "PROVIDER_OR_PROXY",
            "configured_seconds": None,
            "default_seconds": None,
            "effective_seconds": None,
            "timeout_kind": "NOT_DOCUMENTED_LOCALLY",
            "exception": None,
            "exception_wrapping": None,
            "retry_behavior": "unknown",
            "stage_specific": False,
            "active_in_failed_run": None,
        },
    ]


def exception_chain() -> list[dict[str, Any]]:
    return [
        {
            "layer": "requests",
            "incoming": None,
            "outgoing": "requests.exceptions.Timeout",
            "wrapped": False,
            "message_preserved": True,
            "response_attached": False,
            "usage_attached": False,
        },
        {
            "layer": "post_json",
            "file": "app/ai/providers/_http.py",
            "incoming": "requests.exceptions.Timeout",
            "outgoing": "AITimeoutError",
            "wrapped": True,
            "message_preserved": True,
            "response_attached": False,
            "usage_attached": False,
        },
        {
            "layer": "AnthropicEngine._invoke",
            "file": "app/ai/providers/anthropic_engine.py",
            "incoming": "AITimeoutError",
            "outgoing": "AITimeoutError",
            "wrapped": False,
            "message_preserved": True,
            "response_attached": False,
            "usage_attached": False,
        },
        {
            "layer": "BaseAIEngine.generate",
            "file": "app/ai/providers/base.py",
            "incoming": "AITimeoutError",
            "outgoing": "AITimeoutError",
            "wrapped": False,
            "message_preserved": True,
            "response_attached": False,
            "usage_attached": False,
            "note": "AIError.response stays None because transport never produced ProviderResult",
        },
        {
            "layer": "call_with_retry",
            "file": "app/ai/retry.py",
            "incoming": "AITimeoutError",
            "outgoing": "AITimeoutError",
            "wrapped": False,
            "message_preserved": True,
            "retry": False,
            "max_attempts": MAX_ATTEMPTS,
        },
        {
            "layer": "GuardedEngine / RealCallGuard",
            "file": "app/source_analysis/real_run.py",
            "incoming": "AITimeoutError",
            "outgoing": "AITimeoutError",
            "wrapped": False,
            "call_counted_before_invoke": True,
        },
        {
            "layer": "run_global_clean_source_analysis",
            "file": "app/source_analysis_global_clean/runner.py",
            "incoming": "AITimeoutError",
            "outgoing": "recorded_failure",
            "wrapped": False,
            "transport_written": False,
            "source_map_published": False,
            "project_state": "failed",
        },
    ]


def documented_failed_run() -> dict[str, Any]:
    """Faits du run 3B Final, lus depuis le code et les artefacts connus."""
    return {
        "error": "AITimeoutError",
        "configured_guard_seconds": float(REAL_CALL_TIMEOUT_SECONDS),
        "provider_body_received": False,
        "transport_created": False,
        "source_map_published": False,
        "segments": 8298,
        "words": 38313,
        "duration_seconds": 19954.601,
        "estimated_input_tokens": 142953,
        "usable_input_budget": 572000,
        "remaining_margin": 429047,
        "max_output_tokens": EXPECTED_MODEL_MAX_OUTPUT,
        "request_id_available": False,
        "provider_usage_available": False,
        "cost_known": False,
        "http_status": None,
        "latency_ms": None,
        "actual_real_calls": 1,
        "max_attempts": MAX_ATTEMPTS,
        "retry": False,
    }


def load_failed_run_facts(
    project_name: str,
    *,
    sortie_dir: Path | None = None,
) -> dict[str, Any]:
    facts = documented_failed_run()
    dry = dry_run_path(project_name, sortie_dir=sortie_dir)
    result = result_path(project_name, sortie_dir=sortie_dir)
    if dry.is_file():
        payload = json.loads(dry.read_text(encoding="utf-8"))
        input_block = payload.get("input") or {}
        preflight = payload.get("preflight") or {}
        facts["segments"] = input_block.get("segments", facts["segments"])
        facts["words"] = input_block.get("words", facts["words"])
        facts["duration_seconds"] = input_block.get(
            "duration_seconds", facts["duration_seconds"]
        )
        facts["estimated_input_tokens"] = preflight.get(
            "estimated_tokens", facts["estimated_input_tokens"]
        )
        facts["usable_input_budget"] = preflight.get(
            "usable_input_budget", facts["usable_input_budget"]
        )
        facts["remaining_margin"] = preflight.get(
            "remaining_margin", facts["remaining_margin"]
        )
        facts["max_output_tokens"] = preflight.get(
            "resolved_max_output", facts["max_output_tokens"]
        )
    if result.is_file():
        payload = json.loads(result.read_text(encoding="utf-8"))
        usage = payload.get("usage") or {}
        cost = payload.get("cost") or {}
        provider = payload.get("provider") or {}
        source_map = payload.get("source_map") or {}
        execution = payload.get("execution") or {}
        facts["provider_usage_available"] = usage.get("usage_source") == "provider"
        facts["cost_known"] = cost.get("status") == "known"
        facts["request_id_available"] = bool(provider.get("request_id_present"))
        facts["http_status"] = provider.get("http_status")
        facts["latency_ms"] = provider.get("latency_ms")
        facts["source_map_published"] = bool(source_map.get("published"))
        facts["actual_real_calls"] = execution.get(
            "actual_real_calls", facts["actual_real_calls"]
        )
        facts["retry"] = bool(execution.get("retry"))
        facts["provider_body_received"] = provider.get("http_status") is not None
    facts["transport_created"] = transport_path(
        project_name, sortie_dir=sortie_dir
    ).is_file()
    facts["source_map_exists"] = source_map_path(
        project_name, sortie_dir=sortie_dir
    ).is_file()
    state = load_project_state(project_name)
    block = state_module.load_state_block(state)
    facts["project_state_status"] = block.get("status")
    facts["project_state_error"] = block.get("error")
    return facts


def inspect_project_state(
    project_name: str,
    *,
    sortie_dir: Path | None = None,
) -> dict[str, Any]:
    state = load_project_state(project_name)
    block = state_module.load_state_block(state)
    return {
        "status": block.get("status"),
        "error": block.get("error"),
        "path": block.get("path"),
        "success": block.get("status") == state_module.STATUS_COMPLETED,
    }


def multi_window_status() -> dict[str, Any]:
    from app.source_analysis.context_strategy import plan_windows

    return {
        "plan_windows_exists": callable(plan_windows),
        "multi_window_consolidation_available": False,
        "evidence": (
            "plan_windows() découpe sur frontières SRC mais analyzer.py et "
            "le runner 3B Final lèvent si strategy != global. Aucune "
            "consolidation multi-fenêtres n'est implémentée ni autorisée."
        ),
    }


def canary_comparison() -> dict[str, Any]:
    return {
        "canary_3b45": {
            "segments": 10,
            "words": 100,
            "estimated_total_preflight": 3314,
            "provider_input_tokens": 6545,
            "provider_output_tokens": 3544,
            "latency_ms": 37297,
        },
        "final_3b": {
            "segments": 8298,
            "words": 38313,
            "estimated_input_tokens": 142953,
            "timeout_seconds": float(REAL_CALL_TIMEOUT_SECONDS),
            "provider_body": False,
        },
        "CANARY_SCALING_IS_NOT_LINEARLY_PREDICTIVE": (
            CANARY_SCALING_IS_NOT_LINEARLY_PREDICTIVE
        ),
    }


def observability_gaps() -> list[str]:
    return [
        "request_start_monotonic_time_not_persisted",
        "http_connection_established_time_absent",
        "headers_received_time_absent",
        "first_byte_time_absent",
        "body_complete_time_absent",
        "exception_subclass_connect_vs_read_not_recorded",
        "effective_timeout_not_in_result_artifact",
        "error_type_omitted_from_result_json",
        "request_id_unavailable_before_json_body",
        "no_streaming_progress_because_non_streaming",
        "elapsed_time_not_written_on_timeout_failure",
    ]


def build_timeout_root_cause_audit(
    *,
    failed_run: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    facts = dict(failed_run) if failed_run is not None else documented_failed_run()
    effective = resolve_3b_final_timeout_seconds()
    layers = timeout_layers()
    active = [
        layer
        for layer in layers
        if layer.get("active_in_failed_run") is True
        and layer.get("timeout_kind")
        not in {"NOT_A_TIMEOUT", "NOT_PRESENT_ON_3B_FINAL_PATH"}
        and layer.get("effective_seconds")
    ]
    active_seconds = [
        float(layer["effective_seconds"])
        for layer in active
        if isinstance(layer.get("effective_seconds"), (int, float))
        and layer["effective_seconds"] == effective
    ]
    lowest = min(active_seconds) if active_seconds else effective
    highest = max(active_seconds) if active_seconds else effective
    settings = resolve_stage_settings(STAGE)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "failed_run": {
            "error": facts.get("error"),
            "configured_guard_seconds": float(REAL_CALL_TIMEOUT_SECONDS),
            "provider_body_received": bool(facts.get("provider_body_received")),
            "transport_created": bool(facts.get("transport_created")),
            "source_map_published": bool(facts.get("source_map_published")),
        },
        "timeout_layers": layers,
        "effective_timeout": {
            "seconds": effective,
            "source": "app/source_analysis_global_clean/constants.py:REAL_CALL_TIMEOUT_SECONDS",
            "kind": "hardcoded_constant",
            "overridden_by": None,
            "lowest_active_timeout_seconds": lowest,
            "highest_active_timeout_seconds": highest,
            "ai_default_timeout_seconds": default_timeout_seconds(),
            "ai_default_active": False,
            "request_timeout_seconds": None,
            "http_timeout_form": HTTP_TIMEOUT_FORM,
            "production_timeout_unchanged": production_timeout_unchanged(),
        },
        "authorization_wait": {
            "counts_toward_timeout": AUTHORIZATION_WAIT_COUNTS,
            "timeout_clock_starts_at": TIMEOUT_CLOCK_STARTS_AT,
            "evidence": (
                "No authorization wait exists in the 3B Final runner or engine. "
                "Preflight, dry-run write and credential check complete before "
                "guarded.generate(). BaseAIEngine.generate() starts a monotonic "
                "latency clock immediately before _invoke; that clock measures "
                "latency and does not abort. The aborting clock is the requests "
                "connect/read timeout started at requests.post() in post_json."
            ),
            "runner_has_authorization_wait": False,
            "generate_clock_is_latency_only": True,
        },
        "http": {
            "client": "requests",
            "sdk": None,
            "streaming": False,
            "response_mode": ANTHROPIC_RESPONSE_MODE,
            "connect_timeout": effective,
            "read_timeout": effective,
            "total_timeout": None,
            "timeout_argument": "timeout=<float>",
            "post_target": "/v1/messages",
        },
        "exception_chain": exception_chain(),
        "aitimeouterror_origin": {
            "constructed_in": "app/ai/providers/_http.py:post_json",
            "after_capture_of": "requests.exceptions.Timeout",
            "not_an_internal_timer": True,
            "response_attached": False,
        },
        "failed_request": {
            "segments": facts.get("segments"),
            "words": facts.get("words"),
            "estimated_input_tokens": facts.get("estimated_input_tokens"),
            "usable_input_budget": facts.get("usable_input_budget"),
            "remaining_margin": facts.get("remaining_margin"),
            "max_output_tokens": facts.get("max_output_tokens"),
            "request_id_available": bool(facts.get("request_id_available")),
            "provider_usage_available": bool(facts.get("provider_usage_available")),
            "cost_known": bool(facts.get("cost_known")),
            "corpus_fits_context_budget": True,
        },
        "architecture": {
            "global_run_risks": [
                "long_provider_compute_time",
                "large_max_output_128000",
                "timeout_probability_on_non_streaming_wait",
                "connection_interruption_loses_entire_body",
                "single_shot_cost_unknown_on_timeout",
                "structured_generation_complexity",
                "no_resume_within_provider_generation",
                "no_partial_body_preservation",
            ],
            "global_run_benefits": [
                "global_semantic_context",
                "single_coherent_analysis",
                "no_cross_window_consolidation",
                "simpler_deterministic_normalization",
                "avoids_topic_idea_duplication_across_windows",
            ],
            "multi_window_consolidation_available": False,
            "timeout_config": {
                "global_provider_default": True,
                "stage_specific_field": stage_settings_has_timeout_field(),
                "runner_specific_hardcoded": True,
                "can_set_source_analysis_without_other_stages": (
                    "today_only_by_changing_REAL_CALL_TIMEOUT_SECONDS_in_"
                    "source_analysis_global_clean_or_passing_engine_timeout"
                ),
                "proposed_next": "StageSettings.request_timeout_seconds",
            },
            "stage_settings": settings.to_dict(),
        },
        "decision": {
            "primary_classification": PRIMARY_CLASSIFICATION,
            "secondary_risks": list(SECONDARY_RISKS),
            "increase_3600_only_sufficient": INCREASE_3600_ONLY_SUFFICIENT,
            "lower_timeout_elsewhere": LOWER_TIMEOUT_ELSEWHERE,
            "next_timeout_candidate_seconds": NEXT_TIMEOUT_CANDIDATE,
            "next_timeout_justification": NEXT_TIMEOUT_JUSTIFICATION,
            "next_timeout_confidence": NEXT_TIMEOUT_CONFIDENCE,
            "recommendation_confidence": RECOMMENDATION_CONFIDENCE,
            "next_step": NEXT_STEP,
            "new_anthropic_call_authorized": NEW_ANTHROPIC_CALL_AUTHORIZED,
        },
        "provider_continuation": PROVIDER_MAY_HAVE_CONTINUED,
        "request_id_recoverable": REQUEST_ID_RECOVERABLE,
        "cost_meaning": COST_MEANS,
        "canary_comparison": canary_comparison(),
        "observability_gaps": observability_gaps(),
        "clock": {
            "latency_uses_monotonic": True,
            "timeout_enforced_by": "requests/urllib3",
            "recommend_monotonic_for_future_elapsed": True,
        },
        "streaming_option": {
            "implemented": False,
            "would_reset_read_timeout_if_chunks_arrive": "LIKELY",
            "partial_response_preservation": "UNKNOWN",
            "structured_output_compatibility": "UNKNOWN_REQUIRES_EXTERNAL_VERIFICATION",
        },
        "async_batch_option": "EXTERNAL_VERIFICATION_REQUIRED",
        "network": dict(_EMPTY_NETWORK),
        "engine_generate": 0,
    }
    return payload


def diagnostic_sha256(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(dict(payload), ensure_ascii=False, indent=2) + "\n"
    return content_hash(encoded)


def build_deterministic_audit(
    *,
    failed_run: Mapping[str, Any] | None = None,
) -> tuple[dict[str, Any], str, str]:
    first = build_timeout_root_cause_audit(failed_run=failed_run)
    second = build_timeout_root_cause_audit(failed_run=failed_run)
    sha1 = diagnostic_sha256(first)
    sha2 = diagnostic_sha256(second)
    if sha1 != sha2:
        raise RuntimeError("Diagnostic 3B.5 non déterministe : SHA run1 ≠ run2.")
    return first, sha1, sha2


def assert_offline_package() -> None:
    hits = package_calls_generate_or_post()
    if hits:
        raise RuntimeError("Chemin réseau/generate interdit dans l'audit : " + ", ".join(hits))
    if not production_timeout_unchanged():
        raise RuntimeError("Timeout de production modifié pendant l'audit.")
    if not anthropic_payload_is_non_streaming():
        raise RuntimeError("Payload Anthropic inattendu : champ stream présent.")
    if package_dir_imports_forbidden():
        raise RuntimeError("Import interdit dans le package d'audit.")


def package_dir_imports_forbidden() -> bool:
    root = Path(__file__).resolve().parent
    forbidden = {
        "requests",
        "urllib",
        "httpx",
        "openai",
        "anthropic",
    }
    for path in root.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = {alias.name.split(".")[0] for alias in node.names}
                if names & forbidden:
                    return True
            if isinstance(node, ast.ImportFrom) and node.module:
                top = node.module.split(".")[0]
                if top in forbidden:
                    return True
    return False


def assert_source_map_absent(
    project_name: str,
    *,
    sortie_dir: Path | None = None,
) -> None:
    path = source_map_path(project_name, sortie_dir=sortie_dir)
    if path.exists():
        raise RuntimeError(f"source_map.json ne doit pas exister : {path}")


def audit_dir_for(project_name: str, *, sortie_dir: Path | None = None) -> Path:
    return audit_dir(project_name, sortie_dir=sortie_dir)
