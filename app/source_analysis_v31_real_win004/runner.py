"""
Runner A.27 — un appel Anthropic WIN004 maximum, prompt 1.4.0, v3.1-local-lite.

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
from app.source_analysis_v31_real_win004.canonical import reconstruct_mixed_with_a21
from app.source_analysis_v31_real_win004.comparison import (
    classify_subtype_failure,
    compare_with_a22_a24,
)
from app.source_analysis_v31_real_win004.constants import (
    AUTHORIZATION_SCOPE,
    CONNECT_TIMEOUT_SECONDS,
    EXPECTED_ANALYSIS_SIGNATURE,
    MAX_ANTHROPIC_POST,
    MAX_ATTEMPTS,
    MAX_ENGINE_GENERATE,
    MAX_OUTPUT_TOKENS,
    MODE,
    MODEL,
    PHASE,
    PROJECT_NAME,
    PROMPT_VERSION,
    PROVIDER,
    READ_TIMEOUT_SECONDS,
    SCHEMA_VERSION,
    SUBTYPE_FAILURE_CLASS_IF_PASS,
    THINKING_CONTRACT,
    THINKING_MODE,
    TRANSPORT_VERSION,
    WINDOW_ID,
)
from app.source_analysis_v31_real_win004.costing import actual_cost
from app.source_analysis_v31_real_win004.engine import (
    CountingAnthropicEngine,
    build_real_engine,
    credential_available,
    describe_engine,
)
from app.source_analysis_v31_real_win004.guard import (
    LocalLiteWin004Error,
    OneShotCallGuard,
    validate_authorization_scope,
    validate_target,
)
from app.source_analysis_v31_real_win004.metrics import (
    output_size_metrics,
    record_metrics,
    src_metrics,
)
from app.source_analysis_v31_real_win004.paths import (
    a27_lock_path,
    forensic_windows_root,
)
from app.source_analysis_v31_real_win004.preflight import run_preflight
from app.source_analysis_v31_real_win004.review import review_transport
from app.source_analysis_v31_real_win004.validate import interpret_local_lite_response


@dataclass
class LocalLiteWin004Result:
    mode: str
    project_name: str
    authorization_scope: str
    accepted: bool = False
    error: str | None = None
    blocked_precall: bool = False
    engine_generate_attempts: int = 0
    anthropic_post_attempts: int = 0
    preflight: dict[str, Any] = field(default_factory=dict)
    execution: dict[str, Any] = field(default_factory=dict)
    review: dict[str, Any] = field(default_factory=dict)
    comparison: dict[str, Any] = field(default_factory=dict)
    handles: dict[str, Any] = field(default_factory=dict)
    src_audit: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    canonical: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "phase": PHASE,
            "mode": self.mode,
            "project_name": self.project_name,
            "authorization_scope": self.authorization_scope,
            "accepted": self.accepted,
            "error": self.error,
            "blocked_precall": self.blocked_precall,
            "engine_generate_attempts": self.engine_generate_attempts,
            "anthropic_post_attempts": self.anthropic_post_attempts,
            "preflight": _safe_preflight(self.preflight),
            "execution": self.execution,
            "review": self.review,
            "comparison": self.comparison,
            "handles": self.handles,
            "src_audit": self.src_audit,
            "metadata": self.metadata,
            "canonical": self.canonical,
        }


def _safe_preflight(preflight: dict[str, Any]) -> dict[str, Any]:
    payload = dict(preflight)
    payload.pop("request", None)
    payload.pop("window_obj", None)
    payload.pop("transcript_obj", None)
    return payload


def _consume_lock(project_name: str, *, sortie_dir: Path | None) -> None:
    path = a27_lock_path(project_name, sortie_dir=sortie_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise LocalLiteWin004Error(
            "A.27 real-call lock already present — authorization consumed. NO RETRY."
        )
    path.write_text(
        f"{PHASE}\n{AUTHORIZATION_SCOPE}\n{WINDOW_ID}\nconsumed=1\n",
        encoding="utf-8",
    )


def _classify(
    *,
    generate_attempts: int,
    post_attempts: int,
    http_success: bool | None,
    finish_reason: str | None,
    structured: str,
    decoder: str,
    registry: str,
    resolution: str,
    validator: str,
    capacity: bool,
    handle_ok: bool,
    numeric: bool,
    src_ok: bool,
    metadata_ok: bool,
    leakage: int,
    old_v3: int,
    invalid_importance: int,
    defect: str | None,
    quality: str | None,
    canonical_ok: bool,
    mixed_ok: bool,
    contamination: int,
    unauthorized: bool,
    error: str | None,
    tests_failed: bool,
) -> str:
    if unauthorized or generate_attempts > 1 or post_attempts > 1:
        return "FAIL"
    if tests_failed:
        return "FAIL"
    if generate_attempts == 0 and error:
        return "BLOCKED_PRECALL"
    if error and not http_success:
        return "FAIL"
    if finish_reason in {"max_tokens", "length"}:
        return "FAIL"
    pipeline = (structured, decoder, registry, resolution, validator)
    if any(status != "PASS" for status in pipeline):
        return "FAIL"
    if not src_ok or not metadata_ok or leakage > 0 or old_v3 > 0 or invalid_importance > 0:
        return "FAIL"
    if capacity or not handle_ok or numeric:
        return "FAIL"
    if contamination > 0:
        return "FAIL"
    if defect == "PERSISTS":
        return "FAIL"
    if quality == "INADEQUATE":
        return "FAIL"
    if quality == "REVIEW_REQUIRED" or defect == "DIFFERENT_FAILURE":
        return "PARTIAL"
    if generate_attempts != 1:
        return "FAIL"
    if not canonical_ok or not mixed_ok:
        return "PARTIAL"
    if (
        quality == "ACCEPTABLE_FOR_LOCAL_EXTRACTION"
        and defect == SUBTYPE_FAILURE_CLASS_IF_PASS
        and canonical_ok
        and mixed_ok
    ):
        return "PASS"
    return "PARTIAL"


def run_local_lite_win004(
    project_name: str = PROJECT_NAME,
    *,
    dry_run: bool = True,
    execute_real: bool = False,
    authorization_scope: str | None = None,
    window_id: str | None = WINDOW_ID,
    allow_real_provider: bool = False,
    engine=None,
    sortie_dir: Path | None = None,
    artifact_sortie_dir: Path | None = None,
    write_artifacts: bool = False,
    tests: str | None = None,
) -> LocalLiteWin004Result:
    result = LocalLiteWin004Result(
        mode="DRY_RUN" if (dry_run or not execute_real) else "EXECUTE",
        project_name=project_name,
        authorization_scope=str(authorization_scope or ""),
    )
    try:
        scope = validate_authorization_scope(authorization_scope)
        validate_target(window_id)
        result.authorization_scope = scope
        preflight = run_preflight(
            project_name,
            authorization_scope=scope,
            window_id=window_id,
            sortie_dir=sortie_dir,
            artifact_sortie_dir=artifact_sortie_dir,
            tests=tests,
            engine=engine,
        )
    except LocalLiteWin004Error as exc:
        result.error = str(exc)
        result.mode = "BLOCKED_PRECALL"
        result.blocked_precall = True
        result.accepted = False
        return result

    result.preflight = preflight
    result.accepted = True
    if write_artifacts:
        from app.source_analysis_v31_real_win004.writer import write_preflight_artifact

        write_preflight_artifact(
            project_name,
            preflight,
            sortie_dir=artifact_sortie_dir if artifact_sortie_dir is not None else sortie_dir,
        )

    if dry_run or not execute_real:
        return result

    if execute_real and dry_run:
        result.error = "--dry-run and --execute-real are exclusive."
        result.mode = "REJECTED"
        result.accepted = False
        return result

    if engine is None and not allow_real_provider:
        result.accepted = False
        result.error = "exécution réelle refusée : allow_real_provider=false."
        result.mode = "REJECTED"
        return result

    if engine is None:
        if not credential_available():
            result.accepted = False
            result.blocked_precall = True
            result.error = (
                "Anthropic credential unavailable — BLOCKED_PRECALL. "
                "REAL PROVIDER CALLS = 0."
            )
            result.mode = "BLOCKED_PRECALL"
            return result
        try:
            engine = build_real_engine()
        except LocalLiteWin004Error as exc:
            result.accepted = False
            result.blocked_precall = True
            result.error = str(exc)
            result.mode = "BLOCKED_PRECALL"
            return result

    write_dir = artifact_sortie_dir if artifact_sortie_dir is not None else sortie_dir
    request = preflight["request"]
    window = preflight["window_obj"]
    transcript = preflight["transcript_obj"]
    identity = preflight["analysis_signature"]
    if identity != EXPECTED_ANALYSIS_SIGNATURE:
        result.accepted = False
        result.blocked_precall = True
        result.error = "Signature changed after preflight — STOP WITHOUT NETWORK."
        result.mode = "BLOCKED_PRECALL"
        return result

    forensic_root = forensic_windows_root(project_name, sortie_dir=write_dir)
    forensic_root.mkdir(parents=True, exist_ok=True)
    guard = OneShotCallGuard(max_calls=MAX_ENGINE_GENERATE)
    forensic_path = None
    http_meta: dict[str, Any] = {}
    validation: dict[str, Any] = {}
    response_meta: dict[str, Any] = {}
    error_text: str | None = None
    http_success: bool | None = None
    raw_text = ""

    if isinstance(engine, CountingAnthropicEngine):
        try:
            _consume_lock(project_name, sortie_dir=write_dir)
        except LocalLiteWin004Error as exc:
            result.accepted = False
            result.blocked_precall = True
            result.error = str(exc)
            result.mode = "BLOCKED_PRECALL"
            return result

    try:
        with provider_forensic_scope(
            windows_root=forensic_root,
            window_id=WINDOW_ID,
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
                    window_id=WINDOW_ID,
                    analysis_signature=identity,
                    provider=getattr(getattr(exc, "response", None), "provider", None),
                    model=getattr(getattr(exc, "response", None), "model", None) or MODEL,
                    stage=request.metadata.get("stage") if request.metadata else None,
                )
                persist_error_forensics(
                    exc,
                    windows_root=forensic_root,
                    window_id=WINDOW_ID,
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
                    raw_text = attached.text or ""
                    validation = interpret_local_lite_response(
                        None,
                        window=window,
                        raw_text=attached.text,
                    )
                error_text = str(exc)
                response = None
            except AIError as exc:
                persist_error_forensics(
                    exc,
                    windows_root=forensic_root,
                    window_id=WINDOW_ID,
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
                envelope = current_http_envelope() or getattr(
                    response, "http_envelope", None
                )
                if envelope is None and isinstance(getattr(response, "metadata", None), dict):
                    http_meta = dict(response.metadata.get("provider_http") or {})
                    http_success = http_meta.get("http_success")
                if envelope is not None:
                    persist_provider_forensics(envelope)
                    http_meta = envelope.compact_metadata()
                    forensic_path = envelope.forensic_path
                    http_success = envelope.http_success
                response_meta = response.to_dict()
                raw_text = response.text or ""
                validation = interpret_local_lite_response(
                    response.parsed if isinstance(response.parsed, dict) else None,
                    window=window,
                    raw_text=response.text,
                )
    except KeyboardInterrupt:
        result.error = "KeyboardInterrupt"
        result.engine_generate_attempts = guard.generate_attempts
        result.anthropic_post_attempts = int(getattr(engine, "post_attempts", 0) or 0)
        return result

    post_attempts = int(getattr(engine, "post_attempts", 0) or 0)
    result.engine_generate_attempts = guard.generate_attempts
    result.anthropic_post_attempts = post_attempts
    thinking_tokens = response_meta.get("thinking_tokens") if response_meta else None
    if thinking_tokens is None and isinstance(http_meta.get("usage"), dict):
        usage = http_meta["usage"]
        details = usage.get("output_tokens_details")
        if isinstance(details, dict) and "thinking_tokens" in details:
            thinking_tokens = details.get("thinking_tokens")
        elif "thinking_tokens" in usage:
            thinking_tokens = usage.get("thinking_tokens")
    input_tokens = response_meta.get("input_tokens")
    output_tokens = response_meta.get("output_tokens")
    if input_tokens is None:
        input_tokens = http_meta.get("input_tokens")
    if output_tokens is None:
        output_tokens = http_meta.get("output_tokens")
    finish_reason = response_meta.get("finish_reason") or http_meta.get("finish_reason")
    structured = validation.get("structured_parse", "FAIL")
    decoder = validation.get("v31_decoder", "FAIL")
    registry = validation.get("handle_registry", "FAIL")
    resolution = validation.get("handle_resolution", "FAIL")
    validator = validation.get("v31_validator", "FAIL")
    capacity = bool(validation.get("capacity_signal"))
    transport = validation.get("transport")
    handles = validation.get("handles") or {}
    handle_gate = validation.get("handle_gate") or {}
    src_audit = validation.get("src_audit") or {}
    src_forensic = validation.get("src_forensic") or {}
    metadata = validation.get("metadata") or {}
    rec = record_metrics(transport if isinstance(transport, dict) else None)
    src = src_metrics(transport if isinstance(transport, dict) else None, window)
    sizes = output_size_metrics(
        raw_text=raw_text,
        transport=transport if isinstance(transport, dict) else None,
        output_tokens=output_tokens,
        max_output=MAX_OUTPUT_TOKENS,
    )
    cost = actual_cost(input_tokens=input_tokens, output_tokens=output_tokens)
    local_est = preflight["local_input_estimate"]
    input_ratio = (
        round(float(input_tokens) / float(local_est), 6)
        if input_tokens and local_est
        else None
    )
    handle_ok = bool(handle_gate.get("handle_gate_pass"))
    numeric = handle_gate.get("numeric_link_regression") == "YES"
    src_ok = bool(src_forensic.get("src_success"))
    leakage = int(metadata.get("idea_subtype_leakage") or 0)
    old_v3 = int(metadata.get("old_v3_idea_shape") or 0)
    invalid_importance = int(metadata.get("invalid_importance") or 0)
    metadata_ok = bool(metadata.get("local_lite_metadata_pass"))
    technical_ok = (
        http_success is True
        and bool(response_meta)
        and finish_reason not in {"max_tokens", "length"}
        and structured == "PASS"
        and decoder == "PASS"
        and registry == "PASS"
        and resolution == "PASS"
        and validator == "PASS"
        and src_ok
        and metadata_ok
        and leakage == 0
        and old_v3 == 0
        and invalid_importance == 0
        and not capacity
        and handle_ok
        and not numeric
    )
    review: dict[str, Any] = {
        "performed": False,
        "semantic_quality": None,
        "thinking_disabled_local_extraction": None,
        "unsupported_content": None,
        "transport_valid": False,
    }
    if isinstance(transport, dict) or raw_text:
        review = review_transport(
            transport if isinstance(transport, dict) else None,
            window=window,
            transcript=transcript,
            capacity_signal=capacity,
            handle_gate_pass=handle_ok,
            technical_ok=technical_ok,
            src_audit=src_audit,
        )
        metadata = review.get("metadata") or metadata
        leakage = int(metadata.get("idea_subtype_leakage") or 0)
        old_v3 = int(metadata.get("old_v3_idea_shape") or 0)
        invalid_importance = int(metadata.get("invalid_importance") or 0)
        metadata_ok = bool(metadata.get("local_lite_metadata_pass"))
    defect = classify_subtype_failure(
        leakage=leakage,
        old_v3=old_v3,
        invalid_importance=invalid_importance,
        structured=structured,
        technical_ok=technical_ok,
    )
    canonical: dict[str, Any] = {}
    mixed_ok = False
    canonical_ok = False
    contamination = 0
    if technical_ok and isinstance(transport, dict):
        canonical = reconstruct_mixed_with_a21(
            transport,
            window,
            signature=identity,
            project_name=project_name,
            sortie_dir=sortie_dir,
        )
        win004 = canonical.get("win004") or {}
        canonical_ok = win004.get("idea_validation") == "PASS"
        mixed_ok = canonical.get("mixed_compatibility") == "PASS"
        contamination = int(win004.get("importance_to_kind_contamination") or 0)
    execution = {
        "result": None,
        "authorization_scope": scope,
        "authorized_target": WINDOW_ID,
        "provider": PROVIDER,
        "model": MODEL,
        "thinking_mode": THINKING_MODE,
        "thinking_contract": THINKING_CONTRACT,
        "effort": "omitted",
        "engine": describe_engine(engine),
        "engine_generate_attempts": guard.generate_attempts,
        "anthropic_post_attempts": post_attempts,
        "http": http_meta,
        "http_status": http_meta.get("http_status"),
        "request_id": http_meta.get("request_id") or response_meta.get("request_id"),
        "response_received": http_meta.get("response_received"),
        "http_success": http_success,
        "provider_elapsed_ms": http_meta.get("elapsed_ms")
        or response_meta.get("latency_ms"),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "thinking_tokens": thinking_tokens,
        "thinking_tokens_reported": thinking_tokens is not None,
        "thinking_unexpected": bool(
            thinking_tokens not in {0, None} and int(thinking_tokens or 0) > 0
        ),
        "finish_reason": finish_reason,
        "usage_source": response_meta.get("usage_source"),
        "airesponse_created": bool(response_meta),
        "structured_parse": structured,
        "v31_decoder": decoder,
        "v3_decoder": decoder,
        "handle_registry": registry,
        "handle_resolution": resolution,
        "v31_validator": validator,
        "v3_validator": validator,
        "capacity_signal": "present" if capacity else "absent",
        "validation_errors": validation.get("errors") or [],
        "records": rec,
        "handles": handles,
        "handle_gate": handle_gate,
        "src": src,
        "src_audit": src_audit,
        "src_forensic": src_forensic,
        "metadata": metadata,
        "inventory": validation.get("inventory") or {},
        "output_size": sizes,
        "output_vs_32000": (
            round(float(output_tokens) / float(MAX_OUTPUT_TOKENS), 4)
            if output_tokens is not None
            else None
        ),
        "local_input_estimate": local_est,
        "actual_provider_input": input_tokens,
        "input_ratio": input_ratio,
        "cost": cost,
        "forensic_path": forensic_path,
        "prompt_version": PROMPT_VERSION,
        "transport": TRANSPORT_VERSION,
        "analysis_signature": identity,
        "cache": preflight["cache"]["status"],
        "real_windows_ready": "1 / 7",
        "other_windows_authorized": False,
        "win001_authorized": False,
        "consolidation_authorized": False,
        "source_map": "NOT PUBLISHED",
        "production_default": "window-planner-v2.0",
        "v3_production_activation": False,
        "v31_production_activation": False,
        "v21_small_production_activation": False,
        "phase_3b": "INCOMPLETE",
        "retry": False,
        "connect_timeout_seconds": CONNECT_TIMEOUT_SECONDS,
        "read_timeout_seconds": READ_TIMEOUT_SECONDS,
        "max_attempts": MAX_ATTEMPTS,
        "technical_ok": technical_ok,
        "idea_subtype_leakage": leakage,
        "old_v3_idea_shape": old_v3,
        "invalid_importance": invalid_importance,
        "a22_a24_subtype_failure_class": defect,
        "canonical": canonical,
        "importance_to_kind_contamination": contamination,
        "mixed_compatibility": canonical.get("mixed_compatibility"),
    }
    comparison = compare_with_a22_a24(
        execution=execution,
        transport=transport if isinstance(transport, dict) else None,
        review=review,
        src_forensic=src_forensic,
    )
    verdict = _classify(
        generate_attempts=guard.generate_attempts,
        post_attempts=post_attempts,
        http_success=http_success,
        finish_reason=finish_reason,
        structured=structured,
        decoder=decoder,
        registry=registry,
        resolution=resolution,
        validator=validator,
        capacity=capacity,
        handle_ok=handle_ok,
        numeric=numeric,
        src_ok=src_ok,
        metadata_ok=metadata_ok,
        leakage=leakage,
        old_v3=old_v3,
        invalid_importance=invalid_importance,
        defect=defect,
        quality=review.get("semantic_quality"),
        canonical_ok=canonical_ok,
        mixed_ok=mixed_ok,
        contamination=contamination,
        unauthorized=False,
        error=error_text,
        tests_failed=False,
    )
    execution["result"] = verdict
    execution["semantic_quality"] = review.get("semantic_quality")
    execution["unsupported_content"] = review.get("unsupported_content")
    execution["thinking_disabled_local_extraction"] = review.get(
        "thinking_disabled_local_extraction"
    )
    execution["a22_a24_subtype_failure_class"] = comparison.get(
        "a22_a24_subtype_failure_class"
    )
    if (
        technical_ok
        and verdict == "PASS"
        and review.get("semantic_quality") == "ACCEPTABLE_FOR_LOCAL_EXTRACTION"
        and canonical_ok
        and mixed_ok
    ):
        execution["real_windows_ready"] = "2 / 7"
    else:
        execution["real_windows_ready"] = "1 / 7"
    result.error = error_text
    result.execution = execution
    result.review = review
    result.comparison = comparison
    result.handles = handles
    result.src_audit = src_audit
    result.metadata = metadata
    result.canonical = canonical
    if write_artifacts:
        from app.source_analysis_v31_real_win004.writer import write_execution_artifacts

        write_execution_artifacts(
            project_name,
            result,
            transport=transport if isinstance(transport, dict) else None,
            sortie_dir=write_dir,
        )
    return result


__all__ = ["LocalLiteWin004Result", "run_local_lite_win004"]
