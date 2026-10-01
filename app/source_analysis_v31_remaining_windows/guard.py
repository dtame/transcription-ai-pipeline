"""Gardes fail-closed A.28 : scope exact, cinq fenêtres autorisées, séquentiel."""

from __future__ import annotations

from app.source_analysis.errors import MaxRealCallsExceededError
from app.source_analysis_v31_remaining_windows.constants import (
    AUTHORIZATION_SCOPE,
    AUTHORIZED_WINDOW_IDS,
    FORBIDDEN_WINDOW_IDS,
    MAX_ENGINE_GENERATE,
    MODEL,
    PROVIDER,
)


class RemainingWindowsError(RuntimeError):
    """Échec local avant réseau, ou arrêt obligatoire après une tentative."""


def validate_authorization_scope(authorization_scope: str | None) -> str:
    scope = str(authorization_scope or "").strip()
    if scope != AUTHORIZATION_SCOPE:
        raise RemainingWindowsError(
            "Authorization scope must be exactly "
            f"{AUTHORIZATION_SCOPE}, received {scope!r}."
        )
    return scope


def validate_target(window_id: str | None) -> str:
    target = str(window_id or "").strip()
    if not target:
        raise RemainingWindowsError(
            "Target window is required and must be one of "
            + ", ".join(AUTHORIZED_WINDOW_IDS)
        )
    if target in FORBIDDEN_WINDOW_IDS:
        raise RemainingWindowsError(
            f"Forbidden real target {target!r} — WIN001/WIN004 and extras "
            "are not authorized in A.28."
        )
    if target not in AUTHORIZED_WINDOW_IDS:
        raise RemainingWindowsError(
            f"Scope {AUTHORIZATION_SCOPE} authorizes only "
            f"{AUTHORIZED_WINDOW_IDS}, received {target!r}."
        )
    return target


def validate_provider(*, provider: str, model: str) -> None:
    if provider != PROVIDER:
        raise RemainingWindowsError(
            f"Authorization covers {PROVIDER} only, received {provider!r}."
        )
    if model != MODEL:
        raise RemainingWindowsError(
            f"Authorization covers {MODEL} only, received {model!r}."
        )


class OneShotCallGuard:
    """Incrémente AVANT generate : un échec consomme l'autorisation fenêtre."""

    def __init__(self, max_calls: int = 1) -> None:
        self.max_calls = int(max_calls)
        self.generate_attempts = 0

    def guarded_generate(self, engine, request):
        if self.generate_attempts >= self.max_calls:
            raise MaxRealCallsExceededError(
                f"A.28 window authorizes at most {self.max_calls} "
                f"engine.generate attempt(s); a {self.generate_attempts + 1}th "
                "was refused."
            )
        self.generate_attempts += 1
        return engine.generate(request)


class PhaseCallGuard:
    """Budget de phase : 5 generate maximum, jamais en parallèle."""

    def __init__(self, max_calls: int = MAX_ENGINE_GENERATE) -> None:
        self.max_calls = int(max_calls)
        self.generate_attempts = 0
        self.in_flight = 0
        self.attempted: list[str] = []

    def begin(self, window_id: str) -> None:
        if self.generate_attempts >= self.max_calls:
            raise MaxRealCallsExceededError(
                f"A.28 authorizes at most {self.max_calls} engine.generate "
                f"attempt(s); a {self.generate_attempts + 1}th was refused."
            )
        if self.in_flight:
            raise RemainingWindowsError(
                "A.28 forbids queuing or overlapping provider calls. "
                "At most one real request may be in flight."
            )
        if window_id in self.attempted:
            raise RemainingWindowsError(
                f"{window_id} already attempted this phase — NO RETRY."
            )
        self.in_flight = 1
        self.generate_attempts += 1
        self.attempted.append(window_id)

    def end(self) -> None:
        self.in_flight = 0


__all__ = [
    "OneShotCallGuard",
    "PhaseCallGuard",
    "RemainingWindowsError",
    "validate_authorization_scope",
    "validate_provider",
    "validate_target",
]
