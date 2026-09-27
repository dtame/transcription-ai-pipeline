"""Gardes fail-closed A.21 : scope exact, WIN001 only, Anthropic only, un generate."""

from __future__ import annotations

from app.source_analysis.errors import MaxRealCallsExceededError
from app.source_analysis_v3_hardened_win001.constants import (
    AUTHORIZATION_SCOPE,
    FORBIDDEN_WINDOW_IDS,
    MODEL,
    PROVIDER,
    WINDOW_ID,
)


class HardenedV3Win001Error(RuntimeError):
    """Échec local avant réseau, ou arrêt obligatoire après une tentative."""


def validate_authorization_scope(authorization_scope: str | None) -> str:
    scope = str(authorization_scope or "").strip()
    if scope != AUTHORIZATION_SCOPE:
        raise HardenedV3Win001Error(
            "Authorization scope must be exactly "
            f"{AUTHORIZATION_SCOPE}, received {scope!r}."
        )
    return scope


def validate_target(window_id: str | None) -> str:
    target = str(window_id or "").strip()
    if not target:
        raise HardenedV3Win001Error("Target window is required and must be WIN001.")
    if target in FORBIDDEN_WINDOW_IDS:
        raise HardenedV3Win001Error(
            f"Forbidden real target {target!r} — only {WINDOW_ID} is authorized."
        )
    if target != WINDOW_ID:
        raise HardenedV3Win001Error(
            f"Scope {AUTHORIZATION_SCOPE} authorizes only {WINDOW_ID}, "
            f"received {target!r}."
        )
    return target


def validate_provider(*, provider: str, model: str) -> None:
    if provider != PROVIDER:
        raise HardenedV3Win001Error(
            f"Authorization covers {PROVIDER} only, received {provider!r}."
        )
    if model != MODEL:
        raise HardenedV3Win001Error(
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
                f"A.21 authorizes at most {self.max_calls} engine.generate "
                f"attempt(s); a {self.generate_attempts + 1}th was refused."
            )
        self.generate_attempts += 1
        return engine.generate(request)


__all__ = [
    "HardenedV3Win001Error",
    "OneShotCallGuard",
    "validate_authorization_scope",
    "validate_provider",
    "validate_target",
]
