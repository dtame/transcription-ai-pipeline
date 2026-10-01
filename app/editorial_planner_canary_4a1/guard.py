"""Gardes fail-closed : scope, synthétique only, un seul appel."""

from __future__ import annotations

import re
from typing import Any, Iterable, Mapping

from app.editorial_planner_canary_4a1.constants import (
    AUTHORIZATION_SCOPE,
    FORBIDDEN_TRANSCRIPT_IDS,
    FORBIDDEN_WINDOW_IDS,
    PASTORAL_MARKERS,
    PROJECT_NAME,
    SYNTHETIC_SRC_IDS,
    TRANSCRIPT_ID,
)
from app.source_analysis.errors import MaxRealCallsExceededError
from app.source_analysis.models import SourceMap


class PlannerCanaryError(RuntimeError):
    """Échec local avant réseau, ou arrêt obligatoire après une tentative."""


def validate_authorization_scope(authorization_scope: str | None) -> str:
    scope = str(authorization_scope or "").strip()
    if scope != AUTHORIZATION_SCOPE:
        raise PlannerCanaryError(
            "Authorization scope must be exactly "
            f"{AUTHORIZATION_SCOPE}, received {scope!r}."
        )
    return scope


def _blob(parts: Iterable[Any]) -> str:
    return "\n".join(str(part or "") for part in parts).lower()


def assert_no_pastoral_text(*parts: Any) -> None:
    blob = _blob(parts)
    hits = [marker for marker in PASTORAL_MARKERS if marker.lower() in blob]
    if hits:
        raise PlannerCanaryError(
            "Pastoral / production markers present in canary payload: "
            + ", ".join(hits)
        )


def assert_synthetic_source_map(source_map: SourceMap) -> None:
    if source_map.project_name != PROJECT_NAME:
        raise PlannerCanaryError(
            f"Canary project must be {PROJECT_NAME!r}, "
            f"received {source_map.project_name!r}."
        )
    if source_map.transcript_id in FORBIDDEN_TRANSCRIPT_IDS:
        raise PlannerCanaryError(
            f"Forbidden transcript identity {source_map.transcript_id!r}."
        )
    if source_map.transcript_id != TRANSCRIPT_ID:
        raise PlannerCanaryError(
            f"Canary transcript_id must be {TRANSCRIPT_ID}, "
            f"received {source_map.transcript_id!r}."
        )
    refs = tuple(source_map.all_source_refs())
    unexpected = [ref for ref in refs if ref not in SYNTHETIC_SRC_IDS]
    if unexpected:
        raise PlannerCanaryError(
            f"Non-synthetic SRC ids forbidden: {unexpected}."
        )
    for ref in refs:
        if ref.startswith("SRC0"):
            raise PlannerCanaryError(f"Production-range SRC id forbidden: {ref}.")
    if any(ref.startswith("WIN") for ref in refs):
        raise PlannerCanaryError("Window-like refs forbidden in synthetic SourceMap.")


def assert_no_technical_windows(payload: Mapping[str, Any] | str) -> None:
    if isinstance(payload, str):
        blob = payload
    else:
        blob = str(payload)
    lowered = blob.lower()
    forbidden = (
        "analysis_window",
        "chunk_id",
        "chunk_index",
        "technical_window",
        "window_id",
        "win_id",
        "processed/chunk",
    )
    hits = [token for token in forbidden if token in lowered]
    for window_id in FORBIDDEN_WINDOW_IDS:
        if window_id.lower() in lowered:
            hits.append(window_id)
    if hits:
        raise PlannerCanaryError(
            "Technical window/chunk concept present: " + ", ".join(hits)
        )


def assert_synthetic_only_payload(
    payload: Mapping[str, Any],
    *,
    user_text: str,
    system_text: str,
    digest_text: str = "",
) -> None:
    messages = payload.get("messages") or []
    message_text = []
    for item in messages:
        if isinstance(item, dict):
            message_text.append(item.get("content") or "")
    combined = "\n".join([system_text, user_text, *message_text])
    assert_no_pastoral_text(combined)
    # Frozen planner prompt names technical windows only to forbid them.
    # Scan the digest / fixture, not the prohibition sentence.
    if digest_text:
        assert_no_technical_windows(digest_text)
    for match in re.findall(r"\bSRC\d{6}\b", combined):
        if match not in SYNTHETIC_SRC_IDS:
            raise PlannerCanaryError(
                f"Non-synthetic SRC identifier present in payload: {match}."
            )
    if re.search(r"\bWIN00[1-7]\b", combined):
        raise PlannerCanaryError("Production WIN id present in payload.")
    if "pastoral_retreat_v2_validation" in combined.lower():
        raise PlannerCanaryError("Production project name present in payload.")


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
    "PlannerCanaryError",
    "assert_no_pastoral_text",
    "assert_no_technical_windows",
    "assert_synthetic_only_payload",
    "assert_synthetic_source_map",
    "validate_authorization_scope",
]
