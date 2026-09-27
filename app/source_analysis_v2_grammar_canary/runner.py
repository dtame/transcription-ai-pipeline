"""
Runner canary V2 grammar + thinking-config.

Défaut : dry-run, 0 POST. Réel : --execute-real + scope exact.
Une tentative. Pas de retry. STOP obligatoire.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.ai.errors import AIError, AIStructuredOutputError
from app.ai.provider_forensics import (
    current_http_envelope,
    persist_error_forensics,
    persist_interrupt_forensics,
    persist_provider_forensics,
    provider_forensic_scope,
)
from app.ai.structured_forensics import persist_structured_output_forensics
from app.source_analysis.errors import MaxRealCallsExceededError
from app.source_analysis_v2_grammar_canary.constants import (
    AUTHORIZATION_SCOPE,
    CANARY_CONNECT_TIMEOUT_SECONDS,
    CANARY_MAX_OUTPUT_TOKENS,
    CANARY_READ_TIMEOUT_SECONDS,
    CANARY_VERSION,
    CANARY_WINDOW_ID,
    MAX_ANTHROPIC_POST,
    MAX_ATTEMPTS,
    MAX_ENGINE_GENERATE,
    MODE,
    MODEL,
    PHASE,
    PROJECT_NAME,
    PROVIDER,
    SCHEMA_VERSION,
    SEMANTIC_TRANSPORT_VERSION_V2,
    THINKING_CONTRACT,
    THINKING_MODE,
    WINDOW_ANALYSIS_PROMPT_VERSION_V12,
)
from app.source_analysis_v2_grammar_canary.costing import actual_cost
from app.source_analysis_v2_grammar_canary.engine import (
    CountingAnthropicEngine,
    build_real_canary_engine,
    credential_available,
    describe_engine,
)
from app.source_analysis_v2_grammar_canary.facts import historical_freeze
from app.source_analysis_v2_grammar_canary.fixture import build_synthetic_fixture
from app.source_analysis_v2_grammar_canary.guard import (
    GrammarCanaryError,
    OneShotCallGuard,
    validate_authorization_scope,
)
from app.source_analysis_v2_grammar_canary.paths import (
    canary_lock_path,
    canary_windows_root,
)
from app.source_analysis_v2_grammar_canary.payload import build_audited_request
from app.source_analysis_v2_grammar_canary.validate import interpret_canary_response

@dataclass
class CanaryRunResult:
    mode: str
    project_name: str
    authorization_scope: str
    accepted: bool = False
    error: str | None = None
    engine_generate_attempts: int = 0
    anthropic_post_attempts: int = 0
    dry_run: dict[str, Any] = field(default_factory=dict)
    execution: dict[str, Any] = field(default_factory=dict)
    payload_audit: dict[str, Any] = field(default_factory=dict)
    schema_metrics: dict[str, Any] = field(default_factory=dict)
    freeze: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "phase": PHASE,
            "mode": self.mode,
            "project_name": self.project_name,
            "authorization_scope": self.authorization_scope,
            "accepted": self.accepted,
            "error": self.error,
            "engine_generate_attempts": self.engine_generate_attempts,
            "anthropic_post_attempts": self.anthropic_post_attempts,
            "dry_run": self.dry_run,
            "execution": self.execution,
            "payload_audit": self.payload_audit,
            "schema_metrics": self.schema_metrics,
            "freeze": self.freeze,
        }


def _consume_lock(project_name: str, *, sortie_dir: Path | None) -> None:
    path = canary_lock_path(project_name, sortie_dir=sortie_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise GrammarCanaryError(
            "Canary real-call lock already present — authorization consumed. "
            "NO RETRY."
        )
    path.write_text(
        f"{PHASE}\n{AUTHORIZATION_SCOPE}\nconsumed=1\n",
        encoding="utf-8",
    )


def dry_run_canary(
    project_name: str = PROJECT_NAME,
    *,
    authorization_scope: str = AUTHORIZATION_SCOPE,
    sortie_dir: Path | None = None,
) -> dict[str, Any]:
    validate_authorization_scope(authorization_scope)
    fixture = build_synthetic_fixture()
    built = build_audited_request(fixture)
    freeze = historical_freeze(project_name, sortie_dir=sortie_dir)
    audit = built["audit"]
    return {
        "mode": "DRY_RUN",
        "authorization_scope": authorization_scope,
        "canary_version": CANARY_VERSION,
        "phase": PHASE,
        "runner_mode": MODE,
        "provider": PROVIDER,
        "model": MODEL,
        "thinking_mode": THINKING_MODE,
        "thinking_contract": THINKING_CONTRACT,
        "effort": None,
        "prompt_version": WINDOW_ANALYSIS_PROMPT_VERSION_V12,
        "transport": SEMANTIC_TRANSPORT_VERSION_V2,
        "max_output_tokens": CANARY_MAX_OUTPUT_TOKENS,
        "connect_timeout_seconds": CANARY_CONNECT_TIMEOUT_SECONDS,
        "read_timeout_seconds": CANARY_READ_TIMEOUT_SECONDS,
        "max_attempts": MAX_ATTEMPTS,
        "max_engine_generate": MAX_ENGINE_GENERATE,
        "max_anthropic_post": MAX_ANTHROPIC_POST,
        "retry": False,
        "fallback": False,
        "auto_continue": False,
        "request_identity": audit["request_identity"],
        "schema_hash": audit["raw_schema_hash"],
        "adapted_schema_hash": audit["schema_hash"],
        "synthetic_fixture_hash": audit["synthetic_input_hash"],
        "wrapper_hash": audit["wrapper_hash"],
        "payload_audit": audit,
        "schema_metrics": built["schema_metrics"],
        "fixture": fixture.to_safe_dict(),
        "credential_available": credential_available(),
        "credential_secret_printed": False,
        "engine_generate": False,
        "actual_real_provider_calls": 0,
        "anthropic_post_attempts": 0,
        "freeze": freeze,
        "secrets_included": False,
        "pastoral_content_sent": False,
    }


def _classify(
    *,
    generate_attempts: int,
    post_attempts: int,
    http_success: bool | None,
    structured: str,
    decoder: str,
    validator: str,
    deferred: list[str],
    capacity: bool,
    pastoral: bool,
    isolated: bool,
    error: str | None,
) -> str:
    if pastoral or generate_attempts > 1 or post_attempts > 1 or not isolated:
        return "FAIL"
    if error and not http_success:
        return "FAIL"
    if structured != "PASS" or decoder != "PASS" or validator != "PASS":
        if http_success:
            return "PARTIAL"
        return "FAIL"
    if deferred or capacity:
        return "PARTIAL" if http_success else "FAIL"
    if generate_attempts != 1:
        return "FAIL"
    if post_attempts > 1:
        return "FAIL"
    return "PASS"


def run_grammar_thinking_canary(
    project_name: str = PROJECT_NAME,
    *,
    dry_run: bool = True,
    execute_real: bool = False,
    authorization_scope: str | None = None,
    allow_real_provider: bool = False,
    engine=None,
    sortie_dir: Path | None = None,
    write_artifacts: bool = False,
) -> CanaryRunResult:
    result = CanaryRunResult(
        mode="DRY_RUN" if (dry_run or not execute_real) else "EXECUTE",
        project_name=project_name,
        authorization_scope=str(authorization_scope or ""),
    )
    try:
        scope = validate_authorization_scope(authorization_scope)
        result.authorization_scope = scope
    except GrammarCanaryError as exc:
        result.error = str(exc)
        result.mode = "REJECTED"
        return result

    if execute_real and dry_run:
        result.error = "--dry-run and --execute-real are exclusive."
        result.mode = "REJECTED"
        return result

    try:
        dry = dry_run_canary(
            project_name,
            authorization_scope=scope,
            sortie_dir=sortie_dir,
        )
    except GrammarCanaryError as exc:
        result.error = str(exc)
        result.mode = "REJECTED"
        return result

    result.dry_run = dry
    result.payload_audit = dry["payload_audit"]
    result.schema_metrics = dry["schema_metrics"]
    result.freeze = dry["freeze"]
    result.accepted = True

    if dry_run or not execute_real:
        return result

    if engine is None and not allow_real_provider:
        result.accepted = False
        result.error = "exécution réelle refusée : allow_real_provider=false."
        result.mode = "REJECTED"
        return result

    if engine is None:
        try:
            engine = build_real_canary_engine()
        except GrammarCanaryError as exc:
            result.accepted = False
            result.error = str(exc)
            result.mode = "REJECTED"
            return result

    fixture = build_synthetic_fixture()
    built = build_audited_request(fixture)
    request = built["request"]
    identity = built["audit"]["request_identity"]
    forensic_root = canary_windows_root(project_name, sortie_dir=sortie_dir)
    forensic_root.mkdir(parents=True, exist_ok=True)
    guard = OneShotCallGuard(max_calls=MAX_ENGINE_GENERATE)
    forensic_path = None
    http_meta: dict[str, Any] = {}
    validation: dict[str, Any] = {}
    response_meta: dict[str, Any] = {}
    error_text: str | None = None
    http_success: bool | None = None

    if isinstance(engine, CountingAnthropicEngine):
        try:
            _consume_lock(project_name, sortie_dir=sortie_dir)
        except GrammarCanaryError as exc:
            result.accepted = False
            result.error = str(exc)
            result.mode = "REJECTED"
            return result

    try:
        with provider_forensic_scope(
            windows_root=forensic_root,
            window_id=CANARY_WINDOW_ID,
            analysis_signature=identity,
            provider=PROVIDER,
            model=MODEL,
        ):
            try:
                response = guard.guarded_generate(engine, request)
            except KeyboardInterrupt:
                persist_interrupt_forensics()
                raise
            except AIStructuredOutputError as exc:
                persist_structured_output_forensics(
                    error=exc,
                    windows_root=forensic_root,
                    window_id=CANARY_WINDOW_ID,
                    analysis_signature=identity,
                    provider=getattr(getattr(exc, "response", None), "provider", None),
                    model=getattr(getattr(exc, "response", None), "model", None) or MODEL,
                    stage=request.stage,
                )
                persist_error_forensics(
                    exc,
                    windows_root=forensic_root,
                    window_id=CANARY_WINDOW_ID,
                    analysis_signature=identity,
                )
                envelope = getattr(exc, "http_envelope", None) or current_http_envelope()
                if envelope is not None:
                    http_meta = envelope.compact_metadata()
                    forensic_path = envelope.forensic_path
                    http_success = envelope.http_success
                attached = getattr(exc, "response", None)
                if attached is not None:
                    response_meta = attached.to_dict()
                    validation = interpret_canary_response(
                        None,
                        window=fixture.window,
                        raw_text=attached.text,
                    )
                error_text = str(exc)
                response = None
            except AIError as exc:
                persist_error_forensics(
                    exc,
                    windows_root=forensic_root,
                    window_id=CANARY_WINDOW_ID,
                    analysis_signature=identity,
                )
                envelope = getattr(exc, "http_envelope", None) or current_http_envelope()
                if envelope is not None:
                    http_meta = envelope.compact_metadata()
                    forensic_path = envelope.forensic_path
                    http_success = envelope.http_success
                error_text = str(exc)
                response = None
            except MaxRealCallsExceededError as exc:
                error_text = str(exc)
                response = None
            else:
                envelope = current_http_envelope() or getattr(response, "http_envelope", None)
                if envelope is None and isinstance(getattr(response, "metadata", None), dict):
                    http_meta = dict(response.metadata.get("provider_http") or {})
                    http_success = http_meta.get("http_success")
                if envelope is not None:
                    persist_provider_forensics(envelope)
                    http_meta = envelope.compact_metadata()
                    forensic_path = envelope.forensic_path
                    http_success = envelope.http_success
                response_meta = response.to_dict()
                validation = interpret_canary_response(
                    response.parsed if isinstance(response.parsed, dict) else None,
                    window=fixture.window,
                    raw_text=response.text,
                )
    except KeyboardInterrupt:
        result.error = "KeyboardInterrupt"
        result.engine_generate_attempts = guard.generate_attempts
        result.anthropic_post_attempts = int(getattr(engine, "post_attempts", 0) or 0)
        return result

    post_attempts = int(getattr(engine, "post_attempts", 0) or 0)
    if post_attempts == 0 and isinstance(engine, CountingAnthropicEngine):
        post_attempts = engine.post_attempts
    if post_attempts == 0 and allow_real_provider and isinstance(engine, CountingAnthropicEngine):
        post_attempts = engine.post_attempts

    result.engine_generate_attempts = guard.generate_attempts
    result.anthropic_post_attempts = post_attempts
    thinking_tokens = response_meta.get("thinking_tokens") if response_meta else None
    if thinking_tokens is None and http_meta.get("usage"):
        usage = http_meta["usage"]
        details = usage.get("output_tokens_details") if isinstance(usage, dict) else None
        if isinstance(details, dict) and "thinking_tokens" in details:
            thinking_tokens = details.get("thinking_tokens")
        elif isinstance(usage, dict) and "thinking_tokens" in usage:
            thinking_tokens = usage.get("thinking_tokens")

    input_tokens = response_meta.get("input_tokens")
    output_tokens = response_meta.get("output_tokens")
    if input_tokens is None:
        input_tokens = http_meta.get("input_tokens")
    if output_tokens is None:
        output_tokens = http_meta.get("output_tokens")

    isolated = True
    cost = actual_cost(input_tokens=input_tokens, output_tokens=output_tokens)
    structured = validation.get("structured_parse", "FAIL")
    decoder = validation.get("v2_decoder", "FAIL")
    validator = validation.get("v2_validator", "FAIL")
    deferred = list(validation.get("deferred_kinds") or [])
    capacity = bool(validation.get("capacity_signal"))
    grammar_accepted = "YES" if http_success else "NO"
    thinking_accepted = "YES" if http_success else "NO"
    if error_text and http_success is not True:
        grammar_accepted = "NO"
        thinking_accepted = "NO"

    verdict = _classify(
        generate_attempts=guard.generate_attempts,
        post_attempts=post_attempts,
        http_success=http_success,
        structured=structured,
        decoder=decoder,
        validator=validator,
        deferred=deferred,
        capacity=capacity,
        pastoral=False,
        isolated=isolated,
        error=error_text,
    )
    result.error = error_text
    result.execution = {
        "result": verdict,
        "authorization_scope": scope,
        "provider": PROVIDER,
        "model": MODEL,
        "thinking_mode": THINKING_MODE,
        "effort": "omitted",
        "manual_budget": "absent",
        "task_budget": "absent",
        "engine": describe_engine(engine),
        "engine_generate_attempts": guard.generate_attempts,
        "anthropic_post_attempts": post_attempts,
        "http": http_meta,
        "http_status": http_meta.get("http_status"),
        "request_id": http_meta.get("request_id") or response_meta.get("request_id"),
        "response_received": http_meta.get("response_received"),
        "http_success": http_success,
        "provider_elapsed_ms": http_meta.get("elapsed_ms") or response_meta.get("latency_ms"),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "thinking_tokens": thinking_tokens,
        "thinking_tokens_reported": thinking_tokens is not None,
        "finish_reason": response_meta.get("finish_reason") or http_meta.get("finish_reason"),
        "usage_source": response_meta.get("usage_source"),
        "airesponse_created": bool(response_meta),
        "structured_parse": structured,
        "v2_decoder": decoder,
        "v2_validator": validator,
        "kinds": validation.get("kinds") or [],
        "source_refs": validation.get("source_refs") or [],
        "deferred_kinds": deferred,
        "capacity_signal": "present" if capacity else "absent",
        "validation_errors": validation.get("errors") or [],
        "server_grammar_accepted": grammar_accepted,
        "thinking_disabled_accepted": thinking_accepted,
        "cost": cost,
        "forensic_path": forensic_path,
        "canary_artifact_isolated": isolated,
        "real_windows_ready": "0 / 7",
        "semantic_win001_authorized": False,
        "source_map": "NOT PUBLISHED",
        "production_default": "window-planner-v2.0",
        "phase_3b": "INCOMPLETE",
        "pastoral_content_sent": False,
        "retry": False,
        "transport_excerpt": _safe_transport(validation.get("transport")),
    }
    if write_artifacts:
        from app.source_analysis_v2_grammar_canary.writer import write_canary_artifacts

        write_canary_artifacts(project_name, result, sortie_dir=sortie_dir)
    return result


def _safe_transport(transport: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(transport, dict):
        return None
    records = transport.get("records") or []
    return {
        "theme": transport.get("theme"),
        "intent": transport.get("intent"),
        "record_count": len(records) if isinstance(records, list) else None,
        "kinds": [
            item.get("k")
            for item in records
            if isinstance(item, dict)
        ]
        if isinstance(records, list)
        else [],
    }


__all__ = [
    "CanaryRunResult",
    "dry_run_canary",
    "run_grammar_thinking_canary",
]
