"""Gardes fail-closed : scope, synthétique-only, budget d'appel."""

from __future__ import annotations

import re
from typing import Any, Iterable

from app.source_analysis.errors import MaxRealCallsExceededError
from app.source_analysis_v3_symbolic_grammar_canary.constants import (
    AUTHORIZATION_SCOPE,
    CANARY_TRANSCRIPT_ID,
    CANARY_WINDOW_ID,
    FORBIDDEN_TRANSCRIPT_IDS,
    FORBIDDEN_WINDOW_IDS,
    PASTORAL_MARKERS,
    PRODUCTION_SRC_PATTERN,
    SYNTHETIC_SRC_IDS,
)


class SymbolicGrammarCanaryError(RuntimeError):
    """Échec local avant réseau, ou arrêt obligatoire après une tentative."""


def validate_authorization_scope(authorization_scope: str | None) -> str:
    scope = str(authorization_scope or "").strip()
    if scope != AUTHORIZATION_SCOPE:
        raise SymbolicGrammarCanaryError(
            "Authorization scope must be exactly "
            f"{AUTHORIZATION_SCOPE}, received {scope!r}."
        )
    return scope


def _blob(parts: Iterable[Any]) -> str:
    return "\n".join(str(part or "") for part in parts).lower()


def assert_synthetic_identity(
    *,
    window_id: str,
    transcript_id: str,
    src_ids: Iterable[str],
) -> None:
    if window_id in FORBIDDEN_WINDOW_IDS:
        raise SymbolicGrammarCanaryError(
            f"Forbidden window identity {window_id!r} — canary cannot become WIN001."
        )
    if window_id != CANARY_WINDOW_ID:
        raise SymbolicGrammarCanaryError(
            f"Canary window_id must be {CANARY_WINDOW_ID}, received {window_id!r}."
        )
    if transcript_id in FORBIDDEN_TRANSCRIPT_IDS or transcript_id == "TR001":
        raise SymbolicGrammarCanaryError(
            f"Forbidden transcript identity {transcript_id!r}."
        )
    if transcript_id != CANARY_TRANSCRIPT_ID:
        raise SymbolicGrammarCanaryError(
            f"Canary transcript_id must be {CANARY_TRANSCRIPT_ID}, "
            f"received {transcript_id!r}."
        )
    refs = tuple(str(item) for item in src_ids)
    if refs != SYNTHETIC_SRC_IDS:
        raise SymbolicGrammarCanaryError(
            f"Canary SRC ids must be {SYNTHETIC_SRC_IDS}, received {refs}."
        )
    production = re.compile(PRODUCTION_SRC_PATTERN)
    for ref in refs:
        if production.fullmatch(ref):
            raise SymbolicGrammarCanaryError(
                f"Production-range SRC id forbidden: {ref}."
            )
        if ref.startswith("SRC000"):
            raise SymbolicGrammarCanaryError(
                f"Real SRC000… identifier forbidden: {ref}."
            )


def assert_no_pastoral_text(*parts: Any) -> None:
    blob = _blob(parts)
    hits = [marker for marker in PASTORAL_MARKERS if marker.lower() in blob]
    if hits:
        raise SymbolicGrammarCanaryError(
            "Pastoral / production markers present in canary payload: "
            + ", ".join(hits)
        )


def assert_synthetic_only_payload(
    payload: dict[str, Any],
    *,
    user_text: str,
    system_text: str,
) -> None:
    messages = payload.get("messages") or []
    message_text = []
    for item in messages:
        if isinstance(item, dict):
            message_text.append(item.get("content") or "")
    assert_no_pastoral_text(system_text, user_text, *message_text)
    assert_synthetic_identity(
        window_id=CANARY_WINDOW_ID,
        transcript_id=CANARY_TRANSCRIPT_ID,
        src_ids=SYNTHETIC_SRC_IDS,
    )
    combined = "\n".join([system_text, user_text, *message_text])
    for match in re.findall(r"\bSRC000\d+\b", combined):
        raise SymbolicGrammarCanaryError(
            f"Real SRC000… identifier present in payload: {match}."
        )
    if re.search(r"\bWIN00[1-7]\b", combined):
        raise SymbolicGrammarCanaryError("Production WIN id present in payload.")
    if re.search(r"\bTR001\b", combined):
        raise SymbolicGrammarCanaryError("Production transcript id present in payload.")


class OneShotCallGuard:
    """Incrémente AVANT generate : un échec consomme l'autorisation."""

    def __init__(self, max_calls: int = 1) -> None:
        self.max_calls = int(max_calls)
        self.generate_attempts = 0

    def guarded_generate(self, engine, request):
        if self.generate_attempts >= self.max_calls:
            raise MaxRealCallsExceededError(
                f"Canary authorize at most {self.max_calls} engine.generate "
                f"attempt(s); a {self.generate_attempts + 1}th was refused."
            )
        self.generate_attempts += 1
        return engine.generate(request)


__all__ = [
    "OneShotCallGuard",
    "SymbolicGrammarCanaryError",
    "assert_no_pastoral_text",
    "assert_synthetic_identity",
    "assert_synthetic_only_payload",
    "validate_authorization_scope",
]
