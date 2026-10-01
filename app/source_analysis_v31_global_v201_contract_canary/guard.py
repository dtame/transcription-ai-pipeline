"""Gardes fail-closed A.42 : scope 2.0.1 synthétique, 1 generate, rejet pastoral."""

from __future__ import annotations

import re
from typing import Any, Iterable, Mapping

from app.source_analysis_v31_global_grammar_canary.guard import (
    GlobalGrammarCanaryError,
    OneShotCallGuard,
    assert_no_pastoral_text,
    reject_window_analysis_call,
)
from app.source_analysis_v31_global_v20_grammar_canary.guard import (
    assert_synthetic_identity,
    assert_synthetic_src_ids,
    reject_real_project_input,
)
from app.source_analysis_v31_global_v201_contract_canary.constants import (
    AUTHORIZATION_SCOPE,
    CANARY_TRANSCRIPT_ID,
    CANARY_WINDOW_ID,
    FORBIDDEN_TRANSCRIPT_IDS,
    FORBIDDEN_WINDOW_IDS,
    MODEL,
    PROMPT_VERSION,
    SCHEMA_HASH,
    SYNTHETIC_SRC_IDS,
    THINKING_MODE,
    TRANSPORT_VERSION,
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


def reject_real_consolidation_request(stage: str | None, scope: str | None) -> None:
    text = f"{stage or ''} {scope or ''}"
    if "REAL_GLOBAL_CONSOLIDATION" in text and "2_0_1_SECOND_SYNTHETIC" not in text:
        raise GlobalGrammarCanaryError("Real consolidation request is forbidden.")


def reject_thinking_enabled(thinking_mode: str | None) -> None:
    if str(thinking_mode or "") != THINKING_MODE:
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


def _without_frozen_prompt_v201(text: str) -> str:
    from app.source_analysis_v31_global_drop_domain.prompt_v201 import (
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
    data_blob = _without_frozen_prompt_v201(
        "\n".join([system_text, user_text, *message_text])
    )
    assert_no_pastoral_text(data_blob)
    assert_synthetic_identity(
        window_id="SYN_GLOBAL_V20",
        transcript_id="TR_CANARY_GARDEN_A40",
        src_ids=SYNTHETIC_SRC_IDS,
    )
    reject_real_project_input({"user": data_blob})
    if re.search(r"\bSRC000\d+\b", data_blob):
        raise GlobalGrammarCanaryError("Real SRC000… identifier present in payload.")
    if re.search(r"\bWIN00[1-7]\b", data_blob):
        raise GlobalGrammarCanaryError("Production WIN id present in payload.")
    if CANARY_WINDOW_ID in FORBIDDEN_WINDOW_IDS:
        raise GlobalGrammarCanaryError(f"Forbidden window identity {CANARY_WINDOW_ID!r}.")
    if CANARY_TRANSCRIPT_ID in FORBIDDEN_TRANSCRIPT_IDS:
        raise GlobalGrammarCanaryError(
            f"Forbidden transcript identity {CANARY_TRANSCRIPT_ID!r}."
        )


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
