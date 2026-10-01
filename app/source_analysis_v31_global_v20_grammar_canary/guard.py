"""Gardes fail-closed A.40 : scope 2.0 synthétique, 1 generate, rejet pastoral."""

from __future__ import annotations

import re
from typing import Any, Iterable, Mapping

from app.source_analysis_v31_global_grammar_canary.guard import (
    GlobalGrammarCanaryError,
    OneShotCallGuard,
    assert_no_pastoral_text,
    reject_window_analysis_call,
)
from app.source_analysis_v31_global_v20_grammar_canary.constants import (
    AUTHORIZATION_SCOPE,
    CANARY_TRANSCRIPT_ID,
    CANARY_WINDOW_ID,
    FORBIDDEN_TRANSCRIPT_IDS,
    FORBIDDEN_WINDOW_IDS,
    PRODUCTION_SRC_PATTERN,
    SYNTHETIC_NAMESPACE,
    SYNTHETIC_SRC_IDS,
    SYNTHETIC_WINDOW_IDS,
)


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
        if not ref.startswith("SRC9981"):
            raise GlobalGrammarCanaryError(
                f"A.40 SRC must use synthetic SRC9981… namespace, received {ref}."
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
        if not str(item).startswith(f"{SYNTHETIC_NAMESPACE}:"):
            raise GlobalGrammarCanaryError(
                f"Local window id must use {SYNTHETIC_NAMESPACE}: namespace, "
                f"received {item!r}."
            )


def reject_real_project_input(payload: Mapping[str, Any] | None) -> None:
    blob = _blob(_walk_strings(payload or {}))
    if re.search(r"\bWIN00[1-7]\b", blob):
        raise GlobalGrammarCanaryError(
            "Real project WIN001-WIN007 data is forbidden in the canary."
        )
    if re.search(r"\bSRC0\d{5}\b", blob):
        raise GlobalGrammarCanaryError(
            "Real SRC0xxxxx namespace is forbidden in the canary."
        )
    if "normalized-consolidation-input-1.0" in blob and "SYN:" not in blob:
        raise GlobalGrammarCanaryError(
            "Real project normalized consolidation input is forbidden."
        )
    assert_no_pastoral_text(blob)


def reject_real_consolidation_request(stage: str | None, scope: str | None) -> None:
    text = f"{stage or ''} {scope or ''}"
    if "REAL_GLOBAL_CONSOLIDATION" in text and "2_0_TINY_SYNTHETIC" not in text:
        raise GlobalGrammarCanaryError("Real consolidation request is forbidden.")


def reject_thinking_enabled(thinking_mode: str | None) -> None:
    if str(thinking_mode or "") != "disabled":
        raise GlobalGrammarCanaryError(
            f"thinking must be disabled, received {thinking_mode!r}."
        )


def reject_wrong_architecture(
    *,
    model: str | None,
    prompt_version: str | None,
    transport_version: str | None,
    schema_hash: str | None,
) -> None:
    from app.source_analysis_v31_global_v20_grammar_canary.constants import (
        MODEL,
        PROMPT_VERSION,
        SCHEMA_HASH,
        TRANSPORT_VERSION,
    )

    if model and model != MODEL:
        raise GlobalGrammarCanaryError(f"Different model forbidden: {model!r}.")
    if prompt_version and prompt_version != PROMPT_VERSION:
        raise GlobalGrammarCanaryError(
            f"Different prompt forbidden: {prompt_version!r}."
        )
    if transport_version and transport_version != TRANSPORT_VERSION:
        raise GlobalGrammarCanaryError(
            f"Different transport forbidden: {transport_version!r}."
        )
    if schema_hash and schema_hash != SCHEMA_HASH:
        raise GlobalGrammarCanaryError(
            f"Different schema forbidden: {schema_hash!r}."
        )


def _without_frozen_prompt_v20(text: str) -> str:
    from app.source_analysis_v31_global_output_architecture.prompt_v20 import (
        INSTRUCTIONS,
        SYSTEM_PROMPT,
    )

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
    data_blob = _without_frozen_prompt_v20(
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
    if re.search(r"\bWIN00[1-7]\b", data_blob):
        raise GlobalGrammarCanaryError("Production WIN id present in payload.")


__all__ = [
    "GlobalGrammarCanaryError",
    "OneShotCallGuard",
    "assert_no_pastoral_text",
    "assert_synthetic_identity",
    "assert_synthetic_only_payload",
    "assert_synthetic_src_ids",
    "reject_real_consolidation_request",
    "reject_real_project_input",
    "reject_thinking_enabled",
    "reject_window_analysis_call",
    "reject_wrong_architecture",
    "validate_authorization_scope",
]
