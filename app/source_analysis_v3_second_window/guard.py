"""Gardes fail-closed A.22 : scope exact, cible sélectionnée only, un generate."""

from __future__ import annotations

from app.source_analysis.errors import MaxRealCallsExceededError
from app.source_analysis_v3_second_window.constants import (
    AUTHORIZATION_SCOPE,
    FORBIDDEN_ALWAYS,
    MODEL,
    PREFERRED_WINDOW_ID,
    PROVIDER,
)


class SecondWindowError(RuntimeError):
    """Échec local avant réseau, ou arrêt obligatoire après une tentative."""


def validate_authorization_scope(authorization_scope: str | None) -> str:
    scope = str(authorization_scope or "").strip()
    if scope != AUTHORIZATION_SCOPE:
        raise SecondWindowError(
            "Authorization scope must be exactly "
            f"{AUTHORIZATION_SCOPE}, received {scope!r}."
        )
    return scope


def validate_target(window_id: str | None, selected_window_id: str) -> str:
    target = str(window_id or "").strip()
    selected = str(selected_window_id or "").strip()
    if not selected:
        raise SecondWindowError("Selected target is unbound — STOP WITHOUT NETWORK.")
    if selected == "WIN001":
        raise SecondWindowError("WIN001 is forbidden for A.22. Do not retry A.21.")
    if not target:
        return selected
    if target in FORBIDDEN_ALWAYS:
        raise SecondWindowError(
            f"Forbidden real target {target!r} — A.22 is a second-window canary only."
        )
    if target != selected:
        raise SecondWindowError(
            f"Authorization is bound to {selected!r} only, received {target!r}."
        )
    return target


def validate_selected_is_independent(selected_window_id: str) -> str:
    selected = str(selected_window_id or "").strip()
    if selected == "WIN001" or selected in FORBIDDEN_ALWAYS:
        raise SecondWindowError(
            f"Selected target {selected!r} is not an independent second window."
        )
    if not selected.startswith("WIN"):
        raise SecondWindowError(f"Invalid selected window id {selected!r}.")
    return selected


def validate_provider(*, provider: str, model: str) -> None:
    if provider != PROVIDER:
        raise SecondWindowError(
            f"Authorization covers {PROVIDER} only, received {provider!r}."
        )
    if model != MODEL:
        raise SecondWindowError(
            f"Authorization covers {MODEL} only, received {model!r}."
        )


class OneShotCallGuard:
    """Incrémente AVANT generate : un échec consomme l'autorisation."""

    def __init__(self, max_calls: int = 1) -> None:
        self.max_calls = int(max_calls)
        self.generate_attempts = 0

    def guarded_generate(self, engine, request):
        if self.generate_attempts >= self.max_calls:
            raise MaxRealCallsExceededError(
                f"A.22 authorizes at most {self.max_calls} engine.generate "
                f"attempt(s); a {self.generate_attempts + 1}th was refused."
            )
        self.generate_attempts += 1
        return engine.generate(request)


__all__ = [
    "OneShotCallGuard",
    "PREFERRED_WINDOW_ID",
    "SecondWindowError",
    "validate_authorization_scope",
    "validate_provider",
    "validate_selected_is_independent",
    "validate_target",
]
