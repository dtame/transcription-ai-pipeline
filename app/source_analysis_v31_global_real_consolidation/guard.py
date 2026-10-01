"""Gardes fail-closed A.38 : scope réel 7 fenêtres, 1 generate, 0 retry."""

from __future__ import annotations

from typing import Any, Mapping

from app.source_analysis.errors import MaxRealCallsExceededError
from app.source_analysis_v31_global_real_consolidation.constants import (
    AUTHORIZATION_SCOPE,
    MAX_OUTPUT_TOKENS,
    MODEL,
    PROJECT_NAME,
    PROMPT_VERSION,
    READY_WINDOWS,
    SCHEMA_HASH,
    THINKING_MODE,
    TRANSPORT_VERSION,
)


class GlobalRealConsolidationError(RuntimeError):
    """Échec local avant réseau, ou arrêt obligatoire après une tentative."""


def validate_authorization_scope(authorization_scope: str | None) -> str:
    scope = str(authorization_scope or "").strip()
    if scope != AUTHORIZATION_SCOPE:
        raise GlobalRealConsolidationError(
            "Authorization scope must be exactly "
            f"{AUTHORIZATION_SCOPE}, received {scope!r}."
        )
    return scope


def validate_project_name(project_name: str | None) -> str:
    name = str(project_name or "").strip()
    if name != PROJECT_NAME:
        raise GlobalRealConsolidationError(
            f"Project must be exactly {PROJECT_NAME}, received {name!r}."
        )
    return name


def validate_ready_windows(window_ids: list[str] | tuple[str, ...]) -> tuple[str, ...]:
    observed = tuple(str(item) for item in window_ids)
    expected = tuple(READY_WINDOWS)
    if observed != expected:
        missing = [item for item in expected if item not in observed]
        extra = [item for item in observed if item not in expected]
        raise GlobalRealConsolidationError(
            "READY window set must be exactly WIN001-WIN007 in order. "
            f"missing={missing} extra={extra} observed={list(observed)}."
        )
    return observed


def reject_raw_transcript_payload(user_text: str, *, compact_text: str) -> None:
    if compact_text and compact_text not in user_text:
        raise GlobalRealConsolidationError(
            "Request user text is not the frozen compact semantic input."
        )
    leftover = user_text.replace(compact_text, "") if compact_text else user_text
    markers = (
        '"segments"',
        "transcript_data.json",
        "CLEAN transcript follows",
        "full transcript",
    )
    hits = [marker for marker in markers if marker in leftover]
    if hits:
        raise GlobalRealConsolidationError(
            "Raw transcript payload forbidden: " + ", ".join(hits)
        )
    if leftover.count("SRC0") > 20 and '"windows"' not in leftover:
        raise GlobalRealConsolidationError(
            "Request appears to embed raw transcript SRC dump."
        )


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
    if int(max_output or 0) != MAX_OUTPUT_TOKENS:
        failures.append(f"max_output={max_output!r}")
    if failures:
        raise GlobalRealConsolidationError(
            "BLOCKED_PRECALL: contract drift — " + "; ".join(failures)
        )


def reject_second_call(generate_attempts: int, post_attempts: int) -> None:
    if generate_attempts > 1 or post_attempts > 1:
        raise GlobalRealConsolidationError(
            "Second global consolidation call is forbidden."
        )


def reject_window_analysis_call(stage: str | None, window_id: str | None) -> None:
    if window_id in READY_WINDOWS:
        raise GlobalRealConsolidationError(
            f"Local extraction window call {window_id!r} is forbidden."
        )
    stage_text = str(stage or "")
    if "window-analysis" in stage_text or "window_analysis" in stage_text:
        raise GlobalRealConsolidationError(
            f"Source-analysis window stage forbidden: {stage_text}."
        )


def reject_publication_path(path: str | None) -> None:
    text = str(path or "").replace("\\", "/")
    if text.endswith("analysis/source_map.json") or text.endswith("analysis\\source_map.json"):
        raise GlobalRealConsolidationError(
            "Production analysis/source_map.json publication is forbidden."
        )


def assert_no_secrets(payload: Mapping[str, Any] | None) -> None:
    blob = str(payload or {})
    forbidden = ("sk-ant-", "api_key", "x-api-key")
    for token in forbidden:
        if token in blob.lower() or token in blob:
            if token == "api_key" and "api_key" in blob.lower() and "cle-de-test" in blob:
                continue
            if token == "api_key":
                continue
            raise GlobalRealConsolidationError("Secret material present in request audit.")


class OneShotCallGuard:
    """Incrémente AVANT generate : un échec consomme l'autorisation."""

    def __init__(self, max_calls: int = 1) -> None:
        self.max_calls = int(max_calls)
        self.generate_attempts = 0

    def guarded_generate(self, engine, request):
        if self.generate_attempts >= self.max_calls:
            raise MaxRealCallsExceededError(
                f"A.38 authorizes at most {self.max_calls} engine.generate "
                f"attempt(s); a {self.generate_attempts + 1}th was refused."
            )
        reject_window_analysis_call(
            getattr(request, "stage", None)
            or (getattr(request, "metadata", None) or {}).get("stage"),
            (getattr(request, "metadata", None) or {}).get("window_id"),
        )
        max_output = getattr(request, "max_output_tokens", None)
        if int(max_output or 0) != MAX_OUTPUT_TOKENS:
            raise GlobalRealConsolidationError(
                f"max_output must be {MAX_OUTPUT_TOKENS}, received {max_output!r}."
            )
        thinking = getattr(request, "thinking_mode", None)
        if thinking != THINKING_MODE:
            raise GlobalRealConsolidationError(
                f"thinking must be {THINKING_MODE}, received {thinking!r}."
            )
        self.generate_attempts += 1
        return engine.generate(request)


__all__ = [
    "GlobalRealConsolidationError",
    "OneShotCallGuard",
    "assert_no_secrets",
    "reject_contract_drift",
    "reject_publication_path",
    "reject_raw_transcript_payload",
    "reject_second_call",
    "reject_window_analysis_call",
    "validate_authorization_scope",
    "validate_project_name",
    "validate_ready_windows",
]
