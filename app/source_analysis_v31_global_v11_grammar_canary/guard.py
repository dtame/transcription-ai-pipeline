"""Gardes fail-closed A.37 : scope V11 synthétique, 1 generate, rejet pastoral."""

from __future__ import annotations

from typing import Any, Mapping

from app.source_analysis_v31_global_grammar_canary.guard import (
    GlobalGrammarCanaryError,
    OneShotCallGuard,
    assert_no_pastoral_text,
    assert_synthetic_identity,
    assert_synthetic_src_ids,
    reject_real_project_input,
    reject_window_analysis_call,
)
from app.source_analysis_v31_global_v11_grammar_canary.constants import (
    AUTHORIZATION_SCOPE,
    CANARY_TRANSCRIPT_ID,
    CANARY_WINDOW_ID,
    SYNTHETIC_SRC_IDS,
)


def validate_authorization_scope(authorization_scope: str | None) -> str:
    scope = str(authorization_scope or "").strip()
    if scope != AUTHORIZATION_SCOPE:
        raise GlobalGrammarCanaryError(
            "Authorization scope must be exactly "
            f"{AUTHORIZATION_SCOPE}, received {scope!r}."
        )
    return scope


def _without_frozen_prompt_v101(text: str) -> str:
    from app.source_analysis_v31_global_canary_forensics.prompt_v101 import (
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
    data_blob = _without_frozen_prompt_v101(
        "\n".join([system_text, user_text, *message_text])
    )
    assert_no_pastoral_text(data_blob)
    assert_synthetic_identity(
        window_id=CANARY_WINDOW_ID,
        transcript_id=CANARY_TRANSCRIPT_ID,
        src_ids=SYNTHETIC_SRC_IDS,
    )
    reject_real_project_input({"user": data_blob})


def reject_real_consolidation_request(stage: str | None, scope: str | None) -> None:
    text = f"{stage or ''} {scope or ''}"
    if "REAL_GLOBAL_CONSOLIDATION" in text and "V11_TINY_SYNTHETIC" not in text:
        raise GlobalGrammarCanaryError("Real consolidation request is forbidden.")


__all__ = [
    "GlobalGrammarCanaryError",
    "OneShotCallGuard",
    "assert_no_pastoral_text",
    "assert_synthetic_identity",
    "assert_synthetic_only_payload",
    "assert_synthetic_src_ids",
    "reject_real_consolidation_request",
    "reject_real_project_input",
    "reject_window_analysis_call",
    "validate_authorization_scope",
]
