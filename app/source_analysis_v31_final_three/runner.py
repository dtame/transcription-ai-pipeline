"""
Runner A.31 — trois fenêtres finales, séquentiel, stop-on-first-failure.

Défaut : dry-run, 0 POST. Réel : --execute-real + scope exact.
Une tentative par fenêtre. Pas de retry. STOP obligatoire.
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
from app.source_analysis_v31_final_three.canonical import reconstruct_mixed
from app.source_analysis_v31_final_three.constants import (
    AUTHORIZATION_SCOPE,
    CONNECT_TIMEOUT_SECONDS,
    EXECUTION_ORDER,
    MAX_ANTHROPIC_POST,
    MAX_ATTEMPTS,
    MAX_ENGINE_GENERATE,
    MAX_ENGINE_GENERATE_PER_WINDOW,
    MAX_OUTPUT_TOKENS,
    MODE,
    MODEL,
    PHASE,
    PROJECT_NAME,
    PROMPT_VERSION,
    PROVIDER,
    READ_TIMEOUT_SECONDS,
    READY_BEFORE_COUNT,
    SCHEMA_VERSION,
    SUBTYPE_FAILURE_CLASS_IF_PASS,
    THINKING_CONTRACT,
    THINKING_MODE,
    TOTAL_WINDOWS,
    TRANSPORT_VERSION,
)
from app.source_analysis_v31_final_three.engine import (
    SequentialAnthropicEngine,
    build_real_engine,
    credential_available,
    describe_engine,
)
from app.source_analysis_v31_final_three.guard import (
    FinalThreeError,
    OneShotCallGuard,
    PhaseCallGuard,
    validate_authorization_scope,
    validate_target,
)
from app.source_analysis_v31_final_three.lengths import audit_length_policy
from app.source_analysis_v31_final_three.paths import (
    a31_lock_path,
    forensic_windows_root,
)
from app.source_analysis_v31_final_three.payload import build_audited_request
from app.source_analysis_v31_final_three.preflight import run_preflight
from app.source_analysis_v31_real_win004.comparison import classify_subtype_failure
from app.source_analysis_v31_real_win004.costing import actual_cost
from app.source_analysis_v31_real_win004.metrics import (
    output_size_metrics,
    record_metrics,
    src_metrics,
)
from app.source_analysis_v31_real_win004.validate import interpret_local_lite_response
from app.source_analysis_v31_remaining_windows.review import review_transport


@dataclass
class FinalThreeResult:
    mode: str
    project_name: str
    authorization_scope: str
    accepted: bool = False
    error: str | None = None
    blocked_precall: bool = False
    engine_generate_attempts: int = 0
    anthropic_post_attempts: int = 0
    preflight: dict[str, Any] = field(default_factory=dict)
    windows: dict[str, dict[str, Any]] = field(default_factory=dict)
    stopped_at: str | None = None
    stop_reason: str | None = None
    phase_result: str | None = None
    ready_after_count: int = READY_BEFORE_COUNT
    relation_cross: dict[str, Any] = field(default_factory=dict)
    freeze_candidate: str = "NO"
    test_delta: dict[str, Any] = field(default_factory=dict)

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
            "windows": self.windows,
            "stopped_at": self.stopped_at,
            "stop_reason": self.stop_reason,
            "phase_result": self.phase_result,
            "ready_after_count": self.ready_after_count,
            "relation_cross": self.relation_cross,
            "freeze_candidate": self.freeze_candidate,
            "test_delta": self.test_delta,
        }


def _safe_preflight(preflight: dict[str, Any]) -> dict[str, Any]:
    payload = dict(preflight)
    payload.pop("bundle", None)
    payload.pop("verified", None)
    payload.pop("request", None)
    payload.pop("window_obj", None)
    payload.pop("transcript_obj", None)
    return payload


def _write_lock(
    project_name: str,
    *,
    sortie_dir: Path | None,
    consumed: list[str],
) -> None:
    path = a31_lock_path(project_name, sortie_dir=sortie_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"{PHASE}\n{AUTHORIZATION_SCOPE}\nconsumed={','.join(consumed)}\n",
        encoding="utf-8",
    )


def _classify_window(
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
    length_ok: bool,
    leakage: int,
    old_v3: int,
    invalid_importance: int,
    defect: str | None,
    quality: str | None,
    canonical_ok: bool,
    mixed_ok: bool,
    contamination: int,
    error: str | None,
) -> str:
    if generate_attempts > 1 or post_attempts > 1:
        return "FAIL"
    if generate_attempts == 0 and error:
        return "BLOCKED_PRECALL"
    if error and http_success is False:
        return "FAIL"
    if finish_reason in {"max_tokens", "length"}:
        return "FAIL"
    pipeline = (structured, decoder, registry, resolution, validator)
    if any(status != "PASS" for status in pipeline):
        return "FAIL"
    if not length_ok:
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


def _provider_ok(http_success: bool | None, response_meta: dict[str, Any], finish: str | None) -> bool:
    if http_success is True:
        return True
    if http_success is False:
        return False
    return bool(response_meta) and finish not in {"max_tokens", "length"}


def execute_one_window(
    *,
    window_id: str,
    project_name: str,
    preflight: dict[str, Any],
    engine,
    phase_guard: PhaseCallGuard,
    write_dir: Path | None,
    sortie_dir: Path | None,
) -> dict[str, Any]:
    validate_target(window_id)
    bundle = preflight["bundle"]
    window = bundle["windows"][window_id]
    transcript = bundle["transcript"]
    identity = preflight["verified"][window_id]["analysis_signature"]
    expected = preflight["windows"][window_id]["analysis_signature"]
    if identity != expected:
        raise FinalThreeError(
            f"{window_id} signature changed after preflight — STOP WITHOUT NETWORK."
        )
    built = build_audited_request(window, transcript)
    request = built["request"]
    forensic_root = forensic_windows_root(project_name, sortie_dir=write_dir)
    forensic_root.mkdir(parents=True, exist_ok=True)
    window_guard = OneShotCallGuard(max_calls=MAX_ENGINE_GENERATE_PER_WINDOW)
    forensic_path = None
    http_meta: dict[str, Any] = {}
    validation: dict[str, Any] = {}
    response_meta: dict[str, Any] = {}
    error_text: str | None = None
    http_success: bool | None = None
    raw_text = ""
    posts_before = int(getattr(engine, "post_attempts", 0) or 0)

    phase_guard.begin(window_id)
    try:
        with provider_forensic_scope(
            windows_root=forensic_root,
            window_id=window_id,
            analysis_signature=identity,
            provider=PROVIDER,
            model=MODEL,
        ):
            try:
                response = window_guard.guarded_generate(engine, request)
            except KeyboardInterrupt:
                persist_interrupt_forensics()
                raise
            except AIStructuredOutputError as exc:
                persist_structured_output_forensics(
                    error=exc,
                    windows_root=forensic_root,
                    window_id=window_id,
                    analysis_signature=identity,
                    provider=getattr(getattr(exc, "response", None), "provider", None),
                    model=getattr(getattr(exc, "response", None), "model", None) or MODEL,
                    stage=request.metadata.get("stage") if request.metadata else None,
                )
                persist_error_forensics(
                    exc,
                    windows_root=forensic_root,
                    window_id=window_id,
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
                    window_id=window_id,
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
    finally:
        phase_guard.end()

    window_posts = int(getattr(engine, "post_attempts", 0) or 0) - posts_before
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
    length_source = transport if isinstance(transport, dict) else None
    if length_source is None and isinstance(response_meta.get("parsed"), dict):
        length_source = response_meta["parsed"]
    length_audit = audit_length_policy(length_source)
    length_ok = bool(length_audit.get("pass")) if length_source is not None else False
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
    local_est = preflight["windows"][window_id]["local_input_estimate"]
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
        _provider_ok(http_success, response_meta, finish_reason)
        and bool(response_meta)
        and finish_reason not in {"max_tokens", "length"}
        and structured == "PASS"
        and decoder == "PASS"
        and registry == "PASS"
        and resolution == "PASS"
        and validator == "PASS"
        and length_ok
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
        canonical = reconstruct_mixed(
            transport,
            window,
            signature=identity,
            project_name=project_name,
            sortie_dir=sortie_dir,
        )
        local = canonical.get("local") or {}
        canonical_ok = local.get("idea_validation") == "PASS"
        mixed_ok = canonical.get("mixed_compatibility") == "PASS"
        contamination = int(local.get("importance_to_kind_contamination") or 0)
    coverage = review.get("coverage") or {}
    verdict = _classify_window(
        generate_attempts=window_guard.generate_attempts,
        post_attempts=window_posts,
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
        length_ok=length_ok,
        leakage=leakage,
        old_v3=old_v3,
        invalid_importance=invalid_importance,
        defect=defect,
        quality=review.get("semantic_quality"),
        canonical_ok=canonical_ok,
        mixed_ok=mixed_ok,
        contamination=contamination,
        error=error_text,
    )
    execution = {
        "result": verdict,
        "window_id": window_id,
        "authorization_scope": AUTHORIZATION_SCOPE,
        "authorized_target": window_id,
        "provider": PROVIDER,
        "model": MODEL,
        "thinking_mode": THINKING_MODE,
        "thinking_contract": THINKING_CONTRACT,
        "effort": "omitted",
        "engine": describe_engine(engine),
        "engine_generate_attempts": window_guard.generate_attempts,
        "anthropic_post_attempts": window_posts,
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
        "handle_registry": registry,
        "handle_resolution": resolution,
        "v31_validator": validator,
        "length_policy": "PASS" if length_ok else "FAIL",
        "length_audit": length_audit,
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
        "local_input_estimate": local_est,
        "actual_provider_input": input_tokens,
        "input_ratio": input_ratio,
        "cost": cost,
        "forensic_path": forensic_path,
        "prompt_version": PROMPT_VERSION,
        "transport": TRANSPORT_VERSION,
        "granularity_policy": preflight["windows"][window_id].get("granularity_policy"),
        "analysis_signature": identity,
        "cache": preflight["windows"][window_id]["cache"]["status"],
        "src_range": preflight["windows"][window_id]["src_range"],
        "owned_src_count": preflight["windows"][window_id]["owned_src_count"],
        "word_count": preflight["windows"][window_id]["word_count"],
        "win001_authorized": False,
        "win002_authorized": False,
        "win003_authorized": False,
        "win004_authorized": False,
        "consolidation_authorized": False,
        "source_map": "NOT PUBLISHED",
        "production_default": "window-planner-v2.0",
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
        "semantic_quality": review.get("semantic_quality"),
        "unsupported_content": review.get("unsupported_content"),
        "material_omissions": review.get("material_omissions"),
        "relation_quality_summary": review.get("relation_quality_summary"),
        "beginning": coverage.get("beginning"),
        "middle": coverage.get("middle"),
        "end": coverage.get("end"),
        "max_theme_length": length_audit.get("max_theme_length"),
        "max_idea_length": length_audit.get("max_idea_length"),
        "max_example_length": length_audit.get("max_example_length"),
    }
    return {
        "window_id": window_id,
        "result": verdict,
        "execution": execution,
        "review": review,
        "handles": handles,
        "src_audit": src_audit,
        "metadata": metadata,
        "length_audit": length_audit,
        "canonical": canonical,
        "transport": transport if isinstance(transport, dict) else None,
        "error": error_text,
        "engine_generate_attempts": window_guard.generate_attempts,
        "anthropic_post_attempts": window_posts,
    }


def run_final_three(
    project_name: str = PROJECT_NAME,
    *,
    dry_run: bool = True,
    execute_real: bool = False,
    authorization_scope: str | None = None,
    window_id: str | None = None,
    allow_real_provider: bool = False,
    engine=None,
    sortie_dir: Path | None = None,
    artifact_sortie_dir: Path | None = None,
    write_artifacts: bool = False,
    tests: str | None = None,
    max_windows: int | None = None,
    run_inter_window_tests: bool = False,
) -> FinalThreeResult:
    result = FinalThreeResult(
        mode="DRY_RUN" if (dry_run or not execute_real) else "EXECUTE",
        project_name=project_name,
        authorization_scope=str(authorization_scope or ""),
    )
    try:
        scope = validate_authorization_scope(authorization_scope)
        if window_id is not None:
            validate_target(window_id)
        result.authorization_scope = scope
        preflight = run_preflight(
            project_name,
            authorization_scope=scope,
            sortie_dir=sortie_dir,
            artifact_sortie_dir=artifact_sortie_dir,
            tests=tests,
            engine=engine,
        )
    except FinalThreeError as exc:
        result.error = str(exc)
        result.mode = "BLOCKED_PRECALL"
        result.blocked_precall = True
        result.accepted = False
        result.phase_result = "BLOCKED_PRECALL"
        result.stop_reason = str(exc)
        return result

    result.preflight = preflight
    result.accepted = True
    if write_artifacts:
        from app.source_analysis_v31_final_three.writer import write_preflight_artifact

        write_preflight_artifact(
            project_name,
            preflight,
            sortie_dir=artifact_sortie_dir if artifact_sortie_dir is not None else sortie_dir,
        )

    if dry_run or not execute_real:
        result.phase_result = "DRY_RUN"
        return result

    if engine is None and not allow_real_provider:
        result.accepted = False
        result.error = "exécution réelle refusée : allow_real_provider=false."
        result.mode = "REJECTED"
        result.phase_result = "BLOCKED_PRECALL"
        result.blocked_precall = True
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
            result.phase_result = "BLOCKED_PRECALL"
            return result
        try:
            engine = build_real_engine()
        except FinalThreeError as exc:
            result.accepted = False
            result.blocked_precall = True
            result.error = str(exc)
            result.mode = "BLOCKED_PRECALL"
            result.phase_result = "BLOCKED_PRECALL"
            return result

    write_dir = artifact_sortie_dir if artifact_sortie_dir is not None else sortie_dir
    consumed = list(preflight.get("lock_consumed") or [])
    if consumed:
        for item in consumed:
            if item not in EXECUTION_ORDER:
                result.accepted = False
                result.blocked_precall = True
                result.error = f"Lock contains unauthorized window {item}."
                result.mode = "BLOCKED_PRECALL"
                result.phase_result = "BLOCKED_PRECALL"
                return result
        if consumed != list(EXECUTION_ORDER[: len(consumed)]):
            result.accepted = False
            result.blocked_precall = True
            result.error = "Lock consumed order is not the authorized prefix. NO RETRY."
            result.mode = "BLOCKED_PRECALL"
            result.phase_result = "BLOCKED_PRECALL"
            return result
        from app.source_analysis_v31_final_three.writer import artifact_path
        from app.source_analysis_v31_final_three.constants import window_artifact
        import json

        for item in consumed:
            path = artifact_path(
                project_name,
                window_artifact(item, "execution"),
                sortie_dir=write_dir,
            )
            if not path.is_file():
                result.accepted = False
                result.blocked_precall = True
                result.error = f"{item} lock consumed but execution artifact missing."
                result.mode = "BLOCKED_PRECALL"
                result.phase_result = "BLOCKED_PRECALL"
                return result
            saved = json.loads(path.read_text(encoding="utf-8"))
            verdict = (saved.get("execution") or {}).get("result")
            if verdict != "PASS":
                result.accepted = False
                result.blocked_precall = True
                result.error = f"{item} already attempted with {verdict} — NO RETRY."
                result.mode = "BLOCKED_PRECALL"
                result.phase_result = "BLOCKED_PRECALL"
                return result
            review_path = artifact_path(
                project_name,
                window_artifact(item, "semantic_review"),
                sortie_dir=write_dir,
            )
            canonical_path = artifact_path(
                project_name,
                window_artifact(item, "canonical"),
                sortie_dir=write_dir,
            )
            review = (
                json.loads(review_path.read_text(encoding="utf-8"))
                if review_path.is_file()
                else {}
            )
            canonical = (
                json.loads(canonical_path.read_text(encoding="utf-8"))
                if canonical_path.is_file()
                else {}
            )
            result.windows[item] = {
                "window_id": item,
                "result": "PASS",
                "execution": saved.get("execution") or {},
                "review": review,
                "canonical": canonical,
                "resumed": True,
            }
        result.ready_after_count = READY_BEFORE_COUNT + len(consumed)
    elif isinstance(engine, SequentialAnthropicEngine):
        _write_lock(project_name, sortie_dir=write_dir, consumed=[])

    phase_guard = PhaseCallGuard(max_calls=MAX_ENGINE_GENERATE)
    for item in consumed:
        phase_guard.attempted.append(item)
        phase_guard.generate_attempts += 1
    ready = READY_BEFORE_COUNT + sum(
        1 for item in result.windows.values() if item.get("result") == "PASS"
    )
    remaining = [item for item in EXECUTION_ORDER if item not in consumed]
    if window_id is not None:
        remaining = [window_id]
    if max_windows is not None:
        remaining = remaining[: max(0, int(max_windows))]
    for current in remaining:
        window_result = execute_one_window(
            window_id=current,
            project_name=project_name,
            preflight=preflight,
            engine=engine,
            phase_guard=phase_guard,
            write_dir=write_dir,
            sortie_dir=sortie_dir,
        )
        result.windows[current] = window_result
        result.engine_generate_attempts += int(
            window_result.get("engine_generate_attempts") or 0
        )
        result.anthropic_post_attempts += int(
            window_result.get("anthropic_post_attempts") or 0
        )
        consumed.append(current)
        if isinstance(engine, SequentialAnthropicEngine):
            _write_lock(project_name, sortie_dir=write_dir, consumed=consumed)
        verdict = window_result["result"]
        quality = (window_result.get("review") or {}).get("semantic_quality")
        if (
            verdict == "PASS"
            and quality == "ACCEPTABLE_FOR_LOCAL_EXTRACTION"
            and window_result["execution"].get("technical_ok")
        ):
            ready += 1
            window_result["execution"]["ready"] = True
            if write_artifacts:
                from app.source_analysis_v31_final_three.writer import (
                    write_window_artifacts,
                )

                write_window_artifacts(
                    project_name,
                    window_result,
                    sortie_dir=write_dir,
                )
            if run_inter_window_tests:
                from app.source_analysis_v31_final_three.post_tests import (
                    run_focused_suite,
                )

                junit = (
                    (write_dir or Path("."))
                    / project_name
                    / "audit"
                    / f"a31_{current}_focused.xml"
                )
                focused = run_focused_suite(junit_path=junit)
                window_result["focused_tests"] = focused
                if int(focused.get("failed") or 0) > 0:
                    window_result["execution"]["ready"] = False
                    result.stopped_at = current
                    result.stop_reason = f"{current} focused tests failed"
                    result.phase_result = "FAIL"
                    result.ready_after_count = ready - 1
                    if write_artifacts:
                        from app.source_analysis_v31_final_three.writer import (
                            write_phase_artifacts,
                        )

                        write_phase_artifacts(
                            project_name, result, sortie_dir=write_dir
                        )
                    return result
        else:
            window_result["execution"]["ready"] = False
            result.stopped_at = current
            if verdict == "FAIL":
                result.stop_reason = f"{current} FAIL"
                result.phase_result = "FAIL"
            elif quality == "REVIEW_REQUIRED" or verdict == "PARTIAL":
                result.stop_reason = f"{current} {quality or verdict}"
                result.phase_result = "PARTIAL"
            else:
                result.stop_reason = f"{current} {verdict}"
                result.phase_result = verdict
            result.ready_after_count = ready
            if write_artifacts:
                from app.source_analysis_v31_final_three.writer import (
                    write_phase_artifacts,
                    write_window_artifacts,
                )

                write_window_artifacts(
                    project_name, window_result, sortie_dir=write_dir
                )
                write_phase_artifacts(project_name, result, sortie_dir=write_dir)
            return result

    result.ready_after_count = ready
    result.stopped_at = None
    result.stop_reason = None
    result.phase_result = "PASS" if ready == TOTAL_WINDOWS else "PARTIAL"
    result.freeze_candidate = "YES" if ready == TOTAL_WINDOWS else "NO"
    if write_artifacts:
        from app.source_analysis_v31_final_three.writer import write_phase_artifacts

        write_phase_artifacts(project_name, result, sortie_dir=write_dir)
    return result


__all__ = [
    "FinalThreeResult",
    "execute_one_window",
    "run_final_three",
]
