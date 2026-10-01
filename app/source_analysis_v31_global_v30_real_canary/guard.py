"""Gardes fail-closed A.46 : scope exact A.45, 1 generate, 0 retry, 0 publication."""

from __future__ import annotations

from typing import Any, Mapping

from app.source_analysis.errors import MaxRealCallsExceededError
from app.source_analysis_v31_global_real_consolidation.guard import (
    reject_publication_path,
    reject_raw_transcript_payload,
    reject_window_analysis_call,
)
from app.source_analysis_v31_global_v30_real_canary.constants import (
    AUTHORIZATION_SCOPE,
    MODEL,
    PRODUCTION_MAX_OUTPUT_TOKENS,
    PROJECT_NAME,
    PROMPT_VERSION,
    READY_WINDOWS,
    SCHEMA_HASH,
    THINKING_MODE,
    TRANSPORT_VERSION,
)


class GlobalRealCanaryError(RuntimeError):
    """Échec local avant réseau, ou arrêt obligatoire après une tentative."""


def validate_authorization_scope(authorization_scope: str | None) -> str:
    scope = str(authorization_scope or "").strip()
    if scope != AUTHORIZATION_SCOPE:
        raise GlobalRealCanaryError(
            "Authorization scope must be exactly "
            f"{AUTHORIZATION_SCOPE}, received {scope!r}."
        )
    return scope


def validate_project_name(project_name: str | None) -> str:
    name = str(project_name or "").strip()
    if name != PROJECT_NAME:
        raise GlobalRealCanaryError(
            f"Project must be exactly {PROJECT_NAME}, received {name!r}."
        )
    return name


def validate_ready_windows(window_ids: list[str] | tuple[str, ...]) -> tuple[str, ...]:
    observed = tuple(str(item) for item in window_ids)
    expected = tuple(READY_WINDOWS)
    if observed != expected:
        missing = [item for item in expected if item not in observed]
        extra = [item for item in observed if item not in expected]
        raise GlobalRealCanaryError(
            "READY window set must be exactly WIN001-WIN007 in order. "
            f"missing={missing} extra={extra} observed={list(observed)}."
        )
    return observed


def reject_contract_drift(
    *,
    prompt_version: str | None,
    transport_version: str | None,
    schema_hash: str | None,
    model: str | None,
    thinking_mode: str | None,
    max_output: int | None,
) -> None:
    failures: list[str] = []
    if prompt_version != PROMPT_VERSION:
        failures.append(f"prompt={prompt_version!r}")
    if transport_version != TRANSPORT_VERSION:
        failures.append(f"transport={transport_version!r}")
    if schema_hash != SCHEMA_HASH:
        failures.append(f"schema_hash={schema_hash!r}")
    if model != MODEL:
        failures.append(f"model={model!r}")
    if thinking_mode != THINKING_MODE:
        failures.append(f"thinking={thinking_mode!r}")
    if int(max_output or 0) != PRODUCTION_MAX_OUTPUT_TOKENS:
        failures.append(f"max_output={max_output!r}")
    if failures:
        raise GlobalRealCanaryError(
            "BLOCKED_PRECALL: contract drift — " + "; ".join(failures)
        )


def reject_second_call(generate_attempts: int, post_attempts: int) -> None:
    if generate_attempts > 1 or post_attempts > 1:
        raise GlobalRealCanaryError("Second global consolidation call is forbidden.")


def reject_fallback_provider(provider: str | None, model: str | None) -> None:
    if str(provider or "") not in {"", "anthropic"}:
        raise GlobalRealCanaryError(f"Fallback provider forbidden: {provider!r}.")
    if model and model != MODEL:
        raise GlobalRealCanaryError(f"Different Anthropic model forbidden: {model!r}.")


def reject_openai(provider: str | None) -> None:
    if str(provider or "").lower() == "openai":
        raise GlobalRealCanaryError("OpenAI call is forbidden in A.46.")


class OneShotCallGuard:
    """Incrémente AVANT generate : un échec consomme l'autorisation."""

    def __init__(self, max_calls: int = 1) -> None:
        self.max_calls = int(max_calls)
        self.generate_attempts = 0

    def guarded_generate(self, engine, request):
        if self.generate_attempts >= self.max_calls:
            raise MaxRealCallsExceededError(
                f"A.46 authorizes at most {self.max_calls} engine.generate "
                f"attempt(s); a {self.generate_attempts + 1}th was refused."
            )
        reject_window_analysis_call(
            getattr(request, "stage", None)
            or (getattr(request, "metadata", None) or {}).get("stage"),
            (getattr(request, "metadata", None) or {}).get("window_id"),
        )
        max_output = getattr(request, "max_output_tokens", None)
        if int(max_output or 0) != PRODUCTION_MAX_OUTPUT_TOKENS:
            raise GlobalRealCanaryError(
                f"max_output must be {PRODUCTION_MAX_OUTPUT_TOKENS}, received {max_output!r}."
            )
        thinking = getattr(request, "thinking_mode", None)
        if thinking != THINKING_MODE:
            raise GlobalRealCanaryError(
                f"thinking must be {THINKING_MODE}, received {thinking!r}."
            )
        self.generate_attempts += 1
        return engine.generate(request)


__all__ = [
    "GlobalRealCanaryError",
    "OneShotCallGuard",
    "reject_contract_drift",
    "reject_fallback_provider",
    "reject_openai",
    "reject_publication_path",
    "reject_raw_transcript_payload",
    "reject_second_call",
    "reject_window_analysis_call",
    "validate_authorization_scope",
    "validate_project_name",
    "validate_ready_windows",
]
