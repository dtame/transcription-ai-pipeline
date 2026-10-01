"""Gardes fail-closed A.35 : scope synthétique, 1 generate, rejet pastoral."""

from __future__ import annotations

import re
from typing import Any, Iterable, Mapping

from app.source_analysis.errors import MaxRealCallsExceededError
from app.source_analysis_v31_global_grammar_canary.constants import (
    AUTHORIZATION_SCOPE,
    CANARY_TRANSCRIPT_ID,
    CANARY_WINDOW_ID,
    FORBIDDEN_TRANSCRIPT_IDS,
    FORBIDDEN_WINDOW_IDS,
    PASTORAL_MARKERS,
    PRODUCTION_SRC_PATTERN,
    SYNTHETIC_NAMESPACE,
    SYNTHETIC_SRC_IDS,
    SYNTHETIC_WINDOW_IDS,
)


class GlobalGrammarCanaryError(RuntimeError):
    """Échec local avant réseau, ou arrêt obligatoire après une tentative."""


def validate_authorization_scope(authorization_scope: str | None) -> str:
    scope = str(authorization_scope or "").strip()
    if scope != AUTHORIZATION_SCOPE:
        raise GlobalGrammarCanaryError(
            "Authorization scope must be exactly "
            f"{AUTHORIZATION_SCOPE}, received {scope!r}."
        )
    return scope


def _blob(parts: Iterable[Any]) -> str:
    return "\n".join(str(part or "") for part in parts)


def assert_no_pastoral_text(*parts: Any) -> None:
    blob = _blob(parts)
    lower = blob.lower()
    hits = [marker for marker in PASTORAL_MARKERS if marker.lower() in lower]
    if hits:
        raise GlobalGrammarCanaryError(
            "Pastoral / production markers present in canary payload: "
            + ", ".join(hits)
        )
    if re.search(r"\bWIN00[1-7]\b", blob):
        raise GlobalGrammarCanaryError("Production WIN id present in payload.")
    if re.search(r"\bTR001\b", blob):
        raise GlobalGrammarCanaryError("Production transcript id present in payload.")


def assert_synthetic_src_ids(src_ids: Iterable[str]) -> None:
    refs = tuple(str(item) for item in src_ids)
    production = re.compile(PRODUCTION_SRC_PATTERN)
    for ref in refs:
        if production.fullmatch(ref):
            raise GlobalGrammarCanaryError(
                f"Production-range SRC id forbidden: {ref}."
            )
        if ref.startswith("SRC000"):
            raise GlobalGrammarCanaryError(
                f"Real SRC000… identifier forbidden: {ref}."
            )
        if not ref.startswith("SRC998"):
            raise GlobalGrammarCanaryError(
                f"Canary SRC must use synthetic SRC998… namespace, received {ref}."
            )
    missing = [item for item in SYNTHETIC_SRC_IDS if item not in refs]
    extra = [item for item in refs if item not in SYNTHETIC_SRC_IDS]
    if missing or extra:
        raise GlobalGrammarCanaryError(
            f"Canary SRC set mismatch missing={missing} extra={extra}."
        )


def assert_synthetic_identity(
    *,
    window_id: str,
    transcript_id: str,
    src_ids: Iterable[str],
    local_window_ids: Iterable[str] | None = None,
) -> None:
    if window_id in FORBIDDEN_WINDOW_IDS:
        raise GlobalGrammarCanaryError(
            f"Forbidden window identity {window_id!r}."
        )
    if window_id != CANARY_WINDOW_ID:
        raise GlobalGrammarCanaryError(
            f"Canary window_id must be {CANARY_WINDOW_ID}, received {window_id!r}."
        )
    if transcript_id in FORBIDDEN_TRANSCRIPT_IDS:
        raise GlobalGrammarCanaryError(
            f"Forbidden transcript identity {transcript_id!r}."
        )
    if transcript_id != CANARY_TRANSCRIPT_ID:
        raise GlobalGrammarCanaryError(
            f"Canary transcript_id must be {CANARY_TRANSCRIPT_ID}, "
            f"received {transcript_id!r}."
        )
    assert_synthetic_src_ids(src_ids)
    for item in local_window_ids or SYNTHETIC_WINDOW_IDS:
        if item in FORBIDDEN_WINDOW_IDS or str(item).startswith("WIN"):
            raise GlobalGrammarCanaryError(
                f"Production window identity in synthetic fixture: {item}."
            )
        if not str(item).startswith(SYNTHETIC_NAMESPACE):
            raise GlobalGrammarCanaryError(
                f"Local window id must use {SYNTHETIC_NAMESPACE} namespace, "
                f"received {item!r}."
            )


def reject_real_project_input(payload: Mapping[str, Any] | None) -> None:
    """Refuse normalized pastoral input / WIN001-WIN007 / real SRC namespace."""
    blob = _blob(_walk_strings(payload or {}))
    if re.search(r"\bWIN00[1-7]\b", blob):
        raise GlobalGrammarCanaryError(
            "Real project WIN001-WIN007 data is forbidden in the canary."
        )
    if re.search(r"\bSRC0\d{5}\b", blob):
        raise GlobalGrammarCanaryError(
            "Real SRC0xxxxx namespace is forbidden in the canary."
        )
    if "normalized-consolidation-input-1.0" in blob and "SYN001" not in blob:
        raise GlobalGrammarCanaryError(
            "Real project normalized consolidation input is forbidden."
        )
    assert_no_pastoral_text(blob)


def reject_window_analysis_call(stage: str | None, window_id: str | None) -> None:
    if window_id in FORBIDDEN_WINDOW_IDS:
        raise GlobalGrammarCanaryError(
            f"Source-analysis window call {window_id!r} is forbidden."
        )
    stage_text = str(stage or "")
    if "window" in stage_text and "global" not in stage_text:
        raise GlobalGrammarCanaryError(
            f"Source-analysis window stage forbidden: {stage_text}."
        )


def _without_frozen_prompt(text: str) -> str:
    from app.source_analysis_v31_global_preflight.prompt import INSTRUCTIONS, SYSTEM_PROMPT

    stripped = text
    for block in (SYSTEM_PROMPT, INSTRUCTIONS, SYSTEM_PROMPT.strip(), INSTRUCTIONS.strip()):
        stripped = stripped.replace(block, "")
    return stripped


def assert_synthetic_only_payload(
    payload: Mapping[str, Any],
    *,
    user_text: str,
    system_text: str,
) -> None:
    messages = payload.get("messages") or []
    message_text = []
    for item in messages:
        if isinstance(item, dict):
            message_text.append(item.get("content") or "")
    data_blob = _without_frozen_prompt(
        "\n".join([system_text, user_text, *message_text])
    )
    assert_no_pastoral_text(data_blob)
    assert_synthetic_identity(
        window_id=CANARY_WINDOW_ID,
        transcript_id=CANARY_TRANSCRIPT_ID,
        src_ids=SYNTHETIC_SRC_IDS,
    )
    reject_real_project_input({"user": data_blob})
    if re.search(r"\bSRC000\d+\b", data_blob):
        raise GlobalGrammarCanaryError("Real SRC000… identifier present in payload.")


def _walk_strings(value: Any) -> list[str]:
    found: list[str] = []
    if isinstance(value, str):
        found.append(value)
    elif isinstance(value, Mapping):
        for item in value.values():
            found.extend(_walk_strings(item))
    elif isinstance(value, (list, tuple, set)):
        for item in value:
            found.extend(_walk_strings(item))
    return found


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
        reject_window_analysis_call(
            getattr(request, "stage", None),
            (getattr(request, "metadata", None) or {}).get("window_id"),
        )
        self.generate_attempts += 1
        return engine.generate(request)


__all__ = [
    "GlobalGrammarCanaryError",
    "OneShotCallGuard",
    "assert_no_pastoral_text",
    "assert_synthetic_identity",
    "assert_synthetic_only_payload",
    "assert_synthetic_src_ids",
    "reject_real_project_input",
    "reject_window_analysis_call",
    "validate_authorization_scope",
]
