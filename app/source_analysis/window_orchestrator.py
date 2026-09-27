"""
WindowAnalysisOrchestrator — multi-fenêtres déterministe, FakeAI only.

    WindowPlan
        → ordre source SEQUENTIAL
        → signature 3B.7.2
        → inspect / revalidate cache
        → HIT | recovery transport | generate (budget)
        → persistance indépendante
        → ALL_WINDOWS_READY | WINDOWS_INCOMPLETE

Aucune consolidation. Aucun SourceMap. Aucun parallélisme.
max_attempts = 1. STOP_ON_FIRST_EXECUTION_FAILURE.
"""

from __future__ import annotations

from pathlib import Path

from app.ai.errors import AIError
from app.ai.settings import StageSettings
from app.source_analysis.errors import (
    SourceMapEditorialLeakError,
    SourceMapValidationError,
    WindowAnalysisError,
    WindowCacheAmbiguityError,
    WindowGranularityLimitExceeded,
    WindowOrchestrationError,
    WindowResultValidationError,
    WindowSemanticCapacityExceeded,
    WindowSourceRefError,
    WindowTransportValidationError,
)
from app.source_analysis.orchestration_models import (
    CACHE_HIT,
    EXECUTION_GENERATED,
    EXECUTION_NONE,
    EXECUTION_ORDER_SEQUENTIAL,
    EXECUTION_TRANSPORT_RECOVERED,
    FAILURE_POLICY_STOP_ON_FIRST,
    MAX_ATTEMPTS_PER_WINDOW,
    READINESS_FAILED,
    READINESS_PENDING,
    READINESS_READY,
    WindowOrchestrationResult,
    WindowOrchestrationStatus,
    reporting_counters,
)
from app.source_analysis.transcript_input import TranscriptInput
from app.source_analysis.window_analyzer import WindowAnalysisHooks, analyze_window
from app.source_analysis.window_cache import (
    expected_window_signature,
    inspect_window_cache,
    recover_cached_window,
)
from app.source_analysis.window_models import WindowSemanticResult
from app.source_analysis.window_writer import (
    leftover_partial,
    metadata_path,
    result_path,
    transport_path,
)
from app.source_analysis_hybrid.contracts import WindowPlan


def orchestrate_windows(
    plan: WindowPlan,
    transcript: TranscriptInput,
    *,
    windows_root: Path,
    engine=None,
    settings: StageSettings | None = None,
    project_name: str = "fixture",
    max_new_calls: int | None = None,
    failure_policy: str = FAILURE_POLICY_STOP_ON_FIRST,
    hooks: WindowAnalysisHooks | None = None,
    prompt_version: str | None = None,
) -> WindowOrchestrationResult:
    """
    Traite les fenêtres dans l'ordre du WindowPlan uniquement.

    L'ordre filesystem / mtime / completion provider n'est jamais lu.
    Un budget est consommé dès qu'engine.generate est tenté, même en échec.
    HIT et recovery transport : 0 appel.
    """
    if failure_policy != FAILURE_POLICY_STOP_ON_FIRST:
        raise WindowOrchestrationError(
            f"politique d'échec inconnue : {failure_policy!r}."
        )
    if max_new_calls is not None and int(max_new_calls) < 0:
        raise WindowOrchestrationError("max_new_calls ne peut pas être négatif.")
    if MAX_ATTEMPTS_PER_WINDOW != 1:
        raise WindowOrchestrationError("max_attempts doit rester 1.")

    statuses: list[WindowOrchestrationStatus] = []
    ready_results: list[WindowSemanticResult] = []
    new_calls = 0
    stop_execution = False
    fake_calls_before = _engine_call_count(engine)

    for window in plan.windows:
        signature = expected_window_signature(
            window,
            transcript,
            settings=settings,
            engine=engine,
            prompt_version=prompt_version,
        )
        paths = _paths(project_name, window.window_id, windows_root)
        try:
            inspection = inspect_window_cache(
                window,
                transcript,
                windows_root=windows_root,
                project_name=project_name,
                expected_signature=signature,
                settings=settings,
                engine=engine,
            )
        except WindowCacheAmbiguityError:
            statuses.append(
                _status(
                    window.window_id,
                    signature,
                    cache_state="INVALID",
                    readiness=READINESS_FAILED,
                    error_classification="CACHE_AMBIGUOUS",
                    **paths,
                )
            )
            stop_execution = True
            continue

        if inspection.cache_state == CACHE_HIT and inspection.result is not None:
            ready_results.append(inspection.result)
            statuses.append(
                _status(
                    window.window_id,
                    signature,
                    cache_state=CACHE_HIT,
                    readiness=READINESS_READY,
                    result_valid=True,
                    transport_present=True,
                    **paths,
                )
            )
            continue

        recovered = None
        recovery_error = None
        if inspection.recoverable:
            try:
                recovered = recover_cached_window(
                    window,
                    transcript,
                    inspection,
                    windows_root=windows_root,
                    project_name=project_name,
                    settings=settings,
                    engine=engine,
                    prompt_version=prompt_version,
                )
            except KeyboardInterrupt:
                raise
            except (
                WindowResultValidationError,
                WindowTransportValidationError,
                WindowSourceRefError,
                SourceMapEditorialLeakError,
                SourceMapValidationError,
                WindowAnalysisError,
            ) as exc:
                recovery_error = exc

        if recovered is not None:
            ready_results.append(recovered)
            statuses.append(
                _status(
                    window.window_id,
                    signature,
                    cache_state=inspection.cache_state,
                    execution_kind=EXECUTION_TRANSPORT_RECOVERED,
                    transport_recovered=True,
                    transport_present=True,
                    result_valid=True,
                    readiness=READINESS_READY,
                    **paths,
                )
            )
            continue

        if stop_execution:
            statuses.append(
                _status(
                    window.window_id,
                    signature,
                    cache_state=inspection.cache_state,
                    readiness=READINESS_PENDING,
                    transport_present=inspection.transport_present,
                    error_classification="STOP_POLICY",
                    **paths,
                )
            )
            continue

        if not _can_generate(engine, new_calls, max_new_calls):
            statuses.append(
                _status(
                    window.window_id,
                    signature,
                    cache_state=inspection.cache_state,
                    readiness=READINESS_PENDING,
                    transport_present=inspection.transport_present,
                    error_classification=_pending_reason(
                        engine, new_calls, max_new_calls, inspection, recovery_error
                    ),
                    **paths,
                )
            )
            continue

        generated, consumed, failed, status = _execute_window(
            window,
            transcript,
            engine=engine,
            settings=settings,
            windows_root=windows_root,
            project_name=project_name,
            signature=signature,
            inspection=inspection,
            hooks=hooks,
            paths=paths,
            prompt_version=prompt_version,
        )
        new_calls += consumed
        statuses.append(status)
        if generated is not None:
            ready_results.append(generated)
        if failed:
            stop_execution = True

    fake_calls = _engine_call_count(engine) - fake_calls_before
    all_ready = (
        len(ready_results) == len(plan.windows)
        and all(status.readiness == READINESS_READY for status in statuses)
        and all(status.result_valid for status in statuses)
    )
    result = WindowOrchestrationResult(
        plan_sha256=plan.plan_sha256(),
        planner_version=plan.planner_version,
        transcript_id=plan.transcript_id,
        total_windows=len(plan.windows),
        ready_windows=sum(1 for status in statuses if status.readiness == READINESS_READY),
        generated_windows=sum(
            1 for status in statuses if status.execution_kind == EXECUTION_GENERATED
        ),
        cache_hit_windows=sum(1 for status in statuses if status.cache_state == CACHE_HIT),
        transport_recovered_windows=sum(
            1
            for status in statuses
            if status.execution_kind == EXECUTION_TRANSPORT_RECOVERED
        ),
        failed_windows=sum(
            1 for status in statuses if status.readiness == READINESS_FAILED
        ),
        pending_windows=sum(
            1 for status in statuses if status.readiness == READINESS_PENDING
        ),
        all_windows_ready=all_ready,
        new_calls_consumed=new_calls,
        max_new_calls=max_new_calls,
        execution_order=EXECUTION_ORDER_SEQUENTIAL,
        failure_policy=failure_policy,
        statuses=tuple(statuses),
        ready_results=tuple(ready_results),
        real_anthropic_cost=0,
        real_provider_calls=0,
        fake_ai_calls=max(fake_calls, new_calls),
        reporting={},
    )
    object.__setattr__(result, "reporting", reporting_counters(result))
    return result


def _paths(project_name: str, window_id: str, windows_root: Path) -> dict[str, str]:
    return {
        "transport_path": str(transport_path(project_name, window_id, root=windows_root)),
        "result_path": str(result_path(project_name, window_id, root=windows_root)),
        "metadata_path": str(metadata_path(project_name, window_id, root=windows_root)),
    }


def _can_generate(engine, new_calls: int, max_new_calls: int | None) -> bool:
    if engine is None:
        return False
    if max_new_calls is not None and new_calls >= int(max_new_calls):
        return False
    return True


def _pending_reason(engine, new_calls, max_new_calls, inspection, recovery_error) -> str:
    if engine is None:
        return "EXECUTION_DISABLED"
    if max_new_calls is not None and new_calls >= int(max_new_calls):
        return "BUDGET_EXHAUSTED"
    if recovery_error is not None:
        return _classify_error(recovery_error)
    return inspection.error_classification or "CACHE_MISS"


def _execute_window(
    window,
    transcript,
    *,
    engine,
    settings,
    windows_root: Path,
    project_name: str,
    signature: str,
    inspection,
    hooks,
    paths: dict[str, str],
    prompt_version: str | None = None,
) -> tuple[WindowSemanticResult | None, int, bool, WindowOrchestrationStatus]:
    """Un seul analyze_window. Budget consommé à la tentative, même si échec."""
    try:
        result = analyze_window(
            window,
            transcript,
            engine,
            settings=settings,
            windows_root=windows_root,
            project_name=project_name,
            hooks=hooks,
            prompt_version=prompt_version,
        )
    except KeyboardInterrupt:
        raise
    except (
        AIError,
        WindowAnalysisError,
        SourceMapEditorialLeakError,
        SourceMapValidationError,
        Exception,
    ) as exc:
        if isinstance(exc, KeyboardInterrupt):
            raise
        t_path = Path(paths["transport_path"])
        t_exists = t_path.is_file() and leftover_partial(t_path) is None
        status = _status(
            window.window_id,
            signature,
            cache_state=inspection.cache_state,
            execution_kind=EXECUTION_GENERATED,
            execution_attempted=True,
            call_consumed=True,
            transport_present=t_exists,
            readiness=READINESS_FAILED,
            error_classification=_classify_error(exc),
            **paths,
        )
        return None, 1, True, status

    status = _status(
        window.window_id,
        signature,
        cache_state=inspection.cache_state,
        execution_kind=EXECUTION_GENERATED,
        execution_attempted=True,
        call_consumed=True,
        transport_present=True,
        result_valid=True,
        readiness=READINESS_READY,
        **paths,
    )
    return result, 1, False, status


def _status(
    window_id: str,
    signature: str,
    *,
    cache_state: str,
    readiness: str,
    execution_kind: str = EXECUTION_NONE,
    execution_attempted: bool = False,
    call_consumed: bool = False,
    transport_present: bool = False,
    transport_recovered: bool = False,
    result_valid: bool = False,
    error_classification: str | None = None,
    transport_path: str = "",
    result_path: str = "",
    metadata_path: str = "",
) -> WindowOrchestrationStatus:
    return WindowOrchestrationStatus(
        window_id=window_id,
        expected_signature=signature,
        cache_state=cache_state,
        execution_kind=execution_kind,
        execution_attempted=execution_attempted,
        call_consumed=call_consumed,
        transport_present=transport_present,
        transport_recovered=transport_recovered,
        result_valid=result_valid,
        readiness=readiness,
        error_classification=error_classification,
        transport_path=transport_path,
        result_path=result_path,
        metadata_path=metadata_path,
    )


def _engine_call_count(engine) -> int:
    if engine is None:
        return 0
    return int(getattr(engine, "call_count", 0) or 0)


def _classify_error(exc: Exception) -> str:
    name = type(exc).__name__
    if name in {"AITimeoutError", "AIError", "AITransientError"}:
        return "PROVIDER_ERROR"
    if name == "WindowTransportValidationError":
        return "LOCAL_DECODE_ERROR"
    if name == "WindowSourceRefError":
        return "INVALID_SRC"
    if name == "SourceMapEditorialLeakError":
        return "EDITORIAL_LEAKAGE"
    if name == "WindowResultValidationError":
        return "VALIDATION_FAILED"
    if name == "WindowCacheAmbiguityError":
        return "CACHE_AMBIGUOUS"
    return name


__all__ = ["orchestrate_windows"]
